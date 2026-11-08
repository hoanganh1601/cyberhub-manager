"""Render the real Login in VI/EN/error/minimum size and save window-only PNGs.

Usage: python scripts/capture_login_preview.py --output-dir <preview directory>
This uses a fresh mock bundle and closes the preview after capturing it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import ImageGrab

from cyberhub_manager.app import CyberHubApp
from cyberhub_manager.ui.background import ImmediateTaskRunner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    app = CyberHubApp(mock=True, runner=ImmediateTaskRunner())
    app.geometry("1280x720+20+20")
    app.lift()
    app.attributes("-topmost", True)

    def capture(name: str) -> None:
        app.update_idletasks()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        image = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()))
        path = args.output_dir / name
        image.save(path)
        print(path, flush=True)

    def english() -> None:
        capture("login-vi.png")
        app.current_view.set_language("en")
        app.after(250, error)

    def error() -> None:
        capture("login-en.png")
        view = app.current_view
        view.set_language("vi")
        view.username.entry.insert(0, "quanly01")
        view.password.entry.insert(0, "wrong-password")
        view.submit()
        app.after(250, minimum)

    def minimum() -> None:
        capture("login-auth-error.png")
        app.geometry("1100x650+20+20")
        app.after(400, finish)

    def finish() -> None:
        capture("login-1100x650.png")
        app.destroy()

    app.after(800, english)
    app.mainloop()


if __name__ == "__main__":
    main()
