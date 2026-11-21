"""MySQL aggregates for forecasting; returns plain rows without customer identities."""

def daily_forecast_rows(conn, *, store_id, start_day, end_day):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT DATE(DATE_ADD(i.created_at, INTERVAL 7 HOUR)) AS local_day,
                   COUNT(*) AS session_count,
                   COUNT(DISTINCT i.customer_id) AS customer_count,
                   SUM(i.usage_cost) AS revenue,
                   SUM(CASE WHEN COALESCE(rt.room_type, 'STANDARD') = 'STANDARD' THEN 1 ELSE 0 END) AS standard_sessions,
                   SUM(CASE WHEN rt.room_type = 'VIP' THEN 1 ELSE 0 END) AS vip_sessions,
                   SUM(CASE WHEN rt.room_type = 'COUPLE' THEN 1 ELSE 0 END) AS couple_sessions,
                   SUM(CASE WHEN rt.room_type = 'SUPER_VIP' THEN 1 ELSE 0 END) AS super_vip_sessions,
                   SUM(CASE WHEN COALESCE(rt.room_type, 'STANDARD') = 'STANDARD' THEN i.usage_cost ELSE 0 END) AS standard_revenue,
                   SUM(CASE WHEN rt.room_type = 'VIP' THEN i.usage_cost ELSE 0 END) AS vip_revenue,
                   SUM(CASE WHEN rt.room_type = 'COUPLE' THEN i.usage_cost ELSE 0 END) AS couple_revenue,
                   SUM(CASE WHEN rt.room_type = 'SUPER_VIP' THEN i.usage_cost ELSE 0 END) AS super_vip_revenue
            FROM invoices i
            JOIN usage_sessions u ON u.id = i.session_id
            JOIN machines m ON m.id = u.machine_id
            LEFT JOIN machine_room_types rt ON rt.machine_id = m.id
            WHERE i.store_id = %s AND i.status = 'PAID'
              AND i.created_at >= DATE_SUB(%s, INTERVAL 7 HOUR)
              AND i.created_at < DATE_SUB(DATE_ADD(%s, INTERVAL 1 DAY), INTERVAL 7 HOUR)
            GROUP BY local_day
            ORDER BY local_day
            """,
            (store_id, start_day, end_day),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    return rows
