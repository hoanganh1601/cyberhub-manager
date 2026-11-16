"""Bounded per-login workspaces for the in-memory web demo."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import secrets
from threading import RLock
from time import monotonic

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.exceptions import ServiceUnavailableError
from cyberhub_manager.services.contracts import ServiceBundle

UTC = timezone.utc


@dataclass
class DemoWorkspace:
    services: ServiceBundle
    actor: EmployeeSession
    expires: float
    lock: RLock = field(default_factory=RLock)


class DemoRegistry:
    """One independent, bounded demo dataset per login; single-worker deployment."""

    def __init__(self, limit: int = 64) -> None:
        self.entries: dict[str, DemoWorkspace] = {}
        self.lock = RLock()
        self.limit = limit

    def get(self, key: str | None) -> DemoWorkspace | None:
        with self.lock:
            now = monotonic()
            for expired in [
                sid for sid, item in self.entries.items() if item.expires <= now
            ]:
                del self.entries[expired]
            return self.entries.get(key or "")

    def add(self, services: ServiceBundle, actor: EmployeeSession) -> str:
        with self.lock:
            self.get(None)
            if len(self.entries) >= self.limit:
                raise ServiceUnavailableError(
                    "Bản demo đang có nhiều người dùng. Vui lòng thử lại sau."
                )
            key = secrets.token_urlsafe(32)
            self.entries[key] = DemoWorkspace(
                services, actor, monotonic() + 8 * 3600
            )
            return key

    def remove(self, key: str | None) -> None:
        with self.lock:
            self.entries.pop(key or "", None)


def build_demo_bundle(*, customer_portal: bool = False) -> ServiceBundle:
    from cyberhub_manager.services.mocks.clock import MockClock
    from cyberhub_manager.services.mocks.factory import build_mock_services

    class RunningClock(MockClock):
        def now(self) -> datetime:
            return datetime.now(UTC)

    return build_mock_services(
        clock=RunningClock(datetime.now(UTC)),
        p1=True,
        customer_offers=customer_portal,
        pos_samples=not customer_portal,
    )
