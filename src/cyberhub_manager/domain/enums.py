"""Các enum nghiệp vụ dùng chung trong CyberHub Manager."""

from enum import StrEnum

class Role(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    STAFF = "STAFF"

class StoreStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class EmployeeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"

class CustomerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"

class MachineStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    MAINTENANCE = "MAINTENANCE"

class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class TransactionType(StrEnum):
    TOP_UP = "TOP_UP"
    PROMOTION = "PROMOTION"
    USAGE_PAYMENT = "USAGE_PAYMENT"
    DEBT_SETTLEMENT = "DEBT_SETTLEMENT"

class PaymentMethod(StrEnum):
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    ACCOUNT_BALANCE = "ACCOUNT_BALANCE"
    PROMOTION = "PROMOTION"

class InvoiceStatus(StrEnum):
    PAID = "PAID"
    VOID = "VOID"

class MachineArchiveAction(StrEnum):
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"
