import pytest

from cyberhub_manager.domain.cash_shift import calculate_totals
from cyberhub_manager.domain.exceptions import ConflictError, ValidationError
from cyberhub_manager.domain.maintenance import require_incident_transition
from cyberhub_manager.domain.procurement import parse_quantity_lines


def test_cash_reconciliation_separates_cash_and_transfer():
    totals = calculate_totals(100_000, [
        {"kind": "RECEIPT", "payment_method": "CASH", "amount": 50_000},
        {"kind": "RECEIPT", "payment_method": "TRANSFER", "amount": 80_000},
        {"kind": "EXPENSE", "payment_method": "CASH", "amount": 20_000},
    ])
    assert totals.expected_cash == 130_000
    assert totals.transfer_receipts == 80_000


def test_incident_state_machine_rejects_skipping_repair():
    with pytest.raises(ConflictError):
        require_incident_transition("REPORTED", "VERIFIED")
    assert require_incident_transition("REPORTED", "ASSIGNED")[1].value == "ASSIGNED"


def test_procurement_lines_reject_duplicate_ingredients():
    with pytest.raises(ValidationError):
        parse_quantity_lines([
            {"ingredient_id": 1, "quantity": 2},
            {"ingredient_id": 1, "quantity": 3},
        ])
