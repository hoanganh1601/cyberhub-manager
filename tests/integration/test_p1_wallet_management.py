"""Run P1 money and ownership rules against the migrated real MySQL schema."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import pytest
from cyberhub_manager.domain.enums import Role, PaymentMethod
from cyberhub_manager.domain.p1 import Promotion, CustomerSession
from cyberhub_manager.domain.exceptions import ConflictError, PermissionDeniedError
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.p1_repository import P1Repository, rows, execute
from cyberhub_manager.services.wallet_service import WalletService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.services.management_service import ManagementService
from cyberhub_manager.services.portal_service import PortalService


def test_p1_real_money_receipt_and_customer_history(db_conn, test_scenario):
    scenario = test_scenario(db_conn, hourly_rate=10000)
    execute(
        db_conn,
        "UPDATE employees SET role='MANAGER' WHERE id=%s",
        (scenario.employee_id,),
    )
    actor = AuthRepository().get_active_session_by_id(db_conn, scenario.employee_id)

    @contextmanager
    def transaction():
        yield db_conn

    now = datetime.now(timezone.utc).replace(microsecond=0)
    management = ManagementService(
        transaction_factory=transaction, actor_provider=lambda: actor
    )
    management.save_promotion(
        actor,
        Promotion(
            0,
            "P" + scenario.token,
            "P1 reward",
            actor.store_id,
            100000,
            10,
            now - timedelta(days=1),
            now + timedelta(days=1),
        ),
    )
    wallet = WalletService(
        transaction_factory=transaction, actor_provider=lambda: actor, clock=lambda: now
    )
    result = wallet.top_up(
        scenario.customer_id, 100000, PaymentMethod.CASH, actor.employee_id
    )
    assert result.bonus_amount == 10000 and result.balance_after == 110000
    account = AccountRepository().get_by_id(db_conn, scenario.account_id)
    assert account.bonus_balance == 10000 and account.cash_balance == 100000
    checkout_time = [now]
    sessions = SessionService(
        transaction_factory=transaction,
        actor_provider=lambda: actor,
        clock=lambda: checkout_time[0],
    )
    sessions.open_session(scenario.customer_id, scenario.machine_id, actor)
    checkout_time[0] += timedelta(minutes=90)
    result = sessions.complete_checkout(scenario.machine_id, actor, 0, None)
    assert result.bonus_used == 10000 and result.balance_after == 95000
    assert (
        rows(
            db_conn,
            "SELECT bonus_used FROM invoices WHERE id=%s",
            (result.invoice.invoice.invoice_id,),
        )[0]["bonus_used"]
        == 10000
    )
    account = AccountRepository().get_by_id(db_conn, scenario.account_id)
    assert account.bonus_balance == 0 and account.cash_balance == 95000
    principal = CustomerSession(scenario.customer_id, scenario.account_id, "", "")
    portal = PortalService(transaction_factory=transaction)
    snapshot = portal.snapshot(principal)
    assert len(snapshot["transactions"]) == 3
    assert all(tx["store_name"] == "Test store" for tx in snapshot["transactions"])
    assert (
        portal.invoice(principal, result.invoice.invoice.invoice_id).invoice.bonus_used
        == 10000
    )
    with pytest.raises(PermissionDeniedError):
        portal.snapshot(replace(principal, customer_id=scenario.customer_id + 1))


def test_p1_real_admin_store_employee_and_overlap(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    execute(
        db_conn,
        "UPDATE employees SET role='ADMIN' WHERE id=%s",
        (scenario.employee_id,),
    )
    actor = AuthRepository().get_active_session_by_id(db_conn, scenario.employee_id)

    @contextmanager
    def transaction():
        yield db_conn

    service = ManagementService(
        transaction_factory=transaction, actor_provider=lambda: actor
    )
    other = service.save_store(
        actor, None, "S" + scenario.token, "New location", "New address"
    )
    switched = service.switch_store(actor, other.id)
    actor = switched
    employee = service.save_employee(
        actor,
        None,
        other.id,
        "New employee",
        "e" + scenario.token,
        password="password123",
    )
    assert employee.store_id == other.id and employee.role == "STAFF"
    now = datetime.now(timezone.utc)
    p = Promotion(
        0,
        "P" + scenario.token,
        "Reward",
        other.id,
        100000,
        10,
        now,
        now + timedelta(days=1),
    )
    service.save_promotion(actor, p)
    with pytest.raises(ConflictError):
        service.save_promotion(actor, replace(p, code="Q" + scenario.token))
    assert (
        len(
            rows(
                db_conn,
                "SELECT id FROM management_audit WHERE employee_id=%s",
                (actor.employee_id,),
            )
        )
        == 3
    )


def test_p1_money_rolls_back_if_bonus_ledger_fails(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    actor = AuthRepository().get_active_session_by_id(db_conn, scenario.employee_id)
    now = datetime.now(timezone.utc)
    P1Repository().save_promotion(
        db_conn,
        Promotion(
            0,
            "P" + scenario.token,
            "Reward",
            scenario.store_id,
            100000,
            10,
            now - timedelta(days=1),
            now + timedelta(days=1),
        ),
    )

    @contextmanager
    def boundary():
        execute(db_conn, "SAVEPOINT wallet_p1")
        try:
            yield db_conn
        except Exception:
            execute(db_conn, "ROLLBACK TO SAVEPOINT wallet_p1")
            raise

    class FailingBonusLedger(AccountRepository):
        def insert_bonus_transaction(self, *args, **kwargs):
            raise RuntimeError("ledger unavailable")

    wallet = WalletService(
        account_repo=FailingBonusLedger(),
        transaction_factory=boundary,
        actor_provider=lambda: actor,
    )
    with pytest.raises(RuntimeError):
        wallet.top_up(
            scenario.customer_id, 100000, PaymentMethod.CASH, actor.employee_id
        )
    account = AccountRepository().get_by_id(db_conn, scenario.account_id)
    assert account.balance == 0 and account.bonus_balance == 0
    assert (
        rows(
            db_conn,
            "SELECT id FROM account_transactions WHERE account_id=%s",
            (scenario.account_id,),
        )
        == []
    )


def test_bootstrap_admin_only_once_without_elevating_existing_employee(
    db_conn, test_scenario
):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "bootstrap_admin",
        Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_admin.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scenario = test_scenario(db_conn)
    store = P1Repository().store(db_conn, scenario.store_id)
    new_id = module.bootstrap(
        db_conn,
        "cyberhub_manager_test",
        store.code,
        "admin" + scenario.token,
        "Initial Admin",
        "password123",
    )
    assert new_id != scenario.employee_id
    assert (
        AuthRepository().get_active_session_by_id(db_conn, scenario.employee_id).role
        == Role.STAFF
    )
    with pytest.raises(ConflictError):
        module.bootstrap(
            db_conn,
            "cyberhub_manager_test",
            store.code,
            "second" + scenario.token,
            "Second Admin",
            "password123",
        )
