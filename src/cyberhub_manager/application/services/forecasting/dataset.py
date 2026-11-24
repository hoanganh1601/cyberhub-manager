"""Dataset creation and persistence for offline forecasting."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOM_TYPES = ("STANDARD", "VIP", "COUPLE", "SUPER_VIP")


def is_vietnam_public_holiday(day: date) -> bool:
    """Return fixed-date public holidays used by the first forecasting model.

    Lunar holidays move each year and should be supplied by a future holiday
    calendar table.  Keeping this function explicit avoids silently inventing
    dates in production data.
    """

    return (day.month, day.day) in {(1, 1), (4, 30), (5, 1), (9, 2)}


@dataclass(frozen=True, slots=True)
class DailyObservation:
    day: date
    revenue: float
    customer_count: int
    session_count: int
    standard_sessions: int = 0
    vip_sessions: int = 0
    couple_sessions: int = 0
    super_vip_sessions: int = 0
    standard_revenue: float = 0.0
    vip_revenue: float = 0.0
    couple_revenue: float = 0.0
    super_vip_revenue: float = 0.0
    is_holiday: bool = False
    is_simulated: bool = False

    def __post_init__(self) -> None:
        if self.revenue < 0:
            raise ValueError("revenue must not be negative")
        for field in (
            "customer_count",
            "session_count",
            "standard_sessions",
            "vip_sessions",
            "couple_sessions",
            "super_vip_sessions",
        ):
            if getattr(self, field) < 0:
                raise ValueError(f"{field} must not be negative")
        room_sessions = sum(self.room_sessions.values())
        if room_sessions != self.session_count:
            raise ValueError("room session counts must equal session_count")

    @property
    def room_sessions(self) -> dict[str, int]:
        return {
            "STANDARD": self.standard_sessions,
            "VIP": self.vip_sessions,
            "COUPLE": self.couple_sessions,
            "SUPER_VIP": self.super_vip_sessions,
        }

    @property
    def room_revenue(self) -> dict[str, float]:
        return {
            "STANDARD": self.standard_revenue,
            "VIP": self.vip_revenue,
            "COUPLE": self.couple_revenue,
            "SUPER_VIP": self.super_vip_revenue,
        }

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["day"] = self.day.isoformat()
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DailyObservation":
        payload = dict(value)
        payload["day"] = date.fromisoformat(str(payload["day"]))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class ForecastDataset:
    observations: tuple[DailyObservation, ...]
    source: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if not self.observations:
            raise ValueError("forecast dataset must not be empty")
        days = [item.day for item in self.observations]
        if days != sorted(days) or len(days) != len(set(days)):
            raise ValueError("observations must have unique ascending dates")
        expected = [days[0] + timedelta(days=index) for index in range(len(days))]
        if days != expected:
            raise ValueError("forecast dataset must contain every calendar day")
        simulation_flags = {item.is_simulated for item in self.observations}
        if len(simulation_flags) != 1:
            raise ValueError("real and simulated observations must not be mixed")

    @property
    def is_simulated(self) -> bool:
        return all(item.is_simulated for item in self.observations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source": self.source,
            "is_simulated": self.is_simulated,
            "generated_at": self.generated_at.isoformat(),
            "observations": [item.to_dict() for item in self.observations],
        }

    def save(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output

    @classmethod
    def load(cls, path: str | Path) -> "ForecastDataset":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported forecast dataset schema")
        return cls(
            observations=tuple(
                DailyObservation.from_dict(item)
                for item in payload.get("observations", [])
            ),
            source=str(payload.get("source", "unknown")),
            generated_at=datetime.fromisoformat(payload["generated_at"]),
        )


def _allocate(total: int, shares: tuple[float, ...]) -> tuple[int, ...]:
    raw = [total * share for share in shares]
    allocated = [math.floor(value) for value in raw]
    remainder = total - sum(allocated)
    order = sorted(range(len(raw)), key=lambda index: raw[index] % 1, reverse=True)
    for index in order[:remainder]:
        allocated[index] += 1
    return tuple(allocated)


def generate_demo_dataset(
    *,
    days: int = 180,
    end_day: date | None = None,
    seed: int = 20261116,
) -> ForecastDataset:
    """Generate deterministic, clearly-labelled demo history.

    The values mimic a small cybercafe with stronger Friday/weekend demand,
    gradual growth and different spending levels by room category.
    """

    if not 90 <= days <= 365:
        raise ValueError("demo history must contain between 90 and 365 days")
    end = end_day or (date.today() - timedelta(days=1))
    start = end - timedelta(days=days - 1)
    rng = random.Random(seed)
    observations: list[DailyObservation] = []
    rates = (19_000, 36_000, 44_000, 62_000)

    for index in range(days):
        day = start + timedelta(days=index)
        weekend_factor = (
            1.48 if day.weekday() == 6 else 1.30 if day.weekday() == 5 else 1.0
        )
        friday_factor = 1.16 if day.weekday() == 4 else 1.0
        holiday = is_vietnam_public_holiday(day)
        holiday_factor = 1.42 if holiday else 1.0
        monthly_wave = 1 + 0.08 * math.sin(index * 2 * math.pi / 30.5)
        growth = 1 + 0.0012 * index
        noise = rng.gauss(1.0, 0.075)

        customers = max(
            12,
            round(
                43
                * weekend_factor
                * friday_factor
                * holiday_factor
                * monthly_wave
                * growth
                * noise
            ),
        )
        sessions = max(customers, round(customers * rng.uniform(1.06, 1.22)))
        room_counts = _allocate(sessions, (0.57, 0.24, 0.12, 0.07))
        room_revenues = tuple(
            round(count * rate * rng.uniform(0.88, 1.18), -3)
            for count, rate in zip(room_counts, rates, strict=True)
        )
        observations.append(
            DailyObservation(
                day=day,
                revenue=float(sum(room_revenues)),
                customer_count=customers,
                session_count=sessions,
                standard_sessions=room_counts[0],
                vip_sessions=room_counts[1],
                couple_sessions=room_counts[2],
                super_vip_sessions=room_counts[3],
                standard_revenue=room_revenues[0],
                vip_revenue=room_revenues[1],
                couple_revenue=room_revenues[2],
                super_vip_revenue=room_revenues[3],
                is_holiday=holiday,
                is_simulated=True,
            )
        )

    return ForecastDataset(
        observations=tuple(observations),
        source=f"simulated:{days}-days:seed-{seed}",
        generated_at=datetime.now(timezone.utc),
    )


def load_mysql_dataset(
    conn: Any,
    *,
    store_id: int,
    start_day: date,
    end_day: date,
) -> ForecastDataset:
    """Load privacy-safe daily aggregates from MySQL.

    No customer identity leaves the database. Missing calendar days are filled
    with zeroes so time-series lags remain correct.
    """

    if store_id <= 0:
        raise ValueError("store_id must be positive")
    if start_day > end_day:
        raise ValueError("start_day must not be after end_day")

    from cyberhub_manager.infrastructure.repositories.forecast_repository import daily_forecast_rows

    rows = daily_forecast_rows(conn, store_id=store_id, start_day=start_day, end_day=end_day)

    by_day = {row["local_day"]: row for row in rows}
    observations: list[DailyObservation] = []
    current = start_day
    while current <= end_day:
        row = by_day.get(current, {})
        observations.append(
            DailyObservation(
                day=current,
                revenue=float(row.get("revenue") or 0),
                customer_count=int(row.get("customer_count") or 0),
                session_count=int(row.get("session_count") or 0),
                standard_sessions=int(row.get("standard_sessions") or 0),
                vip_sessions=int(row.get("vip_sessions") or 0),
                couple_sessions=int(row.get("couple_sessions") or 0),
                super_vip_sessions=int(row.get("super_vip_sessions") or 0),
                standard_revenue=float(row.get("standard_revenue") or 0),
                vip_revenue=float(row.get("vip_revenue") or 0),
                couple_revenue=float(row.get("couple_revenue") or 0),
                super_vip_revenue=float(row.get("super_vip_revenue") or 0),
                is_holiday=is_vietnam_public_holiday(current),
                is_simulated=False,
            )
        )
        current += timedelta(days=1)

    return ForecastDataset(
        observations=tuple(observations),
        source=f"mysql:store-{store_id}",
        generated_at=datetime.now(timezone.utc),
    )
