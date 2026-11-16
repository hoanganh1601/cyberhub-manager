"""Store, employee, promotion, and management-audit persistence."""

from datetime import timezone
from uuid import uuid4

from cyberhub_manager.domain.p1 import EmployeeSummary, Promotion, StoreSummary

from .sql import execute, rows, utc


class ManagementRepositoryMixin:
    """Management queries composed into the backwards-compatible P1 facade."""

    def list_stores(self, conn, store_id=None):
        return [
            StoreSummary(**item)
            for item in rows(
                conn,
                "SELECT id,code,name,address,status FROM stores"
                + (" WHERE id=%s" if store_id else "")
                + " ORDER BY code",
                (store_id,) if store_id else (),
            )
        ]

    def store(self, conn, store_id, lock=False):
        result = rows(
            conn,
            "SELECT id,code,name,address,status FROM stores WHERE id=%s"
            + (
                " FOR UPDATE"
                if lock is True
                else " FOR SHARE" if lock == "share" else ""
            ),
            (store_id,),
        )
        return StoreSummary(**result[0]) if result else None

    def save_store(self, conn, store_id, code, name, address, status):
        if store_id is None:
            store_id = execute(
                conn,
                "INSERT INTO stores(code,name,address,status) VALUES(%s,%s,%s,%s)",
                (code, name, address, status),
            )
        else:
            execute(
                conn,
                "UPDATE stores SET code=%s,name=%s,address=%s,status=%s WHERE id=%s",
                (code, name, address, status, store_id),
            )
        return self.store(conn, store_id)

    def has_active_sessions(self, conn, store_id):
        return bool(
            rows(
                conn,
                "SELECT u.id FROM usage_sessions u JOIN machines m ON m.id=u.machine_id "
                "WHERE m.store_id=%s AND u.status='ACTIVE' LIMIT 1",
                (store_id,),
            )
        )

    def list_employees(self, conn, store_id=None, lock=False):
        return [
            EmployeeSummary(**item)
            for item in rows(
                conn,
                "SELECT id,code,store_id,full_name,username,role,status,"
                "must_change_password AS credential_update_required FROM employees"
                + (" WHERE store_id=%s" if store_id else "")
                + " ORDER BY id"
                + (" FOR UPDATE" if lock else ""),
                (store_id,) if store_id else (),
            )
        ]

    def save_employee(self, conn, employee_id, values, password_hash):
        store_id, name, username, role, status = values
        if employee_id is None:
            employee_id = execute(
                conn,
                "INSERT INTO employees(code,store_id,full_name,username,password_hash,role,status,must_change_password) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,TRUE)",
                (
                    "NV-" + uuid4().hex[:17],
                    store_id,
                    name,
                    username,
                    password_hash,
                    role,
                    status,
                ),
            )
        else:
            execute(
                conn,
                "UPDATE employees SET store_id=%s,full_name=%s,username=%s,role=%s,status=%s WHERE id=%s",
                (*values, employee_id),
            )
            if password_hash:
                execute(
                    conn,
                    "UPDATE employees SET password_hash=%s WHERE id=%s",
                    (password_hash, employee_id),
                )
        return next(item for item in self.list_employees(conn) if item.id == employee_id)

    def reset_employee_password(self, conn, employee_id, password_hash):
        execute(
            conn,
            """UPDATE employees SET password_hash=%s,auth_version=auth_version+1,
               must_change_password=TRUE,password_changed_at=CURRENT_TIMESTAMP
               WHERE id=%s""",
            (password_hash, employee_id),
        )

    def list_promotions(self, conn, store_id=None, lock=False):
        result = rows(
            conn,
            "SELECT id,code,name,store_id,minimum_amount,bonus_percent,starts_at,ends_at,is_active,"
            "minimum_tier,minimum_points,target_customer_id FROM promotions"
            + (" WHERE store_id=%s OR store_id IS NULL" if store_id else "")
            + " ORDER BY minimum_amount DESC,id DESC"
            + (" FOR SHARE" if lock == "share" else " FOR UPDATE" if lock else ""),
            (store_id,) if store_id else (),
        )
        return [
            Promotion(
                **{
                    **item,
                    "starts_at": utc(item["starts_at"]),
                    "ends_at": utc(item["ends_at"]),
                    "is_active": bool(item["is_active"]),
                }
            )
            for item in result
        ]

    def save_promotion(self, conn, policy):
        fields = (
            policy.code,
            policy.name,
            policy.store_id,
            policy.minimum_amount,
            policy.bonus_percent,
            policy.starts_at.astimezone(timezone.utc).replace(tzinfo=None),
            policy.ends_at.astimezone(timezone.utc).replace(tzinfo=None),
            policy.is_active,
            policy.minimum_tier,
            policy.minimum_points,
            policy.target_customer_id,
        )
        if policy.id:
            execute(
                conn,
                "UPDATE promotions SET code=%s,name=%s,store_id=%s,minimum_amount=%s,bonus_percent=%s,"
                "starts_at=%s,ends_at=%s,is_active=%s,minimum_tier=%s,minimum_points=%s,"
                "target_customer_id=%s WHERE id=%s",
                (*fields, policy.id),
            )
            entity_id = policy.id
        else:
            entity_id = execute(
                conn,
                "INSERT INTO promotions(code,name,store_id,minimum_amount,bonus_percent,starts_at,ends_at,"
                "is_active,minimum_tier,minimum_points,target_customer_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                fields,
            )
        return next(item for item in self.list_promotions(conn) if item.id == entity_id)

    def audit(self, conn, actor, action, entity_id):
        execute(
            conn,
            "INSERT INTO management_audit(employee_id,store_id,action,entity_id) VALUES(%s,%s,%s,%s)",
            (actor.employee_id, actor.store_id, action, entity_id),
        )
