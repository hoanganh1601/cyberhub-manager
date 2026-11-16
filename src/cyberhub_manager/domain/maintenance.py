"""Machine incident state machine."""

from enum import StrEnum

from .exceptions import ConflictError


class IncidentStatus(StrEnum):
    REPORTED = "REPORTED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_PARTS = "WAITING_PARTS"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    CANCELLED = "CANCELLED"


class IncidentSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


ALLOWED_INCIDENT_TRANSITIONS = {
    IncidentStatus.REPORTED: {IncidentStatus.ASSIGNED, IncidentStatus.CANCELLED},
    IncidentStatus.ASSIGNED: {IncidentStatus.IN_PROGRESS, IncidentStatus.CANCELLED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.WAITING_PARTS, IncidentStatus.COMPLETED},
    IncidentStatus.WAITING_PARTS: {IncidentStatus.IN_PROGRESS, IncidentStatus.COMPLETED},
    IncidentStatus.COMPLETED: {IncidentStatus.VERIFIED, IncidentStatus.IN_PROGRESS},
    IncidentStatus.VERIFIED: set(),
    IncidentStatus.CANCELLED: set(),
}


def require_incident_transition(current: str, target: str) -> tuple[IncidentStatus, IncidentStatus]:
    try:
        source, destination = IncidentStatus(current), IncidentStatus(target)
    except ValueError:
        raise ConflictError("Trạng thái sự cố không hợp lệ") from None
    if destination not in ALLOWED_INCIDENT_TRANSITIONS[source]:
        raise ConflictError(f"Không thể chuyển sự cố từ {source.value} sang {destination.value}")
    return source, destination
