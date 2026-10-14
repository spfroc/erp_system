from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0013_notice_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficialSiteRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("key", models.CharField(db_index=True, max_length=50)),
                ("name", models.CharField(db_index=True, max_length=100)),
                ("domain", models.CharField(db_index=True, max_length=255)),
                ("brand", models.CharField(blank=True, max_length=100)),
                ("company_name", models.CharField(blank=True, max_length=255)),
                ("phone", models.CharField(blank=True, max_length=50)),
                ("status", models.CharField(db_index=True, default="启用", max_length=20)),
            ],
            options={"db_table": "official_sites"},
        ),
        migrations.CreateModel(
            name="OfficialPageRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("slug", models.CharField(db_index=True, max_length=100)),
                ("title", models.CharField(db_index=True, max_length=255)),
                ("template", models.CharField(db_index=True, default="home", max_length=50)),
                ("status", models.CharField(db_index=True, default="draft", max_length=20)),
                ("sort_order", models.IntegerField(default=0)),
            ],
            options={"db_table": "official_pages"},
        ),
    ]
