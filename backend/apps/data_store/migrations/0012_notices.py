from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0011_managed_file_allow_multiple"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticeRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("title", models.CharField(db_index=True, max_length=500)),
                ("project_number", models.CharField(blank=True, db_index=True, max_length=100)),
                ("supplier_name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("department", models.CharField(blank=True, db_index=True, max_length=255)),
                ("category", models.CharField(blank=True, db_index=True, max_length=100)),
                ("notice_kind", models.CharField(db_index=True, default="竞价项目", max_length=50)),
                ("bid_status", models.CharField(blank=True, db_index=True, max_length=50)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("is_public", models.BooleanField(db_index=True, default=False)),
                ("source", models.CharField(db_index=True, default="manual", max_length=30)),
                ("external_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("published_at", models.CharField(blank=True, db_index=True, max_length=40)),
            ],
            options={"db_table": "notices"},
        ),
        migrations.CreateModel(
            name="NoticeCollectionSourceRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("name", models.CharField(db_index=True, max_length=100)),
                ("kind", models.CharField(db_index=True, max_length=50)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("last_run_at", models.CharField(blank=True, max_length=40)),
                ("last_status", models.CharField(blank=True, max_length=20)),
            ],
            options={"db_table": "notice_collection_sources"},
        ),
        migrations.CreateModel(
            name="NoticeCollectionRunRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("source_id", models.CharField(db_index=True, max_length=64)),
                ("source_name", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(db_index=True, max_length=20)),
                ("fetched_count", models.PositiveIntegerField(default=0)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("lead_count", models.PositiveIntegerField(default=0)),
                ("started_at", models.CharField(blank=True, db_index=True, max_length=40)),
                ("finished_at", models.CharField(blank=True, max_length=40)),
            ],
            options={"db_table": "notice_collection_runs"},
        ),
    ]
