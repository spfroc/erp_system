"""重组业务菜单：服务/商品项目管理，合同进财务，取消订单组。"""

from django.db import migrations
from django.utils import timezone

from apps.data_store.nav_defaults import (
    DEFAULT_NAV_GROUPS,
    DEFAULT_NAV_ITEMS,
    OBSOLETE_NAV_GROUP_IDS,
    nav_group_defaults,
    nav_menu_item_defaults,
)


def reorganize_nav(apps, schema_editor):
    NavGroupRecord = apps.get_model("data_store", "NavGroupRecord")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    now = timezone.now()

    keep_group_ids = {row["id"] for row in DEFAULT_NAV_GROUPS}
    for row in DEFAULT_NAV_GROUPS:
        defaults = nav_group_defaults(row)
        NavGroupRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""})

    obsolete_ids = set(OBSOLETE_NAV_GROUP_IDS) | {
        group.id
        for group in NavGroupRecord.objects.filter(is_deleted=False)
        if group.id not in keep_group_ids and group.key in {"projects", "orders"}
    }
    for group_id in obsolete_ids:
        NavGroupRecord.objects.filter(id=group_id, is_deleted=False).update(
            is_deleted=True,
            deleted_at=now,
            deleted_by="migration:0022_reorganize_nav_groups",
            enabled=False,
        )

    for row in DEFAULT_NAV_ITEMS:
        defaults = nav_menu_item_defaults(row)
        NavMenuItemRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0021_nav_categories")]

    operations = [
        migrations.RunPython(reorganize_nav, noop),
    ]
