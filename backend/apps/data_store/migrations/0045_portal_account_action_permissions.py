from django.db import migrations

NEW_PERMS = (
    "portal.account.create",
    "portal.account.edit",
    "portal.account.delete",
)
MANAGE = "portal.account.manage"


def _merge_account_actions(perms):
    values = list(perms or [])
    if MANAGE not in values:
        return values, False
    changed = False
    for key in NEW_PERMS:
        if key not in values:
            values.append(key)
            changed = True
    return values, changed


def grant_portal_account_actions(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    UserRecord = apps.get_model("data_store", "UserRecord")
    CustomerAccountRecord = apps.get_model("data_store", "CustomerAccountRecord")
    ProductRecord = apps.get_model("data_store", "ProductRecord")

    for role in RoleRecord.objects.filter(is_deleted=False):
        data = dict(role.data or {})
        permissions, changed = _merge_account_actions(data.get("permissions") or [])
        if not changed:
            continue
        data["permissions"] = permissions
        role.data = data
        role.save(update_fields=["data", "updated_at"])

    for user in UserRecord.objects.filter(is_deleted=False):
        data = dict(user.data or {})
        permissions, changed = _merge_account_actions(data.get("permissions") or [])
        if not changed:
            continue
        data["permissions"] = permissions
        user.data = data
        user.save(update_fields=["data", "updated_at"])

    for account in CustomerAccountRecord.objects.filter(is_deleted=False):
        data = dict(account.data or {})
        permissions, changed = _merge_account_actions(data.get("permissions") or [])
        if not changed:
            continue
        data["permissions"] = permissions
        account.data = data
        account.save(update_fields=["data", "updated_at"])

    for product in ProductRecord.objects.filter(is_deleted=False):
        data = dict(product.data or {})
        entitlements = data.get("portalEntitlements")
        if not isinstance(entitlements, list):
            continue
        next_entitlements, changed = _merge_account_actions(entitlements)
        if not changed:
            continue
        data["portalEntitlements"] = next_entitlements
        product.data = data
        product.save(update_fields=["data", "updated_at"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0044_product_entitlement_permission"),
    ]

    operations = [
        migrations.RunPython(grant_portal_account_actions, noop_reverse),
    ]
