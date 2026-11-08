"""Browser coverage for account-menu navigation, real image upload and membership UI."""

import argparse
from io import BytesIO
from pathlib import Path
from threading import Thread
from PIL import Image, ImageDraw, ImageFont
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
    photo = Image.new("RGB", (600, 420), "#123e67")
    draw = ImageDraw.Draw(photo)
    for y in range(420):
        draw.line((0, y, 600, y), fill=(10, 70 + y // 4, 100 + y // 3))
    font = ImageFont.load_default(size=130)
    draw.text((300, 210), "VA", font=font, anchor="mm", fill="white")
    output = BytesIO()
    photo.save(output, format="PNG")
    image_bytes = output.getvalue()
    app = create_app(
        dict(TESTING=True, WEB_MODE="demo", SECRET_KEY="membership-browser-only")
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
            page.goto(f"http://127.0.0.1:{server.server_port}/customer")
            page.locator("[name=username]").fill("nguyenvanan")
            page.locator("[name=password]").fill("demo123")
            page.locator("#login-form button[type=submit]").click()
            expect(page.locator("#p3-account-toggle")).to_be_visible()
            assert page.locator(".pc-nav [data-tab=profile]").count() == 0

            def capture(name):
                if args.screenshots:
                    page.screenshot(
                        path=str(args.screenshots / (name + ".png")), full_page=True
                    )

            page.locator("#p3-account-toggle").click()
            expect(page.locator("#p3-account-menu")).to_be_visible()
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Escape")
            expect(page.locator("#p3-account-menu")).to_be_hidden()
            page.locator("#p3-account-toggle").click()
            page.locator("#p3-account-menu [data-p3=avatar]").click()
            page.locator("#p3-avatar-file").set_input_files(
                dict(name="avatar.png", mimeType="image/png", buffer=image_bytes)
            )
            expect(page.locator(".p3-photo-preview>img")).to_be_visible()
            capture("avatar-editor-desktop")
            page.locator("[data-avatar-save]").click()
            expect(page.locator("#p3-account-toggle img")).to_be_visible()
            expect(page.locator(".p3-avatar-dialog")).to_have_count(0)
            while page.locator("#notifications .toast button").count():
                page.locator("#notifications .toast button").first.click()
            page.locator("#p3-account-toggle").click()
            expect(page.locator("#p3-account-menu")).to_be_visible()
            capture("account-menu-desktop")
            page.locator("#p3-account-menu [data-tab=profile]").click()
            expect(page.locator(".p3-profile-avatar img")).to_be_visible()
            capture("profile-desktop")
            page.locator(".pc-nav [data-tab=member]").click()
            expect(page.locator(".p3-hero-points strong")).to_have_text("5")
            expect(page.locator(".p3-tier-list article.selected")).to_contain_text(
                "Đồng"
            )
            capture("membership-desktop")
            page.locator(".pc-nav [data-tab=offers]").click()
            expect(page.locator(".pc-offer .badge.cyan")).to_contain_text(
                "Ưu đãi dành riêng"
            )
            page.locator('[data-portal=tier][data-amount="300000"]').click()
            expect(page.locator(".pc-credit")).to_contain_text("375.000 VND")
            capture("personal-offer-desktop")
            page.locator("[data-action=language][data-lang=en]").click()
            page.locator(".pc-nav [data-tab=member]").click()
            expect(page.locator("h1")).to_have_text("Membership")
            page.set_viewport_size(dict(width=390, height=844))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture("membership-mobile")
            page.locator("#p3-account-toggle").click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            capture("account-menu-mobile")
            page.locator("#p3-account-menu [data-p3=avatar]").click()
            page.locator("[data-avatar-remove]").click()
            expect(page.locator("#p3-account-toggle img")).to_have_count(0)
            page.reload()
            expect(page.locator(".p3-member-teaser")).to_be_visible()
            context.close()
            context = browser.new_context(viewport=dict(width=1440, height=1000))
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.locator("[name=username]").fill("admin01")
            page.locator("[name=password]").fill("demo123")
            page.locator("#login-form button[type=submit]").click()
            page.locator("[data-action=navigate][data-page=promotions]").click()
            page.locator("[data-loyalty-settings]").click()
            page.locator("#p3-settings-form [name=unit_amount]").fill("5000")
            capture("membership-settings-desktop")
            page.locator("#p3-settings-form button[type=submit]").click()
            expect(page.locator(".p3-settings-dialog")).to_have_count(0)
            page.locator("[data-p1=new]").click()
            expect(page.locator("#modal [name=minimum_tier]")).to_be_visible()
            expect(
                page.locator("#modal [name=target_customer_id] option")
            ).to_have_count(6)
            page.locator("#modal [name=code]").fill("MEMBERTEST")
            page.locator("#modal [name=name]").fill("Member reward")
            page.locator("#modal [name=minimum_tier]").select_option("SILVER")
            page.locator("#modal [name=target_customer_id]").select_option("1")
            page.locator("#modal-form button[type=submit]").click()
            expect(page.locator("#modal")).not_to_be_visible()
            assert not errors, errors
            context.close()
            browser.close()
        print(
            "PASS: avatar menu/keyboard, upload/delete, profile navigation, points/tier, personalized quote, admin settings/audience, EN and mobile."
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
