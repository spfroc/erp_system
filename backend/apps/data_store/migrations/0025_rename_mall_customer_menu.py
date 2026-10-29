"""菜单「资料库展示列表」更名为「资料库」。"""

from django.db import migrations


MENU_ID = "nav-item-mallCustomers"
NEW_LABEL = "资料库"


def rename_menu(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    for item in NavMenuItemRecord.objects.filter(id=MENU_ID):
        data = dict(item.data or {})
        data["label"] = NEW_LABEL
        item.data = data
        item.label = NEW_LABEL
        item.save(update_fields=["data", "label"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0024_mall_customer_library")]

    operations = [
        migrations.RunPython(rename_menu, noop),
    ]
