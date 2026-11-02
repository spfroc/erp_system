from django.db import migrations

from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS, nav_menu_item_defaults


MENU_ID = "nav-item-assistant"


def install_assistant_nav(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    rows = {row["id"]: row for row in DEFAULT_NAV_ITEMS}
    item = rows.get(MENU_ID)
    if not item:
        return
    defaults = nav_menu_item_defaults(item)
    NavMenuItemRecord.objects.update_or_create(
        id=item["id"],
        defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )


def remove_assistant_nav(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    NavMenuItemRecord.objects.filter(id=MENU_ID).update(is_deleted=True)


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0029_assistant_permissions"),
    ]

    operations = [
        migrations.RunPython(install_assistant_nav, remove_assistant_nav),
    ]
