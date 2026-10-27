import django.db.models.deletion
from django.db import migrations, models

from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS, nav_menu_item_defaults


def install_dev_ops_nav(apps, schema_editor):
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")
    rows = {row["id"]: row for row in DEFAULT_NAV_ITEMS}
    item = rows.get("nav-item-devOps")
    if not item:
        return
    defaults = nav_menu_item_defaults(item)
    NavMenuItemRecord.objects.update_or_create(
        id=item["id"],
        defaults={**defaults, "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0024_notice_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="DevOpsJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("script_key", models.CharField(db_index=True, max_length=64)),
                ("name", models.CharField(max_length=128)),
                ("enabled", models.BooleanField(db_index=True, default=False)),
                ("schedule_type", models.CharField(default="manual", max_length=16)),
                ("interval_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("cron_expr", models.CharField(blank=True, default="", max_length=64)),
                ("args_json", models.JSONField(blank=True, default=dict)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("next_run_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("updated_by", models.CharField(blank=True, default="", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "dev_ops_job",
            },
        ),
        migrations.CreateModel(
            name="DevOpsJobRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trigger", models.CharField(default="manual", max_length=16)),
                ("status", models.CharField(db_index=True, default="pending", max_length=16)),
                ("celery_task_id", models.CharField(blank=True, default="", max_length=64)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("stdout", models.TextField(blank=True, default="")),
                ("stderr", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="data_store.devopsjob",
                    ),
                ),
            ],
            options={
                "db_table": "dev_ops_job_run",
                "ordering": ["-id"],
            },
        ),
        migrations.RunPython(install_dev_ops_nav, noop),
    ]
