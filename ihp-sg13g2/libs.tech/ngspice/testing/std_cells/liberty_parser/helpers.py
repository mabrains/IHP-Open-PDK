import re
from typing import List, Optional


def norm(v):
    """Unwrap EscapedString/Number and lists -> plain Python types."""
    if v is None:
        return None
    if hasattr(v, "value"):
        return norm(v.value)
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    return v


def gname(g) -> str:
    """Return group arg[0] (e.g., cell/pin/library name)."""
    return g.args[0] if getattr(g, "args", None) else "<unnamed>"


def getstr(g, key) -> Optional[str]:
    v = norm(g.get(key))
    return None if v is None else str(v)


def getf(g, key) -> Optional[float]:
    v = norm(g.get(key))
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _parse_float_list(v) -> List[float]:
    """
    Accept list/tuple/str and return list[float].
    Handles cases like ["0.0186, 0.0966, ..."] and multiline/backslash-continued strings.
    """
    v = norm(v)
    if v is None:
        return []

    if isinstance(v, (list, tuple)):
        out: List[float] = []
        for x in v:
            x = norm(x)
            if x is None:
                continue
            if isinstance(x, (list, tuple)):
                out.extend(_parse_float_list(x))
            elif isinstance(x, str):
                s = (
                    x.replace("{", "")
                    .replace("}", "")
                    .replace("[", "")
                    .replace("]", "")
                )
                s = s.replace("\\\n", " ").replace("\\", " ")
                parts = [p.strip() for p in s.replace("\n", " ").split(",")]
                out.extend(float(p) for p in parts if p != "")
            else:
                out.append(float(str(x)))
        return out

    if isinstance(v, str):
        s = v.replace("{", "").replace("}", "").replace("[", "").replace("]", "")
        s = s.replace("\\\n", " ").replace("\\", " ")
        parts = [p.strip() for p in s.replace("\n", " ").split(",")]
        return [float(p) for p in parts if p != ""]

    # Fallback (number-like scalar)
    return [float(str(v))]


def getlistf(g, key) -> List[float]:
    return _parse_float_list(g.get(key))


def parse_values_matrix(values, idx2_len: int) -> List[List[float]]:
    """
    Convert liberty 'values' into 2D list. If parser returns a string,
    split to floats and chunk by len(index_2). If already nested, normalize.
    """
    vals = norm(values)
    if vals is None:
        return []
    if isinstance(vals, str):
        flat = _parse_float_list(vals)
        if idx2_len > 0:
            return [flat[i : i + idx2_len] for i in range(0, len(flat), idx2_len)]
        return [flat]
    if isinstance(vals, (list, tuple)):
        if vals and not isinstance(vals[0], (list, tuple)):
            flat = _parse_float_list(vals)
            if idx2_len > 0:
                return [flat[i : i + idx2_len] for i in range(0, len(flat), idx2_len)]
            return [flat]
        # nested
        matrix: List[List[float]] = []
        for row in vals:
            matrix.append([float(str(norm(x))) for x in row])
        return matrix
    return []


def preprocess_liberty_text(text: str) -> str:
    """
    Quote unquoted wire load names so the liberty parser won't choke.
    Idempotent: already-quoted values stay untouched.
    """

    def quote_if_needed(match):
        head, name, tail = match.groups()
        name = name.strip()
        if name.startswith('"') and name.endswith('"'):
            return f"{head}{name}{tail}"
        return f'{head}"{name}"{tail}'

    text = re.sub(
        r'(wire_load_from_area\s*\(\s*[^,]+,\s*[^,]+,\s*)([^")\s][^)]*)(\)\s*;)',
        quote_if_needed,
        text,
        flags=re.IGNORECASE,
    )
    return text


def cell_has_output_timing(cell) -> bool:
    """Return True if any OUTPUT pin has at least one timing table with values."""
    for pin in cell.get_groups("pin"):
        if (getstr(pin, "direction") or "").lower() != "output":
            continue
        if not pin.get_groups("timing"):
            continue
        if pin.get_groups("timing"):
            return True
    return False


def parse_values_paired_samples(values, idx1, idx2):
    """
    Return up to three dicts: first/mid/last paired samples:
      {"sample_type": "first|mid|last", "slew_ns": ..., "load_pf": ..., "value": ...}
    """
    mtx = parse_values_matrix(values, idx2_len=len(idx2))
    n_i = len(mtx)
    n_j = len(mtx[0]) if n_i else 0

    def picks(n):
        if n <= 0:
            return []
        if n == 1:
            return [0]
        mid = n // 2
        out = []
        for i in (0, mid, n - 1):
            if 0 <= i < n and i not in out:
                out.append(i)
        return out

    i_pos, j_pos = picks(n_i), picks(n_j)
    labels = ["first", "mid", "last"]
    m = min(len(i_pos), len(j_pos), 3)

    out = []
    for k in range(m):
        i, j = i_pos[k], j_pos[k]
        out.append(
            {
                "sample_type": labels[k],
                "slew_ns": (idx1[i] if i < len(idx1) else None),
                "load_pf": (idx2[j] if j < len(idx2) else None),
                "value": float(mtx[i][j]),
            }
        )
    return out


CELLS_MAP = {
    # Combinational
    "sg13g2_a21o_1": "combinational",
    "sg13g2_a21o_2": "combinational",
    "sg13g2_a21oi_1": "combinational",
    "sg13g2_a21oi_2": "combinational",
    "sg13g2_a221oi_1": "combinational",
    "sg13g2_a22oi_1": "combinational",
    "sg13g2_and2_1": "combinational",
    "sg13g2_and2_2": "combinational",
    "sg13g2_and3_1": "combinational",
    "sg13g2_and3_2": "combinational",
    "sg13g2_and4_1": "combinational",
    "sg13g2_and4_2": "combinational",
    "sg13g2_buf_1": "combinational",
    "sg13g2_buf_2": "combinational",
    "sg13g2_buf_4": "combinational",
    "sg13g2_buf_8": "combinational",
    "sg13g2_buf_16": "combinational",
    "sg13g2_ebufn_2": "combinational",
    "sg13g2_ebufn_4": "combinational",
    "sg13g2_ebufn_8": "combinational",
    "sg13g2_einvn_2": "combinational",
    "sg13g2_einvn_4": "combinational",
    "sg13g2_einvn_8": "combinational",
    "sg13g2_inv_1": "combinational",
    "sg13g2_inv_2": "combinational",
    "sg13g2_inv_4": "combinational",
    "sg13g2_inv_8": "combinational",
    "sg13g2_inv_16": "combinational",
    "sg13g2_mux2_1": "combinational",
    "sg13g2_mux2_2": "combinational",
    "sg13g2_mux4_1": "combinational",
    "sg13g2_nand2_1": "combinational",
    "sg13g2_nand2_2": "combinational",
    "sg13g2_nand2b_1": "combinational",
    "sg13g2_nand2b_2": "combinational",
    "sg13g2_nand3_1": "combinational",
    "sg13g2_nand3b_1": "combinational",
    "sg13g2_nand4_1": "combinational",
    "sg13g2_nor2_1": "combinational",
    "sg13g2_nor2_2": "combinational",
    "sg13g2_nor2b_1": "combinational",
    "sg13g2_nor2b_2": "combinational",
    "sg13g2_nor3_1": "combinational",
    "sg13g2_nor3_2": "combinational",
    "sg13g2_nor4_1": "combinational",
    "sg13g2_nor4_2": "combinational",
    "sg13g2_o21ai_1": "combinational",
    "sg13g2_or2_1": "combinational",
    "sg13g2_or2_2": "combinational",
    "sg13g2_or3_1": "combinational",
    "sg13g2_or3_2": "combinational",
    "sg13g2_or4_1": "combinational",
    "sg13g2_or4_2": "combinational",
    "sg13g2_xor2_1": "combinational",
    "sg13g2_xnor2_1": "combinational",
    "sg13g2_lgcp_1": "combinational",
    # Sequential
    "sg13g2_dfrbp_1": "sequential",
    "sg13g2_dfrbp_2": "sequential",
    "sg13g2_dfrbpq_1": "sequential",
    "sg13g2_dfrbpq_2": "sequential",
    "sg13g2_dlhq_1": "sequential",
    "sg13g2_dlhr_1": "sequential",
    "sg13g2_dlhrq_1": "sequential",
    "sg13g2_dllr_1": "sequential",
    "sg13g2_dllrq_1": "sequential",
    "sg13g2_sdfbbp_1": "sequential",
    "sg13g2_sdfrbp_1": "sequential",
    "sg13g2_sdfrbp_2": "sequential",
    "sg13g2_sdfrbpq_1": "sequential",
    "sg13g2_sdfrbpq_2": "sequential",
    # Physical
    "sg13g2_antennanp": "physical",
    "sg13g2_decap_4": "physical",
    "sg13g2_decap_8": "physical",
    "sg13g2_fill_1": "physical",
    "sg13g2_fill_2": "physical",
    "sg13g2_fill_4": "physical",
    "sg13g2_fill_8": "physical",
    "sg13g2_tiehi": "physical",
    "sg13g2_tielo": "physical",
    "sg13g2_sighold": "physical",
    "sg13g2_slgcp_1": "physical",
    "sg13g2_dlygate4sd1_1": "physical",
    "sg13g2_dlygate4sd2_1": "physical",
    "sg13g2_dlygate4sd3_1": "physical",
}
