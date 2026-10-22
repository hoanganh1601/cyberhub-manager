"""Mock ReportService: danh sách, chi tiết hóa đơn và doanh thu theo ngày.

Ngày lọc là ngày địa phương Asia/Ho_Chi_Minh, bao gồm cả hai đầu mốc.
"""

from __future__ import annotations

from datetime import date

from cyberhub_manager.domain.dtos import (
    DailyRevenue,
    InvoiceDetail,
    InvoiceFilters,
    InvoiceSummary,
)
from cyberhub_manager.domain.enums import InvoiceStatus

from .base import MockServiceBase, clean_text, raise_if_errors
from .store import local_date


def _date_range_errors(
    date_from: date | None,
    date_to: date | None,
    *,
    required: bool,
) -> dict[str, str | None]:
    errors: dict[str, str | None] = {}
    if required and not isinstance(date_from, date):
        errors["date_from"] = "Vui lòng chọn ngày bắt đầu"
    if required and not isinstance(date_to, date):
        errors["date_to"] = "Vui lòng chọn ngày kết thúc"
    if not errors and date_from and date_to and date_from > date_to:
        errors["date_to"] = "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu"
    return errors


class MockReportService(MockServiceBase):
    def list_invoices(
        self,
        store_id: int,
        filters: InvoiceFilters,
    ) -> list[InvoiceSummary]:
        self._check_scenario("list_invoices")
        filters = filters or InvoiceFilters()
        raise_if_errors(
            _date_range_errors(filters.date_from, filters.date_to, required=False)
        )
        keyword = clean_text(filters.keyword).casefold()

        results = []
        for invoice in self._data.invoices.values():
            day = local_date(invoice.created_at)
            if (
                invoice.store_id != store_id
                or (filters.date_from and day < filters.date_from)
                or (filters.date_to and day > filters.date_to)
                or (
                    filters.customer_id is not None
                    and invoice.customer_id != filters.customer_id
                )
                or (filters.status is not None and invoice.status != filters.status)
            ):
                continue
            summary = self._data.to_invoice_summary(invoice)
            if keyword and not any(
                keyword in value.casefold()
                for value in (summary.invoice_code, summary.customer_name)
            ):
                continue
            results.append(summary)
        results.sort(key=lambda s: (s.created_at, s.invoice_id), reverse=True)
        return results

    def get_invoice(self, invoice_id: int) -> InvoiceDetail:
        self._check_scenario("get_invoice")
        return self._data.to_invoice_detail(self._data.get_invoice(invoice_id))

    def daily_revenue(
        self,
        store_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DailyRevenue]:
        self._check_scenario("daily_revenue")
        raise_if_errors(_date_range_errors(date_from, date_to, required=True))

        totals: dict[date, tuple[int, int]] = {}
        for invoice in self._data.invoices.values():
            day = local_date(invoice.created_at)
            if (
                invoice.store_id == store_id
                and invoice.status == InvoiceStatus.PAID
                and date_from <= day <= date_to
            ):
                count, revenue = totals.get(day, (0, 0))
                totals[day] = (count + 1, revenue + invoice.usage_cost)
        return [
            DailyRevenue(date=day, invoice_count=count, revenue=revenue)
            for day, (count, revenue) in sorted(totals.items())
        ]
