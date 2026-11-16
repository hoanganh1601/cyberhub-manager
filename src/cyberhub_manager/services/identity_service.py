"""Resolve a trusted employee principal from server-side session identifiers."""

from __future__ import annotations

from dataclasses import replace

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.p1_repository import P1Repository

from .access import operating_actor
from .db_errors import translate_db_errors


class IdentityService:
    """Revalidate employee status, credential version, and operating store."""

    def __init__(self, auth_repo=None, store_repo=None, transaction_factory=None):
        if transaction_factory is None:
            from cyberhub_manager.database.transaction import transaction

            transaction_factory = transaction
        self._auth = auth_repo or AuthRepository()
        self._stores = store_repo or P1Repository()
        self._transaction = transaction_factory

    def resolve(
        self, employee_id: object, auth_version: object, store_id: object
    ) -> EmployeeSession | None:
        if (
            type(employee_id) is not int
            or employee_id <= 0
            or type(store_id) is not int
            or store_id <= 0
            or type(auth_version) is not int
            or auth_version < 0
        ):
            return None
        with translate_db_errors(), self._transaction() as conn:
            actor = self._auth.get_active_session_by_id(conn, employee_id)
            if actor is None or actor.auth_version != auth_version:
                return None
            if actor.store_id == store_id:
                return actor
            return operating_actor(
                conn,
                self._auth,
                replace(actor, store_id=store_id),
                store_repo=self._stores,
            )
