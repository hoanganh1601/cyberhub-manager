"""Portable, escaped HTML receipts with native/browser printing and CSV export."""

from html import escape
import csv
from io import StringIO


def invoice_html(detail, language="vi", auto_print=False):
    en = language == "en"
    inv, session = detail.invoice, detail.session
    label = lambda vi, english: english if en else vi
    esc = lambda value: escape(str(value), quote=True)
    money = lambda value: f"{value:,} VND" if en else f"{value:,} VND".replace(",", ".")
    from datetime import timedelta, timezone

    format_datetime = lambda value: value.astimezone(
        timezone(timedelta(hours=7))
    ).strftime("%H:%M %d/%m/%Y")
    fields = [
        (label("Cơ sở", "Store"), inv.store_name),
        (
            label("Khách hàng", "Customer"),
            f"{session.customer_name} · {session.customer_code}",
        ),
        (
            label("Máy / Phiên", "Machine / Session"),
            f"{session.machine_code} · {session.session_code}",
        ),
        (label("Bắt đầu", "Started"), format_datetime(session.started_at)),
        (label("Kết thúc", "Ended"), format_datetime(detail.ended_at)),
        (
            label("Thời lượng tính phí", "Billed duration"),
            f"{detail.billed_minutes} " + label("phút", "min"),
        ),
        (label("Đơn giá / giờ", "Hourly rate"), money(session.hourly_rate)),
        (label("Thu ngân", "Cashier"), inv.employee_name),
    ]
    payment = [
        (label("Phí sử dụng", "Usage cost"), money(inv.usage_cost)),
        (label("Đã dùng tiền khuyến mãi", "Paid from bonus"), money(inv.bonus_used)),
        (
            label("Đã dùng số dư chính", "Paid from principal"),
            money(max(0, inv.usage_cost - inv.bonus_used - inv.settlement_amount)),
        ),
        (label("Tiền bù đã thu", "Settlement received"), money(inv.settlement_amount)),
    ]
    void = str(inv.status) == "VOID"
    status = (
        label("ĐÃ HỦY — KHÔNG GHI NHẬN DOANH THU", "VOID — EXCLUDED FROM REVENUE")
        if void
        else label("ĐÃ THANH TOÁN", "PAID")
    )
    row = lambda items: "".join(
        f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in items
    )
    # No script is required; a dedicated print button works under the web CSP.
    return f"""<!doctype html><html lang="{ 'en' if en else 'vi' }"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(inv.invoice_code)} · CyberHub</title>
<style>body{{font:14px 'Segoe UI',Arial,sans-serif;color:#172435;background:#eef2f6;margin:0}}main{{max-width:720px;margin:32px auto;background:white;padding:40px;border-radius:16px}}h1{{margin:0;color:#0088ac}}header{{border-bottom:2px solid #00a9d0;padding-bottom:20px}}.muted{{color:#667789}}.status{{color:{'#b42345' if void else '#087d61'};font-weight:700}}table{{width:100%;border-collapse:collapse;margin:20px 0}}th,td{{text-align:left;padding:9px 0;border-bottom:1px solid #e7edf2}}th{{font-weight:400;color:#667789;width:44%}}td{{text-align:right;overflow-wrap:anywhere}}.total{{font-size:26px;font-weight:700;text-align:right;color:#0088ac}}footer{{margin-top:24px;color:#667789;font-size:12px}}@media print{{body{{background:white}}main{{margin:0;max-width:none;padding:12mm;border-radius:0}}@page{{size:A5;margin:8mm}}}}</style>
<main><header><h1>CyberHub Manager</h1><p class="muted">{label('BIÊN LAI DỊCH VỤ','SERVICE RECEIPT')}</p><h2>{esc(inv.invoice_code)}</h2><span class="status">{status}</span></header>
<table>{row(fields)}</table><table>{row(payment)}</table><div class="total">{money(inv.total_amount)}</div>
<footer>{label('Cảm ơn quý khách! Tiền khuyến mãi không quy đổi thành tiền mặt.','Thank you! Promotional credit cannot be redeemed for cash.')}<br>{label('In hoặc lưu PDF: Ctrl+P / trình đơn In của trình duyệt.','Print or save as PDF: Ctrl+P / your browser print menu.')}</footer></main></html>"""


def invoice_csv(detail):
    inv = detail.invoice
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "invoice_code",
            "store",
            "customer",
            "status",
            "usage_cost_vnd",
            "bonus_used_vnd",
            "settlement_vnd",
            "created_at",
        ]
    )
    # Prefix spreadsheet formulas in all text cells; amounts remain numeric.
    safe = lambda value: (
        "'" + str(value)
        if str(value).lstrip().startswith(("=", "+", "-", "@"))
        else str(value)
    )
    writer.writerow(
        [
            safe(inv.invoice_code),
            safe(inv.store_name),
            safe(inv.customer_name),
            str(inv.status),
            inv.usage_cost,
            inv.bonus_used,
            inv.settlement_amount,
            inv.created_at.isoformat(),
        ]
    )
    return "\ufeff" + output.getvalue()
