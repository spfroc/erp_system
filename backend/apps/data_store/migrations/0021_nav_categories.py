from django.db import migrations, models

from apps.data_store.nav_defaults import (
    DEFAULT_NAV_CATEGORIES,
    DEFAULT_NAV_GROUPS,
    DEFAULT_NAV_ITEMS,
    nav_category_defaults,
    nav_group_defaults,
    nav_menu_item_defaults,
)

GROUP_CATEGORY = {row["key"]: row["categoryKey"] for row in DEFAULT_NAV_GROUPS}
ITEM_BY_ID = {row["id"]: row for row in DEFAULT_NAV_ITEMS}


def upgrade_nav_tree(apps, schema_editor):
    NavCategoryRecord = apps.get_model("data_store", "NavCategoryRecord")
    NavGroupRecord = apps.get_model("data_store", "NavGroupRecord")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")

    for row in DEFAULT_NAV_CATEGORIES:
        defaults = nav_category_defaults(row)
        NavCategoryRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})

    for row in DEFAULT_NAV_GROUPS:
        defaults = nav_group_defaults(row)
        NavGroupRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})

    for group in NavGroupRecord.objects.filter(is_deleted=False):
        category_key = GROUP_CATEGORY.get(group.key) or getattr(group, "category_key", "") or ""
        data = dict(group.data or {})
        data["categoryKey"] = category_key
        group.category_key = category_key
        group.data = data
        group.save(update_fields=["category_key", "data"])

    for row in DEFAULT_NAV_ITEMS:
        defaults = nav_menu_item_defaults(row)
        NavMenuItemRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})

    for item in NavMenuItemRecord.objects.filter(is_deleted=False):
        seed = ITEM_BY_ID.get(item.id)
        data = dict(item.data or {})
        if seed:
            category_key = seed["categoryKey"]
            group_key = seed["groupKey"]
        else:
            group_key = str(getattr(item, "group_key", "") or data.get("groupKey") or "")
            category_key = str(getattr(item, "category_key", "") or data.get("categoryKey") or "")
            if not category_key and group_key:
                category_key = GROUP_CATEGORY.get(group_key, "")
            if not category_key and not group_key:
                category_key = "overview"
        data["categoryKey"] = category_key
        data["groupKey"] = group_key
        item.category_key = category_key
        item.group_key = group_key
        item.data = data
        item.save(update_fields=["category_key", "group_key", "data"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0020_nav_menus")]

    operations = [
        migrations.CreateModel(
            name="NavCategoryRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("key", models.CharField(db_index=True, max_length=64)),
                ("label", models.CharField(max_length=100)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "nav_categories"},
        ),
        migrations.AddField(
            model_name="navgrouprecord",
            name="category_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="navmenuitemrecord",
            name="category_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.RunPython(upgrade_nav_tree, noop),
    ]
