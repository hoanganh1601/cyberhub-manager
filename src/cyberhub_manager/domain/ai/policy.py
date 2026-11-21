"""Assistant admission policy types, independent of persistence."""
from dataclasses import dataclass

class AssistantQuotaExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("assistant request limit exceeded")


@dataclass(frozen=True)
class AssistantLimits:
    per_minute: int = 10
    per_day: int = 100
    global_per_day: int = 1000
    retention_days: int = 30

    def __post_init__(self) -> None:
        for value in (self.per_minute, self.per_day, self.global_per_day, self.retention_days):
            if type(value) is not int or value <= 0:
                raise ValueError("assistant limits must be positive integers")
