"""Store-scoped administration shared by both clients, including audit and RBAC."""

from dataclasses import replace
from datetime import datetime, timezone
import re

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.p1 import Permission, Promotion, can
from cyberhub_manager.repositories.p1_repository import P1Repository
from cyberhub_manager.security import hash_password
from .p1_runtime import errors, retry_on_transient
from cyberhub_manager.domain.loyalty import TIERS, LoyaltySettings


def text(value, key, minimum=1, maximum=100):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValidationError(
            field_errors={key: f"Nhập từ {minimum} đến {maximum} ký tự"}
        )
    return value.strip()


def choice(value, key, options):
    if value not in options:
        raise ValidationError(field_errors={key: "Lựa chọn không hợp lệ"})
    return value


class ManagementService:
    def loyalty_settings(self, actor):
        with self._errors(), self._transaction() as conn:
            self._actor(conn, actor)
            return self._repo.loyalty_settings(conn)

    @retry_on_transient
    def update_loyalty_settings(self, actor, settings):
        if (
            not isinstance(settings, LoyaltySettings)
            or type(settings.enabled) is not bool
        ):
            raise ValidationError(field_errors={"enabled": "Trạng thái không hợp lệ"})
        if (
            type(settings.unit_amount) is not int
            or not 1 <= settings.unit_amount <= 100_000_000
        ):
            raise ValidationError(
                field_errors={"unit_amount": "Nhập số tiền từ 1 đến 100.000.000 VND"}
            )
        if (
            any(
                type(x) is not int
                for x in (
                    settings.silver_spend,
                    settings.gold_spend,
                    settings.platinum_spend,
                )
            )
            or not 0
            < settings.silver_spend
            < settings.gold_spend
            < settings.platinum_spend
            <= 1_000_000_000_000
        ):
            raise ValidationError(
                field_errors={"platinum_spend": "Các mốc hạng phải tăng dần, lớn hơn 0"}
            )
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor)
            if actor.role != Role.ADMIN:
                raise PermissionDeniedError()
            current = self._repo.loyalty_settings(conn, lock=True)
            if type(settings.version) is not int or settings.version != current.version:
                raise ConflictError("Cấu hình đã thay đổi. Vui lòng tải lại")
            result = replace(settings, version=current.version + 1)
            self._repo.save_loyalty_settings(conn, result)
            self._repo.audit(conn, actor, "LOYALTY_SETTINGS_SAVE", 1)
            return result

    def list_machine_rooms(self, actor):
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.OPERATE)
            return self._repo.list_machine_rooms(conn, actor.store_id)

    @retry_on_transient
    def set_machine_room(self, actor, machine_id, room_type):
        if (
            type(machine_id) is not int
            or machine_id <= 0
            or room_type not in ("STANDARD", "VIP")
        ):
            raise ValidationError(
                field_errors={"room_type": "Chọn phòng thường hoặc VIP"}
            )
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_MACHINES)
            machine = self._repo.room_machine(conn, machine_id)
            if not machine or not machine["is_active"]:
                raise NotFoundError()
            if machine["store_id"] != actor.store_id:
                raise PermissionDeniedError()
            if machine["status"] == "IN_USE" or machine["active_session"]:
                raise ConflictError("Chỉ phân phòng khi máy không có phiên đang chạy")
            self._repo.set_machine_room(conn, machine_id, room_type)
            self._repo.audit(conn, actor, "MACHINE_ROOM_SET", machine_id)
            return dict(machine_id=machine_id, room_type=room_type)

    def validate_actor(self, actor):
        with self._errors(), self._transaction() as conn:
            return self._actor(conn, actor)

    def __init__(
        self, repo=None, auth_repo=None, transaction_factory=None, actor_provider=None
    ):
        self._memory = hasattr(repo, "resolve_actor")
        if not self._memory:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.auth_repository import AuthRepository

            transaction_factory = transaction_factory or transaction
            auth_repo = auth_repo or AuthRepository()
        self._repo = repo or P1Repository()
        self._auth = auth_repo
        self._transaction = transaction_factory
        self._actor_provider = actor_provider

    def _errors(self):
        return errors(self._memory)

    def _actor(self, conn, actor, permission=None):
        if actor is None:
            raise PermissionDeniedError()
        if not hasattr(self._repo, "resolve_actor"):
            from .access import operating_actor

            logged_in = self._actor_provider() if self._actor_provider else None
            if (
                logged_in is None
                or logged_in.employee_id != actor.employee_id
                or logged_in.store_id != actor.store_id
            ):
                raise PermissionDeniedError()
        # Memory repository implements the same trust boundary against its own records.
        current = (
            self._repo.resolve_actor(actor)
            if hasattr(self._repo, "resolve_actor")
            else operating_actor(conn, self._auth, actor)
        )
        if permission and not can(current.role, permission):
            raise PermissionDeniedError()
        return current

    def list_stores(self, actor):
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor)
            return self._repo.list_stores(
                conn, None if actor.role == Role.ADMIN else actor.store_id
            )

    def switch_store(self, actor, store_id):
        if type(store_id) is not int or store_id <= 0:
            raise ValidationError(field_errors={"store_id": "Cơ sở không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor)
            if store_id != current.store_id and not can(
                current.role, Permission.SWITCH_STORE
            ):
                raise PermissionDeniedError()
            store = self._repo.store(conn, store_id, lock="share")
            if store is None or store.status != "ACTIVE":
                raise ConflictError("Cơ sở không còn hoạt động")
            switched = replace(
                current, store_id=store.id, store_code=store.code, store_name=store.name
            )
            if hasattr(self._repo, "resolve_actor"):
                self._repo.resolve_actor(switched)
            return switched

    @retry_on_transient
    def save_store(self, actor, store_id, code, name, address, status="ACTIVE"):
        code, name, address = (
            text(code, "code", 1, 20),
            text(name, "name"),
            text(address, "address", 1, 255),
        )
        choice(status, "status", ("ACTIVE", "INACTIVE"))
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_STORES)
            if store_id is not None:
                old = self._repo.store(conn, store_id, lock=True)
                if old is None:
                    raise NotFoundError()
                if status != "ACTIVE" and (
                    store_id == actor.store_id
                    or self._repo.has_active_sessions(conn, store_id)
                ):
                    raise ConflictError(
                        "Không thể ngừng cơ sở đang sử dụng hoặc còn phiên hoạt động"
                    )
                if status != "ACTIVE" and any(
                    e.role == "ADMIN" and e.status == "ACTIVE"
                    for e in self._repo.list_employees(conn, store_id)
                ):
                    raise ConflictError(
                        "Chuyển quản trị viên sang cơ sở khác trước khi ngừng hoạt động"
                    )
            if any(
                s.code.casefold() == code.casefold() and s.id != store_id
                for s in self._repo.list_stores(conn)
            ):
                raise ConflictError(field_errors={"code": "Mã cơ sở đã tồn tại"})
            result = self._repo.save_store(conn, store_id, code, name, address, status)
            self._repo.audit(conn, actor, "STORE_SAVE", result.id)
            return result

    def list_employees(self, actor):
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_EMPLOYEES)
            return self._repo.list_employees(
                conn, None if actor.role == Role.ADMIN else actor.store_id
            )

    @retry_on_transient
    def save_employee(
        self,
        actor,
        employee_id,
        store_id,
        full_name,
        username,
        role="STAFF",
        status="ACTIVE",
        password="",
    ):
        name, username = text(full_name, "full_name", 2), text(
            username, "username", 4, 30
        )
        if not re.fullmatch(r"[A-Za-z0-9_.]{4,30}", username):
            raise ValidationError(
                field_errors={"username": "Tên đăng nhập không hợp lệ"}
            )
        choice(role, "role", ("ADMIN", "MANAGER", "STAFF"))
        choice(status, "status", ("ACTIVE", "INACTIVE", "LOCKED"))
        if employee_id is None or password:
            if (
                not isinstance(password, str)
                or len(password) < 6
                or len(password.encode()) > 72
            ):
                raise ValidationError(
                    field_errors={
                        "password": "Mật khẩu tối thiểu 6 ký tự, tối đa 72 byte"
                    }
                )
        password_hash = hash_password(password) if password else None
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_EMPLOYEES)
            employees = self._repo.list_employees(conn, lock=True)
            old = next((e for e in employees if e.id == employee_id), None)
            if employee_id is not None and old is None:
                raise NotFoundError()
            if actor.role != Role.ADMIN and (
                store_id != actor.store_id
                or role != "STAFF"
                or old
                and (old.store_id != actor.store_id or old.role != "STAFF")
            ):
                raise PermissionDeniedError()
            if employee_id == actor.employee_id and (
                role != str(actor.role)
                or status != "ACTIVE"
                or store_id != old.store_id
            ):
                raise ConflictError(
                    "Không thể tự khóa, chuyển cơ sở hoặc thay đổi quyền của chính mình"
                )
            if (
                old
                and old.role == "ADMIN"
                and old.status == "ACTIVE"
                and (role != "ADMIN" or status != "ACTIVE")
            ):
                if (
                    sum(e.role == "ADMIN" and e.status == "ACTIVE" for e in employees)
                    <= 1
                ):
                    raise ConflictError(
                        "Hệ thống phải còn ít nhất một quản trị viên hoạt động"
                    )
            store = self._repo.store(conn, store_id, lock="share")
            if store is None or store.status != "ACTIVE":
                raise ValidationError(
                    field_errors={"store_id": "Chọn cơ sở đang hoạt động"}
                )
            if any(
                e.username.casefold() == username.casefold() and e.id != employee_id
                for e in employees
            ):
                raise ConflictError(
                    field_errors={"username": "Tên đăng nhập đã tồn tại"}
                )
            result = self._repo.save_employee(
                conn,
                employee_id,
                (store_id, name, username, role, status),
                password_hash,
            )
            self._repo.audit(conn, actor, "EMPLOYEE_SAVE", result.id)
            return result

    def list_promotions(self, actor):
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor)
            return self._repo.list_promotions(
                conn, None if actor.role == Role.ADMIN else actor.store_id
            )

    @retry_on_transient
    def save_promotion(self, actor, policy: Promotion):
        text(policy.code, "code", 1, 20)
        text(policy.name, "name")
        if (
            type(policy.minimum_amount) is not int
            or not 1 <= policy.minimum_amount <= 100_000_000
        ):
            raise ValidationError(
                field_errors={"minimum_amount": "Mốc nạp từ 1 đến 100.000.000 VND"}
            )
        if (
            type(policy.bonus_percent) is not int
            or not 0 <= policy.bonus_percent <= 100
        ):
            raise ValidationError(
                field_errors={"bonus_percent": "Phần trăm từ 0 đến 100"}
            )
        if (
            any(
                not isinstance(d, datetime) or d.utcoffset() is None
                for d in (policy.starts_at, policy.ends_at)
            )
            or policy.ends_at <= policy.starts_at
        ):
            raise ValidationError(
                field_errors={
                    "ends_at": "Thời gian kết thúc phải sau bắt đầu và có múi giờ"
                }
            )
        if type(policy.is_active) is not bool:
            raise ValidationError(field_errors={"is_active": "Trạng thái không hợp lệ"})
        if (
            policy.minimum_tier not in TIERS
            or type(policy.minimum_points) is not int
            or not 0 <= policy.minimum_points <= 1_000_000_000
        ):
            raise ValidationError(
                field_errors={"minimum_points": "Hạng hoặc mốc điểm không hợp lệ"}
            )
        if policy.target_customer_id is not None and (
            type(policy.target_customer_id) is not int or policy.target_customer_id <= 0
        ):
            raise ValidationError(
                field_errors={"target_customer_id": "Khách hàng không hợp lệ"}
            )
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_PROMOTIONS)
            if (
                policy.target_customer_id is not None
                and not self._repo.target_customer_exists(
                    conn, policy.target_customer_id
                )
            ):
                raise ValidationError(
                    field_errors={"target_customer_id": "Không tìm thấy khách hàng"}
                )
            policies = self._repo.list_promotions(conn, lock=True)
            old = next((p for p in policies if p.id == policy.id), None)
            if policy.id and old is None:
                raise NotFoundError()
            if actor.role != Role.ADMIN and (
                policy.store_id != actor.store_id
                or old
                and old.store_id != actor.store_id
            ):
                raise PermissionDeniedError()
            if policy.store_id is not None:
                store = self._repo.store(conn, policy.store_id, lock="share")
                if store is None or store.status != "ACTIVE":
                    raise ValidationError(
                        field_errors={"store_id": "Cơ sở không hợp lệ"}
                    )
            for p in policies:
                if p.id == policy.id:
                    continue
                if p.code.casefold() == policy.code.casefold():
                    raise ConflictError(
                        field_errors={"code": "Mã khuyến mãi đã tồn tại"}
                    )
                if (
                    p.is_active
                    and policy.is_active
                    and p.store_id == policy.store_id
                    and p.minimum_amount == policy.minimum_amount
                    and (p.minimum_tier, p.minimum_points, p.target_customer_id)
                    == (
                        policy.minimum_tier,
                        policy.minimum_points,
                        policy.target_customer_id,
                    )
                    and p.starts_at < policy.ends_at
                    and policy.starts_at < p.ends_at
                ):
                    raise ConflictError(
                        "Đã có chính sách cùng mốc nạp và phạm vi trong khoảng thời gian này"
                    )
            result = self._repo.save_promotion(conn, policy)
            self._repo.audit(conn, actor, "PROMOTION_SAVE", result.id)
            return result
