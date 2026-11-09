"""Đợt 2 — Truy cập dữ liệu phần thưởng/voucher (MySQL). Không tự commit."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from cyberhub_manager.domain.voucher import (
    RewardCatalogItem,
    RewardType,
    Voucher,
    VoucherAction,
    VoucherEvent,
    VoucherSource,
    VoucherStatus,
)
from cyberhub_manager.repositories.p1_repository import execute, rows

_CATALOG_COLUMNS = "id, code, name, store_id, reward_type, value, min_order_amount, valid_days, coin_cost, is_active"

_VOUCHER_SELECT = """
    SELECT v.id, v.code, v.catalog_id, r.name AS catalog_name, v.account_id, a.customer_id,
           c.full_name AS customer_name, v.store_id, v.reward_type, v.value, v.min_order_amount,
           v.status, v.source, v.issued_at, v.expires_at, v.used_at, v.used_store_id, v.used_order_id,
           v.revoked_reason
    FROM customer_vouchers AS v
    JOIN reward_catalog AS r ON r.id = v.catalog_id
    JOIN accounts AS a ON a.id = v.account_id
    JOIN customers AS c ON c.id = a.customer_id
"""


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _catalog(row: dict) -> RewardCatalogItem:
    return RewardCatalogItem(
        id=int(row["id"]),
        code=row["code"],
        name=row["name"],
        store_id=None if row["store_id"] is None else int(row["store_id"]),
        reward_type=RewardType(row["reward_type"]),
        value=int(row["value"]),
        min_order_amount=int(row["min_order_amount"]),
        valid_days=int(row["valid_days"]),
        coin_cost=None if row["coin_cost"] is None else int(row["coin_cost"]),
        is_active=bool(row["is_active"]),
    )


def _voucher(row: dict) -> Voucher:
    return Voucher(
        id=int(row["id"]),
        code=row["code"],
        catalog_id=int(row["catalog_id"]),
        catalog_name=row["catalog_name"],
        account_id=int(row["account_id"]),
        customer_id=int(row["customer_id"]),
        customer_name=row["customer_name"],
        store_id=None if row["store_id"] is None else int(row["store_id"]),
        reward_type=RewardType(row["reward_type"]),
        value=int(row["value"]),
        min_order_amount=int(row["min_order_amount"]),
        status=VoucherStatus(row["status"]),
        source=VoucherSource(row["source"]),
        issued_at=_utc(row["issued_at"]),
        expires_at=_utc(row["expires_at"]),
        used_at=_utc(row["used_at"]),
        used_store_id=None if row["used_store_id"] is None else int(row["used_store_id"]),
        used_order_id=None if row["used_order_id"] is None else int(row["used_order_id"]),
        revoked_reason=row["revoked_reason"],
    )


class VoucherRepository:
    # ----- Danh mục phần thưởng --------------------------------------------------
    def list_catalog(self, conn: Any, store_id: int) -> list[RewardCatalogItem]:
        return [
            _catalog(r)
            for r in rows(
                conn,
                f"SELECT {_CATALOG_COLUMNS} FROM reward_catalog WHERE store_id IS NULL OR store_id = %s"
                " ORDER BY is_active DESC, reward_type, value, id",
                (store_id,),
            )
        ]

    def get_catalog(self, conn: Any, catalog_id: int, *, lock: bool = False) -> RewardCatalogItem | None:
        result = rows(
            conn,
            f"SELECT {_CATALOG_COLUMNS} FROM reward_catalog WHERE id = %s" + (" FOR UPDATE" if lock else ""),
            (catalog_id,),
        )
        return _catalog(result[0]) if result else None

    def catalog_code_taken(self, conn: Any, code: str, exclude_id: int | None) -> bool:
        return bool(
            rows(conn, "SELECT id FROM reward_catalog WHERE code = %s AND id <> %s", (code, exclude_id or 0))
        )

    def insert_catalog(self, conn: Any, **f) -> int:
        return int(
            execute(
                conn,
                "INSERT INTO reward_catalog (code, name, store_id, reward_type, value, min_order_amount,"
                " valid_days, coin_cost, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (f["code"], f["name"], f["store_id"], f["reward_type"].value, f["value"],
                 f["min_order_amount"], f["valid_days"], f["coin_cost"], f["is_active"]),
            )
        )

    def update_catalog(self, conn: Any, catalog_id: int, **f) -> None:
        execute(
            conn,
            "UPDATE reward_catalog SET code = %s, name = %s, store_id = %s, reward_type = %s, value = %s,"
            " min_order_amount = %s, valid_days = %s, coin_cost = %s, is_active = %s WHERE id = %s",
            (f["code"], f["name"], f["store_id"], f["reward_type"].value, f["value"],
             f["min_order_amount"], f["valid_days"], f["coin_cost"], f["is_active"], catalog_id),
        )

    # ----- Khách hàng ----------------------------------------------------------------
    def customer_account(self, conn: Any, customer_id: int, *, lock: bool = False) -> dict | None:
        result = rows(
            conn,
            "SELECT c.id AS customer_id, a.id AS account_id, c.full_name, c.status, a.status AS account_status"
            " FROM customers AS c JOIN accounts AS a ON a.customer_id = c.id WHERE c.id = %s"
            + (" FOR UPDATE" if lock else ""),
            (customer_id,),
        )
        return dict(result[0]) if result else None

    # ----- Voucher -------------------------------------------------------------------
    def insert_voucher(self, conn: Any, *, code, catalog: RewardCatalogItem, account_id, source: VoucherSource,
                       source_ref, issued_by, issued_at, expires_at) -> int:
        return int(
            execute(
                conn,
                "INSERT INTO customer_vouchers (code, catalog_id, account_id, store_id, reward_type, value,"
                " min_order_amount, source, source_ref, issued_by, issued_at, expires_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (code, catalog.id, account_id, catalog.store_id, catalog.reward_type.value, catalog.value,
                 catalog.min_order_amount, source.value, source_ref, issued_by, _naive(issued_at),
                 _naive(expires_at)),
            )
        )

    def voucher_by_source(self, conn: Any, source: VoucherSource, source_ref: str) -> Voucher | None:
        result = rows(conn, _VOUCHER_SELECT + " WHERE v.source = %s AND v.source_ref = %s", (source.value, source_ref))
        return _voucher(result[0]) if result else None

    def get_voucher(self, conn: Any, *, voucher_id: int | None = None, code: str | None = None,
                    lock: bool = False) -> Voucher | None:
        column, value = ("id", voucher_id) if voucher_id is not None else ("code", code)
        if lock:
            # Khóa riêng dòng voucher trước, rồi mới đọc kèm tên khách/danh mục.
            locked = rows(conn, f"SELECT id FROM customer_vouchers WHERE {column} = %s FOR UPDATE", (value,))
            if not locked:
                return None
            column, value = "id", locked[0]["id"]
        result = rows(conn, _VOUCHER_SELECT + f" WHERE v.{column} = %s", (value,))
        return _voucher(result[0]) if result else None

    def account_vouchers(self, conn: Any, account_id: int) -> list[Voucher]:
        return [
            _voucher(r)
            for r in rows(conn, _VOUCHER_SELECT + " WHERE v.account_id = %s ORDER BY v.issued_at DESC, v.id DESC",
                          (account_id,))
        ]

    def order_has_voucher(self, conn: Any, order_id: int) -> bool:
        return bool(rows(conn, "SELECT id FROM customer_vouchers WHERE used_order_id = %s", (order_id,)))

    def mark_used(self, conn: Any, voucher_id: int, *, employee_id, store_id, order_id, used_at) -> bool:
        return bool(
            execute(
                conn,
                "UPDATE customer_vouchers SET status = 'USED', used_at = %s, used_by = %s, used_store_id = %s,"
                " used_order_id = %s WHERE id = %s AND status = 'ISSUED'",
                (_naive(used_at), employee_id, store_id, order_id, voucher_id),
            )
        )

    def revoke(self, conn: Any, voucher_id: int, reason: str) -> bool:
        return bool(
            execute(
                conn,
                "UPDATE customer_vouchers SET status = 'REVOKED', revoked_reason = %s"
                " WHERE id = %s AND status = 'ISSUED'",
                (reason, voucher_id),
            )
        )

    # ----- Nhật ký ------------------------------------------------------------------
    def insert_event(self, conn: Any, *, voucher_id, action: VoucherAction, employee_id, store_id, reason="") -> None:
        execute(
            conn,
            "INSERT INTO voucher_events (voucher_id, action, employee_id, store_id, reason) VALUES (%s, %s, %s, %s, %s)",
            (voucher_id, action.value, employee_id, store_id, reason[:200]),
        )

    def list_events(self, conn: Any, store_id: int, limit: int = 50) -> list[VoucherEvent]:
        return [
            VoucherEvent(
                id=int(r["id"]),
                voucher_id=None if r["voucher_id"] is None else int(r["voucher_id"]),
                voucher_code=r["voucher_code"],
                action=VoucherAction(r["action"]),
                employee_name=r["employee_name"],
                reason=r["reason"],
                created_at=_utc(r["created_at"]),
            )
            for r in rows(
                conn,
                "SELECT e.id, e.voucher_id, v.code AS voucher_code, e.action, emp.full_name AS employee_name,"
                " e.reason, e.created_at FROM voucher_events AS e"
                " LEFT JOIN customer_vouchers AS v ON v.id = e.voucher_id"
                " LEFT JOIN employees AS emp ON emp.id = e.employee_id"
                " WHERE e.store_id = %s ORDER BY e.created_at DESC, e.id DESC LIMIT %s",
                (store_id, limit),
            )
        ]

    # ----- Thực hiện phần thưởng -----------------------------------------------------
    def grant_points(self, conn: Any, *, customer_id, voucher_id, points, employee_id) -> None:
        execute(
            conn,
            "INSERT INTO loyalty_point_grants (customer_id, voucher_id, points, employee_id) VALUES (%s, %s, %s, %s)",
            (customer_id, voucher_id, points, employee_id),
        )

    def credit_playtime(self, conn: Any, *, account_id, amount, employee_id, store_id) -> None:
        """Cộng số dư khuyến mãi + ghi giao dịch PROMOTION (cùng cơ chế thưởng nạp tiền P1)."""
        from cyberhub_manager.repositories.account_repository import AccountRepository
        from cyberhub_manager.services.wallet_service import new_transaction_code

        accounts = AccountRepository()
        if not accounts.credit_bonus(conn, account_id, amount):
            raise LookupError("account not found")
        accounts.insert_bonus_transaction(
            conn, code=new_transaction_code(), account_id=account_id, employee_id=employee_id,
            amount=amount, store_id=store_id, promotion_id=None,
        )
