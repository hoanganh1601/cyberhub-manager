"""Assemble the customer-owned invoice read model across repositories."""

from cyberhub_manager.domain.dtos import InvoiceDetail, SessionSummary
from cyberhub_manager.domain.exceptions import NotFoundError
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository


class CustomerInvoiceQuery:
    def __init__(
        self,
        invoice_repo=None,
        session_repo=None,
        machine_repo=None,
        customer_repo=None,
    ):
        self._invoices = invoice_repo or InvoiceRepository()
        self._sessions = session_repo or SessionRepository()
        self._machines = machine_repo or MachineRepository()
        self._customers = customer_repo or CustomerRepository()

    def get(self, conn, principal, invoice_id: int) -> InvoiceDetail:
        summary = self._invoices.get_summary_by_id(conn, invoice_id)
        if summary is None or summary.customer_id != principal.customer_id:
            raise NotFoundError()
        usage = self._sessions.get_by_id(conn, summary.session_id)
        machine = self._machines.get_by_id(conn, usage.machine_id)
        customer = self._customers.get_by_id(conn, summary.customer_id)
        session = SessionSummary(
            usage.id,
            usage.code,
            customer.id,
            customer.code,
            customer.full_name,
            machine.id,
            machine.code,
            machine.name,
            usage.started_at,
            usage.hourly_rate,
            usage.status,
        )
        return InvoiceDetail(
            summary,
            session,
            usage.ended_at,
            usage.calculate_billed_minutes(usage.ended_at),
        )
