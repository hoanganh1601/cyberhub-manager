"""Generate DBML from the current, MySQL-derived data dictionary."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "docs" / "diagrams" / "data_dictionary.md"
OUTPUT = ROOT / "docs" / "diagrams" / "cyberhub_manager.dbml"
SQL_DIR = ROOT / "sql"


def split_columns(value: str) -> list[str]:
    return [part.strip().strip("`") for part in value.split(",")]


def parse_tables(text: str) -> list[dict[str, object]]:
    chunks = re.split(r"(?m)^### ([a-zA-Z0-9_]+)\s*$", text)
    tables: list[dict[str, object]] = []
    for offset in range(1, len(chunks), 2):
        name, body = chunks[offset], chunks[offset + 1]
        lines = body.splitlines()
        purpose = next((line.strip() for line in lines if line.strip()), "")
        table: dict[str, object] = {
            "name": name,
            "purpose": purpose,
            "columns": [],
            "primary": [],
            "indexes": [],
            "refs": [],
            "checks": [],
        }
        in_columns = False
        for line in lines:
            if line.startswith("| `") and "|" in line[1:]:
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if len(cells) >= 6 and cells[0].startswith("`"):
                    column = {
                        "name": cells[0].strip("`"),
                        "type": cells[1].strip("`").replace("`", ""),
                        "nullable": cells[2] == "Có",
                        "default": cells[3],
                    }
                    table["columns"].append(column)
                    in_columns = True
                    continue
            if line.startswith("Ràng buộc:"):
                in_columns = False
            if line.startswith("Index bổ sung"):
                in_columns = False

            match = re.search(r"PRIMARY KEY \(([^)]+)\)", line)
            if match:
                table["primary"] = split_columns(match.group(1))
                continue

            match = re.search(r"UNIQUE `([^`]+)` \(([^)]+)\)", line)
            if match:
                table["indexes"].append((match.group(1), split_columns(match.group(2)), True))
                continue

            match = None if "FOREIGN KEY" in line else re.search(r"(?:INDEX|KEY) `([^`]+)` \(([^)]+)\)", line)
            if match:
                table["indexes"].append((match.group(1), split_columns(match.group(2)), False))
                continue

            match = re.search(
                r"FOREIGN KEY `([^`]+)` \(([^)]+)\) → `([^`]+)` \(([^)]+)\)(.*)", line
            )
            if match:
                table["refs"].append(
                    (match.group(1), split_columns(match.group(2)), match.group(3), split_columns(match.group(4)), match.group(5).strip())
                )
                continue

            match = re.search(r"CHECK `([^`]+)`:", line)
            if match:
                table["checks"].append((match.group(1), line.split(": `", 1)[-1].rstrip("`")))

        tables.append(table)
    return tables


def source_files() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(SQL_DIR.glob("[0-9][0-9][0-9]_*.sql")):
        source = path.relative_to(ROOT).as_posix()
        for match in re.finditer(
            r"(?im)^\s*CREATE TABLE\s+(?:IF NOT EXISTS\s+)?([a-zA-Z0-9_]+)",
            path.read_text(encoding="utf-8"),
        ):
            result[match.group(1).lower()] = source
    return result


def render(tables: list[dict[str, object]], sources: dict[str, str]) -> str:
    output = [
        "// CyberHub Manager — DBML sinh từ docs/diagrams/data_dictionary.md.",
        "// Dictionary phản ánh schema MySQL sau các migration 001–027.",
        "// Bảng schema_migrations do migration runner tạo riêng nên không nằm trong 70 bảng nghiệp vụ.",
        "",
    ]

    for table in tables:
        name = str(table["name"])
        output.append(f"// {table['purpose']}")
        output.append(f"// DDL: {sources.get(name, 'xem migration ALTER/index trong thư mục sql/')}")
        for check_name, check in table["checks"]:
            output.append(f"// CHECK {check_name}: {check}")
        output.append(f"Table {name} {{")

        primary = list(table["primary"])
        inline_primary = primary if len(primary) == 1 else []
        for column in table["columns"]:
            col_name = str(column["name"])
            # DBML parsers reject MySQL's UNSIGNED modifier; retain the base type.
            col_type = re.sub(r"\s+unsigned\b", "", str(column["type"]), flags=re.IGNORECASE)
            attrs: list[str] = []
            if not column["nullable"]:
                attrs.append("not null")
            if col_name in inline_primary:
                attrs.append("pk")
            default = str(column["default"])
            default_update_note = ""
            if default == "AUTO_INCREMENT":
                attrs.append("increment")
            elif default != "—" and default:
                if default == "``":
                    attrs.append("default: ''")
                else:
                    expression = re.match(r"`([^`]+)`", default)
                    if expression:
                        value = expression.group(1)
                        if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
                            attrs.append(f"default: {value}")
                        elif value.upper() in {"TRUE", "FALSE", "NULL"}:
                            attrs.append(f"default: {value.lower()}")
                        elif "(" in value or value.upper() in {"CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME"}:
                            attrs.append(f"default: `{value}`")
                        else:
                            attrs.append(f"default: '{value}'")
                        if "tự cập nhật khi sửa" in default:
                            default_update_note = " // ON UPDATE CURRENT_TIMESTAMP"
                    elif default.startswith("'") and default.endswith("'"):
                        attrs.append(f"default: {default}")
                    elif re.fullmatch(r"-?\d+(?:\.\d+)?", default) or default.upper() in {"TRUE", "FALSE", "NULL"}:
                        attrs.append(f"default: {default.lower() if default.upper() in {'TRUE', 'FALSE', 'NULL'} else default}")
                    else:
                        attrs.append(f"default: `{default}`")
            suffix = f" [{', '.join(attrs)}]" if attrs else ""
            output.append(f"  {col_name} {col_type}{suffix}{default_update_note}")

        indexes: list[str] = []
        if len(primary) > 1:
            indexes.append(f"  ({', '.join(primary)}) [pk]")
        for index_name, columns, unique in table["indexes"]:
            flags = ["unique"] if unique else []
            flags.append(f"name: '{index_name}'")
            indexes.append(f"  ({', '.join(columns)}) [{', '.join(flags)}]")
        if indexes:
            output.extend(["", "  indexes {"])
            output.extend(indexes)
            output.append("  }")
        output.append("}")
        output.append("")

    for table in tables:
        for fk_name, local_columns, target, remote_columns, actions in table["refs"]:
            left = f"{table['name']}.{local_columns[0]}" if len(local_columns) == 1 else f"{table['name']}.({', '.join(local_columns)})"
            right = f"{target}.{remote_columns[0]}" if len(remote_columns) == 1 else f"{target}.({', '.join(remote_columns)})"
            action_note = f" // {actions}" if actions else ""
            output.append(f"Ref {fk_name}: {left} > {right}{action_note}")

    return "\n".join(output).rstrip() + "\n"


def main() -> None:
    tables = parse_tables(DICTIONARY.read_text(encoding="utf-8"))
    if len(tables) != 70:
        raise SystemExit(f"Expected 70 business tables in the dictionary; found {len(tables)}")
    OUTPUT.write_text(render(tables, source_files()), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(tables)} tables)")


if __name__ == "__main__":
    main()
