"""Reset demo data only in explicitly allowed databases."""
from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.database.connection import get_connection

ALLOWED_RESET_DATABASES = frozenset({
    "cyberhub_manager_migration_test",
    "cyberhub_manager_demo",
})

# Delete dependent records before their parent records.
RESET_TABLES = (
    "invoices",
    "account_transactions",
    "usage_sessions",
    "machines",
    "accounts",
    "customers",
    "employees",
    "stores",
)

def validate_reset_database(
    connection: PooledMySQLConnection,
) -> str:
    """Reject reset requests outside the demo database allowlist."""
    database = connection.database

    if database not in ALLOWED_RESET_DATABASES:
        raise RuntimeError(
            f"Reset is not allowed for database: {database}"
        )

    return database

def clear_demo_data(
    connection: PooledMySQLConnection,
) -> dict[str, int]:
    """Delete demo database rows without committing."""
    validate_reset_database(connection)

    deleted_counts: dict[str, int] = {}

    with connection.cursor() as cursor:
        for table in RESET_TABLES:
            cursor.execute(f"DELETE FROM `{table}`")
            deleted_counts[table] = cursor.rowcount

    return deleted_counts

def run_reset(expected_database: str | None = None) -> None:
    """Reset demo data after verifying the target database."""
    connection = get_connection()

    try:
        database = validate_reset_database(connection)

        if (
            expected_database is not None
            and database != expected_database
        ):
            raise RuntimeError(
                f"Wrong database: expected {expected_database}, "
                f"got {database}"
            )

        confirmation_text = f"RESET {database}"
        confirmation = input(
            f"Type '{confirmation_text}' to delete demo data: "
        )

        if confirmation != confirmation_text:
            print("Reset cancelled.")
            return

        connection.start_transaction()
        deleted_counts = clear_demo_data(connection)
        connection.commit()

        for table, count in deleted_counts.items():
            print(f"[DELETE] {table}: {count}")

        print("Demo data reset successfully.")
        print("Migration history was preserved.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

if __name__ == "__main__":
    run_reset()