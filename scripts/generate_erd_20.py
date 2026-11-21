"""Generate readable ERD views for the 20-table database course report."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cơ sở dữ liệu" / "figures"

views = [
    {
        "file": "erd_20_core.pdf",
        "title": "CyberHub Manager — nghiệp vụ lõi",
        "nodes": {
            "stores": (0, 2, "PK id"),
            "employees": (1, 2, "PK id"),
            "customers": (2, 2, "PK id"),
            "machines": (0, 1, "PK id · FK store_id"),
            "usage_sessions": (1, 1, "PK id · FK customer_id, machine_id"),
            "accounts": (2, 1, "PK id · FK customer_id (UK)"),
            "promotions": (0, 0, "PK id · FK store_id"),
            "account_transactions": (1, 0, "PK id · FK account_id, employee_id"),
            "invoices": (2, 0, "PK id · FK session_id (UK)"),
        },
        "edges": [
            ("stores", "machines", -0.05),
            ("stores", "promotions", 0.02),
            ("employees", "usage_sessions", 0.05),
            ("employees", "account_transactions", 0.04),
            ("employees", "invoices", -0.05),
            ("customers", "accounts", 0.05),
            ("customers", "usage_sessions", -0.05),
            ("customers", "invoices", 0.08),
            ("machines", "usage_sessions", 0.02),
            ("usage_sessions", "account_transactions", 0.02),
            ("usage_sessions", "invoices", -0.04),
            ("accounts", "account_transactions", -0.02),
            ("promotions", "account_transactions", 0.05),
        ],
        "color": "#e8eef8",
    },
    {
        "file": "erd_20_pos.pdf",
        "title": "CyberHub Manager — thực đơn và POS",
        "nodes": {
            "stores": (0, 3, "PK id"),
            "employees": (1, 3, "PK id"),
            "accounts": (2, 3, "PK id"),
            "machines": (3, 3, "PK id"),
            "menu_categories": (0, 2, "PK id · FK store_id"),
            "menu_items": (1, 2, "PK id · FK category_id"),
            "usage_sessions": (2, 2, "PK id · FK customer_id, machine_id"),
            "menu_orders": (3, 2, "PK id · FK store_id, account_id"),
            "menu_promotions": (0, 1, "PK id · FK store_id, item_id"),
            "menu_order_items": (1, 1, "PK order_id, item_id"),
            "menu_order_pricing": (2, 1, "PK order_id · FK promotion_id"),
            "pos_order_reversals": (3, 1, "PK id · FK order_id (UK)"),
        },
        "edges": [
            ("stores", "menu_categories", 0.02),
            ("stores", "menu_orders", -0.08),
            ("employees", "menu_orders", 0.03),
            ("accounts", "menu_orders", 0.03),
            ("machines", "menu_orders", -0.03),
            ("menu_categories", "menu_items", 0.02),
            ("menu_items", "menu_order_items", 0.02),
            ("menu_orders", "menu_order_items", -0.02),
            ("menu_orders", "menu_order_pricing", 0.02),
            ("menu_promotions", "menu_order_pricing", -0.02),
            ("menu_items", "menu_promotions", -0.02),
            ("menu_orders", "pos_order_reversals", 0.02),
            ("usage_sessions", "menu_orders", 0.06),
        ],
        "color": "#fff2dc",
    },
    {
        "file": "erd_20_support.pdf",
        "title": "CyberHub Manager — phân công, kiểm toán và thông báo",
        "nodes": {
            "stores": (0, 2, "PK id"),
            "employees": (1, 2, "PK id"),
            "customers": (2, 2, "PK id"),
            "employee_store_assignments": (0, 1, "PK employee_id, store_id"),
            "management_audit": (1, 1, "PK id · FK employee_id, store_id"),
            "customer_notification_events": (2, 1, "PK id · FK store_id (nullable)"),
            "customer_notification_reads": (1, 0, "PK event_id, customer_id"),
        },
        "edges": [
            ("stores", "employee_store_assignments", 0.02),
            ("employees", "employee_store_assignments", -0.03),
            ("employees", "management_audit", -0.02),
            ("stores", "management_audit", 0.10),
            ("stores", "customer_notification_events", 0.03),
            ("customer_notification_events", "customer_notification_reads", -0.03),
            ("customers", "customer_notification_reads", 0.03),
        ],
        "color": "#f3eafb",
    },
]


def draw_view(view: dict) -> None:
    nodes = view["nodes"]
    cols = max(x for x, _, _ in nodes.values()) + 1
    rows = max(y for _, y, _ in nodes.values()) + 1
    fig, ax = plt.subplots(figsize=(10.8, 2.0 + rows * 1.75))
    box_w, box_h = 2.45, 0.72
    x_step, y_step = 3.05, 1.55
    x0, y0 = 0.15, 0.65
    positions = {name: (x0 + col * x_step, y0 + row * y_step) for name, (col, row, _) in nodes.items()}
    ax.set_xlim(-0.05, x0 + max(cols - 1, 0) * x_step + box_w + 0.15)
    ax.set_ylim(0.25, y0 + max(rows - 1, 0) * y_step + box_h + 0.35)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_title(view["title"], fontsize=15, weight="bold", pad=16)

    for parent, child, curve in view["edges"]:
        px, py = positions[parent]
        cx, cy = positions[child]
        ax.add_patch(FancyArrowPatch(
            (px + box_w / 2, py + box_h / 2),
            (cx + box_w / 2, cy + box_h / 2),
            arrowstyle="-|>", mutation_scale=9, linewidth=0.9,
            color="#738399", alpha=0.8,
            connectionstyle=f"arc3,rad={curve}",
            shrinkA=22, shrinkB=22, zorder=1,
        ))

    for name, (_, _, keys) in nodes.items():
        x, y = positions[name]
        ax.add_patch(FancyBboxPatch(
            (x, y), box_w, box_h,
            boxstyle="round,pad=0.035,rounding_size=0.06",
            linewidth=1.0, edgecolor="#35465c", facecolor=view["color"], zorder=2,
        ))
        ax.text(x + 0.10, y + 0.47, name, fontsize=8.4, weight="bold", va="center", zorder=3)
        ax.text(x + 0.10, y + 0.19, keys, fontsize=6.4, color="#344054", va="center", zorder=3)

    fig.tight_layout(pad=0.45)
    fig.savefig(OUT / view["file"], bbox_inches="tight")
    plt.close(fig)


OUT.mkdir(parents=True, exist_ok=True)
for view in views:
    draw_view(view)
print("Generated three ERD views for the 20-table report.")
