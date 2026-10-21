"""Create fictional demo data without overwriting existing records."""

from getpass import getpass

from mysql.connector.pooling import PooledMySQLConnection

from cyberhub_manager.database.connection import get_connection
from cyberhub_manager.security import hash_password


DEMO_STORE_CODE = "DEMO_STORE_01"

# Each entry contains: code, full_name, username, role.
DEMO_EMPLOYEES = (
    (
        "DEMO_EMP_01",
        "Quản lý demo",
        "demo.manager",
        "MANAGER",
    ),
    (
        "DEMO_EMP_02",
        "Nhân viên demo 01",
        "demo.staff01",
        "STAFF",
    ),
    (
        "DEMO_EMP_03",
        "Nhân viên demo 02",
        "demo.staff02",
        "STAFF",
    ),
)

DEMO_CUSTOMER_COUNT = 5
DEMO_MACHINE_COUNT = 20
DEMO_HOURLY_RATE = 10_000

def seed_store(connection: PooledMySQLConnection) -> int:
    """Create the demo store if missing and return its ID."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM stores WHERE code = %s",
            (DEMO_STORE_CODE,),
        )
        existing = cursor.fetchone()

        if existing is not None:
            print(f"[SKIP] Store: {DEMO_STORE_CODE}")
            return int(existing[0])

        cursor.execute(
            """
            INSERT INTO stores (code, name, address, status)
            VALUES (%s, %s, %s, %s)
            """,
            (
                DEMO_STORE_CODE,
                "CyberHub Demo",
                "Địa chỉ giả lập phục vụ demo",
                "ACTIVE",
            ),
        )

        store_id = cursor.lastrowid

        if store_id is None:
            raise RuntimeError("Cannot retrieve the demo store ID.")

    print(f"[INSERT] Store: {DEMO_STORE_CODE}")
    return int(store_id)

def seed_employees(
    connection: PooledMySQLConnection,
    store_id: int,
    demo_password: str,
) -> None:
    """Create missing demo employees without resetting existing ones."""
    with connection.cursor() as cursor:
        for code, full_name, username, role in DEMO_EMPLOYEES:
            cursor.execute(
                """
                SELECT store_id, username
                FROM employees
                WHERE code = %s
                """,
                (code,),
            )
            existing = cursor.fetchone()

            if existing is not None:
                if (
                    int(existing[0]) != store_id
                    or existing[1] != username
                ):
                    raise RuntimeError(
                        f"Demo employee identity conflict: {code}"
                    )

                print(f"[SKIP] Employee: {username}")
                continue

            cursor.execute(
                """
                INSERT INTO employees (
                    code,
                    store_id,
                    full_name,
                    username,
                    password_hash,
                    role,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    store_id,
                    full_name,
                    username,
                    hash_password(demo_password),
                    role,
                    "ACTIVE",
                ),
            )

            print(f"[INSERT] Employee: {username}")

def seed_customers(
    connection: PooledMySQLConnection,
) -> dict[int, int]:
    """Create missing demo customers and return their database IDs."""
    customer_ids: dict[int, int] = {}

    with connection.cursor() as cursor:
        for number in range(1, DEMO_CUSTOMER_COUNT + 1):
            code = f"DEMO_CUS_{number:02d}"

            cursor.execute(
                "SELECT id FROM customers WHERE code = %s",
                (code,),
            )
            existing = cursor.fetchone()

            if existing is not None:
                customer_ids[number] = int(existing[0])
                print(f"[SKIP] Customer: {code}")
                continue

            cursor.execute(
                """
                INSERT INTO customers (
                    code,
                    full_name,
                    phone,
                    status
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    code,
                    f"Khách demo {number:02d}",
                    f"0{number:09d}",
                    "ACTIVE",
                ),
            )

            customer_id = cursor.lastrowid

            if customer_id is None:
                raise RuntimeError(
                    f"Cannot retrieve the demo customer ID: {code}"
                )

            customer_ids[number] = int(customer_id)
            print(f"[INSERT] Customer: {code}")

    return customer_ids

def seed_accounts(
    connection: PooledMySQLConnection,
    customer_ids: dict[int, int],
    demo_password: str,
) -> None:
    with connection.cursor() as cursor:
        for number, customer_id in sorted(customer_ids.items()):
            code = f"DEMO_ACC_{number:02d}"
            username = f"demo.customer{number:02d}"

            cursor.execute(
                """
                SELECT customer_id, username
                FROM accounts
                WHERE code = %s
                """,
                (code,),
            )
            existing = cursor.fetchone()

            if existing is not None:
                if (
                    int(existing[0]) != customer_id
                    or existing[1] != username
                ):
                    raise RuntimeError(
                        f"Demo account identity conflict: {code}"
                    )

                print(f"[SKIP] Account: {username}")
                continue

            cursor.execute(
                """
                INSERT INTO accounts (
                    code,
                    customer_id,
                    username,
                    password_hash,
                    balance,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    customer_id,
                    username,
                    hash_password(demo_password),
                    0,
                    "ACTIVE",
                ),
            )

            print(f"[INSERT] Account: {username}")

def seed_machines(
    connection: PooledMySQLConnection,
    store_id: int,
) -> None:
    """Create missing demo machines without changing existing ones."""
    with connection.cursor() as cursor:
        for number in range(1, DEMO_MACHINE_COUNT + 1):
            code = f"DEMO_PC_{number:02d}"

            cursor.execute(
                "SELECT store_id FROM machines WHERE code = %s",
                (code,),
            )
            existing = cursor.fetchone()

            if existing is not None:
                if int(existing[0]) != store_id:
                    raise RuntimeError(
                        f"Demo machine store conflict: {code}"
                    )

                print(f"[SKIP] Machine: {code}")
                continue

            cursor.execute(
                """
                INSERT INTO machines (
                    code,
                    store_id,
                    name,
                    status,
                    hourly_rate,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    store_id,
                    f"Máy demo {number:02d}",
                    "AVAILABLE",
                    DEMO_HOURLY_RATE,
                    True,
                ),
            )

            print(f"[INSERT] Machine: {code}")

def run_seed(expected_database: str | None = None) -> None:
    """Create demo data in one transaction."""
    connection = get_connection()

    try:
        actual_database = connection.database

        if (
            expected_database is not None
            and actual_database != expected_database
        ):
            raise RuntimeError(
                f"Wrong database: expected {expected_database}, "
                f"got {actual_database}"
            )

        print(f"Database: {actual_database}")

        demo_password = getpass(
            "Demo password (not your MySQL password): "
        )
        confirmation = getpass("Confirm demo password: ")

        if not demo_password:
            raise ValueError("Demo password must not be empty.")

        if demo_password != confirmation:
            raise ValueError("Demo passwords do not match.")

        connection.start_transaction()

        with connection.cursor() as cursor:
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}

        required = {
            "001_initial_schema.sql",
            "002_indexes.sql",
        }

        if not required.issubset(applied):
            raise RuntimeError(
                "Required migrations are missing. Run migrations first."
            )

        store_id = seed_store(connection)
        seed_employees(connection, store_id, demo_password)

        customer_ids = seed_customers(connection)
        seed_accounts(connection, customer_ids, demo_password)

        seed_machines(connection, store_id)

        connection.commit()
        print("Demo seed committed successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()