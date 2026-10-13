from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("data_store", "0005_managed_file")]

    operations = [
        migrations.CreateModel(
            name="ProjectMemoRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("project_id", models.CharField(db_index=True, max_length=64)),
                ("content", models.CharField(max_length=200)),
                ("created_by", models.CharField(blank=True, max_length=100)),
            ],
            options={"db_table": "project_memos"},
        ),
    ]
