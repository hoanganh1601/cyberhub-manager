"""Run reservation warning/expiry maintenance outside web request processes."""

from __future__ import annotations

import argparse
import logging
import time

from dotenv import load_dotenv

from cyberhub_manager.services.menu_service import MenuService


def main(argv=None):
    parser = argparse.ArgumentParser(description="POS stock hold maintenance")
    parser.add_argument("--once", action="store_true", help="process one batch and exit")
    parser.add_argument("--interval", type=int, default=30, help="poll interval in seconds")
    args = parser.parse_args(argv)
    if not 5 <= args.interval <= 3600:
        parser.error("--interval must be between 5 and 3600 seconds")
    load_dotenv()
    service = MenuService()
    while True:
        try:
            result = service.maintain_holds()
            logging.info("POS holds: warned=%s expired=%s", result["warned"], result["expired"])
        except Exception:
            logging.exception("POS hold maintenance failed; next run will retry")
            if args.once:
                raise
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
