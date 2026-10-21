"""DTO dùng chung giữa service và UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineArchiveAction,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
    TransactionType,
)


@dataclass(frozen=True)
class EmployeeSession:
    employee_id: int
    employee_code: str
    full_name: str
    username: str
    store_id: int
    store_code: str
    store_name: str
    role: Role


@dataclass(frozen=True)
class CustomerSummary:
    customer_id: int
    customer_code: str
    full_name: str
    phone: str
    account_id: int
    username: str
    balance: int
    customer_status: CustomerStatus
    account_status: AccountStatus


@dataclass(frozen=True)
class SessionSummary:
    session_id: int
    session_code: str
    customer_id: int
    customer_code: str
    customer_name: str
    machine_id: int
    machine_code: str
    machine_name: str
    started_at: datetime
    hourly_rate: int
    status: SessionStatus


@dataclass(frozen=True)
class ActiveSessionSummary:
    session: SessionSummary
    account_balance: int
    elapsed_seconds: int
    estimated_cost: int
    projected_balance: int
    as_of: datetime


@dataclass(frozen=True)
class MachineSummary:
    machine_id: int
    machine_code: str
    store_id: int
    name: str
    status: MachineStatus
    hourly_rate: int
    is_active: bool
    updated_at: datetime
    active_session: ActiveSessionSummary | None


@dataclass(frozen=True)
class TransactionSummary:
    transaction_id: int
    transaction_code: str
    account_id: int
    session_id: int | None
    type: TransactionType
    amount: int
    method: PaymentMethod
    employee_id: int
    employee_name: str
    created_at: datetime


@dataclass(frozen=True)
class TopUpResult:
    customer_id: int
    account_id: int
    balance_before: int
    balance_after: int
    transaction: TransactionSummary


@dataclass(frozen=True)
class OpenSessionPreview:
    customer_id: int
    machine_id: int
    balance: int
    hourly_rate: int
    minimum_balance: int
    estimated_minutes: int
    can_open: bool
    blocked_reason: str | None
    as_of: datetime


@dataclass(frozen=True)
class CheckoutPreview:
    session: SessionSummary
    calculated_at: datetime
    elapsed_seconds: int
    billed_minutes: int
    usage_cost: int
    balance_before: int
    projected_balance: int
    settlement_required: int


@dataclass(frozen=True)
class InvoiceSummary:
    invoice_id: int
    invoice_code: str
    session_id: int
    customer_id: int
    customer_name: str
    employee_id: int
    employee_name: str
    store_id: int
    store_name: str
    usage_cost: int
    settlement_amount: int
    total_amount: int
    status: InvoiceStatus
    created_at: datetime


@dataclass(frozen=True)
class InvoiceDetail:
    invoice: InvoiceSummary
    session: SessionSummary
    ended_at: datetime
    billed_minutes: int


@dataclass(frozen=True)
class CheckoutResult:
    invoice: InvoiceDetail
    balance_after: int


@dataclass(frozen=True)
class DailyRevenue:
    date: date
    invoice_count: int
    revenue: int


@dataclass(frozen=True)
class MachineArchiveResult:
    machine_id: int
    action: MachineArchiveAction


@dataclass(frozen=True)
class InvoiceFilters:
    date_from: date | None = None
    date_to: date | None = None
    keyword: str = ""
    customer_id: int | None = None
    status: InvoiceStatus | None = None