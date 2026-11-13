"""Kênh gửi thông báo ra ngoài web (worker nền), tách khỏi transaction POS.

Sink nhận một thông điệp đã gồm khóa chống trùng (`idempotency_key`) và chỉ được báo kết quả bằng
hai loại lỗi: `TransientDeliveryError` (thử lại sau) hoặc `PermanentDeliveryError` (dừng hẳn).
Giao ít nhất một lần: sau sự cố giữa lúc gửi và lúc ghi kết quả, thông điệp có thể tới lần nữa,
nên bên nhận phải dùng `idempotency_key` để loại trùng.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 5
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class DeliveryError(Exception):
    """Gốc của mọi lỗi gửi; `str(error)` được lưu vào last_error nên không được chứa bí mật."""


class TransientDeliveryError(DeliveryError):
    """Lỗi tạm thời (mạng, 5xx, 429): worker thử lại theo backoff."""


class PermanentDeliveryError(DeliveryError):
    """Lỗi không thể tự khỏi (4xx, cấu hình sai): worker đánh dấu DEAD, không thử lại."""


class LogSink:
    """Kênh mặc định: chỉ ghi log. Dùng để chạy thử worker mà không cần dịch vụ ngoài."""

    channel = "log"

    def deliver(self, message: Mapping[str, object]) -> None:
        logger.info("Notification %s kind=%s code=%s", message["idempotency_key"], message["kind"], message["code"])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Không đi theo chuyển hướng: POST bị đổi thành GET sẽ làm mất thông báo âm thầm."""

    def redirect_request(self, *args, **kwargs):
        return None


class WebhookSink:
    """POST JSON tới một URL; ký HMAC-SHA256 nếu có secret. Không gửi tên/số điện thoại khách."""

    channel = "webhook"

    def __init__(self, url: str, secret: str | None = None, *, timeout: float = WEBHOOK_TIMEOUT_SECONDS,
                 clock=time.time, opener=None):
        parts = urlsplit(url)
        local = (parts.hostname or "") in LOCAL_HOSTS
        if parts.scheme != "https" and not (parts.scheme == "http" and local):
            raise ValueError("CYBERHUB_NOTIFY_WEBHOOK_URL must be https (http only for localhost)")
        if not parts.hostname:
            raise ValueError("CYBERHUB_NOTIFY_WEBHOOK_URL has no host")
        self._url = url
        self._secret = secret.encode() if secret else None
        self._timeout = timeout
        self._clock = clock
        self._opener = opener or urllib.request.build_opener(_NoRedirect)

    def deliver(self, message: Mapping[str, object]) -> None:
        body = json.dumps(message, ensure_ascii=False, sort_keys=True).encode()
        headers = {"Content-Type": "application/json", "Idempotency-Key": str(message["idempotency_key"]),
                   "User-Agent": "cyberhub-notification-worker"}
        if self._secret:
            stamp = str(int(self._clock()))
            digest = hmac.new(self._secret, stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
            headers["X-CyberHub-Timestamp"] = stamp
            headers["X-CyberHub-Signature"] = f"sha256={digest}"
        request = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                response.read(1)
        except urllib.error.HTTPError as error:
            text = f"HTTP {error.code}"
            if error.code in (408, 425, 429) or error.code >= 500:
                raise TransientDeliveryError(text) from None
            raise PermanentDeliveryError(text) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise TransientDeliveryError(f"network error: {type(error).__name__}") from None


def sink_from_env(env: Mapping[str, str] | None = None):
    """Chọn kênh theo CYBERHUB_NOTIFY_SINK (`log` mặc định hoặc `webhook`); cấu hình sai thì ValueError."""
    env = os.environ if env is None else env
    name = (env.get("CYBERHUB_NOTIFY_SINK") or "log").strip().lower()
    if name == "log":
        return LogSink()
    if name == "webhook":
        url = (env.get("CYBERHUB_NOTIFY_WEBHOOK_URL") or "").strip()
        if not url:
            raise ValueError("CYBERHUB_NOTIFY_WEBHOOK_URL is required when CYBERHUB_NOTIFY_SINK=webhook")
        return WebhookSink(url, (env.get("CYBERHUB_NOTIFY_WEBHOOK_SECRET") or None))
    raise ValueError("CYBERHUB_NOTIFY_SINK must be 'log' or 'webhook'")
