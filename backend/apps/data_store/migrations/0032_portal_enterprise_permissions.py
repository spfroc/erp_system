from django.db import migrations

PORTAL_PERMS = [
    "portal.notice.view",
    "portal.notice.subscribe",
    "portal.stats.view",
    "portal.order.view",
    "portal.invoice.view",
    "portal.contract.view",
    "portal.account.view",
    "portal.account.manage",
]


def grant_portal_permissions(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    UserRecord = apps.get_model("data_store", "UserRecord")

    def merge(perms):
        values = list(perms or [])
        changed = False
        for key in PORTAL_PERMS:
            if key not in values:
                values.append(key)
                changed = True
        return values, changed

    for role in RoleRecord.objects.filter(is_deleted=False):
        data = dict(role.data or {})
        existing = set(data.get("permissions") or [])
        # 仅管理员角色补齐目录权限，避免普通角色被动扩大
        if "user.manage" not in existing and "customerAccount.manage" not in existing:
            continue
        permissions, changed = merge(data.get("permissions") or [])
        if not changed:
            continue
        data["permissions"] = permissions
        role.data = data
        role.save(update_fields=["data", "updated_at"])

    for user in UserRecord.objects.filter(is_deleted=False):
        data = dict(user.data or {})
        existing = set(data.get("permissions") or [])
        if "user.manage" not in existing and "customerAccount.manage" not in existing:
            continue
        permissions, changed = merge(data.get("permissions") or [])
        if not changed:
            continue
        data["permissions"] = permissions
        user.data = data
        user.save(update_fields=["data", "updated_at"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0031_library_contacts_list_index"),
    ]

    operations = [
        migrations.RunPython(grant_portal_permissions, noop_reverse),
    ]
