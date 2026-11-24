"""Persistence for machine incidents, parts and immutable status history."""

from cyberhub_manager.infrastructure.repositories.sql import execute, rows


class MaintenanceRepository:
    def employees(self, conn, store_id):
        return rows(conn,
            "SELECT e.id,p.full_name,e.role FROM employees e "
            "JOIN employee_profiles p ON p.id=e.profile_id "
            "WHERE p.home_store_id=%s AND e.status='ACTIVE' AND p.employment_status='ACTIVE' "
            "ORDER BY p.full_name,e.id", (store_id,))

    def machines(self, conn, store_id):
        return rows(conn,
            "SELECT id AS machine_id,code AS machine_code,name FROM machines "
            "WHERE store_id=%s AND is_active=1 ORDER BY code,id", (store_id,))

    def machine(self, conn, machine_id, *, lock=False):
        result = rows(conn,
            "SELECT id,store_id,code,name,status,is_active FROM machines WHERE id=%s" +
            (" FOR UPDATE" if lock else ""), (machine_id,))
        return result[0] if result else None

    def employee_in_store(self, conn, employee_id, store_id):
        result = rows(conn,
            "SELECT e.id,p.full_name,e.role,e.status FROM employees e "
            "JOIN employee_profiles p ON p.id=e.profile_id "
            "WHERE e.id=%s AND p.home_store_id=%s",
            (employee_id,store_id))
        return result[0] if result else None

    def get_incident(self, conn, incident_id, *, lock=False):
        if lock:
            if not rows(conn, "SELECT id FROM machine_incidents WHERE id=%s FOR UPDATE", (incident_id,)):
                return None
        result = rows(conn,
            "SELECT i.*,m.store_id,m.code AS machine_code,m.name AS machine_name,"
            "rp.full_name AS reporter_name,ap.full_name AS assignee_name,"
            "vp.full_name AS verifier_name FROM machine_incidents i "
            "JOIN machines m ON m.id=i.machine_id "
            "JOIN employees r ON r.id=i.reported_by JOIN employee_profiles rp ON rp.id=r.profile_id "
            "LEFT JOIN employees a ON a.id=i.assigned_to LEFT JOIN employee_profiles ap ON ap.id=a.profile_id "
            "LEFT JOIN employees v ON v.id=i.verified_by LEFT JOIN employee_profiles vp ON vp.id=v.profile_id "
            "WHERE i.id=%s", (incident_id,))
        return result[0] if result else None

    def list_incidents(self, conn, store_id, status=None):
        sql = ("SELECT i.*,m.store_id,m.code AS machine_code,m.name AS machine_name,"
               "rp.full_name AS reporter_name,ap.full_name AS assignee_name "
               "FROM machine_incidents i JOIN machines m ON m.id=i.machine_id "
               "JOIN employees r ON r.id=i.reported_by JOIN employee_profiles rp ON rp.id=r.profile_id "
               "LEFT JOIN employees a ON a.id=i.assigned_to LEFT JOIN employee_profiles ap ON ap.id=a.profile_id "
               "WHERE m.store_id=%s")
        params = [store_id]
        if status:
            sql += " AND i.status=%s"; params.append(status)
        return rows(conn, sql + " ORDER BY i.reported_at DESC,i.id DESC LIMIT 200", tuple(params))

    def history(self, conn, incident_id):
        events = rows(conn,
            "SELECT x.*,ep.full_name AS employee_name FROM machine_incident_events x "
            "JOIN employees e ON e.id=x.employee_id "
            "JOIN employee_profiles ep ON ep.id=e.profile_id WHERE x.incident_id=%s "
            "ORDER BY x.created_at,x.id", (incident_id,))
        parts = rows(conn,
            "SELECT id,name,quantity,unit_cost,quantity*unit_cost AS total_cost "
            "FROM machine_incident_parts WHERE incident_id=%s ORDER BY id", (incident_id,))
        return events, parts

    def create(self, conn, *, code, store_id, machine_id, employee_id, severity, title, description):
        # store_id is derived from machines (NF-02); kept in signature for caller compatibility.
        _ = store_id
        incident_id = execute(conn,
            "INSERT INTO machine_incidents(code,machine_id,reported_by,severity,title,description) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (code,machine_id,employee_id,severity,title,description))
        self.event(conn, incident_id, employee_id, None, "REPORTED", description)
        return incident_id

    def event(self, conn, incident_id, employee_id, source, target, note):
        execute(conn,
            "INSERT INTO machine_incident_events(incident_id,employee_id,from_status,to_status,note) "
            "VALUES(%s,%s,%s,%s,%s)", (incident_id,employee_id,source,target,note))

    def transition(self, conn, incident, *, target, employee_id, assigned_to=None,
                   note="", resolution=None, labor_cost=None, parts=None):
        updates = ["status=%s"]; params = [target]
        if assigned_to is not None:
            updates.append("assigned_to=%s"); params.append(assigned_to)
        if target == "IN_PROGRESS" and incident["started_at"] is None:
            updates.append("started_at=UTC_TIMESTAMP()")
        if target == "IN_PROGRESS" and incident["status"] == "COMPLETED":
            updates.append("completed_at=NULL")
        if target == "COMPLETED":
            updates.extend(["completed_at=UTC_TIMESTAMP()","resolution=%s","labor_cost=%s"])
            params.extend([resolution,labor_cost])
            execute(conn,"DELETE FROM machine_incident_parts WHERE incident_id=%s",(incident["id"],))
            total = 0
            for part in parts or []:
                execute(conn,"INSERT INTO machine_incident_parts(incident_id,name,quantity,unit_cost) VALUES(%s,%s,%s,%s)",
                        (incident["id"],part["name"],part["quantity"],part["unit_cost"]))
                total += part["quantity"] * part["unit_cost"]
            updates.append("parts_cost=%s"); params.append(total)
        if target == "VERIFIED":
            updates.extend(["verified_at=UTC_TIMESTAMP()","verified_by=%s"]); params.append(employee_id)
        params.extend([incident["id"],incident["status"]])
        changed = execute(conn,"UPDATE machine_incidents SET " + ",".join(updates) +
                          " WHERE id=%s AND status=%s",tuple(params))
        if changed == 1:
            self.event(conn,incident["id"],employee_id,incident["status"],target,note)
        return changed

    def set_machine_maintenance(self, conn, machine_id, enabled):
        target = "MAINTENANCE" if enabled else "AVAILABLE"
        expected = "AVAILABLE" if enabled else "MAINTENANCE"
        return execute(conn,"UPDATE machines SET status=%s WHERE id=%s AND status=%s AND is_active=TRUE",
                       (target,machine_id,expected))
