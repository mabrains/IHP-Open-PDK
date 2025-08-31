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
