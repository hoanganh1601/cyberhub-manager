"""Gửi thông báo trong sổ customer_notification_events ra kênh ngoài web (log hoặc webhook).

    python -m scripts.run_notification_worker --interval 15
    python -m scripts.run_notification_worker --once

Kênh chọn bằng CYBERHUB_NOTIFY_SINK (`log` mặc định, hoặc `webhook` kèm CYBERHUB_NOTIFY_WEBHOOK_URL
và tùy chọn CYBERHUB_NOTIFY_WEBHOOK_SECRET). Xem docs/POS_INVENTORY_LIFECYCLE.md §9.
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from cyberhub_manager.worker import run_worker


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Customer notification dispatcher")
    parser.add_argument("--once", action="store_true", help="process one batch and exit")
    parser.add_argument("--interval", type=int, default=15, help="poll interval in seconds")
    parser.add_argument("--batch", type=int, default=20, help="deliveries per run (1-500)")
    parser.add_argument("--max-attempts", type=int, default=6, help="give up (DEAD) after this many attempts")
    parser.add_argument("--lookback-hours", type=int, default=24,
                        help="only deliver events created within this many hours")
    args = parser.parse_args(argv)
    if not 5 <= args.interval <= 3600:
        parser.error("--interval must be between 5 and 3600 seconds")
    if not 1 <= args.batch <= 500:
        parser.error("--batch must be between 1 and 500")
    load_dotenv()
    from cyberhub_manager.services.notification_dispatcher import NotificationDispatcher
    from cyberhub_manager.services.notification_sinks import sink_from_env

    try:
        dispatcher = NotificationDispatcher(sink_from_env(), max_attempts=args.max_attempts,
                                            lookback_hours=args.lookback_hours)
    except ValueError as error:
        parser.error(str(error))
    return run_worker("notifications", lambda: dispatcher.run_once(limit=args.batch),
                      interval=args.interval, once=args.once, install_signals=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main())
