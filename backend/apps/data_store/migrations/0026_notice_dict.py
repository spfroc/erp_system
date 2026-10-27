from django.db import migrations, models

from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS, nav_menu_item_defaults
from apps.data_store.notice_dict import DEFAULT_NATURES, DEFAULT_ORG_TYPES, KIND_NATURE, KIND_ORG_TYPE


def _grant_dict_permissions(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    next_permissions = list(permissions)
    changed = False
    has_notice = "notice.manage" in next_permissions or "notice.tag.manage" in next_permissions
    if has_notice or "notice.view" in next_permissions or "notice.tag.view" in next_permissions:
        for key in ("notice.orgType.view", "notice.nature.view"):
            if key not in next_permissions:
                next_permissions.append(key)
                changed = True
    if "notice.manage" in next_permissions or "notice.tag.manage" in next_permissions:
        for key in ("notice.orgType.manage", "notice.nature.manage"):
            if key not in next_permissions:
                next_permissions.append(key)
                changed = True
    return next_permissions, changed


def seed_and_grant(apps, schema_editor):
    NoticeDictItem = apps.get_model("data_store", "NoticeDictItem")
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")

    for kind, names in ((KIND_ORG_TYPE, DEFAULT_ORG_TYPES), (KIND_NATURE, DEFAULT_NATURES)):
        if NoticeDictItem.objects.filter(kind=kind).exists():
            continue
        NoticeDictItem.objects.bulk_create(
            [
                NoticeDictItem(kind=kind, name=name, sort_order=index * 10, enabled=True)
                for index, name in enumerate(names)
            ]
        )

    for role in RoleRecord.objects.all():
        data = dict(role.data or {})
        permissions, changed = _grant_dict_permissions(list(data.get("permissions") or []))
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
            permissions, role_changed = _grant_dict_permissions(list(role.get("permissions") or []))
            if role_changed:
                changed = True
                next_roles.append({**role, "permissions": permissions})
            else:
                next_roles.append(role)
        if changed:
            payload["roles"] = next_roles
            state.data = payload
            state.save(update_fields=["data"])

    rows = {row["id"]: row for row in DEFAULT_NAV_ITEMS}
    for item_id in ("nav-item-noticeOrgTypes", "nav-item-noticeNatures"):
        defaults = nav_menu_item_defaults(rows[item_id])
        NavMenuItemRecord.objects.update_or_create(
            id=item_id,
            defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0025_dev_ops_jobs"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticeDictItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("org_type", "公告类型"), ("nature", "性质")], db_index=True, max_length=16)),
                ("name", models.CharField(max_length=32)),
                ("sort_order", models.IntegerField(default=0)),
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "notice_dict_item",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="noticedictitem",
            constraint=models.UniqueConstraint(fields=("kind", "name"), name="uk_notice_dict_kind_name"),
        ),
        migrations.RunPython(seed_and_grant, noop_reverse),
    ]
