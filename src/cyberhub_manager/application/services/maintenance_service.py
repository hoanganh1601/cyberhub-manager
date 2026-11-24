"""Machine incident workflow and maintenance history."""

from uuid import uuid4

from cyberhub_manager.domain.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from cyberhub_manager.domain.maintenance import IncidentSeverity, IncidentStatus, require_incident_transition
from cyberhub_manager.domain.policies import Permission, can
from cyberhub_manager.infrastructure.repositories.maintenance_repository import MaintenanceRepository

from cyberhub_manager.application.services.operational_base import OperationalServiceBase


def _text(value, field, maximum, minimum=1):
    value = value.strip() if isinstance(value, str) else ""
    if not minimum <= len(value) <= maximum:
        raise ValidationError(field_errors={field: f"Nhập từ {minimum} đến {maximum} ký tự"})
    return value


class MaintenanceService(OperationalServiceBase):
    def __init__(self, repo=None, **kwargs):
        super().__init__(**kwargs); self._repo = repo or MaintenanceRepository()

    def overview(self, actor, status=None):
        with self._errors(), self._transaction() as conn:
            current=self._actor(conn,actor,Permission.MAINTENANCE_VIEW)
            if status is not None:
                try: status=IncidentStatus(status).value
                except ValueError: raise ValidationError(field_errors={"status":"Trạng thái không hợp lệ"}) from None
            manage=can(current.role,Permission.MAINTENANCE_MANAGE)
            return dict(incidents=self._repo.list_incidents(conn,current.store_id,status),
                        machines=self._repo.machines(conn,current.store_id),
                        employees=self._repo.employees(conn,current.store_id) if manage else [],
                        can_manage=manage,
                        can_update=can(current.role,Permission.MAINTENANCE_UPDATE))

    def detail(self, actor, incident_id):
        with self._errors(), self._transaction() as conn:
            current=self._actor(conn,actor,Permission.MAINTENANCE_VIEW)
            incident=self._repo.get_incident(conn,incident_id)
            if incident is None or incident["store_id"]!=current.store_id: raise NotFoundError("Không tìm thấy sự cố")
            events,parts=self._repo.history(conn,incident_id)
            return dict(incident=incident,events=events,parts=parts)

    def report(self, actor, *, machine_id, severity, title, description):
        try: severity=IncidentSeverity(severity).value
        except ValueError: raise ValidationError(field_errors={"severity":"Mức độ không hợp lệ"}) from None
        title=_text(title,"title",120); description=_text(description,"description",1000)
        with self._errors(), self._transaction() as conn:
            current=self._actor(conn,actor,Permission.MAINTENANCE_REPORT)
            machine=self._repo.machine(conn,machine_id,lock=True)
            if machine is None or machine["store_id"]!=current.store_id or not machine["is_active"]:
                raise NotFoundError("Không tìm thấy máy")
            incident_id=self._repo.create(conn,code="INC-"+uuid4().hex[:16].upper(),store_id=current.store_id,
                machine_id=machine_id,employee_id=current.employee_id,severity=severity,title=title,description=description)
            self._audit.audit(conn,current,"INCIDENT_REPORT",incident_id)
            return self._repo.get_incident(conn,incident_id)

    def transition(self, actor, incident_id, *, status, assigned_to=None, note="",
                   resolution=None, labor_cost=0, parts=None):
        note=_text(note,"note",500,0)
        try:
            target=IncidentStatus(status)
        except (TypeError, ValueError):
            raise ValidationError(field_errors={"status":"Trạng thái không hợp lệ"}) from None
        with self._errors(), self._transaction() as conn:
            preview=self._repo.get_incident(conn,incident_id)
            if preview is None: raise NotFoundError("Không tìm thấy sự cố")
            manage_target=target in (IncidentStatus.ASSIGNED,IncidentStatus.VERIFIED,IncidentStatus.CANCELLED)
            current=self._actor(conn,actor,Permission.MAINTENANCE_MANAGE if manage_target else Permission.MAINTENANCE_UPDATE)
            incident=self._repo.get_incident(conn,incident_id,lock=True)
            if incident is None or incident["store_id"]!=current.store_id: raise NotFoundError("Không tìm thấy sự cố")
            _,target=require_incident_transition(incident["status"],target.value)
            assignee=assigned_to
            if target is IncidentStatus.ASSIGNED:
                if type(assignee) is not int or not self._repo.employee_in_store(conn,assignee,current.store_id):
                    raise ValidationError(field_errors={"assigned_to":"Nhân viên xử lý không hợp lệ"})
            elif not can(current.role,Permission.MAINTENANCE_MANAGE):
                if incident["assigned_to"] != current.employee_id:
                    raise PermissionDeniedError("Chỉ người được phân công mới được cập nhật")
                assignee=None
            if target is IncidentStatus.VERIFIED and incident["assigned_to"]==current.employee_id:
                raise PermissionDeniedError("Người sửa không được tự xác nhận nghiệm thu")
            parsed_parts=[]
            if target is IncidentStatus.COMPLETED:
                resolution=_text(resolution,"resolution",1000)
                if type(labor_cost) is not int or not 0<=labor_cost<=1_000_000_000:
                    raise ValidationError(field_errors={"labor_cost":"Chi phí không hợp lệ"})
                if not isinstance(parts,list) or len(parts)>50: raise ValidationError(field_errors={"parts":"Tối đa 50 linh kiện"})
                for part in parts:
                    name=_text(part.get("name") if isinstance(part,dict) else None,"parts",120)
                    quantity=part.get("quantity"); unit_cost=part.get("unit_cost")
                    if type(quantity) is not int or not 1<=quantity<=1000 or type(unit_cost) is not int or not 0<=unit_cost<=1_000_000_000:
                        raise ValidationError(field_errors={"parts":"Linh kiện không hợp lệ"})
                    parsed_parts.append(dict(name=name,quantity=quantity,unit_cost=unit_cost))
            machine=self._repo.machine(conn,incident["machine_id"],lock=True)
            if target is IncidentStatus.IN_PROGRESS and machine["status"]!="MAINTENANCE":
                if machine["status"]!="AVAILABLE" or self._repo.set_machine_maintenance(conn,machine["id"],True)!=1:
                    raise ConflictError("Máy đang được sử dụng, chưa thể bắt đầu sửa")
            if target is IncidentStatus.VERIFIED and self._repo.set_machine_maintenance(conn,machine["id"],False)!=1:
                raise ConflictError("Trạng thái máy không còn phù hợp để nghiệm thu")
            if self._repo.transition(conn,incident,target=target.value,employee_id=current.employee_id,
                assigned_to=assignee,note=note,resolution=resolution,labor_cost=labor_cost,parts=parsed_parts)!=1:
                raise ConflictError("Sự cố vừa được cập nhật")
            self._audit.audit(conn,current,"INCIDENT_"+target.value,incident_id)
            return self._repo.get_incident(conn,incident_id)
