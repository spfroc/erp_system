from django.db import migrations, models

from apps.data_store.nav_defaults import DEFAULT_NAV_GROUPS, DEFAULT_NAV_ITEMS, nav_group_defaults, nav_menu_item_defaults

VIEW = "menu.view"
MANAGE = "menu.manage"


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    if "user.manage" not in permissions:
        return permissions, False
    next_permissions = list(permissions)
    changed = False
    for key in (VIEW, MANAGE):
        if key not in next_permissions:
            next_permissions.append(key)
            changed = True
    return next_permissions, changed


def grant_and_seed(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")
    NavGroupRecord = apps.get_model("data_store", "NavGroupRecord")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")

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

    if not NavGroupRecord.objects.filter(is_deleted=False).exists():
        for row in DEFAULT_NAV_GROUPS:
            defaults = nav_group_defaults(row)
            NavGroupRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})

    if not NavMenuItemRecord.objects.filter(is_deleted=False).exists():
        for row in DEFAULT_NAV_ITEMS:
            defaults = nav_menu_item_defaults(row)
            NavMenuItemRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0019_customer_accounts")]

    operations = [
        migrations.CreateModel(
            name="NavGroupRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("key", models.CharField(db_index=True, max_length=64)),
                ("label", models.CharField(max_length=100)),
                ("icon_key", models.CharField(blank=True, max_length=64)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "nav_groups"},
        ),
        migrations.CreateModel(
            name="NavMenuItemRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("view_id", models.CharField(db_index=True, max_length=64)),
                ("label", models.CharField(max_length=100)),
                ("group_key", models.CharField(blank=True, db_index=True, max_length=64)),
                ("permission", models.CharField(db_index=True, max_length=64)),
                ("icon_key", models.CharField(blank=True, max_length=64)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "nav_menu_items"},
        ),
        migrations.RunPython(grant_and_seed, noop),
    ]
