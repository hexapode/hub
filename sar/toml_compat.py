"""TOML parser and serializer compatibility layer.

Uses Python 3.11+ `tomllib` or `tomli` when available, with a compliant
pure-Python fallback for environments without external packages.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, BinaryIO


class TOMLDecodeError(ValueError):
    """Raised when TOML parsing fails."""


try:
    import tomllib as _stdlib_toml  # type: ignore

    def loads(s: str) -> dict[str, Any]:
        try:
            return _stdlib_toml.loads(s)
        except Exception as exc:
            raise TOMLDecodeError(str(exc)) from exc

    def load(fp: BinaryIO) -> dict[str, Any]:
        return loads(fp.read().decode("utf-8"))

except ImportError:
    try:
        import tomli as _tomli  # type: ignore

        def loads(s: str) -> dict[str, Any]:
            try:
                return _tomli.loads(s)
            except Exception as exc:
                raise TOMLDecodeError(str(exc)) from exc

        def load(fp: BinaryIO) -> dict[str, Any]:
            return loads(fp.read().decode("utf-8"))

    except ImportError:

        def load(fp: BinaryIO) -> dict[str, Any]:
            return loads(fp.read().decode("utf-8"))

        def loads(s: str) -> dict[str, Any]:
            return _parse_toml(s)


def _strip_comment_outside_strings(line: str) -> str:
    in_single = False
    in_double = False
    escape = False
    for idx, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_double:
            escape = True
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == "#" and not in_single and not in_double:
            return line[:idx]
    return line


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    depth_brack = 0
    depth_brace = 0
    in_single = False
    in_double = False
    escape = False

    for ch in text:
        if escape:
            cur.append(ch)
            escape = False
            continue
        if ch == "\\" and in_double:
            cur.append(ch)
            escape = True
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
            continue
        if not in_single and not in_double:
            if ch == "[":
                depth_brack += 1
            elif ch == "]":
                depth_brack -= 1
                if depth_brack < 0:
                    raise TOMLDecodeError("Unbalanced brackets")
            elif ch == "{":
                depth_brace += 1
            elif ch == "}":
                depth_brace -= 1
                if depth_brace < 0:
                    raise TOMLDecodeError("Unbalanced braces")
            elif ch == sep and depth_brack == 0 and depth_brace == 0:
                parts.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)

    if in_single or in_double or depth_brack != 0 or depth_brace != 0:
        raise TOMLDecodeError(f"Unclosed delimiter in: {text!r}")

    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def _find_eq(line: str) -> int:
    in_single = False
    in_double = False
    escape = False
    for i, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_double:
            escape = True
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == "=" and not in_single and not in_double:
            return i
    return -1


def _unescape_basic_string(s: str) -> str:
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\":
            i += 1
            if i >= n:
                raise TOMLDecodeError("Trailing backslash in string")
            esc = s[i]
            if esc == "n":
                out.append("\n")
            elif esc == "t":
                out.append("\t")
            elif esc == "r":
                out.append("\r")
            elif esc == '"':
                out.append('"')
            elif esc == "\\":
                out.append("\\")
            elif esc == "\n":
                # line continuation
                while i + 1 < n and s[i + 1] in (" ", "\t", "\n", "\r"):
                    i += 1
            else:
                out.append("\\" + esc)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _parse_value(raw: str) -> Any:
    val = raw.strip()
    if not val:
        raise TOMLDecodeError("Empty value")

    if val.startswith('"""') and val.endswith('"""') and len(val) >= 6:
        inner = val[3:-3]
        if inner.startswith("\n"):
            inner = inner[1:]
        elif inner.startswith("\r\n"):
            inner = inner[2:]
        return _unescape_basic_string(inner)

    if val.startswith("'''") and val.endswith("'''") and len(val) >= 6:
        inner = val[3:-3]
        if inner.startswith("\n"):
            inner = inner[1:]
        elif inner.startswith("\r\n"):
            inner = inner[2:]
        return inner

    if val.startswith('"') and val.endswith('"') and len(val) >= 2:
        # Verify no unescaped quote inside
        inner = val[1:-1]
        return _unescape_basic_string(inner)

    if val.startswith("'") and val.endswith("'") and len(val) >= 2:
        return val[1:-1]

    if val == "true":
        return True
    if val == "false":
        return False

    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        items = _split_top_level(inner, ",")
        return [_parse_value(item) for item in items if item]

    if val.startswith("{") and val.endswith("}"):
        inner = val[1:-1].strip()
        if not inner:
            return {}
        result: dict[str, Any] = {}
        pairs = _split_top_level(inner, ",")
        for pair in pairs:
            if not pair:
                continue
            eq_idx = _find_eq(pair)
            if eq_idx < 0:
                raise TOMLDecodeError(f"Invalid inline table entry: {pair!r}")
            k_raw = pair[:eq_idx].strip()
            v_raw = pair[eq_idx + 1 :].strip()
            _set_dotted_key(result, _parse_key_path(k_raw), _parse_value(v_raw))
        return result

    # ISO Date YYYY-MM-DD or DateTime
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        try:
            y, m, d = map(int, val.split("-"))
            return datetime.date(y, m, d)
        except ValueError as exc:
            raise TOMLDecodeError(str(exc)) from exc

    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", val):
        try:
            iso = val.replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(iso)
        except ValueError as exc:
            raise TOMLDecodeError(str(exc)) from exc

    # Integer
    if re.match(r"^[+-]?\d(_?\d)*$", val):
        return int(val.replace("_", ""))

    # Float
    if re.match(r"^[+-]?\d(_?\d)*(\.\d(_?\d)*)?([eE][+-]?\d(_?\d)*)?$", val):
        return float(val.replace("_", ""))

    raise TOMLDecodeError(f"Cannot parse TOML value: {val!r}")


def _parse_key_path(key_expr: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    in_single = False
    in_double = False
    for ch in key_expr.strip():
        if ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
        elif ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
        elif ch == "." and not in_single and not in_double:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if in_single or in_double:
        raise TOMLDecodeError(f"Unclosed quote in key: {key_expr!r}")
    parts.append("".join(cur).strip())
    cleaned: list[str] = []
    for p in parts:
        if not p:
            raise TOMLDecodeError(f"Empty key segment in: {key_expr!r}")
        if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
            cleaned.append(p[1:-1])
        else:
            if not re.match(r"^[A-Za-z0-9_-]+$", p):
                raise TOMLDecodeError(f"Invalid bare key: {p!r}")
            cleaned.append(p)
    return cleaned


def _set_dotted_key(target: dict[str, Any], path: list[str], value: Any) -> None:
    cur = target
    for k in path[:-1]:
        if k not in cur:
            cur[k] = {}
        elif not isinstance(cur[k], dict):
            raise TOMLDecodeError(f"Key conflict at {k!r}")
        cur = cur[k]
    last = path[-1]
    if last in cur:
        raise TOMLDecodeError(f"Duplicate key: {last!r}")
    cur[last] = value


def _parse_toml(s: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current_table: dict[str, Any] = root
    lines = s.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i]
        line = _strip_comment_outside_strings(raw_line).strip()
        i += 1
        if not line:
            continue

        # Array of tables [[...]]
        if line.startswith("[[") and line.endswith("]]"):
            header = line[2:-2].strip()
            path = _parse_key_path(header)
            cur = root
            for k in path[:-1]:
                if k not in cur:
                    cur[k] = {}
                elif isinstance(cur[k], list):
                    cur = cur[k][-1]
                    continue
                elif not isinstance(cur[k], dict):
                    raise TOMLDecodeError(f"Invalid table path at {k!r}")
                cur = cur[k]
            last = path[-1]
            if last not in cur:
                cur[last] = []
            elif not isinstance(cur[last], list):
                raise TOMLDecodeError(f"Conflict with non-array table {last!r}")
            new_entry: dict[str, Any] = {}
            cur[last].append(new_entry)
            current_table = new_entry
            continue

        # Standard table [...]
        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip()
            path = _parse_key_path(header)
            cur = root
            for k in path:
                if k not in cur:
                    cur[k] = {}
                    cur = cur[k]
                elif isinstance(cur[k], list):
                    cur = cur[k][-1]
                elif not isinstance(cur[k], dict):
                    raise TOMLDecodeError(f"Conflict at table {k!r}")
                else:
                    cur = cur[k]
            current_table = cur
            continue

        eq_idx = _find_eq(line)
        if eq_idx < 0:
            raise TOMLDecodeError(f"Expected key = value, got: {line!r}")

        key_part = line[:eq_idx].strip()
        val_part = line[eq_idx + 1 :].strip()

        # Check for multiline strings or multiline arrays/inline tables
        if val_part.startswith('"""') or val_part.startswith("'''"):
            delim = val_part[:3]
            if not (len(val_part) >= 6 and val_part.endswith(delim)):
                acc = [raw_line[raw_line.index("=") + 1 :].lstrip()]
                closed = False
                while i < n:
                    next_raw = lines[i]
                    i += 1
                    acc.append(next_raw)
                    if delim in next_raw:
                        closed = True
                        break
                if not closed:
                    raise TOMLDecodeError("Unclosed multiline string")
                val_part = "\n".join(acc).strip()
        elif val_part.startswith("[") or val_part.startswith("{"):
            open_ch = val_part[0]
            close_ch = "]" if open_ch == "[" else "}"
            acc = [val_part]
            while True:
                joined = " ".join(acc)
                try:
                    _split_top_level(joined[1:-1] if joined.endswith(close_ch) else joined, ",")
                    if joined.endswith(close_ch):
                        val_part = joined
                        break
                except TOMLDecodeError:
                    pass
                if i >= n:
                    raise TOMLDecodeError(f"Unclosed {open_ch}...{close_ch}")
                next_clean = _strip_comment_outside_strings(lines[i]).strip()
                i += 1
                if next_clean:
                    acc.append(next_clean)

        path = _parse_key_path(key_part)
        parsed_val = _parse_value(val_part)
        _set_dotted_key(current_table, path, parsed_val)

    return root


def _format_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, str):
        if "\n" in v:
            escaped = v.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            return f'"""\n{escaped}"""'
        escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t")
        return f'"{escaped}"'
    if isinstance(v, list):
        return "[" + ", ".join(_format_scalar(x) for x in v) + "]"
    if isinstance(v, dict):
        items = [f"{k} = {_format_scalar(val)}" for k, val in v.items()]
        return "{ " + ", ".join(items) + " }"
    raise TypeError(f"Unsupported TOML type: {type(v)}")


def dumps(data: dict[str, Any]) -> str:
    """Serialize a dictionary to clean TOML."""
    lines: list[str] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    array_tables: list[tuple[str, list[dict[str, Any]]]] = []

    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, dict):
            tables.append((k, v))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            array_tables.append((k, v))
        else:
            lines.append(f"{k} = {_format_scalar(v)}")

    for table_name, table_dict in tables:
        lines.append("")
        lines.append(f"[{table_name}]")
        subtables: list[tuple[str, dict[str, Any]]] = []
        for k, v in table_dict.items():
            if v is None:
                continue
            if isinstance(v, dict) and any(isinstance(subv, dict) for subv in v.values()):
                subtables.append((f"{table_name}.{k}", v))
            elif isinstance(v, dict) and k == "records_source":
                subtables.append((f"{table_name}.{k}", v))
            else:
                lines.append(f"{k} = {_format_scalar(v)}")
        for sub_name, sub_dict in subtables:
            lines.append("")
            lines.append(f"[{sub_name}]")
            for sk, sv in sub_dict.items():
                if sv is not None:
                    lines.append(f"{sk} = {_format_scalar(sv)}")

    for arr_name, arr_list in array_tables:
        for item in arr_list:
            lines.append("")
            lines.append(f"[[{arr_name}]]")
            for k, v in item.items():
                if v is not None:
                    lines.append(f"{k} = {_format_scalar(v)}")

    return "\n".join(lines).strip() + "\n"
