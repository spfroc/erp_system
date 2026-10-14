from django.db import migrations


NOTICE_VIEW = "notice.view"
NOTICE_MANAGE = "notice.manage"


def _wanted_permissions(permissions):
    wanted = set()
    if "lead.manage" in permissions or "user.manage" in permissions:
        wanted.add(NOTICE_VIEW)
        wanted.add(NOTICE_MANAGE)
    return wanted


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    next_permissions = list(permissions)
    wanted = _wanted_permissions(next_permissions)
    changed = False
    for key in (NOTICE_VIEW, NOTICE_MANAGE):
        if key in wanted and key not in next_permissions:
            next_permissions.append(key)
            changed = True
    return next_permissions, changed


def grant_notice_permissions(apps, schema_editor):
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
    dependencies = [("data_store", "0012_notices")]

    operations = [migrations.RunPython(grant_notice_permissions, noop)]
