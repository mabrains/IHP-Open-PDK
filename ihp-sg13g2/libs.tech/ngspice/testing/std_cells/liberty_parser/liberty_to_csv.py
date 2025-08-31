import json
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from liberty.parser import parse_liberty
from liberty_parser.helpers import (
    cell_has_output_timing,
    getf,
    getlistf,
    getstr,
    gname,
    norm,
    parse_values_matrix,
    preprocess_liberty_text,
)
from liberty_parser.types import (
    CellSummary,
    LeakagePower,
    PinCapacitance,
    PowerArc,
    TimingArc,
)


class LibertyDataExtractor:
    """Extracts structured data from parsed Liberty objects"""

    def extract_cell_summary(self, cell) -> CellSummary:
        """Extract cell-level summary information"""
        leakage_modes: List[LeakagePower] = []
        for leak_group in cell.get_groups("leakage_power"):
            value = getf(leak_group, "value")
            when = getstr(leak_group, "when")
            leakage_modes.append(LeakagePower(value=value, when=when))

        return CellSummary(
            cell=gname(cell),
            area=getf(cell, "area"),
            footprint=getstr(cell, "cell_footprint"),
            cell_leakage_power=getf(cell, "cell_leakage_power"),
            leakage_modes=leakage_modes,
        )

    def extract_pin_capacitances(self, cell) -> List[PinCapacitance]:
        """Extract pin capacitance information"""
        pin_caps: List[PinCapacitance] = []
        for pin in cell.get_groups("pin"):
            pin_caps.append(
                PinCapacitance(
                    pin=gname(pin),
                    direction=getstr(pin, "direction"),
                    capacitance=getf(pin, "capacitance"),
                    rise_capacitance=getf(pin, "rise_capacitance"),
                    fall_capacitance=getf(pin, "fall_capacitance"),
                    min_capacitance=getf(pin, "min_capacitance"),
                    max_capacitance=getf(pin, "max_capacitance"),
                )
            )
        return pin_caps

    def extract_timing_arcs(self, cell) -> List[TimingArc]:
        """Extract timing arcs from all output pins"""
        timing_arcs: List[TimingArc] = []
        for pin in cell.get_groups("pin"):
            if (getstr(pin, "direction") or "").lower() != "output":
                continue
            out_pin = gname(pin)
            for timing in pin.get_groups("timing"):
                related_pin = getstr(timing, "related_pin")
                timing_sense = getstr(timing, "timing_sense")
                timing_type = getstr(timing, "timing_type")

                for table_type in [
                    "cell_rise",
                    "cell_fall",
                    "rise_transition",
                    "fall_transition",
                ]:
                    for table in timing.get_groups(table_type):
                        idx1 = getlistf(table, "index_1")
                        idx2 = getlistf(table, "index_2")
                        matrix = parse_values_matrix(table.get("values"), len(idx2))

                        for i, row in enumerate(matrix):
                            for j, val in enumerate(row):
                                timing_arcs.append(
                                    TimingArc(
                                        out_pin=out_pin,
                                        related_pin=related_pin,
                                        timing_sense=timing_sense,
                                        timing_type=timing_type,
                                        kind=table_type,
                                        i=i,
                                        j=j,
                                        slew_ns=idx1[i] if i < len(idx1) else None,
                                        load_pf=idx2[j] if j < len(idx2) else None,
                                        value_ns=float(val),
                                    )
                                )
        return timing_arcs

    def extract_power_arcs(self, cell) -> List[PowerArc]:
        """Extract internal power arcs from all output pins"""
        power_arcs: List[PowerArc] = []
        for pin in cell.get_groups("pin"):
            if (getstr(pin, "direction") or "").lower() != "output":
                continue
            p_name = gname(pin)
            for power in pin.get_groups("internal_power"):
                related_pin = getstr(power, "related_pin")

                for table_type in ["rise_power", "fall_power"]:
                    for table in power.get_groups(table_type):
                        idx1 = getlistf(table, "index_1")
                        idx2 = getlistf(table, "index_2")
                        matrix = parse_values_matrix(table.get("values"), len(idx2))

                        for i, row in enumerate(matrix):
                            for j, val in enumerate(row):
                                power_arcs.append(
                                    PowerArc(
                                        pin=p_name,
                                        related_pin=related_pin,
                                        kind=table_type,
                                        i=i,
                                        j=j,
                                        slew_ns=idx1[i] if i < len(idx1) else None,
                                        load_pf=idx2[j] if j < len(idx2) else None,
                                        value_mw=float(val),
                                    )
                                )
        return power_arcs

    def convert(self, lib_path: Path, out_dir: Path) -> Path:
        """Convert Liberty file to per-cell CSV structure"""
        print(f"Parsing Liberty file: {lib_path}")

        text = lib_path.read_text(encoding="utf-8", errors="ignore")
        text = preprocess_liberty_text(text)
        root = parse_liberty(text)

        library = (
            root if root.group_name == "library" else root.get_groups("library")[0]
        )

        exporter = CSVExporter(out_dir)

        exporter.export_library_meta(library)

        index_rows: List[Dict[str, str]] = []
        cells = library.get_groups("cell")
        cells = [c for c in cells if cell_has_output_timing(c)]
        print(f"Found {len(cells)} cells to process")

        for cell in cells:
            cname = gname(cell)
            print(f"Processing cell: {cname}")

            summary = self.extract_cell_summary(cell)
            pin_caps = self.extract_pin_capacitances(cell)
            timing_arcs = self.extract_timing_arcs(cell)
            power_arcs = self.extract_power_arcs(cell)

            file_paths = exporter.export_cell_data(
                cname, summary, pin_caps, timing_arcs, power_arcs
            )

            index_rows.append({"cell": cname, **file_paths})

            print(
                f"  - {len(timing_arcs)} timing arcs, {len(power_arcs)} power arcs, {len(pin_caps)} pins"
            )

        exporter.export_cells_index(index_rows)

        print(f"Successfully converted {len(cells)} cells")
        return out_dir


class CSVExporter:
    """Handles exporting parsed data to CSV files"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_cell_data(
        self,
        cell_name: str,
        summary: CellSummary,
        pin_caps: List[PinCapacitance],
        timing_arcs: List[TimingArc],
        power_arcs: List[PowerArc],
    ) -> Dict[str, str]:
        """Export all cell data to CSV files and return file paths"""
        cell_dir = self.output_dir / cell_name
        cell_dir.mkdir(parents=True, exist_ok=True)

        summary_data = {
            "cell": summary.cell,
            "area": summary.area,
            "footprint": summary.footprint,
            "cell_leakage_power": summary.cell_leakage_power,
            "leakage_modes": json.dumps(
                [{"value": lm.value, "when": lm.when} for lm in summary.leakage_modes],
                ensure_ascii=False,
            ),
        }
        pd.DataFrame([summary_data]).to_csv(cell_dir / "cell_summary.csv", index=False)

        if pin_caps:
            pin_caps_data = [
                {
                    "pin": pc.pin,
                    "direction": pc.direction,
                    "capacitance": pc.capacitance,
                    "rise_capacitance": pc.rise_capacitance,
                    "fall_capacitance": pc.fall_capacitance,
                    "min_capacitance": pc.min_capacitance,
                    "max_capacitance": pc.max_capacitance,
                }
                for pc in pin_caps
            ]
            df_pc = pd.DataFrame(pin_caps_data).sort_values("pin")
        else:
            df_pc = pd.DataFrame(
                columns=[
                    "pin",
                    "direction",
                    "capacitance",
                    "rise_capacitance",
                    "fall_capacitance",
                    "min_capacitance",
                    "max_capacitance",
                ]
            )
        df_pc.to_csv(cell_dir / "pin_caps.csv", index=False)

        if timing_arcs:
            timing_data = [
                {
                    "out_pin": ta.out_pin,
                    "related_pin": ta.related_pin,
                    "timing_sense": ta.timing_sense,
                    "timing_type": ta.timing_type,
                    "kind": ta.kind,
                    "i": ta.i,
                    "j": ta.j,
                    "slew_ns": ta.slew_ns,
                    "load_pf": ta.load_pf,
                    "value_ns": ta.value_ns,
                }
                for ta in timing_arcs
            ]
            df_timing = pd.DataFrame(timing_data).sort_values(
                ["out_pin", "related_pin", "kind", "i", "j"], na_position="last"
            )
        else:
            df_timing = pd.DataFrame(
                columns=[
                    "out_pin",
                    "related_pin",
                    "timing_sense",
                    "timing_type",
                    "kind",
                    "i",
                    "j",
                    "slew_ns",
                    "load_pf",
                    "value_ns",
                ]
            )
        df_timing.to_csv(cell_dir / "timing.csv", index=False)

        if power_arcs:
            power_data = [
                {
                    "pin": pa.pin,
                    "related_pin": pa.related_pin,
                    "kind": pa.kind,
                    "i": pa.i,
                    "j": pa.j,
                    "slew_ns": pa.slew_ns,
                    "load_pf": pa.load_pf,
                    "value_mw": pa.value_mw,
                }
                for pa in power_arcs
            ]
            df_power = pd.DataFrame(power_data).sort_values(
                ["pin", "related_pin", "kind", "i", "j"], na_position="last"
            )
        else:
            df_power = pd.DataFrame(
                columns=[
                    "pin",
                    "related_pin",
                    "kind",
                    "i",
                    "j",
                    "slew_ns",
                    "load_pf",
                    "value_mw",
                ]
            )
        df_power.to_csv(cell_dir / "power.csv", index=False)

        return {
            "cell_summary": str(
                (cell_dir / "cell_summary.csv").relative_to(self.output_dir)
            ),
            "pin_caps": str((cell_dir / "pin_caps.csv").relative_to(self.output_dir)),
            "timing": str((cell_dir / "timing.csv").relative_to(self.output_dir)),
            "power": str((cell_dir / "power.csv").relative_to(self.output_dir)),
        }

    def export_library_meta(self, library_group) -> None:
        """Export library metadata to JSON"""
        meta_attrs = [
            "time_unit",
            "voltage_unit",
            "current_unit",
            "leakage_power_unit",
            "capacitive_load_unit",
            "input_threshold_pct_rise",
            "input_threshold_pct_fall",
            "output_threshold_pct_rise",
            "output_threshold_pct_fall",
            "slew_lower_threshold_pct_rise",
            "slew_lower_threshold_pct_fall",
            "slew_upper_threshold_pct_rise",
            "slew_upper_threshold_pct_fall",
            "nom_voltage",
            "nom_temperature",
            "nom_process",
        ]

        lib_meta: Dict[str, Any] = {}
        for attr in meta_attrs:
            v = library_group.get(attr)
            if v is not None:
                lib_meta[attr] = norm(v)

        meta_file = self.output_dir / "library_meta.json"
        meta_file.write_text(
            json.dumps({"library_meta": lib_meta}, indent=2), encoding="utf-8"
        )

    def export_cells_index(self, index_data: List[Dict[str, str]]) -> None:
        """Export the main cells index CSV"""
        pd.DataFrame(index_data).sort_values("cell").to_csv(
            self.output_dir / "cells_index.csv", index=False
        )


def main():
    """Command line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Liberty file to per-cell CSV structure using liberty-parser"
    )
    parser.add_argument("--lib", "-l", required=True, help="Path to .lib file")
    parser.add_argument("--out", "-o", required=True, help="Output directory")

    args = parser.parse_args()

    try:
        converter = LibertyDataExtractor()
        output_path = converter.convert(Path(args.lib), Path(args.out))

        print(f"\n✅ Success!")
        print(f"Output directory: {output_path}")
        print(f"Main index: {output_path / 'cells_index.csv'}")
        print(f"Library metadata: {output_path / 'library_meta.json'}")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
