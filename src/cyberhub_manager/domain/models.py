"""Các domain model của CyberHub Manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import (
    AccountStatus,
    CustomerStatus,
    EmployeeStatus,
    InvoiceStatus,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
    StoreStatus,
    TransactionType,
)


@dataclass
class Store:
    id: int
    code: str
    name: str
    address: str
    status: StoreStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class Employee:
    id: int
    code: str
    full_name: str
    store_id: int
    username: str
    role: Role
    status: EmployeeStatus


@dataclass
class Account:
    id: int
    code: str
    customer_id: int
    username: str
    balance: int
    status: AccountStatus


@dataclass
class Customer:
    id: int
    code: str
    full_name: str
    phone: str
    status: CustomerStatus
    account: Account


@dataclass
class Machine:
    id: int
    code: str
    store_id: int
    name: str
    status: MachineStatus
    hourly_rate: int
    is_active: bool
    updated_at: datetime


@dataclass
class UsageSession:
    id: int
    code: str
    customer_id: int
    machine_id: int
    opened_by: int
    closed_by: int | None
    started_at: datetime
    ended_at: datetime | None
    hourly_rate: int
    cost: int | None
    status: SessionStatus


@dataclass
class AccountTransaction:
    id: int
    code: str
    account_id: int
    employee_id: int
    session_id: int | None
    type: TransactionType
    amount: int
    method: PaymentMethod
    created_at: datetime


@dataclass
class Invoice:
    id: int
    code: str
    session_id: int
    customer_id: int
    employee_id: int
    store_id: int
    usage_cost: int
    settlement_amount: int
    total_amount: int
    status: InvoiceStatus
    created_at: datetime