"""Chromium checks for five-minute snapshots, usage charts, profile and password edits.

Optional tool dependency: Playwright + Chromium. Uses only an ephemeral demo server.
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
        dict(TESTING=True, WEB_MODE="demo", SECRET_KEY="phase2-browser-local-only")
    )
    server = make_server("127.0.0.1", 0, app, request_handler=QuietHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport=dict(width=1440, height=1000))
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            availability_requests = []
            page.on(
                "request",
                lambda r: (
                    availability_requests.append(r.url)
                    if "/api/portal/availability?" in r.url
                    else None
                ),
            )
            page.clock.install()
            page.goto(f"http://127.0.0.1:{server.server_port}/customer")
            page.locator("[name=username]").fill("nguyenvanan")
            page.locator("[name=password]").fill("demo123")
            page.locator("#login-form button[type=submit]").click()
            expect(page.locator(".pc-stats")).to_be_visible()

            def tab(name):
                if name=='profile':
                    page.locator('#p3-account-toggle').click()
                    page.locator('#p3-account-menu [data-tab="profile"]').click()
                    expect(page.locator('.p2-profile-identity')).to_be_visible()
                    return
                page.locator(f'.pc-nav [data-tab="{name}"]').click()
                expect(page.locator(f'.pc-nav [data-tab="{name}"]')).to_have_attribute(
                    "aria-current", "page"
                )

            def screenshot(name):
                if args.screenshots:
                    while (
                        not page.locator("dialog[open]").count()
                        and page.locator("#notifications .toast button").count()
                    ):
                        page.locator("#notifications .toast button").first.click()
                    page.screenshot(
                        path=str(args.screenshots / (name + ".png")), full_page=True
                    )

            tab("availability")
            expect(page.locator(".p2-room.standard .p2-room-number")).to_have_text("5")
            expect(page.locator(".p2-room.vip .p2-room-number")).to_have_text("8")
            for category, amount in (
                ("standard", "10.000 VND"),
                ("vip", "20.000 VND"),
                ("couple", "25.000 VND"),
                ("super_vip", "35.000 VND"),
            ):
                expect(page.locator(f".p2-room.{category} .p2-room-price")).to_contain_text(amount)
            assert len(availability_requests) == 1
            screenshot("availability-desktop")
            page.clock.fast_forward(299000)
            assert len(availability_requests) == 1, "Must not poll before five minutes"
            with page.expect_response(lambda r: "/api/portal/availability?" in r.url):
                page.clock.fast_forward(1000)
            expect(page.locator(".p2-room.vip .p2-room-number")).to_have_text("8")
            assert len(availability_requests) == 2
            tab("usage")
            expect(page.locator(".p2-usage-chart")).to_be_visible()
            expect(page.locator(".pc-stat").first).to_contain_text("5 giờ")
            screenshot("usage-desktop")
            tab("availability")
            assert (
                len(availability_requests) == 2
            ), "Returning to a fresh snapshot must use the cache"
            page.locator("#p2-availability-store").select_option("2")
            expect(page.locator(".p2-room.standard .p2-room-number")).to_have_text("0")
            expect(page.locator(".p2-room.vip .p2-room-number")).to_have_text("0")
            assert page.locator(".p2-room.vip .p2-room-price").count() == 0
            tab("profile")
            expect(page.locator(".p2-profile-identity h2")).to_have_text(
                "Nguyễn Văn An"
            )
            screenshot("profile-desktop")
            form = page.locator("#p2-profile-form")
            form.locator("[name=full_name]").fill("Nguyễn Văn An Updated")
            form.locator("[name=phone]").fill("0912345678")
            form.locator("[name=current_password]").fill("wrong")
            form.locator("button[type=submit]").click()
            expect(form.locator(".p2-form-error")).to_contain_text("Mật khẩu hiện tại")
            form.locator("[name=current_password]").fill("demo123")
            form.locator("button[type=submit]").click()
            expect(page.locator(".p2-profile-identity h2")).to_have_text(
                "Nguyễn Văn An Updated"
            )
            old_context = browser.new_context()
            old_context.add_cookies(context.cookies())
            password = page.locator("#p2-password-form")
            password.locator("[name=current_password]").fill("demo123")
            password.locator("[name=new_password]").fill("new-password123")
            password.locator("[name=confirmation]").fill("new-password123")
            password.locator("button[type=submit]").click()
            expect(
                page.locator("#p2-password-form [name=current_password]")
            ).to_have_value("")
            assert (
                old_context.request.get(
                    f"http://127.0.0.1:{server.server_port}/api/portal/profile"
                ).status
                == 403
            )
            old_context.close()
            page.locator("[data-action=language][data-lang=en]").click()
            expect(page.locator("#p2-password-form")).to_contain_text(
                "Current password"
            )
            for name in ("availability", "usage", "profile"):
                tab(name)
                assert "undefined" not in page.locator("#pc-main").inner_text()
            page.set_viewport_size(dict(width=390, height=844))
            for name in ("availability", "usage", "profile"):
                tab(name)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), name
                screenshot(name + "-mobile")
            context.close()
            # Staff configuration is a separate demo workspace.
            context = browser.new_context(viewport=dict(width=1440, height=1000))
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.locator("[name=username]").fill("admin01")
            page.locator("[name=password]").fill("demo123")
            page.locator("#login-form button[type=submit]").click()
            page.locator("[data-action=navigate][data-page=machines]").click()
            page.locator("[data-room-settings]").click()
            expect(page.locator(".p2-room-dialog")).to_be_visible()
            page.locator('[data-room-machine="1"]').select_option("VIP")
            expect(page.locator('[data-room-machine="1"]')).to_have_attribute(
                "data-original", "VIP"
            )
            expect(page.locator(".p2-room-feedback")).to_contain_text(
                "Đã cập nhật loại phòng"
            )
            expect(page.locator('[data-room-machine="2"]')).to_be_disabled()
            screenshot("room-settings-desktop")
            assert not errors, errors
            context.close()
            browser.close()
        print(
            "PASS: five-minute polling/cache, room prices and counts, store switch, usage, profile, password revocation, VI/EN, mobile and manager room settings."
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
