"""Memory adapter for the same management and portal business services used by MySQL."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from threading import RLock
from datetime import datetime, timezone

from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    EmployeeStatus,
    Role,
    StoreStatus,
)
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.domain.models import Employee, Store
from cyberhub_manager.domain.p1 import CustomerSession, EmployeeSummary, StoreSummary
from cyberhub_manager.security import hash_password
from .portal import MemoryPortalRepositoryMixin
from .loyalty import MemoryLoyaltyRepositoryMixin


class MemoryP1Repository(MemoryPortalRepositoryMixin,MemoryLoyaltyRepositoryMixin):
    def customer_invoice(self, conn, principal, invoice_id):
        from cyberhub_manager.domain.exceptions import NotFoundError

        invoice = self.data.invoices.get(invoice_id)
        if invoice is None or invoice.customer_id != principal.customer_id:
            raise NotFoundError()
        return self.data.to_invoice_detail(invoice)

    def __init__(self, data):
        self.data = data
        self.lock = RLock()
        self.notification_reads = set()
        self.auth_versions = {}
        self.room_types = {}
        self.avatars={}

    @contextmanager
    def transaction(self):
        with self.lock:
            snapshot = deepcopy(
                (
                    self.data.stores,
                    self.data.employees,
                    self.data.employee_password_hashes,
                    self.data.promotions,
                    self.data.management_audit,
                    self.data._last_ids,
                    self.data.employee_passwords,
                    self.data.operating_stores,
                    self.notification_reads,
                    self.auth_versions,
                    self.room_types,
                    self.data.customers,
                    self.data.customer_password_hashes,
                    self.avatars,
                    self.data.loyalty_settings,
                )
            )
            try:
                yield self
            except Exception:
                (
                    self.data.stores,
                    self.data.employees,
                    self.data.employee_password_hashes,
                    self.data.promotions,
                    self.data.management_audit,
                    self.data._last_ids,
                    self.data.employee_passwords,
                    self.data.operating_stores,
                    self.notification_reads,
                    self.auth_versions,
                    self.room_types,
                    self.data.customers,
                    self.data.customer_password_hashes,
                    self.avatars,
                    self.data.loyalty_settings,
                ) = snapshot
                raise

    def resolve_actor(self, actor):
        employee = self.data.employees.get(getattr(actor, "employee_id", None))
        if (
            employee is None
            or employee.status != EmployeeStatus.ACTIVE
            or employee.role != actor.role
        ):
            raise PermissionDeniedError()
        target = self.store(None, actor.store_id)
        if (
            target is None
            or target.status != "ACTIVE"
            or employee.role != Role.ADMIN
            and employee.store_id != actor.store_id
        ):
            raise PermissionDeniedError()
        self.data.operating_stores[employee.id] = target.id
        return replace(
            self.data.to_employee_session(employee),
            store_id=target.id,
            store_code=target.code,
            store_name=target.name,
        )

    def list_stores(self, conn, store_id=None):
        return [
            StoreSummary(s.id, s.code, s.name, s.address, str(s.status))
            for s in self.data.stores.values()
            if store_id is None or s.id == store_id
        ]

    def store(self, conn, store_id, lock=False):
        return next((s for s in self.list_stores(conn) if s.id == store_id), None)

    def save_store(self, conn, store_id, code, name, address, status):
        store_id = store_id or self.data.next_id("store")
        now = datetime.now(timezone.utc)
        old = self.data.stores.get(store_id)
        self.data.stores[store_id] = Store(
            store_id,
            code,
            name,
            address,
            StoreStatus(status),
            old.created_at if old else now,
            now,
        )
        return self.store(conn, store_id)

    def has_active_sessions(self, conn, store_id):
        return any(
            str(u.status) == "ACTIVE"
            and self.data.machines[u.machine_id].store_id == store_id
            for u in self.data.sessions.values()
        )

    def list_employees(self, conn, store_id=None, lock=False):
        return [
            EmployeeSummary(
                e.id,
                e.code,
                e.store_id,
                e.full_name,
                e.username,
                str(e.role),
                str(e.status),
            )
            for e in self.data.employees.values()
            if store_id is None or e.store_id == store_id
        ]

    def save_employee(self, conn, employee_id, values, password_hash):
        store_id, name, username, role, status = values
        old = self.data.employees.get(employee_id)
        employee_id = employee_id or self.data.next_id("employee")
        self.data.employees[employee_id] = Employee(
            employee_id,
            old.code if old else self.data.make_code("employee", employee_id),
            name,
            store_id,
            username,
            Role(role),
            EmployeeStatus(status),
        )
        if password_hash:
            self.data.employee_password_hashes[employee_id] = password_hash
        if old:
            if (
                employee_id not in self.data.employee_password_hashes
                and old.username in self.data.employee_passwords
            ):
                self.data.employee_password_hashes[employee_id] = hash_password(
                    self.data.employee_passwords[old.username]
                )
            self.data.employee_passwords.pop(old.username, None)
        return next(e for e in self.list_employees(conn) if e.id == employee_id)

    def list_promotions(self, conn, store_id=None, lock=False):
        return [
            p
            for p in self.data.promotions.values()
            if store_id is None or p.store_id in (None, store_id)
        ]

    def save_promotion(self, conn, policy):
        policy = replace(policy, id=policy.id or self.data.next_id("promotion"))
        self.data.promotions[policy.id] = policy
        return policy

    def audit(self, conn, actor, action, entity_id):
        self.data.management_audit.append(
            (actor.employee_id, actor.store_id, action, entity_id)
        )

    def customer_credentials(self, conn, *, username=None, account_id=None, lock=False):
        customer = next(
            (
                c
                for c in self.data.customers.values()
                if (
                    username is not None
                    and c.account.username.casefold() == username.casefold()
                )
                or c.account.id == account_id
            ),
            None,
        )
        if (
            customer is None
            or customer.status != CustomerStatus.ACTIVE
            or customer.account.status != AccountStatus.ACTIVE
        ):
            return None
        password_hash = self.data.customer_password_hashes.get(customer.account.id)
        if password_hash is None:
            return None
        return (
            CustomerSession(
                customer.id,
                customer.account.id,
                customer.full_name,
                customer.account.username,
                self.auth_versions.get(customer.account.id, 0),
            ),
            password_hash,
        )

    def customer_snapshot(self, conn, principal):
        c = self.data.get_customer(principal.customer_id)
        account = c.account
        history = [
            {
                "code": t.code,
                "type": str(t.type),
                "amount": t.amount,
                "method": str(t.method),
                "created_at": t.created_at,
                "store_name": self.data.get_store(
                    self.data.transaction_stores.get(
                        t.id, self.data.employees[t.employee_id].store_id
                    )
                ).name,
            }
            for t in self.data.transactions_for_account(account.id)
        ][:100]
        sessions = []
        for u in sorted(self.data.sessions.values(), key=lambda u: u.id, reverse=True):
            if u.customer_id == c.id:
                m = self.data.machines[u.machine_id]
                sessions.append(
                    dict(
                        code=u.code,
                        machine_code=m.code,
                        store_name=self.data.get_store(m.store_id).name,
                        started_at=u.started_at,
                        ended_at=u.ended_at,
                        hourly_rate=u.hourly_rate,
                        status=str(u.status),
                        cost=u.cost,
                    )
                )
        invoices = [
            dict(
                id=i.id,
                code=i.code,
                usage_cost=i.usage_cost,
                settlement_amount=i.settlement_amount,
                bonus_used=self.data.invoice_bonus.get(i.id, 0),
                status=str(i.status),
                created_at=i.created_at,
                store_name=self.data.get_store(i.store_id).name,
            )
            for i in sorted(
                self.data.invoices.values(), key=lambda i: i.id, reverse=True
            )
            if i.customer_id == c.id
        ][:100]
        return dict(
            profile=principal,
            wallet=dict(
                account_code=account.code,
                balance=account.balance,
                bonus_balance=account.bonus_balance,
                cash_balance=account.cash_balance,
                phone=c.phone,
            ),
            transactions=history,
            sessions=sessions[:100],
            invoices=invoices,
        )
