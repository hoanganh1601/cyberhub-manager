"""Supplier, purchase request, receiving and payable workflows."""

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from cyberhub_manager.domain.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from cyberhub_manager.domain.policies import Permission, can, separated_rbac
from cyberhub_manager.domain.procurement import parse_quantity_lines
from cyberhub_manager.infrastructure.repositories.procurement_repository import ProcurementRepository

from cyberhub_manager.application.services.cash_shift_service import CashShiftService
from cyberhub_manager.application.services.operational_base import OperationalServiceBase


def _text(value, field, maximum, minimum=1):
    value=value.strip() if isinstance(value,str) else ""
    if not minimum<=len(value)<=maximum: raise ValidationError(field_errors={field:f"Nhập từ {minimum} đến {maximum} ký tự"})
    return value


class ProcurementService(OperationalServiceBase):
    def __init__(self, repo=None, shifts=None, **kwargs):
        super().__init__(**kwargs); self._repo=repo or ProcurementRepository()
        self._shifts=shifts or CashShiftService(auth_repo=self._auth,audit_repo=self._audit,transaction_factory=self._transaction)

    def overview(self, actor):
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_VIEW)
            requests=self._repo.list_requests(conn,current.store_id)
            orders=self._repo.list_orders(conn,current.store_id)
            for item in requests: item["lines"]=self._repo.request_lines(conn,item["id"])
            for item in orders: item["lines"]=self._repo.order_lines(conn,item["id"])
            return dict(suppliers=self._repo.list_suppliers(conn,current.store_id),
                ingredients=self._repo.ingredients(conn,current.store_id),requests=requests,
                orders=orders,payables=self._repo.list_payables(conn,current.store_id),
                can_approve=can(current.role,Permission.PROCUREMENT_APPROVE),
                can_receive=can(current.role,Permission.PROCUREMENT_RECEIVE),
                can_pay=can(current.role,Permission.PROCUREMENT_PAY),
                can_approve_payment=can(current.role,Permission.PROCUREMENT_APPROVE_PAYMENT),
                approval_required=separated_rbac(),
                can_manage_suppliers=can(current.role,Permission.PROCUREMENT_MANAGE_SUPPLIERS))

    def approve_payable(self, actor, payable_id, note):
        note = _text(note, "note", 255)
        with self._errors(), self._transaction() as conn:
            current = self._actor(conn, actor, Permission.PROCUREMENT_APPROVE_PAYMENT)
            payable = self._repo.payable(conn, payable_id, lock=True)
            if payable is None or payable["store_id"] != current.store_id:
                raise NotFoundError("Không tìm thấy công nợ")
            if payable["status"] != "UNPAID" or self._repo.payable_approval(conn, payable_id):
                raise ConflictError("Công nợ đã được duyệt hoặc thanh toán")
            self._repo.approve_payable(conn, payable_id, current.employee_id, note)
            self._audit.audit(conn, current, "SUPPLIER_PAYABLE_APPROVE", payable_id)
            return self._repo.payable_approval(conn, payable_id)

    def save_supplier(self, actor, supplier_id=None, **data):
        code=_text(data.get("code"),"code",24); name=_text(data.get("name"),"name",120)
        terms=data.get("payment_terms_days",0); active=data.get("is_active",True)
        if type(terms) is not int or not 0<=terms<=365: raise ValidationError(field_errors={"payment_terms_days":"Thời hạn từ 0 đến 365 ngày"})
        if type(active) is not bool: raise ValidationError(field_errors={"is_active":"Trạng thái không hợp lệ"})
        optional={k:(_text(data.get(k),k,n,0) or None) for k,n in (("phone",20),("email",120),("address",255))}
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_MANAGE_SUPPLIERS)
            if supplier_id:
                old=self._repo.supplier(conn,supplier_id,lock=True)
                if old is None or old["store_id"]!=current.store_id: raise NotFoundError("Không tìm thấy nhà cung cấp")
            entity_id=self._repo.save_supplier(conn,supplier_id=supplier_id,store_id=current.store_id,code=code,name=name,
                payment_terms_days=terms,is_active=active,**optional)
            self._audit.audit(conn,current,"SUPPLIER_SAVE",entity_id)
            return self._repo.supplier(conn,entity_id)

    def create_request(self, actor, *, reason, lines):
        reason=_text(reason,"reason",255); lines=parse_quantity_lines(lines)
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_REQUEST)
            valid={x["id"] for x in self._repo.ingredients(conn,current.store_id)}
            if any(x["ingredient_id"] not in valid for x in lines): raise ValidationError(field_errors={"lines":"Nguyên liệu không thuộc cơ sở"})
            entity_id=self._repo.create_request(conn,code="PR-"+uuid4().hex[:17].upper(),store_id=current.store_id,
                employee_id=current.employee_id,reason=reason,lines=lines)
            self._audit.audit(conn,current,"PURCHASE_REQUEST_CREATE",entity_id)
            return self._repo.request(conn,entity_id)

    def decide_request(self, actor, request_id, approve):
        if type(approve) is not bool: raise ValidationError(field_errors={"approve":"Quyết định không hợp lệ"})
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_APPROVE)
            request=self._repo.request(conn,request_id,lock=True)
            if request is None or request["store_id"]!=current.store_id: raise NotFoundError("Không tìm thấy đề nghị")
            if request["requested_by"]==current.employee_id: raise PermissionDeniedError("Người đề nghị không được tự duyệt")
            if self._repo.decide_request(conn,request_id,current.employee_id,approve)!=1: raise ConflictError("Đề nghị không còn chờ duyệt")
            self._audit.audit(conn,current,"PURCHASE_REQUEST_APPROVE" if approve else "PURCHASE_REQUEST_REJECT",request_id)
            return self._repo.request(conn,request_id)

    def create_order(self, actor, *, request_id, supplier_id, expected_at, lines):
        lines=parse_quantity_lines(lines,with_cost=True)
        if expected_at:
            try: expected_at=datetime.fromisoformat(expected_at)
            except (TypeError,ValueError): raise ValidationError(field_errors={"expected_at":"Ngày nhận dự kiến không hợp lệ"}) from None
        else: expected_at=None
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_APPROVE)
            request=self._repo.request(conn,request_id,lock=True); supplier=self._repo.supplier(conn,supplier_id,lock=True)
            if request is None or request["store_id"]!=current.store_id or request["status"]!="APPROVED": raise ConflictError("Đề nghị chưa được duyệt hoặc không khả dụng")
            if supplier is None or supplier["store_id"]!=current.store_id or not supplier["is_active"]: raise NotFoundError("Nhà cung cấp không khả dụng")
            requested={x["ingredient_id"]:x["quantity"] for x in self._repo.request_lines(conn,request_id)}
            if {x["ingredient_id"]:x["quantity"] for x in lines}!=requested: raise ValidationError(field_errors={"lines":"Đơn mua phải đúng mặt hàng và số lượng đã duyệt"})
            entity_id=self._repo.create_order(conn,code="PO-"+uuid4().hex[:17].upper(),request=request,supplier_id=supplier_id,
                employee_id=current.employee_id,expected_at=expected_at,lines=lines)
            self._audit.audit(conn,current,"PURCHASE_ORDER_CREATE",entity_id)
            return self._repo.order(conn,entity_id)

    def receive(self, actor, order_id, *, request_id, lines, note=""):
        try: request_hex=UUID(request_id).hex
        except (TypeError,ValueError,AttributeError): raise ValidationError(field_errors={"request_id":"Cần UUID hợp lệ"}) from None
        note=_text(note,"note",255,0)
        if not isinstance(lines,list) or not lines: raise ValidationError(field_errors={"lines":"Cần khai báo hàng nhận"})
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_RECEIVE)
            existing=self._repo.receipt_by_request(conn,request_hex,lock=True)
            if existing is not None:
                if existing["store_id"]!=current.store_id or existing["order_id"]!=order_id:
                    raise ConflictError("Mã yêu cầu nhận hàng đã được dùng")
                return dict(receipt_id=existing["id"],order=self._repo.order(conn,order_id))
            order=self._repo.order(conn,order_id,lock=True)
            if order is None or order["store_id"]!=current.store_id or order["status"] not in ("OPEN","PARTIALLY_RECEIVED"):
                raise ConflictError("Đơn mua không thể nhận hàng")
            ordered={x["ingredient_id"]:x for x in self._repo.order_lines(conn,order_id,lock=True)}; parsed=[]; seen=set()
            for raw in lines:
                iid=raw.get("ingredient_id") if isinstance(raw,dict) else None
                if iid not in ordered or iid in seen: raise ValidationError(field_errors={"lines":"Dòng nhận hàng không hợp lệ"})
                accepted=raw.get("accepted_quantity",0); damaged=raw.get("damaged_quantity",0); missing=raw.get("missing_quantity",0)
                if any(type(x) is not int or x<0 for x in (accepted,damaged,missing)) or accepted+damaged+missing<=0:
                    raise ValidationError(field_errors={"lines":"Số lượng nhận, hỏng hoặc thiếu không hợp lệ"})
                remaining=ordered[iid]["quantity"]-ordered[iid]["received_quantity"]-ordered[iid]["damaged_quantity"]
                if accepted+damaged+missing>remaining: raise ConflictError("Số lượng nhận vượt phần còn lại của đơn mua")
                parsed.append(dict(ingredient_id=iid,accepted_quantity=accepted,damaged_quantity=damaged,
                    missing_quantity=missing,unit_cost=ordered[iid]["unit_cost"])); seen.add(iid)
            receipt_id=self._repo.receive(conn,code="GR-"+uuid4().hex[:17].upper(),request_id=request_hex,
                order=order,employee_id=current.employee_id,note=note,lines=parsed)
            amount=sum(x["accepted_quantity"]*x["unit_cost"] for x in parsed)
            if amount:
                due=date.today()+timedelta(days=int(order["payment_terms_days"]))
                self._repo.create_payable(conn,receipt_id=receipt_id,order=order,amount=amount,due_date=due)
            self._audit.audit(conn,current,"GOODS_RECEIVE",receipt_id)
            return dict(receipt_id=receipt_id,order=self._repo.order(conn,order_id))

    def pay_payable(self, actor, payable_id, method):
        if method not in ("CASH","TRANSFER"): raise ValidationError(field_errors={"method":"Chọn tiền mặt hoặc chuyển khoản"})
        with self._errors(),self._transaction() as conn:
            current=self._actor(conn,actor,Permission.PROCUREMENT_PAY)
            payable=self._repo.payable(conn,payable_id,lock=True)
            if separated_rbac() and payable is not None and payable["store_id"] == current.store_id:
                approval = self._repo.payable_approval(conn, payable_id)
                if approval is None:
                    raise ConflictError("Công nợ chưa được phê duyệt")
                if approval["approved_by"] == current.employee_id:
                    raise PermissionDeniedError("Người duyệt không được tự thanh toán")
            if payable is None or payable["store_id"]!=current.store_id: raise NotFoundError("Không tìm thấy công nợ")
            if payable["status"]!="UNPAID": raise ConflictError("Công nợ đã được thanh toán")
            self._shifts.record_system_entry(conn,current,kind="EXPENSE",payment_method=method,amount=payable["amount"],
                source_type="SUPPLIER_PAYABLE",source_id=payable_id,note="Thanh toán công nợ nhà cung cấp")
            if self._repo.pay(conn,payable_id,current.employee_id,method)!=1: raise ConflictError("Công nợ vừa được xử lý")
            self._audit.audit(conn,current,"SUPPLIER_PAYABLE_PAID",payable_id)
            return self._repo.payable(conn,payable_id)
