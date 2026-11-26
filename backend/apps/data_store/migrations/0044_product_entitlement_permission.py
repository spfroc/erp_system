from django.db import migrations

PERMISSION = "product.entitlement.manage"
# 仅授予已有开发/运维或用户权限管理能力的角色，避免普通商品运营误配
GRANT_IF_HAS = ("user.manage", "dev.ops.manage")


def grant_entitlement_permission(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    UserRecord = apps.get_model("data_store", "UserRecord")

    def merge(perms):
        values = list(perms or [])
        if PERMISSION in values:
            return values, False
        if not any(key in values for key in GRANT_IF_HAS):
            return values, False
        values.append(PERMISSION)
        return values, True

    for role in RoleRecord.objects.filter(is_deleted=False):
        data = dict(role.data or {})
        permissions, changed = merge(data.get("permissions") or [])
        if not changed:
            continue
        data["permissions"] = permissions
        role.data = data
        role.save(update_fields=["data", "updated_at"])

    for user in UserRecord.objects.filter(is_deleted=False):
        data = dict(user.data or {})
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
        ("data_store", "0043_portal_notice_inbox_wechat_mp"),
    ]

    operations = [
        migrations.RunPython(grant_entitlement_permission, noop_reverse),
    ]
