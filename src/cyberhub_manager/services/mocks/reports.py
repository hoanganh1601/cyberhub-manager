"""Mock ReportService: danh sách, chi tiết hóa đơn và doanh thu theo ngày.

Ngày lọc là ngày địa phương Asia/Ho_Chi_Minh, bao gồm cả hai đầu mốc.
"""

from __future__ import annotations

from datetime import date, timedelta

from cyberhub_manager.domain.dtos import (
    DailyRevenue,
    InvoiceDetail,
    InvoiceFilters,
    InvoiceSummary,
)
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import InvoiceStatus, Role
from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError

from .base import MockServiceBase, clean_text, raise_if_errors
from .store import VN_TZ, local_date


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

    def assistant_analytics(self, actor, store_ids, date_from, date_to):
        """Demo equivalent of the de-identified, role-scoped 5B snapshot."""
        if (
            not isinstance(actor, EmployeeSession)
            or actor.role not in (Role.MANAGER, Role.ADMIN)
            or type(store_ids) is not tuple
            or not store_ids
            or any(type(store_id) is not int or store_id <= 0 for store_id in store_ids)
        ):
            raise PermissionDeniedError()
        raise_if_errors(_date_range_errors(date_from, date_to, required=True))
        if (date_to - date_from).days not in (6, 29, 89):
            raise ValidationError(field_errors={"days": "Chọn kỳ 7, 30 hoặc 90 ngày"})
        if actor.role == Role.MANAGER and store_ids != (actor.store_id,):
            raise PermissionDeniedError()
        period_days = (date_to - date_from).days + 1
        previous_from = date_from - timedelta(days=period_days)
        previous_to = date_from - timedelta(days=1)
        stores = []
        for store_id in store_ids:
            store = self._data.stores.get(store_id)
            if store is None or store.status.value != "ACTIVE":
                raise PermissionDeniedError()
            if actor.role != Role.ADMIN and store_id != actor.store_id:
                raise PermissionDeniedError()
            current = self.daily_revenue(store_id, date_from, date_to)
            previous = self.daily_revenue(store_id, previous_from, previous_to)
            by_day = {item.date: item for item in current}
            calendar = []
            for index in range(period_days):
                day = date_from + timedelta(days=index)
                item = by_day.get(day)
                calendar.append({
                    "date": day,
                    "invoice_count": item.invoice_count if item else 0,
                    "revenue": item.revenue if item else 0,
                })
            machine_totals = {}
            hour_totals = {}
            for invoice in self._data.invoices.values():
                if (
                    invoice.store_id != store_id or invoice.status != InvoiceStatus.PAID
                    or not date_from <= local_date(invoice.created_at) <= date_to
                ):
                    continue
                usage = self._data.sessions[invoice.session_id]
                machine = self._data.machines[usage.machine_id]
                values = machine_totals.setdefault(machine.id, {
                    "machine_code": machine.code, "machine_name": machine.name,
                    "session_count": 0, "billed_minutes": 0, "revenue": 0,
                })
                values["session_count"] += 1
                values["billed_minutes"] += usage.calculate_billed_minutes(usage.ended_at)
                values["revenue"] += invoice.usage_cost
                hour = invoice.created_at.astimezone(VN_TZ).hour
                hourly = hour_totals.setdefault(hour, {"hour": hour, "invoice_count": 0, "revenue": 0})
                hourly["invoice_count"] += 1
                hourly["revenue"] += invoice.usage_cost
            total = sum(item["revenue"] for item in calendar)
            previous_total = sum(item.revenue for item in previous)
            average = total // period_days
            stores.append({
                "store_id": store.id, "store_code": store.code, "store_name": store.name,
                "date_from": date_from, "date_to": date_to,
                "total_revenue": total,
                "invoice_count": sum(item["invoice_count"] for item in calendar),
                "average_daily_revenue": average,
                "previous_total_revenue": previous_total,
                "change_percent": None if previous_total == 0 else round((total - previous_total) * 100 / previous_total, 1),
                "daily": calendar,
                "low_days": [item for item in calendar if average and item["revenue"] * 100 < average * 60][:10],
                "top_machines": sorted(machine_totals.values(), key=lambda item: (-item["billed_minutes"], -item["session_count"], item["machine_code"]))[:10],
                "peak_hours": sorted(hour_totals.values(), key=lambda item: (-item["revenue"], -item["invoice_count"], item["hour"])),
            })
        return {
            "date_from": date_from, "date_to": date_to,
            "timezone": "Asia/Ho_Chi_Minh", "stores": stores,
            "total_revenue": sum(store["total_revenue"] for store in stores),
            "invoice_count": sum(store["invoice_count"] for store in stores),
        }
