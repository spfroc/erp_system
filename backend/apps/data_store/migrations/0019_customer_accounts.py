from django.contrib.auth.hashers import make_password
from django.db import migrations, models
from django.utils import timezone


VIEW = "customerAccount.view"
MANAGE = "customerAccount.manage"
TEST_ID = "portal-user-test"
TEST_PHONE = "13800138000"
PORTAL_PERMISSIONS = ["portal.notice.view", "portal.notice.subscribe", "portal.stats.view"]


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
    CustomerAccountRecord = apps.get_model("data_store", "CustomerAccountRecord")
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

    if CustomerAccountRecord.objects.filter(id=TEST_ID).exists():
        return
    now = timezone.now()
    payload = {
        "id": TEST_ID,
        "name": "测试客户",
        "phone": TEST_PHONE,
        "password": make_password("Portal123456"),
        "customerName": "测试客户",
        "customerOrgId": "",
        "status": "启用",
        "permissions": PORTAL_PERMISSIONS,
        "subscription": {"enabled": True, "keywords": ""},
        "createdAt": now.isoformat(),
    }
    CustomerAccountRecord.objects.create(
        id=TEST_ID,
        data=payload,
        name=payload["name"],
        phone=payload["phone"],
        customer_name=payload["customerName"],
        customer_org_id="",
        status="启用",
        created_at=now,
        is_deleted=False,
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0018_library_contact_mobile_len")]

    operations = [
        migrations.CreateModel(
            name="CustomerAccountRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("name", models.CharField(max_length=100)),
                ("phone", models.CharField(db_index=True, max_length=50)),
                ("customer_name", models.CharField(blank=True, max_length=255)),
                ("customer_org_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("status", models.CharField(db_index=True, default="启用", max_length=20)),
            ],
            options={"db_table": "customer_accounts"},
        ),
        migrations.RunPython(grant_and_seed, noop),
    ]
