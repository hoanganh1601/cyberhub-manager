"""Exercise the customer portal in Chromium and save optional visual evidence.

Requires the optional local tool Playwright and its Chromium browser.
Run: python scripts/check_customer_portal_ui.py --screenshots docs/testing/customer-phase1
Uses an ephemeral local HTTP server and isolated demo data, never the configured MySQL.
"""

import argparse
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server, WSGIRequestHandler

from cyberhub_manager.web import create_app


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    app = create_app(
        {"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "local-browser-check-only"}
    )
    server = make_server("127.0.0.1", 0, app, request_handler=QuietHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1440, "height": 1050}, locale="vi-VN"
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/customer")
            page.locator('[name="username"]').fill("nguyenvanan")
            page.locator('[name="password"]').fill("demo123")
            page.locator('#login-form button[type="submit"]').click()
            expect(page.locator(".pc-stats")).to_be_visible()
            expect(page.locator(".pc-stat").nth(1)).to_contain_text("50.000 VND")
            expect(page.locator(".pc-stat").nth(2)).to_contain_text("5 giờ")
            expect(page.locator(".pc-chart")).to_be_visible()

            def capture(name):
                if args.screenshots:
                    page.screenshot(
                        path=str(args.screenshots / (name + ".png")), full_page=True
                    )

            capture("overview-desktop")
            page.locator('[data-portal="days"][data-days="7"]').click()
            expect(
                page.locator('[data-portal="days"][data-days="7"]')
            ).to_have_attribute("aria-pressed", "true")
            page.locator('[data-portal="tab"][data-tab="offers"]').first.click()
            expect(page.locator(".pc-offer")).to_have_count(3)
            page.locator('[data-portal="tier"][data-amount="100000"]').first.click()
            expect(page.locator(".pc-credit")).to_contain_text("110.000 VND")
            capture("offers-desktop")
            page.locator("#pc-store").select_option("2")
            expect(page.locator("#pc-store")).to_have_value("2")
            page.locator('#pc-quote-form [name="amount"]').fill("150000")
            page.locator('#pc-quote-form button[type="submit"]').click()
            expect(page.locator(".pc-credit")).to_contain_text("165.000 VND")
            expect(page.locator(".pc-next-tier")).to_contain_text("50.000 VND")
            page.locator('[data-action="language"][data-lang="en"]').click()
            expect(page.locator(".pc-offer-banner")).to_contain_text("Top up smart")
            expect(page.locator(".pc-credit")).to_contain_text("165,000 VND")
            page.locator('[data-portal="tab"][data-tab="history"]').click()
            expect(page.locator(".pc-history-card")).to_contain_text(
                "Wallet transactions"
            )
            assert "method" not in page.locator("thead").inner_text().splitlines()
            page.locator('[data-portal="history-kind"][data-kind="invoices"]').click()
            expect(page.locator(".pc-pagination")).to_contain_text("2 results")
            capture("history-desktop")
            page.locator('#pc-history-form [name="from"]').fill("2020-01-01")
            page.locator('#pc-history-form [name="to"]').fill("2020-01-02")
            page.locator('#pc-history-form button[type="submit"]').click()
            expect(page.locator(".pc-pagination")).to_contain_text("0 results")
            page.locator('[data-portal="history-clear"]').click()
            expect(page.locator(".pc-pagination")).to_contain_text("2 results")
            with page.expect_popup() as popup:
                page.locator('[data-p1="portal-print"]').first.click()
            expect(popup.value.locator("body")).to_contain_text("SERVICE RECEIPT")
            popup.value.close()
            page.locator(
                '.pc-nav [data-portal="tab"][data-tab="notifications"]'
            ).click()
            expect(page.locator(".pc-notice.unread").first).to_be_visible()
            page.locator('[data-portal="read-all"]').click()
            expect(page.locator(".pc-notice.unread")).to_have_count(0)
            page.reload()
            expect(page.locator(".pc-stats")).to_be_visible()
            page.locator(
                '.pc-nav [data-portal="tab"][data-tab="notifications"]'
            ).click()
            expect(page.locator(".pc-notice.unread")).to_have_count(0)
            page.locator('[data-action="language"][data-lang="vi"]').click()
            expect(page.locator("h1")).to_have_text("Thông báo")
            capture("notifications-desktop")

            page.set_viewport_size({"width": 390, "height": 844})
            for tab in ("home", "offers", "history", "notifications"):
                page.locator(f'[data-portal="tab"][data-tab="{tab}"]').first.click()
                expect(page.locator(f'.pc-nav [data-tab="{tab}"]')).to_have_attribute(
                    "aria-current", "page"
                )
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), tab
                if tab == "home":
                    assert (
                        page.locator(".pc-chart")
                        .get_attribute("viewBox")
                        .startswith("0 0 360 ")
                    )
                capture(tab + "-mobile")
            page.locator('#p3-account-toggle').click()
            page.locator('[data-p1="portal-logout"]').click()
            expect(page.locator("#login-form")).to_be_visible()
            page.locator('[name="username"]').fill("lethibinh")
            page.locator('[name="password"]').fill("demo123")
            page.locator('#login-form button[type="submit"]').click()
            expect(page.locator(".pc-live-machine")).to_contain_text("PC02")
            expect(page.locator(".pc-notice.warning").first).to_contain_text(
                "đã hết số dư"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture("live-session-mobile")
            assert not errors, errors
            context.close()
            browser.close()
        print(
            "PASS: dashboard, offers, quotes, stores, VI/EN, invoices, read receipts and 390px layouts; no JavaScript errors."
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
