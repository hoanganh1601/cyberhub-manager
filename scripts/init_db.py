"""Initialize the database using versioned SQL migrations."""
import hashlib
from pathlib import Path
from cyberhub_manager.database.connection import get_connection
from mysql.connector.pooling import PooledMySQLConnection

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "sql"

CREATE_MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) NOT NULL,
    checksum CHAR(64) NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (version)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
"""

def find_migration_files() -> list[Path]:
    """Find numbered SQL migrations in execution order."""
    if not SQL_DIR.is_dir():
        raise FileNotFoundError(
            f"SQL directory does not exist: {SQL_DIR}"
        )

    migration_files = sorted(
        path
        for path in SQL_DIR.glob("[0-9][0-9][0-9]_*.sql")
        if path.is_file()
    )

    if not migration_files:
        raise FileNotFoundError(
            f"No numbered SQL migrations found in: {SQL_DIR}"
        )

    return migration_files

def read_migration(path: Path) -> tuple[str, str]:
    """Read SQL and calculate its SHA-256 checksum."""
    sql = path.read_text(encoding="utf-8-sig")

    if not sql.strip():
        raise ValueError(f"Migration file is empty: {path.name}")

    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

    return sql, checksum

def ensure_migration_table(
    connection: PooledMySQLConnection,
) -> None:
    """Create the migration tracking table if it does not exist."""
    with connection.cursor() as cursor:
        cursor.execute(CREATE_MIGRATION_TABLE_SQL)

    connection.commit()

def get_applied_migrations(
    connection: PooledMySQLConnection,
) -> dict[str, str]:
    """Return applied migration filenames and their checksums."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT version, checksum
            FROM schema_migrations
            ORDER BY version
            """
        )
        rows = cursor.fetchall()

    return {
        version: checksum
        for version, checksum in rows
    }

def execute_migration_sql(
    connection: PooledMySQLConnection,
    sql: str,
) -> None:
    """Execute a SQL script and consume all statement results."""
    with connection.cursor() as cursor:
        cursor.execute(sql)

        while True:
            if cursor.with_rows:
                cursor.fetchall()

            if not cursor.nextset():
                break

def apply_migration(
    connection: PooledMySQLConnection,
    path: Path,
) -> None:
    """Apply one migration and record it only after success."""
    sql, checksum = read_migration(path)

    try:
        execute_migration_sql(connection, sql)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO schema_migrations (version, checksum)
                VALUES (%s, %s)
                """,
                (path.name, checksum),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

def run_migrations() -> None:
    """Validate migration history and apply pending migrations."""
    migration_files = find_migration_files()

    checksums = {
        path.name: read_migration(path)[1]
        for path in migration_files
    }

    connection = get_connection()

    try:
        ensure_migration_table(connection)
        applied = get_applied_migrations(connection)

        # Validate all recorded migrations before applying new ones.
        for version, saved_checksum in applied.items():
            if version not in checksums:
                raise RuntimeError(
                    f"Applied migration file is missing: {version}"
                )

            if checksums[version] != saved_checksum:
                raise RuntimeError(
                    f"Applied migration has been modified: {version}"
                )

        for path in migration_files:
            if path.name in applied:
                print(f"[SKIP] {path.name}")
                continue

            print(f"[APPLY] {path.name}")

            try:
                apply_migration(connection, path)
            except Exception as exc:
                raise RuntimeError(
                    f"Migration failed: {path.name}. "
                    "DDL may be partially applied. "
                    "Inspect the database before retrying."
                ) from exc

            print(f"[OK] {path.name}")

        print("Database migrations completed.")

    finally:
        connection.close()

if __name__ == "__main__":
    run_migrations()