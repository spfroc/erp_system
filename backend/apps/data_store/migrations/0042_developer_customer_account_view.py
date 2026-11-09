from django.db import migrations

VIEW = "customerAccount.view"
DEV_MANAGE = "dev.ops.manage"


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    if DEV_MANAGE not in permissions:
        return permissions, False
    if VIEW in permissions:
        return permissions, False
    return [*permissions, VIEW], True


def grant_developer_customer_account_view(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")
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


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0041_notice_mapped_category_m2m"),
    ]

    operations = [
        migrations.RunPython(grant_developer_customer_account_view, noop_reverse),
    ]
