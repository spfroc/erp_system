from django.db import migrations


SITE_VIEW = "site.view"
SITE_MANAGE = "site.manage"


def _wanted_permissions(permissions):
    wanted = set()
    if "user.manage" in permissions or "notice.manage" in permissions:
        wanted.add(SITE_VIEW)
        wanted.add(SITE_MANAGE)
    return wanted


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    next_permissions = list(permissions)
    wanted = _wanted_permissions(next_permissions)
    changed = False
    for key in (SITE_VIEW, SITE_MANAGE):
        if key in wanted and key not in next_permissions:
            next_permissions.append(key)
            changed = True
    return next_permissions, changed


def grant_site_permissions(apps, schema_editor):
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


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0014_official_sites")]

    operations = [migrations.RunPython(grant_site_permissions, noop)]
