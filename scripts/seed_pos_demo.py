"""Tạo dữ liệu mẫu POS + kho trên MySQL (chạy lại an toàn, không ghi đè dữ liệu đã có).

Điều kiện: đã chạy `scripts/init_db.py` (migration 016–021) và `scripts/seed_db.py` (cửa hàng, nhân viên,
khách, máy DEMO). Chạy từ thư mục gốc:

    python scripts/seed_pos_demo.py            # hỏi xác nhận trước khi ghi
    python scripts/seed_pos_demo.py --yes      # không hỏi (mật khẩu lấy từ CYBERHUB_DEMO_PASSWORD)
    python scripts/seed_pos_demo.py --no-orders  # chỉ tạo tài khoản, menu, kho

Script dùng chính các service nghiệp vụ (MenuService, WalletService, SessionService) dưới danh nghĩa nhân
viên demo, nên sổ kho, công thức chụp theo đơn, thông báo và audit nhất quán như thao tác thật.
Từ chối chạy trên database test (`cyberhub_manager_test`).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from getpass import getpass
from uuid import UUID

from dotenv import load_dotenv

STORE_CODE = "DEMO_STORE_01"
FORBIDDEN_DATABASES = frozenset({"cyberhub_manager_test"})
REQUIRED_MIGRATIONS = ("016_pos_roles.sql", "018_pos_reversals.sql", "019_pos_promotions.sql",
                       "021_notification_deliveries.sql")
ORDER_NOTE_PREFIX = "DEMO:"  # đánh dấu đơn mẫu để chạy lại không tạo trùng

# (code, họ tên, username, role) — bổ sung cho 3 tài khoản của scripts/seed_db.py
POS_EMPLOYEES = (
    ("DEMO_EMP_04", "Bếp demo", "demo.kitchen", "KITCHEN"),
    ("DEMO_EMP_05", "Thủ kho demo", "demo.inventory", "INVENTORY"),
)

# (trang, tên nhóm, thứ tự)
CATEGORIES = (
    ("DRINK", "Nước giải khát", 1),
    ("DRINK", "Cà phê", 2),
    ("FOOD", "Món chính", 1),
    ("FOOD", "Ăn vặt", 2),
)

# (tên nguyên liệu, đơn vị, ngưỡng cảnh báo, tồn đầu kỳ). Cố ý có nguyên liệu dưới ngưỡng và hết hàng.
INGREDIENTS = (
    ("Lon Coca", "each", 12, 48),
    ("Chai nước suối", "each", 12, 36),
    ("Cà phê bột", "g", 500, 3000),
    ("Sữa đặc", "ml", 500, 450),  # dưới ngưỡng: cảnh báo sắp hết
    ("Mì gói", "each", 10, 40),
    ("Trứng gà", "each", 12, 30),
    ("Cơm nguội", "g", 2000, 8000),
    ("Xúc xích", "each", 10, 6),  # dưới ngưỡng sau khi bán 1 phần
    ("Khoai tây đông lạnh", "g", 1000, 0),  # hết hàng: món khoai tây chiên không đặt được
)

# (tên món, nhóm, giá, mô tả, công thức {nguyên liệu: định lượng}, thứ tự)
ITEMS = (
    ("Coca", "Nước giải khát", 15_000, "Lon 330ml", {"Lon Coca": 1}, 1),
    ("Nước suối", "Nước giải khát", 8_000, "Chai 500ml", {"Chai nước suối": 1}, 2),
    ("Cà phê sữa", "Cà phê", 25_000, "Cà phê phin sữa đặc", {"Cà phê bột": 20, "Sữa đặc": 30}, 1),
    ("Mì trứng", "Món chính", 30_000, "Mì gói nấu trứng", {"Mì gói": 1, "Trứng gà": 1}, 1),
    ("Cơm chiên trứng", "Món chính", 40_000, "Cơm chiên trứng", {"Cơm nguội": 250, "Trứng gà": 1}, 2),
    ("Xúc xích chiên", "Ăn vặt", 20_000, "2 cây", {"Xúc xích": 2}, 1),
    ("Khoai tây chiên", "Ăn vặt", 25_000, "Phần vừa", {"Khoai tây đông lạnh": 150}, 2),
)

# Mỗi đơn: (username khách, máy, danh sách (món, số lượng), trạng thái cuối, ghi chú)
ORDERS = (
    ("demo.customer01", "DEMO_PC_01", (("Coca", 2), ("Mì trứng", 1)), "NEW", "DEMO: ít đá"),
    ("demo.customer02", "DEMO_PC_02", (("Cà phê sữa", 2),), "PREPARING", "DEMO: giao nhanh"),
    ("demo.customer03", "DEMO_PC_03", (("Cơm chiên trứng", 1), ("Nước suối", 1)), "SERVED", "DEMO: chờ thanh toán"),
    ("demo.customer03", "DEMO_PC_03", (("Xúc xích chiên", 1),), "PAID", "DEMO: đã trả tiền mặt"),
    ("demo.customer04", "DEMO_PC_04", (("Coca", 1),), "CANCELLED", "DEMO: khách đổi ý"),
    ("demo.customer04", "DEMO_PC_04", (("Mì trứng", 1),), "PAID_REVERSAL_PENDING", "DEMO: chờ quản lý duyệt hoàn"),
    ("demo.customer05", "DEMO_PC_05", (("Nước suối", 2),), "REFUNDED", "DEMO: đã hoàn tiền"),
)

MENU_ROLE_NOTE = "Quản lý lo menu; thủ kho lo nguyên liệu, công thức và nhập kho; bếp chỉ chuẩn bị/phục vụ."


def deterministic_request_id(*parts: str) -> str:
    """UUID v4 hợp lệ nhưng cố định theo đầu vào, để chạy lại script không nhập kho lần hai."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()[:16]
    return str(UUID(bytes=digest, version=4))


def validate_catalog() -> None:
    """Kiểm tra tĩnh các bảng dữ liệu mẫu (được test để không lệch nhau)."""
    ingredient_names = {name for name, *_ in INGREDIENTS}
    category_names = {name for _, name, _ in CATEGORIES}
    item_names = set()
    for name, category, price, _, recipe, _ in ITEMS:
        if category not in category_names or name in item_names or not recipe:
            raise ValueError(f"Món mẫu không hợp lệ: {name}")
        if not 1_000 <= price <= 10_000_000 or not set(recipe) <= ingredient_names:
            raise ValueError(f"Giá hoặc công thức không hợp lệ: {name}")
        item_names.add(name)
    for _, _, lines, status, note in ORDERS:
        if not note.startswith(ORDER_NOTE_PREFIX) or not {n for n, _ in lines} <= item_names:
            raise ValueError(f"Đơn mẫu không hợp lệ: {note}")


def check_database(database: str) -> None:
    if database in FORBIDDEN_DATABASES:
        raise SystemExit(f"Từ chối: {database} là database test, không nạp dữ liệu mẫu vào đây.")


class Desk:
    """Nhân viên đang thao tác; các service đọc qua actor_provider như khi đăng nhập thật."""

    def __init__(self):
        self.actor = None

    def provider(self):
        return self.actor

    def as_(self, actor):
        self.actor = actor
        return actor


def _one(conn, sql, params=()):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def ensure_employees(conn, store_id, password) -> None:
    from cyberhub_manager.security import hash_password

    cursor = conn.cursor()
    try:
        for code, full_name, username, role in POS_EMPLOYEES:
            cursor.execute("SELECT store_id, username FROM employees WHERE code = %s", (code,))
            existing = cursor.fetchone()
            if existing is not None:
                if int(existing[0]) != store_id or existing[1] != username:
                    raise RuntimeError(f"Xung đột nhân viên demo: {code}")
                print(f"[SKIP] Employee: {username}")
                continue
            if not password:
                raise SystemExit("Cần mật khẩu demo để tạo tài khoản mới (CYBERHUB_DEMO_PASSWORD hoặc nhập tay).")
            cursor.execute(
                "INSERT INTO employees (code, store_id, full_name, username, password_hash, role, status)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')",
                (code, store_id, full_name, username, hash_password(password), role),
            )
            print(f"[INSERT] Employee: {username} ({role})")
    finally:
        cursor.close()


def run(args) -> int:
    validate_catalog()
    load_dotenv()
    from cyberhub_manager.database.connection import get_connection
    from cyberhub_manager.database.transaction import transaction
    from cyberhub_manager.domain.enums import PaymentMethod
    from cyberhub_manager.repositories.auth_repository import AuthRepository
    from cyberhub_manager.repositories.inventory_repository import InventoryRepository
    from cyberhub_manager.repositories.menu_repository import MenuRepository
    from cyberhub_manager.repositories.p1_repository import P1Repository
    from cyberhub_manager.services.menu_service import MenuService
    from cyberhub_manager.services.session_service import SessionService
    from cyberhub_manager.services.wallet_service import WalletService

    probe = get_connection()
    try:
        database = probe.database
        check_database(database)
        cursor = probe.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}
        cursor.close()
        missing = [m for m in REQUIRED_MIGRATIONS if m not in applied]
        if missing:
            raise SystemExit(f"Thiếu migration {', '.join(missing)}. Chạy: python scripts/init_db.py")
        store = _one(probe, "SELECT id FROM stores WHERE code = %s", (STORE_CODE,))
        if store is None:
            raise SystemExit(f"Chưa có cửa hàng {STORE_CODE}. Chạy: python scripts/seed_db.py trước.")
        store_id = int(store["id"])
    finally:
        probe.close()

    print(f"Database: {database} | cửa hàng: {STORE_CODE}")
    if not args.yes and input("Nạp dữ liệu mẫu POS vào database này? [y/N] ").strip().lower() != "y":
        print("Đã hủy.")
        return 1
    password = os.getenv("CYBERHUB_DEMO_PASSWORD")
    if password is None and not args.yes:
        password = getpass("Mật khẩu demo cho tài khoản mới (nếu chưa có; Enter để bỏ qua): ") or None

    with transaction() as conn:
        ensure_employees(conn, store_id, password)

    desk = Desk()
    auth, menu_repo, inv_repo, p1 = AuthRepository(), MenuRepository(), InventoryRepository(), P1Repository()
    menu = MenuService(actor_provider=desk.provider)
    wallet = WalletService(actor_provider=desk.provider)
    sessions = SessionService(actor_provider=desk.provider)

    def actor(username):
        with transaction() as conn:
            row = _one(conn, "SELECT id FROM employees WHERE username = %s AND store_id = %s", (username, store_id))
            if row is None:
                raise SystemExit(f"Thiếu tài khoản {username}. Chạy scripts/seed_db.py hoặc cung cấp mật khẩu để tạo.")
            return desk.as_(auth.get_active_session_by_id(conn, int(row["id"])))

    manager, staff = actor("demo.manager"), actor("demo.staff01")
    kitchen, stock = actor("demo.kitchen"), actor("demo.inventory")

    # ----- Menu (quản lý) ---------------------------------------------------------------------------------------
    desk.as_(manager)
    with transaction() as conn:
        categories = {c.name: c.id for c in menu_repo.list_categories(conn, store_id)}
        items = {i.name: i.id for i in menu_repo.list_items(conn, store_id)}
    for page, name, order in CATEGORIES:
        if name in categories:
            print(f"[SKIP] Category: {name}")
            continue
        categories[name] = menu.save_category(manager, None, page=page, name=name, sort_order=order,
                                              is_active=True).id
        print(f"[INSERT] Category: {name}")
    for name, category, price, description, _, order in ITEMS:
        if name in items:
            print(f"[SKIP] Item: {name}")
            continue
        items[name] = menu.save_item(manager, None, category_id=categories[category], name=name,
                                     description=description, price=price, sort_order=order,
                                     is_visible=True, is_available=True).id
        print(f"[INSERT] Item: {name}")

    # ----- Nguyên liệu, công thức, tồn đầu kỳ (thủ kho) ---------------------------------------------------------
    desk.as_(stock)
    with transaction() as conn:
        ingredients = {r["name"]: int(r["id"]) for r in inv_repo.list_ingredients(conn, store_id)}
    for name, unit, reorder_point, opening in INGREDIENTS:
        if name not in ingredients:
            ingredients[name] = int(menu.add_ingredient(stock, name=name, unit=unit,
                                                        reorder_point=reorder_point)["id"])
            print(f"[INSERT] Ingredient: {name}")
        else:
            print(f"[SKIP] Ingredient: {name}")
        if opening:
            # request_id cố định theo (cửa hàng, nguyên liệu): chạy lại không nhập kho thêm.
            menu.receive_ingredient(stock, ingredients[name], quantity=opening, reference_code="DEMO-OPENING",
                                    request_id=deterministic_request_id("demo-opening", STORE_CODE, name),
                                    note="Tồn đầu kỳ (dữ liệu mẫu)")
    for name, *_, recipe, _ in ITEMS:
        with transaction() as conn:
            has_recipe = bool(inv_repo.get_recipe(conn, items[name]))
        if has_recipe:
            print(f"[SKIP] Recipe: {name}")
            continue
        menu.set_item_recipe(stock, items[name], track_stock=True, parts=[
            dict(ingredient_id=ingredients[ing], quantity_per_unit=qty) for ing, qty in recipe.items()])
        print(f"[INSERT] Recipe: {name}")

    if args.no_orders:
        print("Đã bỏ qua phiên máy và đơn mẫu (--no-orders).")
        return 0

    # ----- Phiên máy và đơn mẫu ---------------------------------------------------------------------------------
    with transaction() as conn:
        existing = _one(conn, "SELECT COUNT(*) AS n FROM menu_orders WHERE store_id = %s AND note LIKE %s",
                        (store_id, ORDER_NOTE_PREFIX + "%"))
    if int(existing["n"]):
        print(f"[SKIP] Đơn mẫu: đã có {existing['n']} đơn DEMO, không tạo thêm.")
        return 0

    desk.as_(manager)
    principals = {}
    for username, machine_code in sorted({(o[0], o[1]) for o in ORDERS}):
        with transaction() as conn:
            principals[username] = p1.customer_credentials(conn, username=username)[0]
            customer_id = principals[username].customer_id
            machine = _one(conn, "SELECT id FROM machines WHERE code = %s AND store_id = %s", (machine_code, store_id))
            has_session = menu_repo.active_session(conn, customer_id)
        if has_session:
            print(f"[SKIP] Session: {username}")
            continue
        wallet.top_up(customer_id, 100_000, PaymentMethod.CASH, manager.employee_id)
        sessions.open_session(customer_id, int(machine["id"]), manager)
        print(f"[INSERT] Session: {username} @ {machine_code}")

    for username, _, lines, final, note in ORDERS:
        payload = [dict(item_id=items[name], quantity=qty) for name, qty in lines]
        order = menu.place_order(principals[username], payload, note)
        steps = {
            "NEW": [],
            "PREPARING": [(kitchen, "PREPARING")],
            "SERVED": [(kitchen, "PREPARING"), (kitchen, "SERVED")],
            "PAID": [(kitchen, "PREPARING"), (kitchen, "SERVED"), (staff, "PAY")],
            "CANCELLED": [(staff, "CANCELLED")],
            "PAID_REVERSAL_PENDING": [(kitchen, "PREPARING"), (kitchen, "SERVED"), (staff, "PAY"), (staff, "REVERSAL")],
            "REFUNDED": [(kitchen, "PREPARING"), (kitchen, "SERVED"), (staff, "PAY"), (staff, "REVERSAL"),
                         (manager, "REFUND")],
        }[final]
        for who, step in steps:
            desk.as_(who)
            if step == "PAY":
                menu.pay_order(who, order.id, "CASH")
            elif step == "REVERSAL":
                menu.request_reversal(who, order.id, reason="Khách báo món không đúng (dữ liệu mẫu)",
                                      disposition="WASTE")
            elif step == "REFUND":
                menu.decide_reversal(who, order.id, approve=True, refund_confirmed=True, refund_method="CASH")
            elif step == "CANCELLED":
                menu.finish_order(who, order.id, "CANCELLED", reason="Khách đổi ý (dữ liệu mẫu)")
            else:
                menu.finish_order(who, order.id, step)
        print(f"[INSERT] Order {order.code}: {final}")
    print("Hoàn tất. Xem docs/POS_ACCEPTANCE.md để nghiệm thu.")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows cp1252 không in được tiếng Việt
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="Seed POS/inventory demo data into MySQL")
    parser.add_argument("--yes", action="store_true", help="không hỏi xác nhận")
    parser.add_argument("--no-orders", action="store_true", help="chỉ tạo tài khoản, menu, kho")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
