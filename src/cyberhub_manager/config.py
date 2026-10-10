"""HA-01 — Hoàng Anh: placeholder cho cấu hình đọc từ environment."""

"""Load application settings from environment variables."""

from dataclasses import dataclass, field
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str = field(repr=False)
    log_level: str = "INFO"


def _required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def load_settings() -> Settings:
    raw_port = os.getenv("MYSQL_PORT", "3306")

    try:
        mysql_port = int(raw_port)
    except ValueError as error:
        raise RuntimeError("MYSQL_PORT must be an integer") from error

    return Settings(
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=mysql_port,
        mysql_database=_required("MYSQL_DATABASE"),
        mysql_user=_required("MYSQL_USER"),
        mysql_password=_required("MYSQL_PASSWORD"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )