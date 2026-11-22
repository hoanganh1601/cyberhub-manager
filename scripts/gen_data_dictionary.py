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
    "employee_profiles",
    "employee_store_assignments",
    "customers",
    "customer_store_links",
    "accounts",
    "machines",
    "usage_sessions",
    "active_usage_sessions",
    "account_transactions",
    "invoices",
    "promotions",
    "management_audit",
    "customer_notification_reads",
    "machine_room_types",
    "loyalty_policy_versions",
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
    # Hoàn/hủy và khuyến mãi POS
    "pos_order_reversals",
    "menu_promotions",
    "menu_promotion_versions",
    "menu_order_pricing",
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
    # Ca/két tiền, bảo trì và mua hàng
    "cash_shifts",
    "active_employee_shifts",
    "cash_shift_entries",
    "machine_incidents",
    "machine_incident_parts",
    "machine_incident_events",
    "suppliers",
    "purchase_requests",
    "purchase_request_lines",
    "purchase_orders",
    "purchase_order_lines",
    "goods_receipts",
    "goods_receipt_lines",
    "supplier_payables",
    # Đợt thương mại — đối tác, game/ads ngoài và đối soát doanh thu
    "commercial_partners",
    "commercial_contracts",
    "commercial_campaigns",
    "commercial_placements",
    "commercial_play_sessions",
    "commercial_events",
    "commercial_reward_grants",
    "commercial_settlements",
    "commercial_settlement_lines",
    "supplier_payable_approvals",
    "customer_email_tokens",
    "customer_mail_outbox",
    "customer_security_audit",
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
        "Thông tin xác thực và phân quyền đăng nhập của nhân viên; thông tin nhân sự thuộc `employee_profiles` (chuẩn 3NF NF-03).",
        {
            "id": "Khóa chính (dùng làm khóa tham chiếu lịch sử cho mọi chứng từ).",
            "profile_id": "Hồ sơ nhân sự duy nhất (`employee_profiles.id`); UNIQUE nên mỗi hồ sơ gắn tối đa một tài khoản đăng nhập.",
            "username": "Tên đăng nhập, duy nhất, 4–30 ký tự.",
            "password_hash": "Mật khẩu đã băm bcrypt; không bao giờ trả ra UI/DTO.",
            "role": "`ADMIN` / `DIRECTOR` / `MANAGER` / `STAFF` / `KITCHEN` / `INVENTORY`; backend cấp quyền tối thiểu theo từng thao tác.",
            "status": "`ACTIVE` / `INACTIVE` / `LOCKED`. Chỉ ACTIVE đăng nhập được.",
            "auth_version": "Phiên bản xác thực; tăng khi đổi/đặt lại mật khẩu để thu hồi phiên cũ.",
            "must_change_password": "TRUE khi tài khoản đang dùng mật khẩu tạm và phải đổi trước khi thao tác.",
            "password_changed_at": "Thời điểm đổi hoặc đặt lại mật khẩu gần nhất (UTC), có thể NULL với dữ liệu cũ.",
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
            "email": "Email đăng ký/kích hoạt tài khoản; NULL với tài khoản cũ chưa xác minh, UNIQUE nếu có.",
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
            "web_login_enabled": "FALSE khi tài khoản đăng ký tại quầy chưa kích hoạt email; TRUE mới cho đăng nhập web.",
            "email_verified_at": "Thời điểm email được xác minh khi kích hoạt (UTC); NULL nếu chưa xác minh.",
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
        "Một lần khách dùng một máy, từ lúc mở đến lúc checkout; ràng buộc chiếm dụng đang hoạt động nằm tại `active_usage_sessions` (chuẩn 3NF).",
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
        },
    ),
    "active_usage_sessions": (
        "Bảng chiếm dụng 3NF ghi nhận các phiên đang ACTIVE; UNIQUE trên `machine_id` và `customer_id` thay cột sinh để chặn mở trùng.",
        {
            "session_id": "Phiên đang ACTIVE; PK/FK tới `usage_sessions.id` (tự đồng bộ qua trigger khi mở/đóng phiên).",
            "machine_id": "Máy đang bị chiếm dụng; UNIQUE ⇒ mỗi máy tối đa một phiên ACTIVE.",
            "customer_id": "Khách đang chơi; UNIQUE ⇒ mỗi khách tối đa một phiên ACTIVE.",
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
        "Hóa đơn tạo khi checkout thành công; khóa ứng viên `session_id` (UNIQUE), tham chiếu phiên bản chính sách điểm bất biến (`loyalty_policy_versions`). Các giá trị dẫn xuất (`total_amount`, `loyalty_eligible_amount`, `loyalty_points`, `loyalty_unit`) tính qua view `v_invoices`.",
        {
            "id": "Khóa chính.",
            "code": "Mã hóa đơn, duy nhất (`INV-` + hex).",
            "session_id": "Phiên được thanh toán; UNIQUE ⇒ mỗi phiên tối đa một hóa đơn.",
            "customer_id": "Khách (khớp `usage_sessions.customer_id` nhờ trigger `trg_invoices_bi/bu`).",
            "employee_id": "Nhân viên checkout.",
            "store_id": "Cửa hàng (khớp `machines.store_id` của phiên nhờ trigger `trg_invoices_bi/bu`).",
            "usage_cost": "Phí sử dụng (VND). Doanh thu ngày = tổng `usage_cost` của hóa đơn PAID.",
            "settlement_amount": "Phần tiền bù thực ghi nhận, bằng đúng `settlement_required` khi checkout; không cộng lần nữa vào doanh thu.",
            "bonus_used": "Phần phí sử dụng trừ từ khuyến mãi, chụp tại checkout.",
            "loyalty_rule_version": "FK tới `loyalty_policy_versions.version` chụp bất biến tại lúc lập hóa đơn.",
            "status": "`PAID` / `VOID`.",
            "created_at": "Thời điểm checkout (UTC); báo cáo quy đổi sang giờ Việt Nam (UTC+7).",
        },
    ),
}


DESCRIPTIONS["accounts"][1]["bonus_balance"] = "Số dư khuyến mãi (VND), dùng trước, không quy đổi tiền mặt. Số dư chính `cash_balance` tính qua view `v_accounts`."
DESCRIPTIONS["accounts"][1]["auth_version"] = "Phiên bản xác thực khách hàng; tăng khi đổi mật khẩu để thu hồi các phiên cũ."
DESCRIPTIONS["employee_profiles"] = (
    "Nguồn sự thật duy nhất về hồ sơ nhân sự (mã, tên, cơ sở chính, trạng thái làm việc); độc lập với thông tin đăng nhập tại `employees` (chuẩn 3NF NF-03).",
    {
        "id": "Khóa chính.",
        "code": "Mã hồ sơ nhân sự, duy nhất.",
        "home_store_id": "Cơ sở công tác chính.",
        "full_name": "Họ tên nhân sự.",
        "employment_status": "`ACTIVE` / `INACTIVE`, tách khỏi trạng thái khóa đăng nhập.",
        "created_at": "Thời điểm tạo (UTC).",
        "updated_at": "Thời điểm sửa gần nhất (UTC).",
    },
)
DESCRIPTIONS["employee_store_assignments"] = (
    "Phân công bổ sung cho MANAGER được vận hành tại nhiều cơ sở; không thay đổi cơ sở chính trong hồ sơ.",
    {
        "employee_id": "Nhân viên được phân công; phần thứ nhất của khóa chính.",
        "store_id": "Cơ sở được phép vận hành; phần thứ hai của khóa chính.",
        "granted_by": "ADMIN đã cấp quyền phân công.", "granted_at": "Thời điểm cấp (UTC).",
    },
)
DESCRIPTIONS["customer_store_links"] = (
    "Phạm vi khách hàng tại từng cơ sở, suy ra từ giao dịch/phiên hoặc liên kết được xác minh tại quầy.",
    {
        "customer_id": "Khách hàng; phần thứ nhất của khóa chính.", "store_id": "Cơ sở liên quan; phần thứ hai của khóa chính.",
        "source": "Nguồn chứng minh liên kết, ví dụ `INVOICE`, `SESSION` hoặc đăng ký tại quầy.",
        "created_at": "Thời điểm lập liên kết (UTC).",
    },
)
DESCRIPTIONS["supplier_payable_approvals"] = (
    "Bản ghi duyệt công nợ nhà cung cấp; dùng kiểm soát phân tách người duyệt và người chi.",
    {
        "payable_id": "Công nợ được duyệt; khóa chính/FK nên mỗi công nợ được duyệt tối đa một lần.",
        "approved_by": "Nhân viên phê duyệt, phải khác người thanh toán theo service trong chính sách tách quyền.",
        "approved_at": "Thời điểm duyệt (UTC).", "note": "Ghi chú duyệt bắt buộc.",
    },
)
DESCRIPTIONS["customer_email_tokens"] = (
    "Token kích hoạt/đặt lại mật khẩu khách; chỉ lưu hash và nonce dẫn xuất, token thô không được lưu.",
    {
        "id": "Khóa chính.", "account_id": "Tài khoản khách nhận token.",
        "purpose": "`ACTIVATE` hoặc `RESET`.", "token_hash": "SHA-256 token thô; UNIQUE, dùng tra cứu/xác thực.",
        "nonce": "Nonce ngẫu nhiên dùng dẫn xuất token cho worker, không phải token thô.",
        "expires_at": "Hạn sử dụng (UTC).", "used_at": "Thời điểm dùng thành công; NULL nếu chưa dùng.",
        "created_at": "Thời điểm phát hành (UTC).",
    },
)
DESCRIPTIONS["customer_mail_outbox"] = (
    "Transactional outbox gửi email khách sau khi transaction đăng ký/reset đã commit.",
    {
        "id": "Khóa chính.", "token_id": "Token cần gửi; UNIQUE để tránh gửi trùng outbox.",
        "status": "`PENDING` / `SENDING` / `SENT` / `FAILED`.", "attempts": "Số lần worker đã thử gửi.",
        "next_attempt_at": "Thời điểm đủ điều kiện thử lại (UTC).", "sent_at": "Thời điểm gửi thành công (UTC).",
        "last_error": "Thông báo lỗi rút gọn của lần gửi gần nhất.",
    },
)
DESCRIPTIONS["customer_security_audit"] = (
    "Audit bất biến cho thao tác kích hoạt, đặt lại mật khẩu và các sự kiện bảo mật khách.",
    {
        "id": "Khóa chính.", "account_id": "Tài khoản khách chịu tác động.",
        "employee_id": "Nhân viên liên quan nếu thao tác tại quầy; NULL với luồng email tự phục vụ.",
        "store_id": "Cơ sở liên quan nếu có; NULL với luồng web tự phục vụ.",
        "action": "Tên sự kiện bảo mật.", "created_at": "Thời điểm ghi audit (UTC).",
    },
)
DESCRIPTIONS["pos_order_reversals"] = ("Yêu cầu hoàn/hủy toàn bộ đơn POS có maker-checker và quyết định hoàn kho hoặc ghi hao hụt; cơ sở suy ra từ `menu_orders` qua `usage_sessions`→`machines` (NF-02).", {
    "id":"Khóa chính.", "order_id":"Đơn POS; UNIQUE nên mỗi đơn có tối đa một yêu cầu hoàn/hủy.",
    "requested_by":"Nhân viên đề nghị.", "reason":"Lý do bắt buộc.", "disposition":"`RESTOCK` hoặc `WASTE`.",
    "status":"`PENDING` / `APPROVED` / `REJECTED`.", "decided_by":"Quản lý quyết định (khác `requested_by`); NULL khi đang chờ.",
    "decided_at":"Thời điểm quyết định (UTC).", "refund_amount":"Số tiền hoàn VND.", "refund_method":"`CASH` / `TRANSFER`.",
    "refund_reference":"Tham chiếu giao dịch hoàn.", "created_at":"Thời điểm tạo (UTC).",
})
DESCRIPTIONS["menu_promotions"] = ("Chính sách khuyến mãi POS hiện hành theo cơ sở; mỗi lần lưu tạo một phiên bản bất biến tại `menu_promotion_versions` (NF-04).", {
    "id":"Khóa chính.", "store_id":"Cơ sở áp dụng.", "code":"Mã duy nhất trong cơ sở.",
    "kind":"`BOGO` / `PLAY_DRINK` / `TIER_PERCENT`.", "item_id":"Món áp dụng (cùng cơ sở nhờ trigger); NULL khi ưu đãi không gắn một món.",
    "value":"Giá trị cấu hình theo loại ưu đãi.", "minimum_tier":"Hạng tối thiểu nếu có.",
    "starts_at":"Bắt đầu hiệu lực (UTC).", "ends_at":"Kết thúc hiệu lực (UTC).", "is_active":"Bật/tắt chính sách.",
})
DESCRIPTIONS["menu_promotion_versions"] = ("Phiên bản bất biến của chính sách khuyến mãi POS để hóa đơn/đơn hàng lịch sử tham chiếu đúng quy tắc đã áp dụng (NF-04).", {
    "id":"Khóa chính.", "promotion_id":"Chính sách khuyến mãi cha.", "version":"Số phiên bản tăng dần (≥ 1); cùng `promotion_id` là UNIQUE.",
    "code":"Mã khuyến mãi chụp tại phiên bản.", "kind":"Loại ưu đãi chụp tại phiên bản.",
    "item_id":"Món áp dụng chụp tại phiên bản; NULL nếu không gắn món.", "value":"Giá trị ưu đãi chụp tại phiên bản.",
    "minimum_tier":"Hạng tối thiểu chụp tại phiên bản.", "starts_at":"Bắt đầu hiệu lực (UTC).",
    "ends_at":"Kết thúc hiệu lực (UTC).", "created_at":"Thời điểm tạo phiên bản (UTC).",
})
DESCRIPTIONS["menu_order_pricing"] = ("Kết quả định giá POS dạng cấu trúc chuẩn 3NF (không còn `snapshot_json` hay cột dẫn xuất `final_amount`, đọc qua `v_menu_order_pricing`).", {
    "order_id":"Đơn POS; khóa chính/FK.", "promotion_version_id":"Phiên bản khuyến mãi bất biến đã chọn; NULL nếu không áp dụng.",
    "applied_source":"Nguồn ưu đãi đang hiệu lực: `NONE` / `PROMOTION` / `VOUCHER`.",
    "member_tier":"Hạng thành viên tại lúc đặt đơn (`BRONZE` / `SILVER` / `GOLD` / `PLATINUM`).",
    "discount_amount":"Số tiền giảm từ khuyến mãi POS (VND).", "voucher_id":"Voucher đồ ăn/đồ uống đã áp nếu có.",
    "voucher_discount_amount":"Số tiền giảm từ voucher (VND).",
})
DESCRIPTIONS["cash_shifts"] = ("Ca làm việc và đối chiếu két tiền của một nhân viên tại một cơ sở; chênh lệch `variance` tính qua `v_cash_shifts`, chiếm dụng ca mở nằm tại `active_employee_shifts`.", {
    "id":"Khóa chính.", "code":"Mã ca duy nhất.", "store_id":"Cơ sở mở ca.", "employee_id":"Nhân viên chịu trách nhiệm ca.",
    "status":"`OPEN` / `PENDING_REVIEW` / `CLOSED`.", "opening_cash":"Tiền mặt đầu ca.", "expected_cash":"Tiền mặt hệ thống tính cuối ca.",
    "counted_cash":"Tiền mặt thực đếm cuối ca.", "opened_at":"Thời điểm mở ca (UTC).",
    "submitted_at":"Thời điểm nhân viên nộp đối chiếu (UTC).", "closed_at":"Thời điểm đóng ca (UTC).", "reviewed_by":"Quản lý duyệt chênh lệch (khác `employee_id`).",
    "review_note":"Ghi chú duyệt.",
})
DESCRIPTIONS["active_employee_shifts"] = ("Bảng chiếm dụng 3NF bảo đảm mỗi nhân viên chỉ có tối đa một ca `OPEN`/`PENDING_REVIEW` cùng lúc (thay cột sinh `active_employee_id`).", {
    "shift_id":"Ca đang mở hoặc chờ duyệt; PK/FK tới `cash_shifts.id` (tự đồng bộ qua trigger).",
    "employee_id":"Nhân viên đang mở ca; UNIQUE ⇒ không thể mở đồng thời hai ca.",
})
DESCRIPTIONS["cash_shift_entries"] = ("Sổ bất biến thu, chi, hoàn và điều chỉnh theo ca; cơ sở suy ra từ `cash_shifts.store_id` (NF-02).", {
    "id":"Khóa chính.", "shift_id":"Ca sở hữu bút toán.", "employee_id":"Nhân viên ghi nhận.",
    "kind":"`RECEIPT` / `EXPENSE` / `REFUND` / `ADJUSTMENT_IN` / `ADJUSTMENT_OUT`.", "payment_method":"`CASH` / `TRANSFER`.",
    "amount":"Số tiền dương (VND).", "source_type":"Loại chứng từ nguồn.", "source_id":"Mã nguồn; kết hợp phương thức thanh toán để chống ghi trùng.",
    "note":"Ghi chú nghiệp vụ.", "created_at":"Thời điểm ghi sổ (UTC).",
})
DESCRIPTIONS["machine_incidents"] = ("Phiếu sự cố và vòng đời bảo trì máy từ báo lỗi đến nghiệm thu; cơ sở suy ra từ `machines.store_id` (NF-02).", {
    "id":"Khóa chính.", "code":"Mã sự cố duy nhất.", "machine_id":"Máy gặp sự cố.",
    "reported_by":"Người báo lỗi.", "assigned_to":"Người được phân công; có thể NULL trước khi phân công.", "severity":"`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`.",
    "status":"`REPORTED` / `ASSIGNED` / `IN_PROGRESS` / `WAITING_PARTS` / `COMPLETED` / `VERIFIED` / `CANCELLED`.",
    "title":"Tiêu đề ngắn.", "description":"Mô tả lỗi.", "resolution":"Kết quả xử lý.", "labor_cost":"Chi phí nhân công.", "parts_cost":"Chi phí linh kiện.",
    "reported_at":"Thời điểm báo (UTC).", "started_at":"Thời điểm bắt đầu sửa (UTC).", "completed_at":"Thời điểm hoàn thành sửa (UTC).",
    "verified_at":"Thời điểm nghiệm thu (UTC).", "verified_by":"Người nghiệm thu (khác `assigned_to`).",
})
DESCRIPTIONS["machine_incident_parts"] = ("Linh kiện sử dụng cho một phiếu sửa máy.", {
    "id":"Khóa chính.", "incident_id":"Phiếu sự cố.", "name":"Tên linh kiện.", "quantity":"Số lượng.", "unit_cost":"Đơn giá VND.",
})
DESCRIPTIONS["machine_incident_events"] = ("Lịch sử chuyển trạng thái sự cố máy, chỉ thêm.", {
    "id":"Khóa chính.", "incident_id":"Phiếu sự cố.", "employee_id":"Người thực hiện.", "from_status":"Trạng thái trước; NULL ở sự kiện đầu.",
    "to_status":"Trạng thái sau.", "note":"Ghi chú chuyển trạng thái.", "created_at":"Thời điểm (UTC).",
})
DESCRIPTIONS["suppliers"] = ("Nhà cung cấp theo cơ sở và điều khoản thanh toán.", {
    "id":"Khóa chính.", "store_id":"Cơ sở quản lý nhà cung cấp.", "code":"Mã duy nhất trong cơ sở.", "name":"Tên nhà cung cấp.",
    "phone":"Số điện thoại.", "email":"Email liên hệ.", "address":"Địa chỉ.", "payment_terms_days":"Số ngày công nợ.",
    "is_active":"FALSE khi ngừng giao dịch mới.", "created_at":"Thời điểm tạo (UTC).",
})
DESCRIPTIONS["purchase_requests"] = ("Đề nghị nhập hàng có người lập và người quyết định (tách nhiệm vụ `decided_by <> requested_by`).", {
    "id":"Khóa chính.", "code":"Mã đề nghị duy nhất.", "store_id":"Cơ sở đề nghị.", "requested_by":"Người lập.",
    "status":"`PENDING` / `APPROVED` / `REJECTED` / `ORDERED`.", "reason":"Lý do nhập.", "decided_by":"Người duyệt/từ chối.",
    "decided_at":"Thời điểm quyết định (UTC).", "created_at":"Thời điểm tạo (UTC).",
})
DESCRIPTIONS["purchase_request_lines"] = ("Nguyên liệu và số lượng trong đề nghị nhập.", {
    "request_id":"Đề nghị; phần thứ nhất khóa chính.", "ingredient_id":"Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính.", "quantity":"Số lượng đề nghị.",
})
DESCRIPTIONS["purchase_orders"] = ("Đơn mua hàng tạo từ đề nghị đã duyệt và gắn nhà cung cấp; cơ sở suy ra từ `purchase_requests.store_id` (NF-02).", {
    "id":"Khóa chính.", "code":"Mã đơn mua duy nhất.", "request_id":"Đề nghị nguồn; UNIQUE.",
    "supplier_id":"Nhà cung cấp (cùng cơ sở với đề nghị nhờ trigger).", "created_by":"Người tạo đơn.", "status":"`OPEN` / `PARTIALLY_RECEIVED` / `RECEIVED` / `CANCELLED`.",
    "ordered_at":"Thời điểm đặt (UTC).", "expected_at":"Thời điểm dự kiến nhận (UTC).", "total_amount":"Tổng giá trị VND.",
})
DESCRIPTIONS["purchase_order_lines"] = ("Dòng đơn mua và tiến độ nhận theo nguyên liệu.", {
    "order_id":"Đơn mua; phần thứ nhất khóa chính.", "ingredient_id":"Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính.", "quantity":"Số lượng đặt.",
    "unit_cost":"Đơn giá nhập.", "received_quantity":"Số lượng đã nhận đạt.", "damaged_quantity":"Số lượng đã nhận hỏng.",
})
DESCRIPTIONS["goods_receipts"] = ("Phiếu nhận hàng idempotent, tạo nhập kho và công nợ theo số lượng đạt; cơ sở suy ra từ `purchase_orders`→`purchase_requests` (NF-02).", {
    "id":"Khóa chính.", "code":"Mã phiếu nhận duy nhất.", "order_id":"Đơn mua.", "received_by":"Người nhận.",
    "request_id":"Khóa idempotency của yêu cầu nhận.", "note":"Ghi chú.", "received_at":"Thời điểm nhận (UTC).", "accepted_amount":"Giá trị hàng đạt được nhận.",
})
DESCRIPTIONS["goods_receipt_lines"] = ("Chi tiết hàng đạt, hỏng và thiếu trong một lần nhận.", {
    "receipt_id":"Phiếu nhận; phần thứ nhất khóa chính.", "ingredient_id":"Nguyên liệu (cùng cơ sở nhờ trigger); phần thứ hai khóa chính.",
    "accepted_quantity":"Số lượng đạt nhập kho.", "damaged_quantity":"Số lượng hỏng.", "missing_quantity":"Số lượng thiếu.", "unit_cost":"Đơn giá chụp khi nhận.",
})
DESCRIPTIONS["supplier_payables"] = ("Công nợ phát sinh từ phiếu nhận hàng và trạng thái thanh toán; cơ sở và nhà cung cấp suy ra từ `goods_receipts`→`purchase_orders`→`purchase_requests` (NF-02).", {
    "id":"Khóa chính.", "receipt_id":"Phiếu nhận nguồn; UNIQUE.",
    "amount":"Tổng phải trả.", "paid_amount":"Số đã trả.", "due_date":"Hạn thanh toán.", "status":"`UNPAID` / `PAID`.",
    "paid_at":"Thời điểm thanh toán (UTC).", "paid_by":"Người thanh toán (khác người duyệt nhờ trigger).", "payment_method":"`CASH` / `TRANSFER`; NULL khi chưa trả.",
})
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
DESCRIPTIONS["loyalty_policy_versions"] = (
    "Phiên bản bất biến của chính sách tích điểm và xét hạng thành viên; hóa đơn lịch sử tham chiếu đúng version đã áp dụng (NF-01/NF-04).",
    {
        "version": "Khóa chính — số phiên bản tăng dần (≥ 1).",
        "enabled": "Bật/tắt tích điểm cho hóa đơn mới thuộc phiên bản này.",
        "unit_amount": "VND hợp lệ / 1 điểm, làm tròn xuống theo từng hóa đơn.",
        "silver_spend": "Mốc chi tiêu hợp lệ hạng Bạc.",
        "gold_spend": "Mốc chi tiêu hợp lệ hạng Vàng.",
        "platinum_spend": "Mốc chi tiêu hợp lệ hạng Kim cương (mã PLATINUM).",
        "created_at": "Thời điểm ban hành phiên bản (UTC).",
    },
)
DESCRIPTIONS["loyalty_settings"] = (
    "Con trỏ singleton (id=1) trỏ tới phiên bản chính sách tích điểm đang hiệu lực; chỉ Admin được cập nhật kèm khóa lạc quan theo version.",
    {
        "id": "Singleton id=1.",
        "current_version": "FK tới `loyalty_policy_versions.version` đang áp dụng.",
        "updated_at": "Thời điểm cập nhật con trỏ gần nhất (UTC).",
    },
)
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
DESCRIPTIONS["menu_items"] = ("Món ăn/đồ uống của cơ sở; cơ sở suy ra từ `menu_categories.store_id` (NF-02), tên món duy nhất toàn cơ sở qua trigger `trg_menu_items_bi/bu`.", {
    "id": "Khóa chính.",
    "category_id": "Nhóm món (xác định cơ sở bán món).",
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
DESCRIPTIONS["menu_orders"] = ("Đơn POS đồ ăn/thức uống của khách đang chơi; cơ sở, máy và tài khoản suy ra từ `usage_sessions` (NF-02), đọc đầy đủ qua `v_menu_orders`.", {
    "id": "Khóa chính.", "code": "Mã yêu cầu, duy nhất (`ORD-` + hex).",
    "session_id": "Phiên ACTIVE lúc đặt (xác định khách, máy và cơ sở phục vụ).",
    "note": "Ghi chú của khách (≤ 200 ký tự).", "total_amount": "Tổng tiền theo giá chụp lúc đặt (VND).",
    "status": "`NEW` / `PREPARING` / `SERVED` / `PAID` / `CANCELLED` / `REFUNDED`.", "handled_by": "Nhân viên tiếp nhận/phục vụ/hủy; NULL khi còn NEW.",
    "payment_method": "`CASH` / `TRANSFER` khi đã thanh toán (bắt buộc NOT NULL); NULL trước đó.",
    "paid_at": "Thời điểm thanh toán tại quầy (UTC).", "paid_by": "Nhân viên xác nhận thanh toán.",
    "cancel_reason": "Lý do hủy đơn; giữ được cả với đơn cũ chưa có ảnh chụp công thức.",
    "reservation_expires_at": "Hạn giữ tồn cho đơn mới (UTC); tác vụ timeout dùng để giải phóng idempotent.",
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
    "Sổ cái kho bất biến: nhập, giữ chỗ, hoàn giữ chỗ, tiêu thụ, hao hụt, trả và điều chỉnh; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02).",
    {
        "id": "Khóa chính.",
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
    "Phiếu kiểm kê đề xuất; cơ sở suy ra từ `inventory_ingredients.store_id` (NF-02), người phê duyệt bắt buộc khác `proposed_by` (CHECK SoD).",
    {
        "id": "Khóa chính.",
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
    "created_at": "Thời điểm quay (UTC); ngày nghiệp vụ UTC+7 được suy ra khi đọc."})
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
    "issued_at": "Thời điểm cấp token (UTC); ngày nghiệp vụ UTC+7 được suy ra khi đọc.",
    "min_complete_at": "Sớm nhất được nhận thưởng = bắt đầu + thời lượng (UTC).",
    "expires_at": "Hạn token (UTC).", "completed_at": "Thời điểm hoàn thành hợp lệ (UTC).",
    "provider_txn_id": "Mã giao dịch của mạng quảng cáo; UNIQUE chống gửi lại.",
    "reject_reason": "`TOO_EARLY` / `EXPIRED` / `CAP` / `LOCKED` / `SUPERSEDED`."})

DESCRIPTIONS["machine_room_types"]=("Phân loại máy theo phòng thường/VIP; máy chưa gán thuộc phòng thường.",{
    "machine_id":"Máy được phân loại; khóa chính và khóa ngoại; CASCADE chỉ xóa ánh xạ khi máy được phép xóa.",
    "room_type":"STANDARD = phòng thường, VIP = phòng VIP; không suy đoán từ giá giờ hoặc tên máy."
})

# ----- Đối tác game và quảng cáo ---------------------------------------------------
DESCRIPTIONS["commercial_partners"] = ("Đối tác cung cấp game hoặc mạng quảng cáo.", {
    "id": "Khóa chính.", "code": "Mã đối tác, duy nhất.", "name": "Tên pháp lý hoặc tên giao dịch.",
    "partner_type": "`GAME` / `AD_NETWORK` / `BOTH`.",
    "status": "`ACTIVE` / `SUSPENDED` / `TERMINATED`.",
    "callback_secret_ref": "Tham chiếu bí mật xác minh callback; không lưu secret thô trong bảng.",
    "contact_name": "Người liên hệ.", "contact_email": "Email liên hệ.",
    "created_at": "Thời điểm tạo (UTC).", "updated_at": "Thời điểm cập nhật (UTC).",
})
DESCRIPTIONS["commercial_contracts"] = ("Hợp đồng thương mại có maker-checker và mô hình tính doanh thu.", {
    "id": "Khóa chính.", "partner_id": "Đối tác ký hợp đồng.", "code": "Mã hợp đồng, duy nhất.",
    "status": "`DRAFT` / `ACTIVE` / `SUSPENDED` / `EXPIRED` / `TERMINATED`.",
    "revenue_model": "`CPM` / `CPC` / `CPA` / `FIXED`.",
    "rate_amount": "Đơn giá nguyên theo VND; CPM tính trên 1.000 impression.",
    "currency": "Tiền tệ; P1 chỉ hỗ trợ `VND`.", "starts_on": "Ngày bắt đầu hiệu lực.",
    "ends_on": "Ngày kết thúc hiệu lực.", "created_by": "Nhân viên lập hợp đồng.",
    "approved_by": "Người duyệt; phải khác người lập theo service.", "approved_at": "Thời điểm duyệt (UTC).",
    "created_at": "Thời điểm tạo (UTC).",
})
DESCRIPTIONS["commercial_campaigns"] = ("Chiến dịch game/quảng cáo thuộc một hợp đồng đã duyệt.", {
    "id": "Khóa chính.", "contract_id": "Hợp đồng chi phối chiến dịch.", "code": "Mã chiến dịch, duy nhất.",
    "name": "Tên chiến dịch.", "kind": "`AD` / `GAME`.",
    "status": "`DRAFT` / `ACTIVE` / `PAUSED` / `ENDED`; `ENDED` là trạng thái cuối.",
    "starts_at": "Thời điểm bắt đầu (UTC).", "ends_at": "Thời điểm kết thúc (UTC).",
    "budget_amount": "Ngân sách giám sát vận hành; không tự ý cắt tiền đối soát.",
    "reward_type": "`NONE` / `COINS` / `VOUCHER` / `EXTRA_SPIN`.",
    "reward_amount": "Số lượng phần thưởng chụp tại chiến dịch.", "created_by": "Nhân viên tạo.",
    "created_at": "Thời điểm tạo (UTC).",
})
DESCRIPTIONS["commercial_placements"] = ("Vị trí phát game/quảng cáo, có thể giới hạn theo cửa hàng.", {
    "id": "Khóa chính.", "campaign_id": "Chiến dịch sở hữu vị trí.",
    "store_id": "Cửa hàng áp dụng; NULL = toàn hệ thống.", "code": "Mã vị trí, duy nhất.",
    "placement_type": "`AD` / `GAME`.", "surface": "`PORTAL_BANNER` / `REWARDED_AD` / `GAME_CENTER`.",
    "embed_url": "URL HTTPS của game ngoài.", "allowed_origin": "Origin HTTPS được phép gửi thông điệp.",
    "sandbox_policy": "Chính sách iframe sandbox đã được allowlist ở backend.",
    "legacy_game_id": "Game nội bộ cũ nếu vị trí ánh xạ vào game có sẵn.",
    "legacy_ad_creative_id": "Nội dung quảng cáo nội bộ cũ nếu có.",
    "status": "`ACTIVE` / `INACTIVE`.", "created_at": "Thời điểm tạo (UTC).",
})
DESCRIPTIONS["commercial_play_sessions"] = ("Phiên chơi ngoài có token một lần và hạn sử dụng.", {
    "id": "Khóa chính.", "placement_id": "Vị trí game được mở.", "account_id": "Tài khoản khách chơi.",
    "token_hash": "SHA-256 của token; không lưu token thô.",
    "status": "`ISSUED` / `COMPLETED` / `EXPIRED` / `REJECTED`.",
    "reward_type": "Loại thưởng chụp tại lúc phát hành.", "reward_amount": "Số lượng thưởng chụp.",
    "issued_at": "Thời điểm phát hành (UTC).", "expires_at": "Hạn token (UTC).",
    "completed_at": "Thời điểm hoàn tất đã xác minh (UTC).",
})
DESCRIPTIONS["commercial_events"] = ("Sổ sự kiện impression/start/complete/click, chống ghi trùng; chiến dịch suy ra từ `commercial_placements.campaign_id` (NF-02).", {
    "id": "Khóa chính.", "placement_id": "Vị trí phát sinh sự kiện.",
    "play_session_id": "Phiên chơi liên quan; có thể NULL.", "account_id": "Tài khoản liên quan; có thể NULL.",
    "event_type": "`IMPRESSION` / `START` / `COMPLETE` / `CLICK`.",
    "event_key": "Khóa idempotency nội bộ, duy nhất.",
    "provider_event_id": "Mã sự kiện phía đối tác, duy nhất nếu có.",
    "verification_method": "`CLIENT` / `SERVER` / `SSV`; COMPLETE không được dùng CLIENT.",
    "accepted": "TRUE nếu hợp lệ để thống kê/đối soát.", "occurred_at": "Thời điểm xảy ra (UTC).",
    "verified_at": "Thời điểm server xác minh (UTC).", "payload_digest": "SHA-256 payload đã xác minh.",
    "created_at": "Thời điểm ghi nhận (UTC).",
})
DESCRIPTIONS["commercial_reward_grants"] = ("Outbox phần thưởng; callback không được cộng xu/phát voucher trực tiếp.", {
    "id": "Khóa chính.", "event_id": "COMPLETE event đã xác minh; duy nhất.",
    "account_id": "Tài khoản nhận thưởng (khớp sự kiện nhờ trigger `trg_commercial_reward_grants_bi`).", "reward_type": "`COINS` / `VOUCHER` / `EXTRA_SPIN`.",
    "reward_amount": "Số lượng thưởng.", "status": "`PENDING` / `APPLIED` / `FAILED`.",
    "attempts": "Số lần worker thử áp dụng.", "created_at": "Thời điểm tạo (UTC).",
    "applied_at": "Thời điểm áp dụng thành công (UTC).", "failure_reason": "Lý do thất bại cuối cùng.",
})
DESCRIPTIONS["commercial_settlements"] = ("Kỳ đối soát doanh thu có maker-checker; `net_amount` tính qua `v_commercial_settlements` (NF-01).", {
    "id": "Khóa chính.", "contract_id": "Hợp đồng được đối soát.",
    "period_start": "Ngày đầu kỳ.", "period_end": "Ngày cuối kỳ.",
    "gross_amount": "Doanh thu gộp tính từ snapshot sự kiện.", "adjustment_amount": "Điều chỉnh có dấu.",
    "adjustment_reason": "Lý do bắt buộc (NOT NULL, ≥ 5 ký tự) khi điều chỉnh khác 0.",
    "status": "`DRAFT` / `APPROVED` / `PAID` / `VOID`.", "generated_by": "Nhân viên tạo kỳ.",
    "reviewed_by": "Người duyệt (khác `generated_by` nhờ CHECK SoD).", "reviewed_at": "Thời điểm duyệt (UTC).",
    "paid_at": "Thời điểm ghi nhận đã thanh toán (UTC).", "created_at": "Thời điểm tạo (UTC).",
})
DESCRIPTIONS["commercial_settlement_lines"] = ("Dòng snapshot đối soát theo vị trí và loại sự kiện; thành tiền `amount` tính qua `v_commercial_settlement_lines` (NF-01).", {
    "settlement_id": "Kỳ đối soát.", "placement_id": "Vị trí được tính tiền.",
    "event_type": "`IMPRESSION` / `CLICK` / `COMPLETE` / `FIXED`.",
    "units": "Số đơn vị hợp lệ.", "unit_rate": "Đơn giá VND chụp từ hợp đồng.",
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
    w("Nguồn: các migration `sql/001_*.sql` đến `sql/031_*.sql` (MySQL 8.4, InnoDB, utf8mb4, chuẩn 3NF nghiêm ngặt). Quy ước:")
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
    # Windows PowerShell may expose a legacy cp1252 stream even though the
    # generated Markdown is UTF-8. Do not turn a successful schema check into
    # a UnicodeEncodeError merely because the status message is Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Sinh docs/diagrams/data_dictionary.md từ schema MySQL")
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi file")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database đã migrate để đọc schema")
    args = parser.parse_args(argv)

    os.environ["MYSQL_DATABASE"] = args.database
    from cyberhub_manager.infrastructure.database.connection import get_connection

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
