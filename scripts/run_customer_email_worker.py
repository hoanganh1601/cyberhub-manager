"""Send committed customer activation/recovery mail from the MySQL outbox.

Run beside the web server: python -m scripts.run_customer_email_worker
Use --once to process one due item and exit.
"""

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import os
import smtplib
from time import sleep

from dotenv import load_dotenv

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.repositories.customer_email_repository import CustomerEmailRepository
from cyberhub_manager.services.customer_email_service import token_from_nonce


def settings():
    load_dotenv()
    host = os.getenv("CYBERHUB_SMTP_HOST", "")
    user = os.getenv("CYBERHUB_SMTP_USERNAME", "")
    password = os.getenv("CYBERHUB_SMTP_PASSWORD", "")
    sender = os.getenv("CYBERHUB_SMTP_FROM", "")
    origin = os.getenv("CYBERHUB_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
    port = int(os.getenv("CYBERHUB_SMTP_PORT", "465"))
    if not all((host, user, password, sender)) or port not in (465, 587):
        raise RuntimeError("Configure CYBERHUB_SMTP_HOST, PORT, USERNAME, PASSWORD and FROM")
    if not origin.startswith("https://") and not origin.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise RuntimeError("CYBERHUB_PUBLIC_URL must use HTTPS outside localhost")
    token_from_nonce("00" * 32)  # Check the stable signing secret before claiming mail.
    return host, port, user, password, sender, origin


def send_message(item, config):
    host, port, user, password, sender, origin = config
    purpose = item["purpose"]
    page = "activate" if purpose == "ACTIVATE" else "reset-password"
    link = f"{origin}/{page}#token={token_from_nonce(item['nonce'])}"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = item["email"]
    message["Subject"] = "CyberHub - Kich hoat tai khoan" if purpose == "ACTIVATE" else "CyberHub - Dat lai mat khau"
    message.set_content(
        f"Xin chào {item['full_name']},\n\n"
        + (f"Tên đăng nhập: {item['username']}\n" if purpose == "ACTIVATE" else "")
        + f"Mở liên kết để {'kích hoạt tài khoản' if purpose == 'ACTIVATE' else 'đặt lại mật khẩu'}:\n{link}\n\n"
        + "Liên kết có thời hạn. Nếu bạn không yêu cầu, hãy bỏ qua email này.\nCyberHub"
    )
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)


def run_once(repo, config):
    with transaction() as conn:
        item = repo.claim_due(conn)
    if item is None:
        return False
    if item["used_at"] is not None or item["expires_at"] <= datetime.now(timezone.utc).replace(tzinfo=None):
        with transaction() as conn:
            repo.cancel_delivery(conn, item["id"])
        return True
    try:
        send_message(item, config)
    except (OSError, smtplib.SMTPException) as exc:
        with transaction() as conn:
            repo.finish_delivery(conn, item["id"], success=False,
                                 error=type(exc).__name__,
                                 retry_seconds=min(3600, 60 * 2 ** min(item["attempts"], 5)))
    else:
        with transaction() as conn:
            repo.finish_delivery(conn, item["id"], success=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = settings()
    repo = CustomerEmailRepository()
    if args.once:
        run_once(repo, config)
        return
    while True:
        if not run_once(repo, config):
            sleep(5)


if __name__ == "__main__":
    main()
