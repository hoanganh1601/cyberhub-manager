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
    "promotions",
    "management_audit",
    "customer_notification_reads",
    "machine_room_types",
    "loyalty_settings",
    "customer_avatars",
    # Đợt 1 — menu đồ ăn/đồ uống
    "menu_categories",
    "menu_items",
    "menu_item_images",
    "menu_item_changes",
    "menu_orders",
    "menu_order_items",
    # Kho, công thức và kiểm kê
    "inventory_ingredients",
    "menu_item_recipes",
    "menu_order_recipe_snapshots",
    "inventory_movements",
    "inventory_counts",
    # Thông báo bền vững theo vòng đời đơn
    "customer_notification_events",
    # Đợt 2 — voucher và phần thưởng
    "reward_catalog",
    "customer_vouchers",
    "voucher_events",
    "loyalty_point_grants",
    # Đợt 3 — game và xu game
    "games",
    "game_prizes",
    "game_wallets",
    "game_sessions",
    "game_coin_ledger",
    # Đợt 4 — quảng cáo nhận thưởng
    "ad_settings",
    "ad_creatives",
    "ad_reward_events",
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
            "role": "`ADMIN` / `MANAGER` / `STAFF` / `KITCHEN` / `INVENTORY`; backend cấp quyền tối thiểu theo từng thao tác.",
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
            "balance": "Số dư sổ cái (VND), có dấu để hỗ trợ dữ liệu nợ. Cảnh báo âm trong phiên dùng số dư dự kiến; checkout P0 phải bù đủ để số dư cuối không âm. Mọi thay đổi phải kèm `account_transactions`.",
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
            "settlement_amount": "Phần tiền bù thực ghi nhận, bằng đúng `settlement_required` khi checkout; không phải tiền khách đưa, không cộng lần nữa vào doanh thu. Schema giới hạn ≤ `usage_cost`; nợ cũ âm phải nạp bù qua ví trước checkout.",
            "total_amount": "Tổng hóa đơn; P0 luôn bằng `usage_cost` (tiền bù không cộng lần hai).",
            "status": "`PAID` / `VOID`.",
            "created_at": "Thời điểm checkout (UTC); báo cáo quy đổi sang giờ Việt Nam (UTC+7).",
        },
    ),
}


DESCRIPTIONS["accounts"][1].update({"bonus_balance":"Số dư khuyến mãi (VND), dùng trước, không quy đổi tiền mặt.","cash_balance":"Cột sinh tự động: tổng balance trừ bonus_balance; số dư chính."})
DESCRIPTIONS["accounts"][1]["auth_version"]="Phiên bản xác thực khách hàng; tăng khi đổi mật khẩu để thu hồi các phiên cũ."
DESCRIPTIONS["invoices"][1].update({
    "loyalty_eligible_amount":"Phí trả bằng tiền chính/tiền bù (không gồm bonus_used), chụp khi lập hóa đơn; chỉ cộng PAID vào xét hạng.",
    "loyalty_points":"Điểm chụp lúc lập hóa đơn; chỉ cộng PAID, VOID có hiệu lực 0 điểm. Không đổi ra tiền.",
    "loyalty_unit":"Số VND hợp lệ cho một điểm tại thời điểm hóa đơn, không đổi khi cập nhật cấu hình.",
    "loyalty_rule_version":"Phiên bản cấu hình tại lúc lập hóa đơn."})
DESCRIPTIONS["invoices"][1]["bonus_used"] = "Phần phí sử dụng trừ từ khuyến mãi, chụp tại checkout."
DESCRIPTIONS["account_transactions"][1].update({"store_id":"Cơ sở ghi nhận giao dịch tại thời điểm phát sinh.","promotion_id":"Chính sách thưởng đã áp dụng, NULL với giao dịch thường."})
DESCRIPTIONS["promotions"] = ("Chính sách thưởng theo mốc nạp, phạm vi và thời gian.",{
    "id":"Khóa chính.","code":"Mã chính sách duy nhất.","name":"Tên chính sách.","store_id":"Cơ sở áp dụng; NULL = toàn hệ thống.",
    "minimum_amount":"Mốc tiền nạp tối thiểu (VND).","bonus_percent":"Phần trăm thưởng, số nguyên 0–100.",
    "starts_at":"Bắt đầu hiệu lực (UTC, bao gồm).","ends_at":"Kết thúc hiệu lực (UTC, không bao gồm).",
    "is_active":"Bật/tắt chính sách.","created_at":"Thời điểm tạo (UTC)."})
DESCRIPTIONS["management_audit"] = ("Lịch sử thay đổi quản trị, không lưu mật khẩu.",{
    "id":"Khóa chính.","employee_id":"Nhân viên thực hiện.","store_id":"Cơ sở đang vận hành.",
    "action":"Loại thay đổi quản trị.","entity_id":"ID đối tượng được thay đổi.","created_at":"Thời điểm thay đổi (UTC)."})

DESCRIPTIONS["customer_notification_reads"] = (
    "Trạng thái đã đọc thông báo riêng của từng tài khoản khách; không thay đổi sổ tiền.",
    {
        "account_id": "Tài khoản sở hữu trạng thái đọc; phần thứ nhất của khóa chính.",
        "notification_key": "Khóa sự kiện ổn định, phân biệt hoa/thường; phần thứ hai của khóa chính.",
        "read_at": "Thời điểm đánh dấu đã đọc (UTC).",
    },
)
DESCRIPTIONS["promotions"][1].update({
    "minimum_tier":"Hạng tối thiểu (BRONZE/SILVER/GOLD/PLATINUM); mặc định BRONZE.",
    "minimum_points":"Điểm được tính tối thiểu để đủ đối tượng ưu đãi; không tiêu điểm.",
    "target_customer_id":"Khách nhận riêng; NULL áp dụng cho mọi khách đủ các điều kiện còn lại."})
DESCRIPTIONS["loyalty_settings"]=("Cấu hình toàn hệ thống, một dòng id=1; chỉ Admin được sửa, có version chống ghi đè.",{
    "id":"Singleton id=1.","enabled":"Bật/tắt tích điểm cho hóa đơn mới, không xóa điểm cũ hoặc ngừng xét chi tiêu hạng.",
    "unit_amount":"VND hợp lệ / 1 điểm, làm tròn xuống theo từng hóa đơn.","silver_spend":"Mốc chi tiêu hợp lệ hạng Bạc.",
    "gold_spend":"Mốc chi tiêu hợp lệ hạng Vàng.","platinum_spend":"Mốc chi tiêu hợp lệ hạng Kim cương (mã PLATINUM).",
    "version":"Tăng sau mỗi lần cập nhật, được chụp vào hóa đơn mới.","updated_at":"Thời điểm cập nhật UTC."})
DESCRIPTIONS["customer_avatars"]=("Ảnh đại diện riêng theo tài khoản; WebP 512×512 đã chuẩn hóa, không giữ tên file hay metadata gốc.",{
    "account_id":"Tài khoản sở hữu ảnh; PK/FK, CASCADE chỉ dọn ảnh khi tài khoản được phép xóa.",
    "image_data":"Nội dung WebP tối đa 300.000 byte sau chuẩn hóa.","digest":"SHA-256 của nội dung ảnh chuẩn hóa.",
    "updated_at":"Thời điểm cập nhật UTC."})

# ----- Đợt 1: menu đồ ăn/đồ uống ----------------------------------------------------
DESCRIPTIONS["menu_categories"] = ("Nhóm món theo cơ sở, xếp vào trang Đồ ăn (FOOD) hoặc Đồ uống (DRINK).", {
    "id": "Khóa chính.", "store_id": "Cơ sở sở hữu nhóm món.",
    "page": "`FOOD` (trang 1) / `DRINK` (trang 2) của menu sách lật.",
    "name": "Tên nhóm, duy nhất trong một cơ sở.", "sort_order": "Thứ tự hiển thị 0–9999, nhỏ đứng trước.",
    "is_active": "FALSE thì toàn bộ món trong nhóm bị ẩn với khách.", "created_at": "Thời điểm tạo (UTC)."})
DESCRIPTIONS["menu_items"] = ("Món ăn/đồ uống của cơ sở; không xóa cứng, chỉ ẩn để giữ lịch sử gọi món.", {
    "id": "Khóa chính.", "store_id": "Cơ sở bán món; menu khác nhau giữa các cơ sở.",
    "category_id": "Nhóm món; service bảo đảm cùng cơ sở với món.",
    "name": "Tên món, duy nhất trong một cơ sở.", "description": "Mô tả ngắn hiển thị cho khách.",
    "price": "Giá bán (VND, 1.000–10.000.000); backend đọc lại khi khách đặt.",
    "sort_order": "Thứ tự trong nhóm.", "is_visible": "FALSE = ẩn khỏi menu khách.",
    "is_available": "FALSE = hết món; khách không chọn/đặt được.",
    "is_stock_tracked": "TRUE = món dùng công thức kho và phải giữ chỗ nguyên liệu theo vòng đời đơn.",
    "created_at": "Thời điểm tạo (UTC).", "updated_at": "Thời điểm sửa gần nhất (UTC)."})
DESCRIPTIONS["menu_item_images"] = ("Ảnh món đã chuẩn hóa (WebP 512×512, không metadata).", {
    "item_id": "Món sở hữu ảnh; PK/FK.", "image_data": "Nội dung WebP sau chuẩn hóa.",
    "digest": "SHA-256 nội dung ảnh; 12 ký tự đầu dùng làm phiên bản cache.", "updated_at": "Thời điểm cập nhật (UTC)."})
DESCRIPTIONS["menu_item_changes"] = ("Lịch sử thay đổi giá, tên, nhóm, ảnh và trạng thái bán; chỉ thêm, không sửa.", {
    "id": "Khóa chính.", "item_id": "Món bị thay đổi.", "employee_id": "Nhân viên thực hiện.",
    "field": "`CREATE` / `NAME` / `CATEGORY` / `PRICE` / `AVAILABLE` / `VISIBLE` / `IMAGE`.",
    "old_value": "Giá trị cũ (dạng chữ), NULL khi tạo mới.", "new_value": "Giá trị mới (dạng chữ).",
    "created_at": "Thời điểm thay đổi (UTC)."})
DESCRIPTIONS["menu_orders"] = ("Đơn POS đồ ăn/thức uống của khách đang chơi; thanh toán tại quầy, không trừ ví giờ chơi.", {
    "id": "Khóa chính.", "code": "Mã yêu cầu, duy nhất (`ORD-` + hex).",
    "store_id": "Cơ sở của máy đang dùng.", "account_id": "Tài khoản khách đặt món.",
    "session_id": "Phiên ACTIVE lúc đặt.", "machine_id": "Máy giao món tới.",
    "note": "Ghi chú của khách (≤ 200 ký tự).", "total_amount": "Tổng tiền theo giá chụp lúc đặt (VND).",
    "status": "`NEW` / `PREPARING` / `SERVED` / `PAID` / `CANCELLED`.", "handled_by": "Nhân viên tiếp nhận/phục vụ/hủy; NULL khi còn NEW.",
    "payment_method": "`CASH` / `TRANSFER` khi đã thanh toán; NULL trước đó.",
    "paid_at": "Thời điểm thanh toán tại quầy (UTC).", "paid_by": "Nhân viên xác nhận thanh toán.",
    "cancel_reason": "Lý do hủy đơn; giữ được cả với đơn cũ chưa có ảnh chụp công thức.",
    "created_at": "Thời điểm đặt (UTC).", "updated_at": "Thời điểm cập nhật trạng thái (UTC)."})
DESCRIPTIONS["menu_order_items"] = ("Từng món trong yêu cầu gọi món, với tên và giá chụp lúc đặt.", {
    "order_id": "Yêu cầu gọi món.", "item_id": "Món được gọi.",
    "item_name": "Tên món tại thời điểm đặt.", "unit_price": "Đơn giá tại thời điểm đặt (VND).",
    "quantity": "Số lượng 1–20."})

# ----- Kho, công thức, kiểm kê và thông báo đơn -----------------------------------
DESCRIPTIONS["inventory_ingredients"] = (
    "Nguyên liệu tồn kho theo từng cửa hàng; lượng khả dụng bằng tồn thực tế trừ lượng đã giữ chỗ.",
    {
        "id": "Khóa chính.",
        "store_id": "Cửa hàng sở hữu nguyên liệu; cùng `id` tạo khóa tham chiếu ghép cho sổ kho.",
        "code": "Mã nguyên liệu duy nhất trong cửa hàng.",
        "name": "Tên nguyên liệu.",
        "unit": "Đơn vị nguyên tử: `g`, `ml` hoặc `each` (cái).",
        "on_hand": "Lượng thực tế đang có, không âm.",
        "reserved": "Lượng đã giữ cho đơn chưa tiêu thụ/hủy; không vượt `on_hand`.",
        "reorder_point": "Ngưỡng cảnh báo sắp hết.",
        "is_active": "FALSE = ngừng nhập/dùng mới nhưng vẫn giữ lịch sử kho.",
    },
)
DESCRIPTIONS["menu_item_recipes"] = (
    "Công thức hiện hành của món có theo dõi kho.",
    {
        "item_id": "Món dùng nguyên liệu; phần thứ nhất của khóa chính.",
        "ingredient_id": "Nguyên liệu; phần thứ hai của khóa chính.",
        "quantity_per_unit": "Lượng nguyên liệu cần cho một đơn vị món, phải lớn hơn 0.",
    },
)
DESCRIPTIONS["menu_order_recipe_snapshots"] = (
    "Ảnh chụp nhu cầu nguyên liệu của từng dòng đơn, giúp đổi công thức sau này không làm sai giữ/xuất kho cũ.",
    {
        "order_id": "Đơn chứa dòng món; thuộc khóa chính và FK ghép tới `menu_order_items`.",
        "item_id": "Món trong đơn; thuộc khóa chính và FK ghép tới `menu_order_items`.",
        "ingredient_id": "Nguyên liệu đã được chụp cho dòng món.",
        "quantity": "Tổng lượng nguyên liệu cần cho số lượng món đã đặt, phải lớn hơn 0.",
    },
)
DESCRIPTIONS["inventory_movements"] = (
    "Sổ cái kho bất biến: nhập, giữ chỗ, hoàn giữ chỗ, tiêu thụ, hao hụt, trả và điều chỉnh.",
    {
        "id": "Khóa chính.",
        "store_id": "Cửa hàng phát sinh; cùng `ingredient_id` bảo đảm nguyên liệu đúng cửa hàng.",
        "ingredient_id": "Nguyên liệu bị thay đổi.",
        "order_id": "Đơn POS liên quan; NULL với nhập/kiểm kê độc lập.",
        "employee_id": "Nhân viên thực hiện hoặc phê duyệt; NULL với tác vụ hệ thống.",
        "account_id": "Tài khoản khách liên quan; NULL nếu không gắn khách.",
        "kind": "`RECEIVE` / `RESERVE` / `RELEASE` / `CONSUME` / `WASTE` / `RETURN` / `ADJUST` / `ISSUE`.",
        "quantity": "Độ lớn biến động theo đơn vị nguyên liệu, luôn dương.",
        "on_hand_delta": "Biến động có dấu áp vào tồn thực tế.",
        "reserved_delta": "Biến động có dấu áp vào lượng giữ chỗ.",
        "idempotency_key": "Khóa duy nhất chống ghi trùng khi retry.",
        "reference_code": "Mã chứng từ/nguồn nghiệp vụ để đối soát.",
        "note": "Ghi chú nghiệp vụ, không chứa bí mật.",
        "created_at": "Thời điểm ghi sổ (UTC).",
    },
)
DESCRIPTIONS["inventory_counts"] = (
    "Phiếu kiểm kê đề xuất; người khác có thẩm quyền phải phê duyệt trước khi tạo điều chỉnh kho.",
    {
        "id": "Khóa chính.",
        "store_id": "Cửa hàng kiểm kê; cùng `ingredient_id` khóa đúng nguyên liệu.",
        "ingredient_id": "Nguyên liệu được kiểm kê.",
        "request_id": "Khóa yêu cầu duy nhất để chống tạo phiếu trùng.",
        "expected_on_hand": "Tồn thực tế hệ thống tại lúc đề xuất.",
        "expected_reserved": "Lượng giữ chỗ hệ thống tại lúc đề xuất.",
        "expected_movement_id": "Mốc sổ kho gần nhất dùng phát hiện dữ liệu đã thay đổi trước khi duyệt.",
        "counted_on_hand": "Lượng thực đếm do người đề xuất nhập.",
        "proposed_by": "Nhân viên đề xuất kiểm kê.",
        "decided_by": "Nhân viên khác phê duyệt/từ chối; NULL khi đang chờ.",
        "status": "`PENDING` / `APPROVED` / `REJECTED`.",
        "reason": "Lý do kiểm kê hoặc giải trình chênh lệch.",
        "created_at": "Thời điểm đề xuất (UTC).",
        "decided_at": "Thời điểm quyết định (UTC); NULL khi PENDING.",
    },
)
DESCRIPTIONS["customer_notification_events"] = (
    "Sổ sự kiện thông báo bền vững cho khách theo vòng đời đơn; khóa sự kiện chống phát trùng.",
    {
        "id": "Khóa chính.",
        "notification_key": "Khóa idempotency duy nhất, phân biệt hoa/thường.",
        "account_id": "Tài khoản khách nhận thông báo.",
        "store_id": "Cửa hàng phát sinh thông báo.",
        "kind": "Loại sự kiện vòng đời đơn, ví dụ tiếp nhận, chuẩn bị, phục vụ, thanh toán hoặc hết món.",
        "code": "Mã đối tượng hiển thị cho khách, thường là mã đơn.",
        "amount": "Số tiền liên quan để hiển thị; 0 nếu sự kiện không có tiền.",
        "created_at": "Thời điểm tạo sự kiện (UTC).",
    },
)

# ----- Đợt 2: voucher và phần thưởng ---------------------------------------------
DESCRIPTIONS["reward_catalog"] = ("Danh mục phần thưởng; không có loại nào quy đổi tiền mặt.", {
    "id": "Khóa chính.", "code": "Mã phần thưởng, duy nhất.", "name": "Tên hiển thị.",
    "store_id": "Cơ sở áp dụng; NULL = mọi cơ sở (chỉ ADMIN tạo).",
    "reward_type": "`FOOD_DISCOUNT` / `FREE_DRINK` / `PLAYTIME_CREDIT` (số dư khuyến mãi) / `MEMBER_POINTS`.",
    "value": "VND giảm/tặng/cộng giờ, hoặc số điểm với MEMBER_POINTS.",
    "min_order_amount": "Đơn gọi món tối thiểu (chỉ voucher đồ ăn/đồ uống).",
    "valid_days": "Số ngày hiệu lực kể từ lúc phát.", "coin_cost": "Giá đổi bằng xu game (Đợt 3); NULL = không bán.",
    "is_active": "FALSE = tạm ngưng phát.", "created_at": "Thời điểm tạo (UTC)."})
DESCRIPTIONS["customer_vouchers"] = ("Voucher của khách; điều kiện được chụp lúc phát, dùng một lần.", {
    "id": "Khóa chính.", "code": "Mã ngẫu nhiên (secrets) khách đưa cho nhân viên, duy nhất.",
    "catalog_id": "Phần thưởng gốc.", "account_id": "Tài khoản sở hữu voucher.",
    "store_id": "Cơ sở áp dụng (chụp từ danh mục); NULL = mọi cơ sở.",
    "reward_type": "Loại phần thưởng (chụp).", "value": "Giá trị (chụp).",
    "min_order_amount": "Đơn tối thiểu (chụp).",
    "status": "`ISSUED` / `USED` / `REVOKED`; hết hạn suy ra từ `expires_at`.",
    "source": "`MANUAL` / `GAME` / `AD`.", "source_ref": "Mã nguồn; UNIQUE cùng `source` chống phát trùng.",
    "issued_by": "Nhân viên phát (NULL khi do hệ thống).", "issued_at": "Thời điểm phát (UTC).",
    "expires_at": "Hết hạn (UTC).", "used_at": "Thời điểm dùng (UTC).", "used_by": "Nhân viên xác nhận.",
    "used_store_id": "Cơ sở nơi dùng.", "used_order_id": "Yêu cầu gọi món được áp (voucher đồ ăn); UNIQUE.",
    "revoked_reason": "Lý do khóa."})
DESCRIPTIONS["voucher_events"] = ("Nhật ký phát hành, sử dụng, khóa và cả lần bị từ chối; chỉ thêm.", {
    "id": "Khóa chính.", "voucher_id": "Voucher liên quan; NULL khi mã nhập không tồn tại.",
    "action": "`ISSUE` / `REDEEM` / `REVOKE` / `REJECT`.", "employee_id": "Nhân viên thực hiện.",
    "store_id": "Cơ sở phát sinh.", "reason": "Lý do/chi tiết (vd. EXPIRED, USED, WRONG_OWNER).",
    "created_at": "Thời điểm (UTC)."})
DESCRIPTIONS["loyalty_point_grants"] = ("Điểm thành viên tặng qua voucher; cộng vào điểm, không đổi hạng.", {
    "id": "Khóa chính.", "customer_id": "Khách nhận điểm.", "voucher_id": "Voucher MEMBER_POINTS; UNIQUE.",
    "points": "Số điểm tặng.", "employee_id": "Nhân viên xác nhận.", "created_at": "Thời điểm (UTC)."})

# ----- Đợt 3: game và xu game ----------------------------------------------------
DESCRIPTIONS["games"] = ("Cấu hình trò chơi (giai đoạn đầu: vòng quay may mắn), dùng chung mọi cơ sở.", {
    "id": "Khóa chính.", "code": "Mã game, duy nhất (`LUCKY_WHEEL`).", "name": "Tên hiển thị.",
    "is_active": "FALSE = tạm dừng, không quay được.", "daily_limit": "Số lượt mỗi tài khoản mỗi ngày (giờ Việt Nam).",
    "min_interval_seconds": "Khoảng cách tối thiểu giữa hai lượt; nhanh hơn bị tính là bất thường.",
    "updated_at": "Thời điểm sửa gần nhất (UTC)."})
DESCRIPTIONS["game_prizes"] = ("Các ô thưởng trên vòng quay và tỉ lệ trúng tương đối.", {
    "id": "Khóa chính.", "game_id": "Game sở hữu ô thưởng.", "sort_order": "Vị trí ô trên vòng quay (0, 1, ...).",
    "label": "Nhãn hiển thị.", "coins": "Số xu nhận được (0 = chúc may mắn).",
    "weight": "Trọng số; xác suất = weight / tổng weight."})
DESCRIPTIONS["game_wallets"] = ("Ví xu game của tài khoản; xu không phải tiền và không phải điểm thành viên.", {
    "account_id": "Tài khoản khách; PK/FK.", "balance": "Số xu hiện có (≥ 0).",
    "is_locked": "TRUE = tạm khóa quay/đổi thưởng.", "locked_reason": "Lý do khóa (tự động hoặc quản lý).",
    "locked_at": "Thời điểm khóa (UTC).", "suspicious_count": "Số lần bị chặn (hết lượt/quá nhanh) trong ngày.",
    "suspicious_on": "Ngày (giờ Việt Nam) của bộ đếm bất thường.", "updated_at": "Thời điểm cập nhật (UTC)."})
DESCRIPTIONS["game_sessions"] = ("Lịch sử từng lượt quay; kết quả do máy chủ bốc thăm và được chụp lại.", {
    "id": "Khóa chính.", "account_id": "Tài khoản chơi.", "game_id": "Game.",
    "prize_index": "Ô trúng (chụp).", "prize_label": "Nhãn ô trúng (chụp).", "coins": "Xu nhận được (chụp).",
    "played_on": "Ngày chơi theo giờ Việt Nam, dùng đếm lượt.", "created_at": "Thời điểm quay (UTC)."})
DESCRIPTIONS["game_coin_ledger"] = ("Sổ cái xu: mọi thay đổi số dư xu có đúng một dòng; chỉ thêm.", {
    "id": "Khóa chính.", "account_id": "Tài khoản.", "delta": "Số xu cộng (+) hoặc trừ (−), khác 0.",
    "reason": "`PLAY` / `REDEEM` / `AD` / `ADJUST`.",
    "ref": "Tham chiếu duy nhất theo `reason` (vd. `session:12`, khóa yêu cầu đổi thưởng).",
    "balance_after": "Số dư xu sau thay đổi (≥ 0).", "voucher_id": "Voucher nhận được khi đổi xu.",
    "created_at": "Thời điểm (UTC)."})

# ----- Đợt 4: quảng cáo nhận thưởng -------------------------------------------------
DESCRIPTIONS["ad_settings"] = ("Cấu hình chương trình quảng cáo nhận thưởng (một dòng duy nhất).", {
    "id": "Luôn bằng 1.", "enabled": "Bật/tắt chương trình.",
    "mode": "`HOUSE` (quảng cáo nội bộ, máy chủ đo thời lượng) / `NETWORK` (callback có chữ ký HMAC).",
    "daily_cap": "Số lần nhận thưởng tối đa mỗi tài khoản mỗi ngày.",
    "reward_type": "`EXTRA_SPIN` (thêm lượt quay) / `COINS` (xu game).",
    "reward_amount": "Số lượt (1–3) hoặc số xu (1–100) mỗi lần.", "updated_at": "Thời điểm cập nhật (UTC)."})
DESCRIPTIONS["ad_creatives"] = ("Nội dung quảng cáo nội bộ do CyberHub tự soạn.", {
    "id": "Khóa chính.", "code": "Mã nội dung, duy nhất.", "title": "Tiêu đề.", "body": "Nội dung hiển thị.",
    "cta": "Lời kêu gọi hành động.", "duration_seconds": "Thời lượng phải xem (5–60 giây).",
    "is_active": "FALSE = không phát.", "created_at": "Thời điểm tạo (UTC)."})
DESCRIPTIONS["ad_reward_events"] = ("Mỗi lần bắt đầu xem quảng cáo; token dùng một lần, độc lập với kết quả game.", {
    "id": "Khóa chính.", "token": "Token ngẫu nhiên do máy chủ cấp; UNIQUE, chỉ dùng một lần.",
    "account_id": "Tài khoản xem.", "creative_id": "Nội dung đã phát.", "provider": "`HOUSE` / `NETWORK`.",
    "reward_type": "Loại thưởng (chụp từ cấu hình).", "reward_amount": "Số lượng thưởng (chụp).",
    "status": "`ISSUED` / `COMPLETED` / `REJECTED`; hết hạn suy ra từ `expires_at`.",
    "played_on": "Ngày theo giờ Việt Nam, dùng giới hạn mỗi ngày.", "issued_at": "Thời điểm cấp token (UTC).",
    "min_complete_at": "Sớm nhất được nhận thưởng = bắt đầu + thời lượng (UTC).",
    "expires_at": "Hạn token (UTC).", "completed_at": "Thời điểm hoàn thành hợp lệ (UTC).",
    "provider_txn_id": "Mã giao dịch của mạng quảng cáo; UNIQUE chống gửi lại.",
    "reject_reason": "`TOO_EARLY` / `EXPIRED` / `CAP` / `LOCKED` / `SUPERSEDED`."})

DESCRIPTIONS["machine_room_types"]=("Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường.",{
    "machine_id":"Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa.",
    "room_type":"STANDARD = phòng thường, VIP = phòng VIP; không suy đoán từ giá giờ hoặc tên máy."
})

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
    w("Nguồn: các migration `sql/001_*.sql` đến `sql/015_*.sql` (MySQL 8.4, InnoDB, utf8mb4). Quy ước:")
    w("tiền là `BIGINT` đơn vị VND, thời gian là `DATETIME` lưu UTC. Lịch sử nghiệp vụ dùng `RESTRICT`; chỉ ánh xạ phân phòng và ảnh đại diện dùng `CASCADE` khi entity cha được phép xóa.")
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
    w("Đọc từ khóa ngoại: phía cha là `1` khi mọi cột FK `NOT NULL`, `0..1` khi có cột cho phép NULL;")
    w("phía con là `0..1` khi bộ cột FK có UNIQUE, ngược lại `0..n`.")
    w("")
    w("| Cha | | Con | Khóa ngoại | Ý nghĩa |")
    w("|---|:---:|---|---|---|")
    for fk in sorted(fks, key=lambda k: (TABLES.index(k["ref_table"]), TABLES.index(k["t"]), k["name"])):
        col = fk["cols"]
        fk_columns = col.split(",")
        parent = "0..1" if any(nullable[(fk["t"], item)] for item in fk_columns) else "1"
        child = "0..1" if (fk["t"], col) in unique_sets else "0..n"
        meaning = "; ".join(DESCRIPTIONS[fk["t"]][1][item] for item in fk_columns)
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
