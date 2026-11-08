"""Read-only customer access; every request revalidates account ownership and status."""

from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
)
from cyberhub_manager.domain.p1 import CustomerSession
from cyberhub_manager.repositories.p1_repository import P1Repository
from cyberhub_manager.security import verify_password
from .p1_runtime import errors


class PortalService:
    def __init__(self, repo=None, transaction_factory=None):
        self._memory = hasattr(repo, "resolve_actor")
        if transaction_factory is None:
            from cyberhub_manager.database.transaction import transaction

            transaction_factory = transaction
        self._repo = repo or P1Repository()
        self._transaction = transaction_factory

    def _errors(self):
        return errors(self._memory)

    def login(self, username, password):
        if (
            not isinstance(username, str)
            or not isinstance(password, str)
            or len(password.encode()) > 72
        ):
            raise AuthenticationError()
        with self._errors(), self._transaction() as conn:
            record = self._repo.customer_credentials(conn, username=username.strip())
            # Always run password verification, including for a missing/locked user.
            from cyberhub_manager.security import DUMMY_PASSWORD_HASH

            valid = verify_password(
                password, record[1] if record else DUMMY_PASSWORD_HASH
            )
            if not record or not valid:
                raise AuthenticationError()
            return record[0]

    def validate(self, principal):
        if not isinstance(principal, CustomerSession):
            raise PermissionDeniedError()
        with self._errors(), self._transaction() as conn:
            record = self._repo.customer_credentials(
                conn, account_id=principal.account_id
            )
            if not record or record[0].customer_id != principal.customer_id:
                raise PermissionDeniedError()
            return record[0]

    def snapshot(self, principal):
        if not isinstance(principal, CustomerSession):
            raise PermissionDeniedError()
        with self._errors(), self._transaction() as conn:
            record = self._repo.customer_credentials(
                conn, account_id=principal.account_id
            )
            if not record or record[0].customer_id != principal.customer_id:
                raise PermissionDeniedError()
            return self._repo.customer_snapshot(conn, record[0])

    def invoice(self, principal, invoice_id):
        if (
            not isinstance(principal, CustomerSession)
            or type(invoice_id) is not int
            or invoice_id <= 0
        ):
            raise PermissionDeniedError()
        with self._errors(), self._transaction() as conn:
            record = self._repo.customer_credentials(
                conn, account_id=principal.account_id
            )
            if not record or record[0].customer_id != principal.customer_id:
                raise PermissionDeniedError()
            return self._repo.customer_invoice(conn, record[0], invoice_id)
