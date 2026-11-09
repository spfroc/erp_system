from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_maps(apps, schema_editor):
    NoticeCategoryMap = apps.get_model("data_store", "NoticeCategoryMap")
    NoticeMappedCategory = apps.get_model("data_store", "NoticeMappedCategory")
    NoticeSiteOption = apps.get_model("data_store", "NoticeSiteOption")
    NoticeCategoryOptionLink = apps.get_model("data_store", "NoticeCategoryOptionLink")

    cat_by_name: dict[str, object] = {}
    for row in NoticeCategoryMap.objects.all().order_by("sort_order", "id"):
        name = (row.category or "").strip()
        if not name:
            continue
        if name not in cat_by_name:
            cat, _ = NoticeMappedCategory.objects.get_or_create(
                name=name,
                defaults={
                    "enabled": True,
                    "sort_order": int(row.sort_order or 0) or (len(cat_by_name) + 1) * 10,
                },
            )
            cat_by_name[name] = cat
        option, _ = NoticeSiteOption.objects.get_or_create(
            site_id=row.site_id,
            channel_key=row.channel_key or "",
            notice_type=row.notice_type,
            defaults={
                "channel_label": row.channel_label or "",
                "notice_type_label": row.notice_type_label or "",
                "enabled": bool(row.enabled),
                "sort_order": int(row.sort_order or 0),
            },
        )
        NoticeCategoryOptionLink.objects.get_or_create(
            category=cat_by_name[name],
            option=option,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0040_merge_push_log_and_site_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticeMappedCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, unique=True)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "notice_mapped_category",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="NoticeSiteOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("channel_key", models.CharField(blank=True, default="", max_length=64)),
                ("channel_label", models.CharField(blank=True, default="", max_length=64)),
                ("notice_type", models.CharField(max_length=32)),
                ("notice_type_label", models.CharField(blank=True, default="", max_length=64)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "notice_site_option",
                "ordering": ["site_id", "sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="NoticeCategoryOptionLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="option_links",
                        to="data_store.noticemappedcategory",
                    ),
                ),
                (
                    "option",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="category_links",
                        to="data_store.noticesiteoption",
                    ),
                ),
            ],
            options={
                "db_table": "notice_category_option_link",
                "ordering": ["id"],
            },
        ),
        migrations.AddConstraint(
            model_name="noticesiteoption",
            constraint=models.UniqueConstraint(
                fields=("site_id", "channel_key", "notice_type"),
                name="uk_notice_site_option",
            ),
        ),
        migrations.AddConstraint(
            model_name="noticecategoryoptionlink",
            constraint=models.UniqueConstraint(
                fields=("category", "option"),
                name="uk_notice_category_option_link",
            ),
        ),
        migrations.RunPython(migrate_legacy_maps, noop_reverse),
    ]
