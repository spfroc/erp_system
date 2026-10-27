from django.db import migrations
from django.utils import timezone

from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS, nav_menu_item_defaults


def merge_notice_dict_nav(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    rows = {row["id"]: row for row in DEFAULT_NAV_ITEMS}
    defaults = nav_menu_item_defaults(rows["nav-item-noticeDict"])
    NavMenuItemRecord.objects.update_or_create(
        id="nav-item-noticeDict",
        defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )
    now = timezone.now()
    for item_id in ("nav-item-noticeOrgTypes", "nav-item-noticeNatures"):
        NavMenuItemRecord.objects.filter(id=item_id, is_deleted=False).update(
            is_deleted=True,
            deleted_at=now,
            deleted_by="system",
            enabled=False,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0026_notice_dict"),
    ]

    operations = [
        migrations.RunPython(merge_notice_dict_nav, noop_reverse),
    ]
