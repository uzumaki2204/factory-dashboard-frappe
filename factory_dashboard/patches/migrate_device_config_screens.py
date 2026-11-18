"""Move legacy device selections into the Left and Right screen fields."""
import frappe


def execute():
    configs = frappe.get_all(
        "Productivity Dashboard Device Config",
        fields=[
            "name", "display_mode", "left_line", "left_group", "right_line", "right_group",
            "primary_line", "secondary_line", "single_group",
        ],
        limit_page_length=0,
    )

    for config in configs:
        updates = {}
        mode = (config.display_mode or "single").strip().lower()

        if not config.left_line and not config.left_group:
            if mode == "dual":
                if config.primary_line:
                    updates["left_line"] = config.primary_line
            elif config.single_group:
                updates["left_group"] = config.single_group
            elif config.primary_line:
                updates["left_line"] = config.primary_line

        if mode == "dual" and not config.right_line and not config.right_group and config.secondary_line:
            updates["right_line"] = config.secondary_line

        if config.left_group and config.left_line:
            updates["left_line"] = None
        if config.right_group and config.right_line:
            updates["right_line"] = None

        if updates:
            frappe.db.set_value(
                "Productivity Dashboard Device Config", config.name, updates, update_modified=False,
            )
