"""Shared authentication and transaction plumbing for operational services."""

from contextlib import contextmanager

from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.domain.p1 import can
from cyberhub_manager.infrastructure.repositories.auth_repository import AuthRepository
from cyberhub_manager.infrastructure.repositories.management_repository import ManagementRepository

from cyberhub_manager.infrastructure.db_errors import translate_db_errors


class OperationalServiceBase:
    def __init__(self, *, auth_repo=None, audit_repo=None, transaction_factory=None):
        if transaction_factory is None:
            from cyberhub_manager.infrastructure.database.transaction import transaction
            transaction_factory = transaction
        self._auth = auth_repo or AuthRepository()
        self._audit = audit_repo or ManagementRepository()
        self._transaction = transaction_factory

    def _actor(self, conn, actor, permission):
        current = self._auth.get_active_session_by_id(conn, getattr(actor, "employee_id", 0))
        if (current is None or current.auth_version != getattr(actor, "auth_version", None)
                or current.store_id != getattr(actor, "store_id", None)
                or not can(current.role, permission)):
            raise PermissionDeniedError()
        return current

    @contextmanager
    def _errors(self):
        with translate_db_errors():
            yield
