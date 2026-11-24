"""Customer self-service; every request revalidates ownership, status and credentials."""

from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
)
from cyberhub_manager.domain.policies import CustomerSession
from cyberhub_manager.infrastructure.repositories.loyalty_repository import LoyaltyRepository
from cyberhub_manager.infrastructure.repositories.management_repository import ManagementRepository
from cyberhub_manager.infrastructure.repositories.portal_repository import PortalRepository
from cyberhub_manager.infrastructure.security import verify_password
from cyberhub_manager.application.services.service_runtime import errors
from cyberhub_manager.application.services.portal_experience import PortalExperienceMixin
from cyberhub_manager.application.services.portal_profile import PortalProfileMixin
from cyberhub_manager.application.services.portal_membership import PortalMembershipMixin
from datetime import datetime, timezone


class PortalService(PortalExperienceMixin, PortalProfileMixin, PortalMembershipMixin):
    def __init__(
        self,
        repo=None,
        transaction_factory=None,
        clock=None,
        invoice_query=None,
        management_repo=None,
        loyalty_repo=None,
    ):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._memory = hasattr(repo, "resolve_actor")
        if transaction_factory is None:
            from cyberhub_manager.infrastructure.database.transaction import transaction

            transaction_factory = transaction
        self._repo = repo or PortalRepository()
        self._management = management_repo or (
            repo if hasattr(repo, "list_stores") else ManagementRepository()
        )
        self._loyalty = loyalty_repo or (
            repo if hasattr(repo, "loyalty_summary") else LoyaltyRepository()
        )
        if invoice_query is None and repo is None:
            from cyberhub_manager.application.services.customer_invoice_query import CustomerInvoiceQuery

            invoice_query = CustomerInvoiceQuery()
        self._invoice_query = invoice_query
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
            from cyberhub_manager.infrastructure.security import DUMMY_PASSWORD_HASH

            valid = verify_password(
                password, record[1] if record else DUMMY_PASSWORD_HASH
            )
            if not record or not valid:
                raise AuthenticationError()
            return record[0]

    def validate(self, principal):
        with self._errors(), self._transaction() as conn:
            return self._principal(conn, principal)

    def snapshot(self, principal):
        with self._errors(), self._transaction() as conn:
            return self._repo.customer_snapshot(conn, self._principal(conn, principal))

    def invoice(self, principal, invoice_id):
        if (
            not isinstance(principal, CustomerSession)
            or type(invoice_id) is not int
            or invoice_id <= 0
        ):
            raise PermissionDeniedError()
        with self._errors(), self._transaction() as conn:
            current = self._principal(conn, principal)
            if self._invoice_query is not None:
                return self._invoice_query.get(conn, current, invoice_id)
            return self._repo.customer_invoice(conn, current, invoice_id)
