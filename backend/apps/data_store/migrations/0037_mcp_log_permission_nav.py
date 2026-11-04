from django.db import migrations

from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS, nav_menu_item_defaults

MCP_LOG_PERM = "mcpLog.view"
MENU_ID = "nav-item-mcpLogs"
TARGET_ROLE_NAMES = {"开发", "开发运维", "生产管理员"}
TARGET_ROLE_IDS = {"role-developer", "role-production-admin"}


def _merge_perm(permissions: list) -> tuple[list, bool]:
    values = list(permissions or [])
    if MCP_LOG_PERM in values:
        return values, False
    values.append(MCP_LOG_PERM)
    return values, True


def grant_mcp_log_permission(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    for role in RoleRecord.objects.filter(is_deleted=False):
        data = dict(role.data or {})
        name = str(data.get("name") or role.name or "")
        role_id = str(role.id or "")
        if name not in TARGET_ROLE_NAMES and role_id not in TARGET_ROLE_IDS:
            continue
        permissions, changed = _merge_perm(list(data.get("permissions") or []))
        if not changed:
            continue
        data["permissions"] = permissions
        data.setdefault("id", role_id)
        data.setdefault("name", name)
        role.data = data
        role.name = name or role.name
        role.save(update_fields=["data", "name", "updated_at"])


def install_mcp_log_nav(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    rows = {row["id"]: row for row in DEFAULT_NAV_ITEMS}
    item = rows.get(MENU_ID)
    if not item:
        return
    defaults = nav_menu_item_defaults(item)
    NavMenuItemRecord.objects.update_or_create(
        id=item["id"],
        defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )


def reverse_mcp_log(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    NavMenuItemRecord.objects.filter(id=MENU_ID).update(is_deleted=True)


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0036_user_api_token"),
    ]

    operations = [
        migrations.RunPython(grant_mcp_log_permission, reverse_mcp_log),
        migrations.RunPython(install_mcp_log_nav, migrations.RunPython.noop),
    ]
