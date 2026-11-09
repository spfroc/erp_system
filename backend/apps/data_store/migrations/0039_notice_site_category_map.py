from django.db import migrations, models

from apps.data_store.nav_defaults import nav_menu_item_defaults


PERMISSIONS_VIEW = ("notice.site.view", "notice.categoryMap.view")
PERMISSIONS_MANAGE = ("notice.site.manage", "notice.categoryMap.manage")

NAV_ITEMS = (
    {
        "id": "nav-item-noticeSites",
        "viewId": "noticeSites",
        "label": "站点管理",
        "categoryKey": "system",
        "groupKey": "system",
        "permission": "notice.site.view",
        "iconKey": "Globe",
        "sortOrder": 22,
        "enabled": True,
    },
    {
        "id": "nav-item-noticeCategoryMap",
        "viewId": "noticeCategoryMap",
        "label": "分类映射",
        "categoryKey": "system",
        "groupKey": "system",
        "permission": "notice.categoryMap.view",
        "iconKey": "LayoutList",
        "sortOrder": 23,
        "enabled": True,
    },
)


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    next_permissions = list(permissions)
    changed = False
    has_view = "notice.view" in next_permissions or "notice.manage" in next_permissions
    has_manage = "notice.manage" in next_permissions or "user.manage" in next_permissions
    if has_view:
        for key in PERMISSIONS_VIEW:
            if key not in next_permissions:
                next_permissions.append(key)
                changed = True
    if has_manage:
        for key in PERMISSIONS_MANAGE:
            if key not in next_permissions:
                next_permissions.append(key)
                changed = True
    return next_permissions, changed


def seed_and_grant(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")

    for role in RoleRecord.objects.all():
        data = dict(role.data or {})
        permissions, changed = _grant(list(data.get("permissions") or []))
        if changed:
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

    for row in NAV_ITEMS:
        defaults = nav_menu_item_defaults(row)
        NavMenuItemRecord.objects.update_or_create(
            id=row["id"],
            defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0038_notice_content_tag"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticeCrawlSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=64, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("fixed_region", models.CharField(blank=True, default="", max_length=32)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "notice_crawl_site",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="NoticeCategoryMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("channel_key", models.CharField(blank=True, default="", max_length=64)),
                ("channel_label", models.CharField(blank=True, default="", max_length=64)),
                ("notice_type", models.CharField(max_length=32)),
                ("notice_type_label", models.CharField(blank=True, default="", max_length=64)),
                ("category", models.CharField(db_index=True, max_length=64)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "notice_category_map",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="noticecategorymap",
            constraint=models.UniqueConstraint(
                fields=("site_id", "channel_key", "notice_type"),
                name="uk_notice_category_map",
            ),
        ),
        migrations.RunPython(seed_and_grant, noop_reverse),
    ]
