"""Owner-scoped profile, actual usage analysis and aggregate-only room availability."""

import re
from datetime import timedelta

from cyberhub_manager.domain.exceptions import (
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.usage_analysis import analyze_usage, VIETNAM
from cyberhub_manager.security import hash_password, verify_password
from .portal_experience import local_midnight


class PortalPhase2Mixin:
    def availability(self, principal, store_id):
        with self._errors(), self._transaction() as conn:
            self._principal(conn, principal)
            if type(store_id) is not int or store_id <= 0:
                raise ValidationError(field_errors={"store_id": "Vui lòng chọn cơ sở"})
            store = self._repo.store(conn, store_id)
            if not store or store.status != "ACTIVE":
                raise ValidationError(field_errors={"store_id": "Cơ sở không khả dụng"})
            counts = self._repo.portal_room_counts(conn, store_id)
            now = self._clock()
            return dict(
                store_id=store.id,
                store_name=store.name,
                rooms=counts,
                as_of=now,
                next_update_at=now + timedelta(minutes=5),
                refresh_seconds=300,
            )

    def usage_analysis(self, principal, days=30):
        if type(days) is not int or days not in (7, 30, 90):
            raise ValidationError(field_errors={"days": "Chọn 7, 30 hoặc 90 ngày"})
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            now = self._clock().replace(microsecond=0)
            today = now.astimezone(VIETNAM).date()
            first = today - timedelta(days=days - 1)
            start = local_midnight(first)
            rows = self._repo.portal_usage_sessions(conn, principal, start, now)
            return dict(
                **analyze_usage(rows, start, now, now),
                as_of=now,
                date_from=first,
                date_to=today,
                days=days,
                timezone="Asia/Ho_Chi_Minh",
            )

    def profile(self, principal):
        with self._errors(), self._transaction() as conn:
            principal = self._principal(conn, principal)
            return self._repo.portal_profile(conn, principal)

    def _confirm_password(self, conn, principal, password):
        principal = self._principal(conn, principal)
        record = self._repo.customer_credentials(
            conn, account_id=principal.account_id, lock=True
        )
        if not record or record[0].auth_version != principal.auth_version:
            raise PermissionDeniedError()
        if not isinstance(password, str) or not verify_password(password, record[1]):
            raise ValidationError(
                field_errors={"current_password": "Mật khẩu hiện tại không đúng"}
            )
        return record[0]

    def update_profile(self, principal, full_name, phone, current_password):
        name = full_name.strip() if isinstance(full_name, str) else ""
        phone = phone.strip() if isinstance(phone, str) else ""
        errors = {}
        if not 2 <= len(name) <= 100:
            errors["full_name"] = "Họ tên phải có từ 2 đến 100 ký tự"
        if not re.fullmatch(r"0[0-9]{9}", phone):
            errors["phone"] = "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0"
        if errors:
            raise ValidationError(field_errors=errors)
        with self._errors(), self._transaction() as conn:
            principal = self._confirm_password(conn, principal, current_password)
            if self._repo.portal_phone_taken(conn, principal, phone):
                raise ValidationError(
                    field_errors={"phone": "Số điện thoại đã được sử dụng"}
                )
            self._repo.portal_update_profile(conn, principal, name, phone)
            return self._repo.portal_profile(conn, principal)

    def change_password(self, principal, current_password, new_password, confirmation):
        errors = {}
        if (
            not isinstance(new_password, str)
            or len(new_password) < 6
            or len(new_password.encode()) > 72
        ):
            errors["new_password"] = (
                "Mật khẩu mới phải từ 6 ký tự, tối đa 72 byte UTF-8"
            )
        if not isinstance(confirmation, str) or confirmation != new_password:
            errors["confirmation"] = "Xác nhận mật khẩu không khớp"
        if new_password == current_password:
            errors["new_password"] = "Mật khẩu mới phải khác mật khẩu hiện tại"
        if errors:
            raise ValidationError(field_errors=errors)
        with self._errors(), self._transaction() as conn:
            principal = self._confirm_password(conn, principal, current_password)
            self._repo.portal_change_password(
                conn, principal, hash_password(new_password)
            )
            return self._repo.customer_credentials(
                conn, account_id=principal.account_id
            )[0]
