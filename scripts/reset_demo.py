"""Reset demo data only in explicitly allowed databases."""

from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.infrastructure.database.connection import get_connection

ALLOWED_RESET_DATABASES = frozenset({
    "cyberhub_manager_migration_test",
    "cyberhub_manager_demo",
})

# Delete dependent child records before parent records (FK-safe across all 75 tables).
# Singleton migration-seeded configuration tables (loyalty_settings, loyalty_policy_versions,
# games, game_prizes, ad_settings) and schema_migrations are preserved.
RESET_TABLES = (
    # Commercial partners & settlements
    "commercial_settlement_lines",
    "commercial_settlements",
    "commercial_reward_grants",
    "commercial_events",
    "commercial_play_sessions",
    "commercial_placements",
    "commercial_campaigns",
    "commercial_contracts",
    "commercial_partners",
    # Procurement & payables
    "supplier_payable_approvals",
    "supplier_payables",
    "goods_receipt_lines",
    "goods_receipts",
    "purchase_order_lines",
    "purchase_orders",
    "purchase_request_lines",
    "purchase_requests",
    "suppliers",
    # Maintenance
    "machine_incident_events",
    "machine_incident_parts",
    "machine_incidents",
    # Cash shifts
    "cash_shift_entries",
    "active_employee_shifts",
    "cash_shifts",
    # Ads & games (operational rows; keep games/game_prizes/ad_settings config)
    "ad_reward_events",
    "ad_creatives",
    "game_coin_ledger",
    "game_sessions",
    "game_wallets",
    # Vouchers & loyalty grants
    "loyalty_point_grants",
    "voucher_events",
    "menu_order_pricing",
    "customer_vouchers",
    "reward_catalog",
    # POS orders, inventory, menu catalog
    "pos_order_reversals",
    "inventory_counts",
    "inventory_movements",
    "menu_order_recipe_snapshots",
    "menu_item_recipes",
    "inventory_ingredients",
    "menu_order_items",
    "menu_orders",
    "menu_promotion_versions",
    "menu_promotions",
    "menu_item_changes",
    "menu_item_images",
    "menu_items",
    "menu_categories",
    # Customer portal, notifications & security
    "customer_notification_events",
    "customer_notification_reads",
    "customer_avatars",
    "customer_mail_outbox",
    "customer_email_tokens",
    "customer_security_audit",
    "management_audit",
    # Core billing, 3NF ledger & sessions
    "invoices",
    "session_transactions",
    "account_transactions",
    "active_usage_sessions",
    "usage_sessions",
    "machine_room_types",
    "machines",
    "promotions",
    "customer_store_links",
    "accounts",
    "customers",
    "employee_store_assignments",
    "employees",
    "employee_profiles",
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
    database = validate_reset_database(connection)

    deleted_counts: dict[str, int] = {}

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'",
            (database,),
        )
        existing = {row[0] for row in cursor.fetchall()}
        for table in RESET_TABLES:
            if table in existing:
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
            if count:
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
