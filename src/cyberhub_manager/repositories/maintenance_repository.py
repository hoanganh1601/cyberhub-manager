"""Persistence for machine incidents, parts and immutable status history."""

from cyberhub_manager.repositories.sql import execute, rows


class MaintenanceRepository:
    def employees(self, conn, store_id):
        return rows(conn,
            "SELECT id,full_name,role FROM employees WHERE store_id=%s AND status='ACTIVE' "
            "ORDER BY full_name,id", (store_id,))

    def machine(self, conn, machine_id, *, lock=False):
        result = rows(conn,
            "SELECT id,store_id,code,name,status,is_active FROM machines WHERE id=%s" +
            (" FOR UPDATE" if lock else ""), (machine_id,))
        return result[0] if result else None

    def employee_in_store(self, conn, employee_id, store_id):
        result = rows(conn,
            "SELECT id,full_name,role,status FROM employees WHERE id=%s AND store_id=%s",
            (employee_id,store_id))
        return result[0] if result else None

    def get_incident(self, conn, incident_id, *, lock=False):
        result = rows(conn,
            "SELECT i.*,m.code AS machine_code,m.name AS machine_name,"
            "r.full_name AS reporter_name,a.full_name AS assignee_name,"
            "v.full_name AS verifier_name FROM machine_incidents i "
            "JOIN machines m ON m.id=i.machine_id JOIN employees r ON r.id=i.reported_by "
            "LEFT JOIN employees a ON a.id=i.assigned_to LEFT JOIN employees v ON v.id=i.verified_by "
            "WHERE i.id=%s" + (" FOR UPDATE" if lock else ""), (incident_id,))
        return result[0] if result else None

    def list_incidents(self, conn, store_id, status=None):
        sql = ("SELECT i.*,m.code AS machine_code,m.name AS machine_name,"
               "r.full_name AS reporter_name,a.full_name AS assignee_name "
               "FROM machine_incidents i JOIN machines m ON m.id=i.machine_id "
               "JOIN employees r ON r.id=i.reported_by LEFT JOIN employees a ON a.id=i.assigned_to "
               "WHERE i.store_id=%s")
        params = [store_id]
        if status:
            sql += " AND i.status=%s"; params.append(status)
        return rows(conn, sql + " ORDER BY i.reported_at DESC,i.id DESC LIMIT 200", tuple(params))

    def history(self, conn, incident_id):
        events = rows(conn,
            "SELECT x.*,e.full_name AS employee_name FROM machine_incident_events x "
            "JOIN employees e ON e.id=x.employee_id WHERE x.incident_id=%s "
            "ORDER BY x.created_at,x.id", (incident_id,))
        parts = rows(conn,
            "SELECT id,name,quantity,unit_cost,quantity*unit_cost AS total_cost "
            "FROM machine_incident_parts WHERE incident_id=%s ORDER BY id", (incident_id,))
        return events, parts

    def create(self, conn, *, code, store_id, machine_id, employee_id, severity, title, description):
        incident_id = execute(conn,
            "INSERT INTO machine_incidents(code,store_id,machine_id,reported_by,severity,title,description) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (code,store_id,machine_id,employee_id,severity,title,description))
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
