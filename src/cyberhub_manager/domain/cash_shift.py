"""Cash-shift states and deterministic reconciliation rules."""

from dataclasses import dataclass
from enum import StrEnum

from .exceptions import ValidationError


class ShiftStatus(StrEnum):
    OPEN = "OPEN"
    PENDING_REVIEW = "PENDING_REVIEW"
    CLOSED = "CLOSED"


class CashEntryKind(StrEnum):
    RECEIPT = "RECEIPT"
    EXPENSE = "EXPENSE"
    REFUND = "REFUND"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"


class TenderMethod(StrEnum):
    CASH = "CASH"
    TRANSFER = "TRANSFER"


@dataclass(frozen=True)
class ShiftTotals:
    opening_cash: int
    cash_receipts: int
    transfer_receipts: int
    cash_out: int
    transfer_out: int
    expected_cash: int


def calculate_totals(opening_cash: int, entries: list[dict]) -> ShiftTotals:
    if type(opening_cash) is not int or opening_cash < 0:
        raise ValidationError(field_errors={"opening_cash": "Tiền đầu ca không hợp lệ"})
    cash_receipts = transfer_receipts = cash_out = transfer_out = 0
    for entry in entries:
        amount = int(entry["amount"])
        incoming = entry["kind"] in ("RECEIPT", "ADJUSTMENT_IN")
        if entry["payment_method"] == "CASH":
            if incoming:
                cash_receipts += amount
            else:
                cash_out += amount
        elif incoming:
            transfer_receipts += amount
        else:
            transfer_out += amount
    return ShiftTotals(
        opening_cash=opening_cash,
        cash_receipts=cash_receipts,
        transfer_receipts=transfer_receipts,
        cash_out=cash_out,
        transfer_out=transfer_out,
        expected_cash=opening_cash + cash_receipts - cash_out,
    )
