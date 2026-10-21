"""Mock MachineService: danh sách máy vận hành và các thao tác quản trị máy."""

from __future__ import annotations

from cyberhub_manager.domain.dtos import (
    EmployeeSession,
    MachineArchiveResult,
    MachineSummary,
)
from cyberhub_manager.domain.enums import MachineArchiveAction, MachineStatus
from cyberhub_manager.domain.exceptions import ConflictError
from cyberhub_manager.domain.models import Machine

from .base import (
    MockServiceBase,
    clean_text,
    positive_int_error,
    raise_if_errors,
)
from .store import copy_machine

_CODE_TAKEN = "Mã máy đã tồn tại"


def _code_error(code: str) -> str | None:
    if not 1 <= len(code) <= 20:
        return "Mã máy phải có từ 1 đến 20 ký tự"
    return None


def _name_error(name: str) -> str | None:
    if not 1 <= len(name) <= 100:
        return "Tên máy phải có từ 1 đến 100 ký tự"
    return None


class MockMachineService(MockServiceBase):
    def list_machines(self, store_id: int) -> list[MachineSummary]:
        self._check_scenario("list_machines")
        now = self._clock.now()
        machines = sorted(
            (
                machine
                for machine in self._data.machines.values()
                if machine.store_id == store_id and machine.is_active
            ),
            key=lambda machine: machine.code,
        )
        return [self._data.to_machine_summary(m, now) for m in machines]

    def create_machine(
        self,
        code: str,
        store_id: int,
        name: str,
        hourly_rate: int,
        actor: EmployeeSession,
    ) -> Machine:
        self._require_manager(actor)
        self._check_scenario("create_machine")
        self._require_store(actor, store_id)
        code = clean_text(code)
        name = clean_text(name)
        raise_if_errors(
            {
                "code": _code_error(code),
                "name": _name_error(name),
                "hourly_rate": positive_int_error(hourly_rate, "Đơn giá"),
            }
        )
        if self._data.is_machine_code_taken(code):
            raise ConflictError(_CODE_TAKEN, field_errors={"code": _CODE_TAKEN})

        machine_id = self._data.next_id("machine")
        machine = Machine(
            id=machine_id,
            code=code,
            store_id=store_id,
            name=name,
            status=MachineStatus.AVAILABLE,
            hourly_rate=hourly_rate,
            is_active=True,
            updated_at=self._clock.now(),
        )
        self._data.machines[machine_id] = machine
        return copy_machine(machine)

    def update_machine(
        self,
        machine_id: int,
        name: str,
        hourly_rate: int,
        actor: EmployeeSession,
    ) -> Machine:
        self._require_manager(actor)
        self._check_scenario("update_machine")
        machine = self._data.get_machine(machine_id)
        self._require_store(actor, machine.store_id)
        name = clean_text(name)
        raise_if_errors(
            {
                "name": _name_error(name),
                "hourly_rate": positive_int_error(hourly_rate, "Đơn giá"),
            }
        )
        if not machine.is_active:
            raise ConflictError("Không thể sửa máy đã ngừng sử dụng")

        # Phiên đang chạy giữ giá snapshot riêng nên không bị ảnh hưởng.
        machine.update_info(name, hourly_rate)
        return copy_machine(self._data.touch_machine(machine_id, self._clock.now()))

    def set_maintenance(
        self,
        machine_id: int,
        enabled: bool,
        actor: EmployeeSession,
    ) -> Machine:
        self._require_manager(actor)
        self._check_scenario("set_maintenance")
        machine = self._data.get_machine(machine_id)
        self._require_store(actor, machine.store_id)

        # Domain tự từ chối máy IN_USE/đã ngừng sử dụng trước khi đổi trạng thái.
        machine.set_maintenance(enabled)
        return copy_machine(self._data.touch_machine(machine_id, self._clock.now()))

    def archive_machine(
        self,
        machine_id: int,
        actor: EmployeeSession,
    ) -> MachineArchiveResult:
        self._require_manager(actor)
        self._check_scenario("archive_machine")
        machine = self._data.get_machine(machine_id)
        self._require_store(actor, machine.store_id)
        if machine.status == MachineStatus.IN_USE:
            raise ConflictError("Không thể ngừng sử dụng máy đang có phiên")

        if not self._data.machine_has_history(machine_id):
            del self._data.machines[machine_id]
            return MachineArchiveResult(
                machine_id=machine_id, action=MachineArchiveAction.DELETED
            )
        machine.archive()
        self._data.touch_machine(machine_id, self._clock.now())
        return MachineArchiveResult(
            machine_id=machine_id, action=MachineArchiveAction.ARCHIVED
        )
