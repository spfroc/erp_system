from django.db import migrations, models

from apps.data_store.nav_defaults import (
    DEFAULT_NAV_GROUPS,
    DEFAULT_NAV_ITEMS,
    nav_group_defaults,
    nav_menu_item_defaults,
)

PERMISSIONS = ("wechatMp.view", "wechatMp.manage")
GROUP_ID = "nav-group-wechatMp"
MENU_ID = "nav-item-wechatPushLogs"


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    next_perms = list(permissions)
    changed = False
    for key in PERMISSIONS:
        if key not in next_perms:
            next_perms.append(key)
            changed = True
    return next_perms, changed


def grant_wechat_mp_permissions(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")
    NavGroupRecord = apps.get_model("data_store", "NavGroupRecord")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")

    for role in RoleRecord.objects.filter(is_deleted=False):
        data = dict(role.data or {})
        permissions = list(data.get("permissions") or [])
        if "notice.manage" in permissions or "customerAccount.manage" in permissions or "user.manage" in permissions:
            permissions, changed = _grant(permissions)
            if changed:
                data["permissions"] = permissions
                role.data = data
                role.save(update_fields=["data"])

    for state in AppState.objects.all():
        payload = dict(state.data or {})
        roles = payload.get("roles")
        if not isinstance(roles, list):
            continue
        next_roles = []
        changed_any = False
        for role in roles:
            if not isinstance(role, dict):
                next_roles.append(role)
                continue
            item = dict(role)
            permissions = list(item.get("permissions") or [])
            if "notice.manage" in permissions or "customerAccount.manage" in permissions or "user.manage" in permissions:
                permissions, changed = _grant(permissions)
                if changed:
                    item["permissions"] = permissions
                    changed_any = True
            next_roles.append(item)
        if changed_any:
            payload["roles"] = next_roles
            state.data = payload
            state.save(update_fields=["data"])

    groups = {row["id"]: row for row in DEFAULT_NAV_GROUPS}
    group = groups.get(GROUP_ID)
    if group:
        defaults = nav_group_defaults(group)
        NavGroupRecord.objects.update_or_create(
            id=group["id"],
            defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )

    items = {row["id"]: row for row in DEFAULT_NAV_ITEMS}
    item = items.get(MENU_ID)
    if item:
        defaults = nav_menu_item_defaults(item)
        NavMenuItemRecord.objects.update_or_create(
            id=item["id"],
            defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0042_developer_customer_account_view"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalNoticeInbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_account_id", models.CharField(db_index=True, max_length=64)),
                ("notice_raw_id", models.BigIntegerField(db_index=True)),
                ("digest_date", models.DateField(db_index=True)),
                ("push_log_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("title", models.CharField(blank=True, default="", max_length=500)),
                ("project_name", models.CharField(blank=True, default="", max_length=255)),
                ("buyer_name", models.CharField(blank=True, default="", max_length=255)),
                ("region_name", models.CharField(blank=True, default="", max_length=128)),
                ("site_id", models.CharField(blank=True, default="", max_length=64)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "portal_notice_inbox",
            },
        ),
        migrations.AddConstraint(
            model_name="portalnoticeinbox",
            constraint=models.UniqueConstraint(
                fields=("customer_account_id", "notice_raw_id", "digest_date"),
                name="uniq_portal_notice_inbox_account_notice_day",
            ),
        ),
        migrations.AddIndex(
            model_name="portalnoticeinbox",
            index=models.Index(fields=["customer_account_id", "-created_at"], name="portal_inbox_account_created_idx"),
        ),
        migrations.AddIndex(
            model_name="portalnoticeinbox",
            index=models.Index(
                fields=["customer_account_id", "is_read", "-created_at"],
                name="portal_inbox_account_read_idx",
            ),
        ),
        migrations.RunPython(grant_wechat_mp_permissions, noop_reverse),
    ]
