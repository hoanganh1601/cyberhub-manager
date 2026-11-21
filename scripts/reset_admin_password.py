"""Recover an existing active administrator account from the local server console.

This command never creates an account or elevates another role. It is intended
only for the break-glass case where no other administrator can sign in.

python scripts/reset_admin_password.py --database cyberhub_manager --username admin01
"""

from __future__ import annotations

import argparse
from getpass import getpass

from cyberhub_manager.infrastructure.database.connection import get_connection
from cyberhub_manager.domain.exceptions import NotFoundError, ValidationError
from cyberhub_manager.infrastructure.repositories.p1_repository import execute, rows
from cyberhub_manager.infrastructure.security import hash_password


def reset_admin_password(conn, database: str, username: str, password: str) -> int:
    if not isinstance(username, str) or not username.strip():
        raise ValidationError("Administrator username is required")
    if (
        not isinstance(password, str)
        or len(password) < 8
        or len(password.encode("utf-8")) > 72
    ):
        raise ValidationError(
            "Use a password of at least 8 characters and at most 72 UTF-8 bytes"
        )

    current = rows(conn, "SELECT DATABASE() AS name")[0]["name"]
    if current != database:
        raise RuntimeError("Database does not match --database; no password was changed")

    matches = rows(
        conn,
        """SELECT id,store_id FROM employees
           WHERE username=%s AND role='ADMIN' AND status='ACTIVE'
           FOR UPDATE""",
        (username.strip(),),
    )
    if not matches:
        raise NotFoundError("Active administrator account was not found")

    admin = matches[0]
    execute(
        conn,
        """UPDATE employees
           SET password_hash=%s,auth_version=auth_version+1,
               must_change_password=TRUE,password_changed_at=CURRENT_TIMESTAMP
           WHERE id=%s""",
        (hash_password(password), admin["id"]),
    )
    execute(
        conn,
        """INSERT INTO management_audit(employee_id,store_id,action,entity_id)
           VALUES(%s,%s,'ADMIN_PASSWORD_RECOVERY',%s)""",
        (admin["id"], admin["store_id"], admin["id"]),
    )
    return int(admin["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    password = getpass("Temporary administrator password: ")
    if password != getpass("Confirm temporary password: "):
        parser.error("Passwords do not match")

    conn = get_connection()
    try:
        conn.start_transaction()
        reset_admin_password(conn, args.database, args.username, password)
        conn.commit()
        print("Administrator password recovered. Sign in and choose a new password.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
