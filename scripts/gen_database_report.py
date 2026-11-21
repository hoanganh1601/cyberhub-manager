"""Generate the schema reference sections of the LaTeX database report."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "docs" / "diagrams" / "data_dictionary.md"
CHAPTERS = ROOT / "cơ sở dữ liệu" / "chapters"

MODULES = [
    ("Cửa hàng, nhân sự và kiểm toán", ["stores", "employees", "employee_profiles", "employee_store_assignments", "management_audit"]),
    ("Khách hàng, tài khoản và bảo mật", ["customers", "customer_store_links", "accounts", "customer_avatars", "customer_notification_reads", "customer_notification_events", "customer_email_tokens", "customer_mail_outbox", "customer_security_audit"]),
    ("Máy trạm, phiên sử dụng và bảo trì", ["machines", "machine_room_types", "usage_sessions", "machine_incidents", "machine_incident_parts", "machine_incident_events"]),
    ("Giao dịch, hóa đơn và ca tiền mặt", ["account_transactions", "invoices", "cash_shifts", "cash_shift_entries"]),
    ("Thực đơn và bán hàng POS", ["menu_categories", "menu_items", "menu_item_images", "menu_item_changes", "menu_orders", "menu_order_items", "menu_promotions", "menu_order_pricing", "pos_order_reversals"]),
    ("Kho nguyên liệu và định lượng", ["inventory_ingredients", "menu_item_recipes", "menu_order_recipe_snapshots", "inventory_movements", "inventory_counts"]),
    ("Khuyến mãi, voucher và thành viên", ["promotions", "loyalty_settings", "reward_catalog", "customer_vouchers", "voucher_events", "loyalty_point_grants"]),
    ("Trò chơi và xu trò chơi", ["games", "game_prizes", "game_wallets", "game_sessions", "game_coin_ledger"]),
    ("Quảng cáo nhận thưởng", ["ad_settings", "ad_creatives", "ad_reward_events"]),
    ("Nhà cung cấp và mua hàng", ["suppliers", "purchase_requests", "purchase_request_lines", "purchase_orders", "purchase_order_lines", "goods_receipts", "goods_receipt_lines", "supplier_payables", "supplier_payable_approvals"]),
    ("Đối tác thương mại", ["commercial_partners", "commercial_contracts", "commercial_campaigns", "commercial_placements", "commercial_play_sessions", "commercial_events", "commercial_reward_grants", "commercial_settlements", "commercial_settlement_lines"]),
]


def uncode(value: str) -> str:
    return value.strip().strip("`")


def tex_text(value: str) -> str:
    """Escape ordinary text and render Markdown inline-code spans as \texttt."""
    parts = re.split(r"(`[^`]*`)", value)
    rendered: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`"):
            code = part[1:-1].replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#").replace("$", r"\$").replace("{", r"\{").replace("}", r"\}").replace("→", r"$\rightarrow$")
            rendered.append(r"\texttt{" + code + "}")
        else:
            plain = part.replace("\\", r"\textbackslash{}").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#").replace("$", r"\$").replace("{", r"\{").replace("}", r"\}").replace("→", r"$\rightarrow$")
            rendered.append(plain)
    return "".join(rendered)


def parse_dictionary(text: str) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    chunks = re.split(r"(?m)^### ([a-zA-Z0-9_]+)\s*$", text)
    tables: list[dict[str, object]] = []
    for i in range(1, len(chunks), 2):
        name, body = chunks[i], chunks[i + 1]
        lines = body.splitlines()
        purpose = next((line.strip() for line in lines if line.strip()), "")
        table: dict[str, object] = {"name": name, "purpose": purpose, "columns": [], "constraints": []}
        for line in lines:
            if line.startswith("| `"):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if len(cells) >= 6 and cells[0].startswith("`"):
                    table["columns"].append({
                        "name": uncode(cells[0]),
                        "type": uncode(cells[1]),
                        "nullable": cells[2] == "Có",
                        "default": cells[3],
                        "key": cells[4],
                        "meaning": cells[5],
                    })
            if line.startswith("- PRIMARY KEY") or line.startswith("- UNIQUE ") or line.startswith("- FOREIGN KEY ") or line.startswith("- CHECK ") or line.startswith("- INDEX "):
                table["constraints"].append(line[2:].strip())
        tables.append(table)

    relationship_text = text.split("## 2. Quan hệ và cardinality", 1)[1].split("## 3. Chi tiết từng bảng", 1)[0]
    relationships: list[dict[str, str]] = []
    for line in relationship_text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        parent_match = re.search(r"`([^`]+)`", cells[0]) if cells else None
        if len(cells) >= 5 and parent_match:
            relationships.append({
                "parent": parent_match.group(1),
                "cardinality": cells[1],
                "child": re.search(r"`([^`]+)`", cells[2]).group(1),
                "fk": cells[3],
                "meaning": cells[4],
            })
    return tables, relationships


def format_constraint(value: str) -> str:
    return r" $\rightarrow$ ".join(tex_text(part) for part in value.split(" → "))


def write_chapter2(tables: list[dict[str, object]], relationships: list[dict[str, str]]) -> None:
    table_map = {str(t["name"]): t for t in tables}
    outgoing: dict[str, list[dict[str, str]]] = {name: [] for name in table_map}
    incoming: dict[str, list[dict[str, str]]] = {name: [] for name in table_map}
    for rel in relationships:
        outgoing[rel["child"]].append(rel)
        incoming[rel["parent"]].append(rel)

    lines = [
        r"\chapter{Lược đồ E--R và mô tả dữ liệu}",
        r"\section{Phạm vi và nguồn mô tả}",
        r"Schema trong mã nguồn được quản lý bằng các migration SQL từ \texttt{001\_initial\_schema.sql} đến \texttt{027\_customer\_email\_activation.sql}. Data dictionary của dự án mô tả 70 bảng nghiệp vụ dựa trên schema MySQL test; bảng kỹ thuật \texttt{schema\_migrations} do migration runner tạo riêng. Nội dung dưới đây bám theo migration và data dictionary hiện có, không mô tả dữ liệu runtime chưa được kiểm tra.",
        r"\section{Lược đồ E--R quan niệm}",
        r"Sơ đồ quan niệm trong báo cáo giới hạn ở tám thực thể lõi: STORE, EMPLOYEE, CUSTOMER, ACCOUNT, MACHINE, USAGE\_SESSION, ACCOUNT\_TRANSACTION và INVOICE. Đây là phạm vi của hình quan niệm, không phải toàn bộ 70 bảng. Các phân hệ mở rộng được mô tả theo từng bảng ở phần sau; quan hệ vật lý chi tiết được lưu trong data dictionary và file DBML của dự án.",
        r"\begin{figure}[htbp]",
        r"  \centering",
        r"  \includegraphics[width=0.98\textwidth,height=0.66\textheight,keepaspectratio]{figures/erd_conceptual.png}",
        r"  \caption{Mô hình E--R quan niệm của tám thực thể lõi}",
        r"  \label{fig:erd-core}",
        r"\end{figure}",
        r"\section{Mô tả các bảng theo phân hệ}",
    ]

    for module, names in MODULES:
        lines.append(r"\subsection{" + tex_text(module) + "}")
        for name in names:
            table = table_map[name]
            lines.append(r"\subsubsection{Bảng \texttt{" + name.replace("_", r"\_") + "}}")
            lines.append(r"\textbf{Ý nghĩa:} " + tex_text(str(table["purpose"])) + r"\par")
            lines.append(r"\textbf{Thuộc tính:}")
            lines.append(r"\begin{itemize}")
            for col in table["columns"]:
                label = r"\texttt{" + col["name"].replace("_", r"\_") + "}"
                details = [r"\texttt{" + tex_text(str(col["type"])) + "}"]
                if col["key"] not in {"—", ""}:
                    details.append(tex_text(str(col["key"])))
                details.append("NULL" if col["nullable"] else "NOT NULL")
                default = str(col["default"])
                if default not in {"—", ""}:
                    if default == "AUTO_INCREMENT":
                        details.append("AUTO_INCREMENT")
                    elif default == "``":
                        details.append("mặc định chuỗi rỗng")
                    else:
                        details.append("mặc định " + tex_text(default))
                sentence = r"\item " + label + " (" + "; ".join(details) + ")"
                if col["meaning"] not in {"—", ""}:
                    meaning = str(col["meaning"])
                    sentence += r": " + tex_text(meaning)
                    if not meaning.rstrip().endswith((".", ";", ":")):
                        sentence += "."
                else:
                    sentence += "."
                lines.append(sentence)
            lines.append(r"\end{itemize}")

            rels = outgoing[name]
            if rels:
                lines.append(r"\textbf{Quan hệ:}")
                lines.append(r"\begin{itemize}")
                for rel in rels:
                    meaning = tex_text(rel["meaning"])
                    lines.append(r"\item FK " + tex_text(rel["fk"]) + ". Cardinality cha--con: " + tex_text(rel["cardinality"]) + r". " + meaning + ("" if rel["meaning"].rstrip().endswith(".") else "."))
                for rel in incoming[name]:
                    meaning = tex_text(rel["meaning"])
                    lines.append(r"\item Bảng con " + r"\texttt{" + rel["child"].replace("_", r"\_") + "}: FK " + tex_text(rel["fk"]) + "; cardinality cha--con: " + tex_text(rel["cardinality"]) + r". " + meaning + ("" if rel["meaning"].rstrip().endswith(".") else "."))
                lines.append(r"\end{itemize}")
            elif incoming[name]:
                lines.append(r"\textbf{Quan hệ:}")
                lines.append(r"\begin{itemize}")
                for rel in incoming[name]:
                    meaning = tex_text(rel["meaning"])
                    lines.append(r"\item Bảng con " + r"\texttt{" + rel["child"].replace("_", r"\_") + "}: FK " + tex_text(rel["fk"]) + "; cardinality cha--con: " + tex_text(rel["cardinality"]) + r". " + meaning + ("" if rel["meaning"].rstrip().endswith(".") else "."))
                lines.append(r"\end{itemize}")
            else:
                lines.append(r"\textbf{Quan hệ:} Không có khóa ngoại được khai báo trong schema.")

            if table["constraints"]:
                lines.append(r"\textbf{Ràng buộc và chỉ mục trong schema:}")
                lines.append(r"\begin{itemize}")
                for constraint in table["constraints"]:
                    lines.append(r"\item " + format_constraint(str(constraint)))
                lines.append(r"\end{itemize}")

    lines.extend([
        r"\section{Nhận xét về quan hệ}",
        r"Các liên kết trong schema được xác định bằng khóa ngoại. Khả năng một phía tham gia tùy chọn thể hiện qua cột FK cho phép NULL; quan hệ một--một được thể hiện khi FK có ràng buộc UNIQUE hoặc đồng thời là khóa chính. Một số quan hệ nghiệp vụ bổ sung được kiểm tra ở tầng service; chỉ các ràng buộc có trong migration mới được xem là bảo đảm ở mức database.",
        r"\section{Kết luận chương}",
        r"Chương mô tả tám thực thể trong sơ đồ quan niệm lõi và các bảng nghiệp vụ hiện có theo migration. Với từng bảng, thuộc tính, khóa, quan hệ và ràng buộc được trình bày theo data dictionary của dự án; phần schema vật lý tiếp tục được thể hiện bằng lược đồ quan hệ ở Chương 3.",
    ])
    (CHAPTERS / "chuong02.tex").write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def keys_for(table: dict[str, object]) -> tuple[str, str, str]:
    pk: list[str] = []
    unique: list[str] = []
    fks: list[str] = []
    for constraint in table["constraints"]:
        if constraint.startswith("PRIMARY KEY"):
            pk.append(constraint)
        elif constraint.startswith("UNIQUE"):
            unique.append(constraint)
        elif constraint.startswith("FOREIGN KEY"):
            fks.append(constraint)
    return "; ".join(pk), "; ".join(unique), "; ".join(fks)


def write_chapter3(tables: list[dict[str, object]]) -> None:
    lines = [
        r"\chapter{Chuyển lược đồ E--R sang mô hình quan hệ}",
        r"\section{Cơ sở ánh xạ}",
        r"Schema MySQL của CyberHub Manager gồm 70 bảng nghiệp vụ được khai báo qua migration 001--027. Chương này trình bày từng bảng dưới dạng quan hệ, liệt kê đầy đủ cột và các khóa chính, khóa duy nhất, khóa ngoại được khai báo. Kiểu dữ liệu, giá trị mặc định, CHECK và chỉ mục chi tiết đã được mô tả tại Chương 2 và trong các migration SQL.",
        r"\begin{itemize}",
        r"\item Mỗi bảng là một quan hệ; các cột là thuộc tính của quan hệ.",
        r"\item Khóa chính đơn hoặc ghép được lấy nguyên trạng từ DDL.",
        r"\item Khóa ngoại giữ quan hệ giữa các bảng; cột nullable phản ánh khả năng chưa có đối tượng liên quan.",
        r"\item Các bảng liên kết như \texttt{menu\_order\_items} và \texttt{purchase\_order\_lines} dùng khóa chính ghép đúng theo migration.",
        r"\end{itemize}",
        r"\section{Danh sách lược đồ quan hệ}",
    ]
    for module, names in MODULES:
        lines.append(r"\subsection{" + tex_text(module) + "}")
        lines.append(r"\begin{description}[leftmargin=3.6cm,labelwidth=3.4cm,style=nextline]")
        for name in names:
            table = next(t for t in tables if t["name"] == name)
            columns = ", ".join(r"\texttt{" + c["name"].replace("_", r"\_") + "}" for c in table["columns"])
            pk, unique, fks = keys_for(table)
            lines.append(r"\item[\texttt{" + name.replace("_", r"\_") + r"}] \textbf{Cột:} " + columns + ".")
            if pk:
                lines.append(r"Khóa chính: " + format_constraint(pk) + ".")
            if unique:
                lines.append(r"Khóa duy nhất: " + format_constraint(unique) + ".")
            if fks:
                fk_text = format_constraint(fks).replace("; ", ";\\par ")
                lines.append(r"Khóa ngoại: " + fk_text + ".")
        lines.append(r"\end{description}")

    lines.extend([
        r"\section{Ràng buộc toàn vẹn vật lý}",
        r"Các khai báo trên được hiện thực bằng kiểu cột, PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK và INDEX trong migration. Những quy tắc chỉ được kiểm tra tại service không được diễn giải thành ràng buộc database nếu DDL không khai báo chúng. Bảng \texttt{schema\_migrations} là bảng kỹ thuật do runner tạo, không thuộc danh sách 70 bảng nghiệp vụ.",
        r"\section{Kết luận chương}",
        r"Mô hình quan hệ của báo cáo bám theo tên cột và khóa của schema sau migration 027. File \texttt{docs/diagrams/data\_dictionary.md} cung cấp mô tả cột và quan hệ; file \texttt{docs/diagrams/cyberhub\_manager.dbml} có thể dùng để dựng sơ đồ vật lý đầy đủ.",
    ])
    (CHAPTERS / "chuong03.tex").write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    text = DICT.read_text(encoding="utf-8")
    tables, relationships = parse_dictionary(text)
    flattened = [name for _, names in MODULES for name in names]
    if len(tables) != 70 or len(flattened) != 70 or set(flattened) != {str(t["name"]) for t in tables}:
        raise SystemExit("The report module list does not match all 70 dictionary tables")
    write_chapter2(tables, relationships)
    write_chapter3(tables)
    print(f"Generated Chapter 2 and 3 from {len(tables)} dictionary tables and {len(relationships)} FK relationships")


if __name__ == "__main__":
    main()
