"""Review and explicitly apply a per-account ADMIN to DIRECTOR cutover manifest.

Dry-run: python -m scripts.rbac_cutover mapping.json --database cyberhub_manager_test
Apply:   python -m scripts.rbac_cutover mapping.json --database cyberhub_manager_test --apply
No role is inferred from a name, store or employment position.
"""

import argparse
from getpass import getpass
import json
import os
from pathlib import Path

from cyberhub_manager.infrastructure.config import load_settings
from cyberhub_manager.infrastructure.database.connection import get_connection
from cyberhub_manager.infrastructure.repositories.auth_repository import AuthRepository
from cyberhub_manager.infrastructure.security import verify_password


ALLOWED_TARGETS = {"ADMIN", "DIRECTOR", "MANAGER"}


def validate_manifest(manifest, employees):
    if not isinstance(manifest, dict) or not isinstance(manifest.get("approval_reference"), str) \
            or len(manifest["approval_reference"].strip()) < 3:
        raise ValueError("Manifest needs an approval_reference")
    changes = manifest.get("accounts")
    if not isinstance(changes, list) or not changes:
        raise ValueError("Manifest needs an accounts list")
    by_id = {row["id"]: row for row in employees}
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or type(change.get("employee_id")) is not int:
            raise ValueError("Each account needs an integer employee_id")
        employee_id = change["employee_id"]
        if employee_id in seen or employee_id not in by_id:
            raise ValueError("Duplicate or unknown employee_id")
        seen.add(employee_id)
        existing = by_id[employee_id]
        if (change.get("username") != existing["username"] or
                change.get("expected_role") != existing["role"] or
                existing["status"] != "ACTIVE" or
                change.get("target_role") not in ALLOWED_TARGETS):
            raise ValueError(f"Account {employee_id} changed or mapping is invalid")
        if existing["role"] not in ("ADMIN", "DIRECTOR", "MANAGER"):
            raise ValueError("Only leadership accounts may be mapped")
    active_admins = {row["id"] for row in employees if row["role"] == "ADMIN" and row["status"] == "ACTIVE"}
    if not active_admins <= seen:
        raise ValueError("Map every active ADMIN explicitly before cutover")
    final_roles = {row["id"]: row["role"] for row in employees if row["status"] == "ACTIVE"}
    for change in changes:
        final_roles[change["employee_id"]] = change["target_role"]
    if "ADMIN" not in final_roles.values() or "DIRECTOR" not in final_roles.values():
        raise ValueError("Cutover needs at least one technical ADMIN and one business DIRECTOR")
    return changes


def read_employees(conn, lock=False):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id,username,role,status FROM employees ORDER BY id" +
                    (" FOR UPDATE" if lock else ""))
        return cur.fetchall()
    finally:
        cur.close()


def apply_mapping(conn, changes, actor_id):
    cur = conn.cursor()
    try:
        for change in changes:
            if change["expected_role"] == change["target_role"]:
                continue
            if change["employee_id"] == actor_id:
                raise ValueError("The executing ADMIN cannot change their own role")
            cur.execute("UPDATE employees SET role=%s,auth_version=auth_version+1 "
                        "WHERE id=%s AND username=%s AND role=%s AND status='ACTIVE'",
                        (change["target_role"],change["employee_id"],
                         change["username"],change["expected_role"]))
            if cur.rowcount != 1:
                raise ValueError("Account changed during cutover; transaction rolled back")
            cur.execute("INSERT INTO management_audit(employee_id,store_id,action,entity_id) "
                        "SELECT %s,p.home_store_id,'RBAC_CUTOVER',e.id "
                        "FROM employees e JOIN employee_profiles p ON p.id=e.profile_id WHERE e.id=%s",
                        (actor_id,change["employee_id"]))
    finally:
        cur.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--admin-username", help="Required with --apply")
    args = parser.parse_args()
    settings = load_settings()
    if args.database != settings.mysql_database:
        raise RuntimeError("--database must match MYSQL_DATABASE exactly")
    if os.getenv("CYBERHUB_RBAC_POLICY", "legacy").lower() != "legacy":
        raise RuntimeError("Run cutover while the web still uses legacy policy")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT DATABASE()")
            (actual,) = cur.fetchone()
        finally:
            cur.close()
        if actual != args.database:
            raise RuntimeError("Connected database does not match --database")
        conn.start_transaction()
        changes = validate_manifest(manifest, read_employees(conn, lock=args.apply))
        print("Reviewed mapping:")
        for item in changes:
            print(f"  {item['employee_id']} {item['username']}: {item['expected_role']} -> {item['target_role']}")
        if not args.apply:
            conn.rollback()
            print("Dry-run only; no roles changed.")
            return
        if not args.admin_username:
            raise ValueError("--apply requires --admin-username")
        record = AuthRepository().get_active_by_username(conn,args.admin_username)
        if record is None or record.session.role.value != "ADMIN" or not verify_password(
                getpass("Current ADMIN password: "), record.password_hash):
            raise ValueError("ADMIN authentication failed")
        apply_mapping(conn, changes, record.session.employee_id)
        conn.commit()
        print("Cutover committed; changed sessions were revoked. Verify logins before enabling separated policy.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
