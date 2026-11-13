"""Run reservation warning/expiry maintenance outside web request processes.

    python -m scripts.run_pos_maintenance --interval 30      # chạy liên tục
    python -m scripts.run_pos_maintenance --once             # một lượt rồi thoát (mã 1 nếu lỗi)
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from cyberhub_manager.worker import run_worker


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="POS stock hold maintenance")
    parser.add_argument("--once", action="store_true", help="process one batch and exit")
    parser.add_argument("--interval", type=int, default=30, help="poll interval in seconds")
    parser.add_argument("--batch", type=int, default=100, help="max orders handled per run (1-500)")
    args = parser.parse_args(argv)
    if not 5 <= args.interval <= 3600:
        parser.error("--interval must be between 5 and 3600 seconds")
    if not 1 <= args.batch <= 500:
        parser.error("--batch must be between 1 and 500")
    load_dotenv()
    from cyberhub_manager.services.menu_service import MenuService

    service = MenuService()
    return run_worker("pos-holds", lambda: service.maintain_holds(limit=args.batch),
                      interval=args.interval, once=args.once, install_signals=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main())
