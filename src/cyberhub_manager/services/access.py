"""Resolve a trusted employee in an operating store; never trust a submitted role."""

from dataclasses import replace

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.repositories.p1_repository import P1Repository


def operating_actor(conn, auth_repo, requested: EmployeeSession) -> EmployeeSession:
    current = auth_repo.get_active_session_by_id(conn, requested.employee_id)
    if current is None or current.role != requested.role:
        raise PermissionDeniedError()
    if current.store_id == requested.store_id:
        return current
    if current.role != Role.ADMIN:
        raise PermissionDeniedError()
    target = P1Repository().store(conn, requested.store_id, lock="share")
    if target is None or target.status != "ACTIVE":
        raise PermissionDeniedError()
    return replace(
        current, store_id=target.id, store_code=target.code, store_name=target.name
    )
