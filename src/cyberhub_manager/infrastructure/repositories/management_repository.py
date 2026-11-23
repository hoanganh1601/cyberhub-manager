"""Store, employee, promotion, and management-audit persistence."""

from datetime import timezone
from uuid import uuid4

from cyberhub_manager.domain.p1 import EmployeeSummary, Promotion, StoreSummary

from cyberhub_manager.infrastructure.repositories.sql import execute, rows, utc


class ManagementRepository:
    """Persistence for stores, employees, profiles, promotions, rooms, and management audit."""

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

    def assigned_store_ids(self, conn, employee_id):
        return {item["store_id"] for item in rows(
            conn, "SELECT store_id FROM employee_store_assignments WHERE employee_id=%s",
            (employee_id,),
        )}

    def set_store_assignment(self, conn, employee_id, store_id, granter_id, enabled):
        if enabled:
            execute(conn, "INSERT INTO employee_store_assignments(employee_id,store_id,granted_by) "
                    "VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE granted_by=VALUES(granted_by)",
                    (employee_id, store_id, granter_id))
        else:
            execute(conn, "DELETE FROM employee_store_assignments WHERE employee_id=%s AND store_id=%s",
                    (employee_id, store_id))

    def list_employee_profiles(self, conn, store_id=None):
        return rows(conn, "SELECT p.id,e.id AS employee_id,p.code,p.home_store_id,p.full_name,p.employment_status "
                    "FROM employee_profiles p LEFT JOIN employees e ON e.profile_id=p.id"
                    + (" WHERE p.home_store_id=%s" if store_id else "") +
                    " ORDER BY p.id DESC", (store_id,) if store_id else ())

    def employee_profile(self, conn, profile_id, lock=False):
        if lock:
            if not rows(conn, "SELECT id FROM employee_profiles WHERE id=%s FOR UPDATE", (profile_id,)):
                return None
        result = rows(conn, "SELECT p.id,e.id AS employee_id,p.code,p.home_store_id,p.full_name,p.employment_status "
                      "FROM employee_profiles p LEFT JOIN employees e ON e.profile_id=p.id WHERE p.id=%s",
                      (profile_id,))
        return result[0] if result else None

    def create_employee_profile(self, conn, code, store_id, full_name):
        return execute(conn, "INSERT INTO employee_profiles(code,home_store_id,full_name) VALUES(%s,%s,%s)",
                       (code, store_id, full_name))

    def update_employee_profile(self, conn, profile_id, store_id, full_name, status):
        prev = rows(conn, "SELECT home_store_id FROM employee_profiles WHERE id=%s FOR UPDATE", (profile_id,))
        old_store_id = prev[0]["home_store_id"] if prev else None
        execute(conn, "UPDATE employee_profiles SET home_store_id=%s,full_name=%s,employment_status=%s "
                "WHERE id=%s", (store_id, full_name, status, profile_id))
        if old_store_id is not None and (old_store_id != store_id or status == "INACTIVE"):
            execute(conn, "UPDATE employees SET auth_version=auth_version+1 WHERE profile_id=%s",
                    (profile_id,))

    def link_employee_profile(self, conn, profile_id, employee_id):
        # In 3NF (029), employees.profile_id is set atomically at credential creation.
        return None

    def bump_auth_version(self, conn, employee_id):
        execute(conn, "UPDATE employees SET auth_version=auth_version+1 WHERE id=%s", (employee_id,))

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
                "SELECT e.id,p.code,p.home_store_id AS store_id,p.full_name,e.username,e.role,e.status,"
                "e.must_change_password AS credential_update_required "
                "FROM employees e JOIN employee_profiles p ON p.id=e.profile_id"
                + (" WHERE p.home_store_id=%s" if store_id else "")
                + " ORDER BY e.id"
                + (" FOR UPDATE" if lock else ""),
                (store_id,) if store_id else (),
            )
        ]

    def save_employee(self, conn, employee_id, values, password_hash, profile_id=None):
        store_id, name, username, role, status = values
        if employee_id is None:
            if profile_id is None:
                profile_id = execute(
                    conn,
                    "INSERT INTO employee_profiles(code,home_store_id,full_name) VALUES(%s,%s,%s)",
                    ("NV-" + uuid4().hex[:17], store_id, name),
                )
            employee_id = execute(
                conn,
                "INSERT INTO employees(profile_id,username,password_hash,role,status,must_change_password) "
                "VALUES(%s,%s,%s,%s,%s,TRUE)",
                (
                    profile_id,
                    username,
                    password_hash,
                    role,
                    status,
                ),
            )
        else:
            prev = rows(
                conn,
                "SELECT p.id AS profile_id,p.home_store_id FROM employees e "
                "JOIN employee_profiles p ON p.id=e.profile_id WHERE e.id=%s FOR UPDATE",
                (employee_id,),
            )
            old_store_id = prev[0]["home_store_id"] if prev else store_id
            execute(
                conn,
                "UPDATE employees SET auth_version=auth_version+IF(%s<>%s OR username<>%s OR role<>%s OR status<>%s,1,0),"
                "username=%s,role=%s,status=%s WHERE id=%s",
                (old_store_id, store_id, username, role, status, username, role, status, employee_id),
            )
            if password_hash:
                execute(
                    conn,
                    "UPDATE employees SET password_hash=%s WHERE id=%s",
                    (password_hash, employee_id),
                )
            if prev:
                execute(
                    conn,
                    "UPDATE employee_profiles SET home_store_id=%s,full_name=%s WHERE id=%s",
                    (store_id, name, prev[0]["profile_id"]),
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

    def target_customer_exists(self, conn, customer_id):
        return bool(rows(conn, "SELECT id FROM customers WHERE id=%s", (customer_id,)))

    def list_machine_rooms(self, conn, store_id):
        return rows(
            conn,
            "SELECT m.id AS machine_id,m.code AS machine_code,m.name,m.status,"
            "COALESCE(r.room_type,'STANDARD') AS room_type FROM machines m "
            "LEFT JOIN machine_room_types r ON r.machine_id=m.id "
            "WHERE m.store_id=%s AND m.is_active=1 ORDER BY m.code",
            (store_id,),
        )

    def room_machine(self, conn, machine_id):
        result = rows(
            conn,
            "SELECT m.id,m.store_id,m.status,m.is_active,EXISTS(SELECT 1 FROM usage_sessions u "
            "WHERE u.machine_id=m.id AND u.status='ACTIVE') AS active_session FROM machines m WHERE m.id=%s FOR UPDATE",
            (machine_id,),
        )
        return result[0] if result else None

    def set_machine_room(self, conn, machine_id, room_type):
        execute(
            conn,
            "INSERT INTO machine_room_types(machine_id,room_type) VALUES(%s,%s) "
            "ON DUPLICATE KEY UPDATE room_type=%s",
            (machine_id, room_type, room_type),
        )
