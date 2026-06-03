"""Layer 1: LAN protocol — YAML catalog serialization and heartbeat messages.

Pure data format functions — no I/O, no threading. Testable without network.
"""

from __future__ import annotations

import json
from typing import Any

CATALOG_YAML_DELIMITER = "---"
HEARTBEAT_TYPE = "peerpedia_hello"
BROADCAST_ADDR = "255.255.255.255"


# ============================================================================
# Catalog YAML Serialization
# ============================================================================

def catalog_to_yaml_string(data: dict[str, Any]) -> str:
    """Serialize catalog data to YAML frontmatter + Markdown table.

    The output is a valid .md file: YAML frontmatter between --- delimiters,
    followed by a human-readable Markdown table.
    """
    lines = [CATALOG_YAML_DELIMITER]
    _dict_to_yaml_lines(data, lines, indent=0)
    lines.append(CATALOG_YAML_DELIMITER)
    lines.append("")
    lines.append(f"# 知诸网 文章目录 -- {data.get('node_id', 'unknown')}")
    lines.append("")

    articles = data.get("articles", [])
    if articles:
        lines.append("| ID | 标题 | 作者 | 版本 |")
        lines.append("|---|---|---|---|")
        for a in articles:
            aid = a.get("id", "")[:8]
            title = a.get("title", "")
            authors = ", ".join(a.get("authors", []))
            version = a.get("version", "")
            lines.append(f"| {aid} | {title} | {authors} | {version} |")
        lines.append("")

    return "\n".join(lines) + "\n"


def _dict_to_yaml_lines(data: dict[str, Any], lines: list[str], indent: int):
    """Recursively write a dict to YAML lines."""
    prefix = "  " * indent
    for key, value in data.items():
        if value is None:
            lines.append(f"{prefix}{key}: ~")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, float):
            lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, str):
            if "\n" in value or '"' in value or ":" in value:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{prefix}{key}: "{escaped}"')
            else:
                lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}{key}: []")
            else:
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  -")
                        _dict_to_yaml_lines(item, lines, indent + 2)
                    elif isinstance(item, str):
                        if "\n" in item or '"' in item or ":" in item:
                            escaped = item.replace("\\", "\\\\").replace('"', '\\"')
                            lines.append(f'{prefix}  - "{escaped}"')
                        else:
                            lines.append(f"{prefix}  - {item}")
                    else:
                        lines.append(f"{prefix}  - {item}")
        elif isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            _dict_to_yaml_lines(value, lines, indent + 1)
        else:
            lines.append(f"{prefix}{key}: {value}")


# ============================================================================
# Catalog YAML Parsing
# ============================================================================

def parse_catalog_yaml(content: str) -> dict[str, Any]:
    """Parse catalog.md content, extracting the YAML frontmatter.

    Only the YAML frontmatter (between --- delimiters) is parsed.
    The Markdown table below is ignored (it's for human readers).
    """
    lines = content.split("\n")

    # Find the YAML block between first two --- delimiters
    yaml_start = -1
    yaml_end = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == CATALOG_YAML_DELIMITER:
            if yaml_start == -1:
                yaml_start = i
            elif yaml_end == -1:
                yaml_end = i
                break

    if yaml_start == -1 or yaml_end == -1 or yaml_end <= yaml_start + 1:
        return {"node_id": "unknown", "updated": "", "articles": []}

    yaml_lines = lines[yaml_start + 1 : yaml_end]
    return _parse_yaml_lines(yaml_lines)


def _parse_yaml_lines(lines: list[str]) -> dict[str, Any]:
    """Parse a list of YAML lines into a dict using a simple recursive descent parser."""
    result: dict[str, Any] = {}
    i = 0

    def current_indent() -> int:
        if i >= len(lines):
            return 0
        line = lines[i]
        if not line.strip():
            return 0
        return len(line) - len(line.lstrip())

    def parse_value(stripped: str, key_indent: int) -> tuple[Any, int]:
        """Parse a value starting from current position. Returns (value, lines_consumed_after_key)."""
        nonlocal i
        if not stripped:
            # Empty value after colon -- could be nested structure
            j = i + 1
            while j < len(lines):
                nl = lines[j]
                if not nl.strip():
                    j += 1
                    continue
                nindent = len(nl) - len(nl.lstrip())
                if nindent <= key_indent:
                    return None, 0  # Empty/null value
                nstripped = nl.strip()
                if nstripped.startswith("-"):
                    # List of items (possibly dicts)
                    result_list = []
                    while j < len(lines):
                        nl2 = lines[j]
                        if not nl2.strip():
                            j += 1
                            continue
                        nindent2 = len(nl2) - len(nl2.lstrip())
                        if nindent2 < nindent:
                            break
                        nstripped2 = nl2.strip()
                        if nstripped2.startswith("-"):
                            val_str = nstripped2[2:].strip() if len(nstripped2) > 1 else ""
                            if val_str:
                                result_list.append(_parse_scalar(val_str))
                                j += 1
                            else:
                                sub_lines = _collect_indented(lines, j + 1, nindent2 + 2)
                                result_list.append(_parse_yaml_lines(sub_lines))
                                j += 1 + len(sub_lines)
                        else:
                            break
                    i = j - 1
                    return result_list, i - (key_line_idx)
                else:
                    # Nested dict
                    sub_lines = _collect_indented(lines, j, nindent)
                    i = j + len(sub_lines) - 1
                    return _parse_yaml_lines(sub_lines), i - (key_line_idx)
            return None, 0

        # Non-empty value
        return _parse_scalar(stripped), 0

    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if ":" in stripped:
            key, _, value_str = stripped.partition(":")
            key = key.strip()
            value_str = value_str.strip()
            key_line_idx = i

            val, consumed = parse_value(value_str, indent)
            if consumed == 0 and not value_str:
                next_i = i + 1
                if next_i < len(lines):
                    nl = lines[next_i]
                    if nl.strip():
                        nindent = len(nl) - len(nl.lstrip())
                        if nindent > indent:
                            # parse_value already handled this
                            pass
                if val is None and i == key_line_idx:
                    result[key] = None
            else:
                result[key] = val

        i += 1

    return result


def _parse_scalar(value_str: str) -> Any:
    """Parse a single scalar YAML value."""
    value_str = value_str.strip()
    if value_str == "true":
        return True
    if value_str == "false":
        return False
    if value_str in ("null", "~", ""):
        return None
    if (value_str.startswith('"') and value_str.endswith('"')) or \
       (value_str.startswith("'") and value_str.endswith("'")):
        inner = value_str[1:-1]
        if value_str.startswith('"'):
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    if value_str.startswith("[") and value_str.endswith("]"):
        inner = value_str[1:-1]
        if not inner.strip():
            return []
        items = []
        for item in inner.split(","):
            item = item.strip().strip('"').strip("'")
            items.append(item)
        return items
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str


def _collect_indented(lines: list[str], start: int, min_indent: int) -> list[str]:
    """Collect consecutive lines indented at least min_indent from a base context.

    Stops at blank lines followed by lines below min_indent, or end of input.
    """
    result = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            result.append(line)
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent < min_indent:
            break
        result.append(line)
        i += 1
    return result


# ============================================================================
# UDP Heartbeat Messages
# ============================================================================

def build_heartbeat_message(
    node_id: str,
    host: str,
    port: int,
    version: str = "0.2.0",
    articles_count: int = 0,
) -> str:
    """Build a JSON heartbeat message."""
    return json.dumps({
        "type": HEARTBEAT_TYPE,
        "node_id": node_id,
        "host": host,
        "port": port,
        "version": version,
        "articles_count": articles_count,
    })


def parse_heartbeat_message(data: str) -> dict[str, Any] | None:
    """Parse a received heartbeat message.

    Returns the message dict if valid, None otherwise.
    """
    try:
        msg = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None

    if msg.get("type") != HEARTBEAT_TYPE:
        return None

    required = ["node_id", "host", "port"]
    for key in required:
        if key not in msg:
            return None

    return msg
