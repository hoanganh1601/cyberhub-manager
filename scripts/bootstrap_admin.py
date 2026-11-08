"""Create the first administrator after migration; never elevate an existing employee.

python scripts/bootstrap_admin.py --database cyberhub_manager --store STORE_CODE --username admin.user --name "Administrator"
Passwords are read interactively, never from command-line arguments or committed defaults.
"""

import argparse
from getpass import getpass
from uuid import uuid4

from cyberhub_manager.database.connection import get_connection
from cyberhub_manager.repositories.p1_repository import rows, execute
from cyberhub_manager.security import hash_password
from cyberhub_manager.domain.exceptions import ConflictError, ValidationError
from cyberhub_manager.services.management_service import text
import re


def bootstrap(conn, database, store_code, username, name, password):
    name = text(name, "full_name", 2, 100)
    if not isinstance(username, str) or not re.fullmatch(
        r"[A-Za-z0-9_.]{4,30}", username
    ):
        raise ValidationError("Invalid administrator username")
    if (
        not isinstance(password, str)
        or len(password) < 8
        or len(password.encode()) > 72
    ):
        raise ValidationError(
            "Use a password of at least 8 characters and at most 72 UTF-8 bytes"
        )
    current = rows(conn, "SELECT DATABASE() AS name")[0]["name"]
    if current != database:
        raise RuntimeError("Database does not match --database; no account was created")
    # Lock the same employee range as normal administration, including an empty range.
    employees = rows(
        conn, "SELECT id,username,role,status FROM employees ORDER BY id FOR UPDATE"
    )
    if any(e["role"] == "ADMIN" and e["status"] == "ACTIVE" for e in employees):
        raise ConflictError(
            "An active administrator already exists. Use the Employees screen."
        )
    if any(e["username"].casefold() == username.casefold() for e in employees):
        raise ConflictError(
            "Username already exists. Choose a new administrator username."
        )
    stores = rows(
        conn,
        "SELECT id FROM stores WHERE code=%s AND status='ACTIVE' FOR SHARE",
        (store_code,),
    )
    if not stores:
        raise ValidationError("Choose an existing active store code")
    employee_id = execute(
        conn,
        "INSERT INTO employees(code,store_id,full_name,username,password_hash,role,status) VALUES(%s,%s,%s,%s,%s,'ADMIN','ACTIVE')",
        (
            "NV-" + uuid4().hex[:17],
            stores[0]["id"],
            name,
            username,
            hash_password(password),
        ),
    )
    execute(
        conn,
        "INSERT INTO management_audit(employee_id,store_id,action,entity_id) VALUES(%s,%s,'ADMIN_BOOTSTRAP',%s)",
        (employee_id, stores[0]["id"], employee_id),
    )
    return employee_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("database", "store", "username", "name"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    password = getpass("New administrator password: ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    conn = get_connection()
    try:
        conn.start_transaction()
        bootstrap(conn, args.database, args.store, args.username, args.name, password)
        conn.commit()
        print("Initial administrator created. Sign in through desktop or web.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
