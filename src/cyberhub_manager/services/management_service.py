"""Store-scoped administration shared by both clients, including audit and RBAC."""

from dataclasses import replace
from datetime import datetime, timezone
import re
from uuid import uuid4

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.p1 import Permission, Promotion, can, chain_director, separated_rbac
from cyberhub_manager.repositories.management_repository import ManagementRepository
from cyberhub_manager.security import hash_password
from .p1_runtime import errors, retry_on_transient


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
    def list_machine_rooms(self, actor):
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.OPERATE)
            return self._repo.list_machine_rooms(conn, actor.store_id)

    @retry_on_transient
    def set_machine_room(self, actor, machine_id, room_type):
        if (
            type(machine_id) is not int
            or machine_id <= 0
            or room_type not in ("STANDARD", "VIP", "COUPLE", "SUPER_VIP")
        ):
            raise ValidationError(
                field_errors={"room_type": "Chọn loại phòng hợp lệ"}
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
        self._repo = repo or ManagementRepository()
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
            if chain_director(actor.role) or actor.role == Role.ADMIN:
                return self._repo.list_stores(conn)
            if actor.role == Role.MANAGER and separated_rbac():
                home_store_id = (
                    next(
                        employee.store_id
                        for employee in self._repo.list_employees(conn)
                        if employee.id == actor.employee_id
                    )
                    if self._memory
                    else self._auth.get_active_session_by_id(conn, actor.employee_id).store_id
                )
                allowed = {home_store_id} | self._repo.assigned_store_ids(conn, actor.employee_id)
                return [store for store in self._repo.list_stores(conn) if store.id in allowed]
            return self._repo.list_stores(conn, actor.store_id)

    def switch_store(self, actor, store_id):
        if type(store_id) is not int or store_id <= 0:
            raise ValidationError(field_errors={"store_id": "Cơ sở không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor)
            if store_id != current.store_id and not can(current.role, Permission.SWITCH_STORE):
                home_store_id = (
                    next(
                        employee.store_id
                        for employee in self._repo.list_employees(conn)
                        if employee.id == current.employee_id
                    )
                    if self._memory
                    else self._auth.get_active_session_by_id(conn, current.employee_id).store_id
                )
                if (not separated_rbac() or current.role != Role.MANAGER
                        or store_id not in ({home_store_id} | self._repo.assigned_store_ids(conn, current.employee_id))):
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
            permission = (Permission.MANAGE_EMPLOYEE_CREDENTIALS
                          if actor.role == Role.ADMIN else Permission.MANAGE_EMPLOYEES)
            actor = self._actor(conn, actor, permission)
            return self._repo.list_employees(
                conn, None if chain_director(actor.role) or actor.role == Role.ADMIN else actor.store_id
            )

    def list_employee_profiles(self, actor):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor)
            if current.role == Role.ADMIN:
                return self._repo.list_employee_profiles(conn)
            if not can(current.role, Permission.MANAGE_EMPLOYEES):
                raise PermissionDeniedError()
            return self._repo.list_employee_profiles(
                conn, None if chain_director(current.role) else current.store_id
            )

    @retry_on_transient
    def save_employee_profile(self, actor, profile_id, store_id, full_name, employment_status="ACTIVE"):
        name = text(full_name, "full_name", 2)
        choice(employment_status, "employment_status", ("ACTIVE", "INACTIVE"))
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_EMPLOYEES)
            if separated_rbac() and current.role == Role.ADMIN:
                raise PermissionDeniedError()
            if current.role == Role.MANAGER and store_id != current.store_id:
                raise PermissionDeniedError()
            old = self._repo.employee_profile(conn, profile_id, lock=True) if profile_id else None
            if profile_id and old is None:
                raise NotFoundError()
            if old and current.role == Role.MANAGER and old["home_store_id"] != current.store_id:
                raise PermissionDeniedError()
            store = self._repo.store(conn, store_id, lock="share")
            if store is None or store.status != "ACTIVE":
                raise ValidationError(field_errors={"store_id": "Chọn cơ sở đang hoạt động"})
            if old is None:
                profile_id = self._repo.create_employee_profile(
                    conn, "HR-" + uuid4().hex[:16], store_id, name
                )
            else:
                self._repo.update_employee_profile(conn, profile_id, store_id, name, employment_status)
            self._repo.audit(conn, current, "EMPLOYEE_PROFILE_SAVE", profile_id)
            return self._repo.employee_profile(conn, profile_id)

    def set_manager_store_assignment(self, actor, employee_id, store_id, enabled):
        if type(enabled) is not bool or type(employee_id) is not int or type(store_id) is not int:
            raise ValidationError(field_errors={"store_id": "Phân công không hợp lệ"})
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
            if current.role != Role.ADMIN or not separated_rbac():
                raise PermissionDeniedError()
            target = next((x for x in self._repo.list_employees(conn, lock=True) if x.id == employee_id), None)
            store = self._repo.store(conn, store_id, lock="share")
            if target is None or target.role != "MANAGER" or store is None or store.status != "ACTIVE":
                raise ValidationError(field_errors={"store_id": "Chọn quản lý và cơ sở đang hoạt động"})
            if store_id == target.store_id:
                raise ConflictError("Cơ sở chính đã được phân công sẵn")
            self._repo.set_store_assignment(conn, employee_id, store_id, current.employee_id, enabled)
            self._repo.bump_auth_version(conn, employee_id)
            self._repo.audit(conn, current, "MANAGER_STORE_ASSIGN" if enabled else "MANAGER_STORE_REVOKE", employee_id)
            return dict(employee_id=employee_id, store_id=store_id, enabled=enabled)

    def list_manager_store_assignments(self, actor, employee_id):
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
            if current.role != Role.ADMIN:
                raise PermissionDeniedError()
            target = next((x for x in self._repo.list_employees(conn) if x.id == employee_id), None)
            if target is None or target.role != "MANAGER":
                raise NotFoundError()
            return sorted(self._repo.assigned_store_ids(conn, employee_id))

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
        profile_id=None,
    ):
        name, username = text(full_name, "full_name", 2), text(
            username, "username", 4, 30
        )
        if not re.fullmatch(r"[A-Za-z0-9_.]{4,30}", username):
            raise ValidationError(
                field_errors={"username": "Tên đăng nhập không hợp lệ"}
            )
        choice(role, "role", tuple(str(value) for value in Role))
        choice(status, "status", ("ACTIVE", "INACTIVE", "LOCKED"))
        if employee_id is not None and password:
            raise ValidationError(
                field_errors={"password": "Dùng chức năng đặt lại mật khẩu riêng"}
            )
        if employee_id is None:
            if (
                not isinstance(password, str)
                or len(password) < 8
                or len(password.encode()) > 72
            ):
                raise ValidationError(
                    field_errors={
                        "password": "Mật khẩu tối thiểu 8 ký tự, tối đa 72 byte"
                    }
                )
        password_hash = hash_password(password) if password else None
        with self._errors(), self._transaction() as conn:
            credential_change = actor.role == Role.ADMIN
            permission = (Permission.MANAGE_EMPLOYEE_CREDENTIALS if credential_change
                          else Permission.MANAGE_EMPLOYEES)
            actor = self._actor(conn, actor, permission)
            employees = self._repo.list_employees(conn, lock=True)
            old = next((e for e in employees if e.id == employee_id), None)
            profile = None
            if profile_id is not None:
                if old is not None:
                    raise ValidationError(field_errors={"profile_id": "Chỉ gắn hồ sơ khi cấp tài khoản mới"})
                if type(profile_id) is not int or profile_id <= 0:
                    raise ValidationError(field_errors={"profile_id": "Hồ sơ nhân sự không hợp lệ"})
                profile = self._repo.employee_profile(conn, profile_id, lock=True)
                if profile is None or profile["employee_id"] is not None:
                    raise ConflictError("Hồ sơ đã có tài khoản hoặc không tồn tại")
                if (profile["home_store_id"], profile["full_name"], profile["employment_status"]) != (store_id, name, "ACTIVE"):
                    raise ValidationError(field_errors={"profile_id": "Thông tin phải khớp hồ sơ nhân sự đang làm việc"})
            if separated_rbac() and credential_change and old is None and profile is None:
                raise ValidationError(field_errors={"profile_id": "Chọn hồ sơ nhân sự trước khi cấp tài khoản"})
            if employee_id is not None and old is None:
                raise NotFoundError()
            if old is not None and old.role == "ADMIN" and not credential_change:
                raise PermissionDeniedError()
            if (separated_rbac() or actor.role == Role.DIRECTOR) and not credential_change:
                # The existing table requires credentials on INSERT. Only the
                # identity administrator can provision a new row until profile
                # staging is introduced; business roles edit profile fields only.
                if old is None or (username, role, status) != (old.username, old.role, old.status):
                    raise PermissionDeniedError()
                if actor.role == Role.MANAGER and (
                    store_id != actor.store_id or old.store_id != actor.store_id
                ):
                    raise PermissionDeniedError()
            elif separated_rbac() and credential_change and old is not None and (
                store_id != old.store_id or name != old.full_name
            ):
                raise PermissionDeniedError()
            elif actor.role != Role.ADMIN and actor.role != Role.DIRECTOR and (
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
            values = (store_id, name, username, role, status)
            result = (self._repo.save_employee(conn, employee_id, values, password_hash, profile_id)
                      if profile_id is not None else self._repo.save_employee(conn, employee_id, values, password_hash))
            action = ("EMPLOYEE_CREDENTIAL_SAVE" if credential_change else "EMPLOYEE_PROFILE_SAVE") if separated_rbac() else "EMPLOYEE_SAVE"
            self._repo.audit(conn, actor, action, result.id)
            return result

    @retry_on_transient
    def reset_employee_password(self, actor, employee_id, temporary_password):
        if type(employee_id) is not int or employee_id <= 0:
            raise ValidationError(field_errors={"employee_id": "Tài khoản không hợp lệ"})
        if (
            not isinstance(temporary_password, str)
            or len(temporary_password) < 8
            or len(temporary_password.encode()) > 72
        ):
            raise ValidationError(
                field_errors={"temporary_password": "Mật khẩu tạm phải từ 8 ký tự và tối đa 72 byte"}
            )
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
            if actor.role != Role.ADMIN:
                raise PermissionDeniedError()
            if employee_id == actor.employee_id:
                raise ConflictError("Hãy dùng chức năng đổi mật khẩu cho tài khoản của chính bạn")
            target = next(
                (employee for employee in self._repo.list_employees(conn, lock=True) if employee.id == employee_id),
                None,
            )
            if target is None:
                raise NotFoundError()
            self._repo.reset_employee_password(
                conn, employee_id, hash_password(temporary_password)
            )
            self._repo.audit(conn, actor, "EMPLOYEE_PASSWORD_RESET", employee_id)
            return next(
                employee for employee in self._repo.list_employees(conn) if employee.id == employee_id
            )

    def list_promotions(self, actor):
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_PROMOTIONS)
            return self._repo.list_promotions(
                conn, None if chain_director(actor.role) else actor.store_id
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
        with self._errors(), self._transaction() as conn:
            actor = self._actor(conn, actor, Permission.MANAGE_PROMOTIONS)
            policies = self._repo.list_promotions(conn, lock=True)
            old = next((p for p in policies if p.id == policy.id), None)
            if policy.id and old is None:
                raise NotFoundError()
            if not chain_director(actor.role) and (
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
                    and p.starts_at < policy.ends_at
                    and policy.starts_at < p.ends_at
                ):
                    raise ConflictError(
                        "Đã có chính sách cùng mốc nạp và phạm vi trong khoảng thời gian này"
                    )
            result = self._repo.save_promotion(conn, policy)
            self._repo.audit(conn, actor, "PROMOTION_SAVE", result.id)
            return result
