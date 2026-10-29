from django.db import migrations

ASSISTANT_PERMS = ["assistant.view", "assistant.use", "assistant.manage"]


def grant_assistant_permissions(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    UserRecord = apps.get_model("data_store", "UserRecord")

    def merge(perms):
        values = list(perms or [])
        changed = False
        for key in ASSISTANT_PERMS:
            if key not in values:
                values.append(key)
                changed = True
        return values, changed

    for role in RoleRecord.objects.filter(is_deleted=False):
        data = dict(role.data or {})
        permissions, changed = merge(data.get("permissions") or [])
        # 仅给已有 user.manage 或全量管理员角色补齐，避免普通角色被动扩大
        existing = set(data.get("permissions") or [])
        if "user.manage" not in existing and "dev.ops.manage" not in existing:
            continue
        if not changed:
            continue
        data["permissions"] = permissions
        role.data = data
        role.save(update_fields=["data", "updated_at"])

    for user in UserRecord.objects.filter(is_deleted=False):
        data = dict(user.data or {})
        existing = set(data.get("permissions") or [])
        if "user.manage" not in existing:
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
        ("data_store", "0028_notice_deal_kind"),
        ("data_store", "0025_rename_mall_customer_menu"),
    ]

    operations = [
        migrations.RunPython(grant_assistant_permissions, noop_reverse),
    ]
