"""HA-10 — Sinh data dictionary từ schema MySQL thật (information_schema).

Cấu trúc (kiểu, NULL, mặc định, PK/UK/FK, CHECK, index, cardinality) đọc từ database nên luôn khớp
migration; phần "Ý nghĩa" viết tay trong DESCRIPTIONS. Thiếu mô tả cho một cột mới thì script báo lỗi.

    python scripts/gen_data_dictionary.py            # ghi docs/diagrams/data_dictionary.md
    python scripts/gen_data_dictionary.py --check    # chỉ kiểm tra file có khớp schema không (exit 1 nếu lệch)

Mặc định đọc cyberhub_manager_test (đã migrate bằng scripts/prepare_test_db.py).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "diagrams" / "data_dictionary.md"
DEFAULT_DATABASE = "cyberhub_manager_test"

# Bảng nghiệp vụ theo thứ tự trình bày; bảng kỹ thuật (schema_migrations, bảng probe của test) không đưa vào.
TABLES = (
    "stores",
    "employees",
    "customers",
    "accounts",
    "machines",
    "usage_sessions",
    "account_transactions",
    "invoices",
)

DESCRIPTIONS: dict[str, tuple[str, dict[str, str]]] = {
    "stores": (
        "Cửa hàng net. Nhân viên, máy và hóa đơn đều thuộc một cửa hàng.",
        {
            "id": "Khóa chính.",
            "code": "Mã cửa hàng, duy nhất.",
            "name": "Tên cửa hàng.",
            "address": "Địa chỉ.",
            "status": "`ACTIVE` / `INACTIVE`. Cửa hàng ngừng hoạt động thì nhân viên không đăng nhập được.",
            "created_at": "Thời điểm tạo (UTC).",
            "updated_at": "Thời điểm sửa gần nhất (UTC).",
        },
    ),
    "employees": (
        "Nhân viên đăng nhập ứng dụng; vai trò quyết định quyền thao tác.",
        {
            "id": "Khóa chính.",
            "code": "Mã nhân viên, duy nhất.",
            "store_id": "Cửa hàng nhân viên làm việc.",
            "full_name": "Họ tên.",
            "username": "Tên đăng nhập, duy nhất, 4–30 ký tự.",
            "password_hash": "Mật khẩu đã băm bcrypt; không bao giờ trả ra UI/DTO.",
            "role": "`ADMIN` / `MANAGER` / `STAFF`. Chỉ MANAGER, ADMIN được quản lý máy và đổi trạng thái khách.",
            "status": "`ACTIVE` / `INACTIVE` / `LOCKED`. Chỉ ACTIVE đăng nhập được.",
            "created_at": "Thời điểm tạo (UTC).",
            "updated_at": "Thời điểm sửa gần nhất (UTC).",
        },
    ),
    "customers": (
        "Thông tin cá nhân của khách chơi.",
        {
            "id": "Khóa chính.",
            "code": "Mã khách hàng, duy nhất (`CUS-` + hex).",
            "full_name": "Họ tên, 2–100 ký tự.",
            "phone": "Số điện thoại 10 số bắt đầu bằng 0, duy nhất.",
            "status": "`ACTIVE` / `INACTIVE`. Khách INACTIVE không được mở phiên mới.",
            "created_at": "Thời điểm tạo (UTC).",
            "updated_at": "Thời điểm sửa gần nhất (UTC).",
        },
    ),
    "accounts": (
        "Tài khoản đăng nhập máy trạm và ví tiền của khách; mỗi khách đúng một tài khoản.",
        {
            "id": "Khóa chính.",
            "code": "Mã tài khoản, duy nhất (`ACC-` + hex).",
            "customer_id": "Khách sở hữu tài khoản; UNIQUE nên mỗi khách tối đa một tài khoản.",
            "username": "Tên đăng nhập máy trạm, duy nhất, chữ/số/`_`/`.`, 4–30 ký tự.",
            "password_hash": "Mật khẩu đã băm bcrypt.",
            "balance": "Số dư (VND). Có thể âm sau checkout khi phí vượt số dư; chỉ đổi kèm một dòng `account_transactions`.",
            "status": "`ACTIVE` / `LOCKED`. LOCKED không mở phiên được nhưng vẫn nạp tiền để trả nợ.",
            "created_at": "Thời điểm tạo (UTC).",
            "updated_at": "Thời điểm sửa gần nhất (UTC).",
        },
    ),
    "machines": (
        "Máy trạm của cửa hàng và trạng thái hiện tại.",
        {
            "id": "Khóa chính.",
            "code": "Mã máy, duy nhất (vd. `PC01`).",
            "store_id": "Cửa hàng sở hữu máy.",
            "name": "Tên hiển thị.",
            "status": "`AVAILABLE` / `IN_USE` / `MAINTENANCE`. Chỉ AVAILABLE mới mở phiên được.",
            "hourly_rate": "Đơn giá mỗi giờ (VND, > 0). Phiên chụp lại giá này lúc mở.",
            "is_active": "FALSE = đã ngừng sử dụng (archive) vì có lịch sử, không xóa cứng.",
            "created_at": "Thời điểm tạo (UTC).",
            "updated_at": "Thời điểm sửa gần nhất (UTC); dùng để hiển thị thời gian trống của máy.",
        },
    ),
    "usage_sessions": (
        "Một lần khách dùng một máy, từ lúc mở đến lúc checkout.",
        {
            "id": "Khóa chính.",
            "code": "Mã phiên, duy nhất (`SS-` + hex).",
            "customer_id": "Khách dùng máy.",
            "machine_id": "Máy được dùng.",
            "opened_by": "Nhân viên mở phiên.",
            "closed_by": "Nhân viên checkout; NULL khi phiên đang chạy.",
            "started_at": "Thời điểm bắt đầu (UTC).",
            "ended_at": "Thời điểm kết thúc (UTC); NULL khi phiên ACTIVE.",
            "hourly_rate": "Đơn giá chụp từ máy lúc mở phiên; đổi giá máy sau đó không ảnh hưởng phiên.",
            "cost": "Tiền phí tính lúc checkout (VND); NULL khi phiên ACTIVE.",
            "status": "`ACTIVE` / `COMPLETED` / `CANCELLED`.",
            "active_machine_id": "Cột sinh tự động: `machine_id` khi ACTIVE, ngược lại NULL. UNIQUE ⇒ mỗi máy tối đa một phiên ACTIVE.",
            "active_customer_id": "Cột sinh tự động: `customer_id` khi ACTIVE, ngược lại NULL. UNIQUE ⇒ mỗi khách tối đa một phiên ACTIVE.",
        },
    ),
    "account_transactions": (
        "Sổ cái biến động số dư: mọi lần cộng/trừ `accounts.balance` đều có đúng một dòng; không sửa, không xóa.",
        {
            "id": "Khóa chính.",
            "code": "Mã giao dịch, duy nhất (`TX-` + hex).",
            "account_id": "Tài khoản bị thay đổi số dư.",
            "employee_id": "Nhân viên thực hiện.",
            "session_id": "Phiên liên quan (trừ phí, bù tiền lúc checkout); NULL với nạp tiền độc lập.",
            "type": "`TOP_UP` / `PROMOTION` / `USAGE_PAYMENT` / `DEBT_SETTLEMENT`.",
            "amount": "Số tiền có dấu (VND): dương khi cộng, âm khi `USAGE_PAYMENT`.",
            "method": "`CASH` / `TRANSFER` / `ACCOUNT_BALANCE` / `PROMOTION`, phải hợp với `type`.",
            "created_at": "Thời điểm ghi (UTC).",
        },
    ),
    "invoices": (
        "Hóa đơn tạo khi checkout thành công; lưu lại khách, nhân viên, cửa hàng để giữ đúng lịch sử.",
        {
            "id": "Khóa chính.",
            "code": "Mã hóa đơn, duy nhất (`INV-` + hex).",
            "session_id": "Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn.",
            "customer_id": "Khách (lưu thẳng để báo cáo không phải đi qua phiên).",
            "employee_id": "Nhân viên checkout.",
            "store_id": "Cửa hàng; dùng cho báo cáo doanh thu.",
            "usage_cost": "Phí sử dụng (VND). Doanh thu ngày = tổng `usage_cost` của hóa đơn PAID.",
            "settlement_amount": "Phần khách trả thêm bằng tiền mặt/chuyển khoản khi số dư không đủ; ≤ `usage_cost`.",
            "total_amount": "Tổng hóa đơn; P0 luôn bằng `usage_cost` (tiền bù không cộng lần hai).",
            "status": "`PAID` / `VOID`.",
            "created_at": "Thời điểm checkout (UTC); báo cáo quy đổi sang giờ Việt Nam (UTC+7).",
        },
    ),
}


_KIND_ORDER = {"PRIMARY KEY": 0, "UNIQUE": 1, "FOREIGN KEY": 2, "CHECK": 3}


def _rows(conn: Any, sql: str, params: tuple = ()) -> list[dict]:
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def _clean_clause(clause: str) -> str:
    text = clause.replace("\\'", "'").replace("_utf8mb4", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def build_markdown(conn: Any) -> str:
    """Toàn bộ nội dung data_dictionary.md cho schema mà `conn` đang trỏ tới."""

    placeholders = ", ".join(["%s"] * len(TABLES))
    columns = _rows(
        conn,
        f"""
        SELECT TABLE_NAME AS t, COLUMN_NAME AS c, COLUMN_TYPE AS type, IS_NULLABLE AS nullable,
               COLUMN_DEFAULT AS dflt, EXTRA AS extra, COLUMN_KEY AS ckey
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({placeholders})
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """,
        TABLES,
    )
    keys = _rows(
        conn,
        f"""
        SELECT tc.TABLE_NAME AS t, tc.CONSTRAINT_NAME AS name, tc.CONSTRAINT_TYPE AS kind,
               GROUP_CONCAT(k.COLUMN_NAME ORDER BY k.ORDINAL_POSITION) AS cols,
               MAX(k.REFERENCED_TABLE_NAME) AS ref_table,
               GROUP_CONCAT(k.REFERENCED_COLUMN_NAME ORDER BY k.ORDINAL_POSITION) AS ref_cols,
               MAX(r.UPDATE_RULE) AS on_update, MAX(r.DELETE_RULE) AS on_delete
        FROM information_schema.TABLE_CONSTRAINTS AS tc
        LEFT JOIN information_schema.KEY_COLUMN_USAGE AS k
               ON k.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND k.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
              AND k.TABLE_NAME = tc.TABLE_NAME
        LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS AS r
               ON r.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
        WHERE tc.TABLE_SCHEMA = DATABASE() AND tc.TABLE_NAME IN ({placeholders})
        GROUP BY tc.TABLE_NAME, tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE
        ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME
        """,
        TABLES,
    )
    checks = {
        row["name"]: _clean_clause(row["clause"])
        for row in _rows(
            conn,
            """
            SELECT CONSTRAINT_NAME AS name, CHECK_CLAUSE AS clause
            FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE()
            """,
        )
    }
    generated = {
        (row["t"], row["c"]): _clean_clause(row["expr"])
        for row in _rows(
            conn,
            f"""
            SELECT TABLE_NAME AS t, COLUMN_NAME AS c, GENERATION_EXPRESSION AS expr
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({placeholders}) AND GENERATION_EXPRESSION <> ''
            """,
            TABLES,
        )
    }
    indexes = _rows(
        conn,
        f"""
        SELECT TABLE_NAME AS t, INDEX_NAME AS name, MAX(NON_UNIQUE) AS non_unique,
               GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS cols
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({placeholders})
        GROUP BY TABLE_NAME, INDEX_NAME
        ORDER BY TABLE_NAME, INDEX_NAME
        """,
        TABLES,
    )

    by_table: dict[str, list[dict]] = {t: [] for t in TABLES}
    for col in columns:
        by_table[col["t"]].append(col)
    missing = [t for t in TABLES if not by_table[t]]
    if missing:
        raise RuntimeError(f"Schema thiếu bảng: {', '.join(missing)}. Chạy migration trước.")

    fks = [k for k in keys if k["kind"] == "FOREIGN KEY"]
    unique_sets = {(k["t"], k["cols"]) for k in keys if k["kind"] in ("PRIMARY KEY", "UNIQUE")}
    unique_sets |= {(i["t"], i["cols"]) for i in indexes if not i["non_unique"]}
    constraint_names = {k["name"] for k in keys}
    nullable = {(c["t"], c["c"]): c["nullable"] == "YES" for c in columns}

    out: list[str] = []
    w = out.append
    w("# Data dictionary — CyberHub Manager")
    w("")
    w("<!-- File sinh tự động bởi scripts/gen_data_dictionary.py từ schema MySQL. Không sửa tay;")
    w("     sửa DESCRIPTIONS trong script rồi chạy lại. -->")
    w("")
    w("Nguồn: `sql/001_initial_schema.sql` + `sql/002_indexes.sql` (MySQL 8.4, InnoDB, utf8mb4). Quy ước:")
    w("tiền là `BIGINT` đơn vị VND, thời gian là `DATETIME` lưu UTC, mọi khóa ngoại `RESTRICT` (không xóa dây chuyền).")
    w("")
    w("## 1. Danh sách bảng")
    w("")
    w("| Bảng | Mục đích | Số cột |")
    w("|---|---|---:|")
    for t in TABLES:
        w(f"| [`{t}`](#{t}) | {_cell(DESCRIPTIONS[t][0])} | {len(by_table[t])} |")
    w("")
    w("## 2. Quan hệ và cardinality")
    w("")
    w("Đọc từ khóa ngoại: phía cha là `1` khi cột FK `NOT NULL`, `0..1` khi cho phép NULL;")
    w("phía con là `0..1` khi cột FK có UNIQUE, ngược lại `0..n`.")
    w("")
    w("| Cha | | Con | Khóa ngoại | Ý nghĩa |")
    w("|---|:---:|---|---|---|")
    for fk in sorted(fks, key=lambda k: (TABLES.index(k["ref_table"]), TABLES.index(k["t"]), k["name"])):
        col = fk["cols"]
        parent = "0..1" if nullable[(fk["t"], col)] else "1"
        child = "0..1" if (fk["t"], col) in unique_sets else "0..n"
        meaning = DESCRIPTIONS[fk["t"]][1][col]
        w(f"| `{fk['ref_table']}` | {parent} — {child} | `{fk['t']}` | `{fk['t']}.{col}` → `{fk['ref_table']}.{fk['ref_cols']}` | {_cell(meaning)} |")
    w("")
    w("## 3. Chi tiết từng bảng")

    for t in TABLES:
        purpose, meanings = DESCRIPTIONS[t]
        undocumented = [c["c"] for c in by_table[t] if c["c"] not in meanings]
        if undocumented:
            raise RuntimeError(f"Thiếu mô tả cho {t}.{', '.join(undocumented)} trong DESCRIPTIONS")
        table_keys = sorted(
            (k for k in keys if k["t"] == t),
            key=lambda k: (_KIND_ORDER.get(k["kind"], 9), k["name"]),
        )
        fk_by_col = {k["cols"]: k for k in table_keys if k["kind"] == "FOREIGN KEY"}
        uk_cols = {k["cols"] for k in table_keys if k["kind"] == "UNIQUE"}
        uk_cols |= {i["cols"] for i in indexes if i["t"] == t and not i["non_unique"] and i["name"] != "PRIMARY"}

        w("")
        w(f"### {t}")
        w("")
        w(purpose)
        w("")
        w("| Cột | Kiểu | NULL | Mặc định | Khóa | Ý nghĩa |")
        w("|---|---|:---:|---|---|---|")
        for col in by_table[t]:
            name = col["c"]
            tags = []
            if col["ckey"] == "PRI":
                tags.append("PK")
            if name in uk_cols:
                tags.append("UK")
            if name in fk_by_col:
                fk = fk_by_col[name]
                tags.append(f"FK → `{fk['ref_table']}.{fk['ref_cols']}`")
            default = col["dflt"]
            if default is None:
                default_text = "—"
            else:
                default_text = f"`{default}`"
            extra = (col["extra"] or "").replace("DEFAULT_GENERATED", "").strip()
            if "auto_increment" in extra:
                default_text = "AUTO_INCREMENT"
            elif "on update" in extra:
                default_text += ", tự cập nhật khi sửa"
            meaning = meanings[name]
            if (t, name) in generated:
                meaning += f" Biểu thức: `{generated[(t, name)]}` (STORED)."
            w(
                f"| `{name}` | `{col['type']}` | {'Có' if col['nullable'] == 'YES' else 'Không'} | "
                f"{_cell(default_text)} | {', '.join(tags) or '—'} | {_cell(meaning)} |"
            )

        w("")
        w("Ràng buộc:")
        w("")
        for k in table_keys:
            if k["kind"] == "PRIMARY KEY":
                w(f"- PRIMARY KEY (`{k['cols']}`)")
            elif k["kind"] == "UNIQUE":
                w(f"- UNIQUE `{k['name']}` (`{k['cols']}`)")
            elif k["kind"] == "FOREIGN KEY":
                w(
                    f"- FOREIGN KEY `{k['name']}` (`{k['cols']}`) → `{k['ref_table']}` (`{k['ref_cols']}`) "
                    f"ON UPDATE {k['on_update']} ON DELETE {k['on_delete']}"
                )
            elif k["kind"] == "CHECK":
                w(f"- CHECK `{k['name']}`: `{_cell(checks.get(k['name'], '?'))}`")

        extra_indexes = [i for i in indexes if i["t"] == t and i["name"] not in constraint_names and i["name"] != "PRIMARY"]
        if extra_indexes:
            w("")
            w("Index bổ sung (`002_indexes.sql`):")
            w("")
            for i in extra_indexes:
                kind = "UNIQUE INDEX" if not i["non_unique"] else "INDEX"
                w(f"- {kind} `{i['name']}` (`{i['cols'].replace(',', ', ')}`)")
    w("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh docs/diagrams/data_dictionary.md từ schema MySQL")
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi file")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database đã migrate để đọc schema")
    args = parser.parse_args(argv)

    os.environ["MYSQL_DATABASE"] = args.database
    from cyberhub_manager.database.connection import get_connection

    conn = get_connection()
    try:
        content = build_markdown(conn)
    finally:
        conn.close()

    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if args.check:
        if current.replace("\r\n", "\n") != content:
            print(f"{OUTPUT.name} không khớp schema. Chạy: python scripts/gen_data_dictionary.py", file=sys.stderr)
            return 1
        print(f"{OUTPUT.name} khớp schema.")
        return 0
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Đã ghi {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
