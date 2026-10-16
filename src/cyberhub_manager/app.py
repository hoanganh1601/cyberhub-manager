"""HA-01 — Hoàng Anh: placeholder cho composition root/entry point."""

"""Application composition root and entry point."""

import customtkinter as ctk

from cyberhub_manager.config import load_settings


def main() -> None:
    load_settings() # đọc cấu hình

    app = ctk.CTk() # tạo cửa sổ DeskTop tối thiểu
    app.title("CyberHub Manager")
    app.geometry("960x600")
    app.mainloop()


if __name__ == "__main__":
    main()