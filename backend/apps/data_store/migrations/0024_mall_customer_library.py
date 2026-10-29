"""资料库展示列表：菜单项 + mallCustomer 权限一次性授予。"""

from django.db import migrations

from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS, nav_menu_item_defaults

VIEW = "mallCustomer.view"
MANAGE = "mallCustomer.manage"
MENU_ID = "nav-item-mallCustomers"


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    wanted = set()
    if "library.view" in permissions or "library.manage" in permissions or "user.manage" in permissions:
        wanted.update({VIEW, MANAGE})
    if not wanted:
        return permissions, False
    next_permissions = list(permissions)
    changed = False
    for key in (VIEW, MANAGE):
        if key in wanted and key not in next_permissions:
            next_permissions.append(key)
            changed = True
    return next_permissions, changed


def apply_mall_customer_nav_and_perms(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")

    for row in DEFAULT_NAV_ITEMS:
        if row["id"] != MENU_ID:
            continue
        defaults = nav_menu_item_defaults(row)
        NavMenuItemRecord.objects.update_or_create(
            id=row["id"],
            defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )

    for role in RoleRecord.objects.all():
        data = dict(role.data or {})
        permissions, changed = _grant(list(data.get("permissions") or []))
        if not changed:
            continue
        data["permissions"] = permissions
        role.data = data
        role.save(update_fields=["data"])

    for state in AppState.objects.all():
        payload = dict(state.data or {})
        roles = payload.get("roles")
        if not isinstance(roles, list):
            continue
        changed = False
        next_roles = []
        for role in roles:
            if not isinstance(role, dict):
                next_roles.append(role)
                continue
            permissions, role_changed = _grant(list(role.get("permissions") or []))
            if role_changed:
                changed = True
                next_roles.append({**role, "permissions": permissions})
            else:
                next_roles.append(role)
        if changed:
            payload["roles"] = next_roles
            state.data = payload
            state.save(update_fields=["data"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0023_grant_menu_permissions")]

    operations = [
        migrations.RunPython(apply_mall_customer_nav_and_perms, noop),
    ]
