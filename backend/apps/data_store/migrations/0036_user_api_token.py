from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0035_merge_preempt_and_mall"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserApiToken",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("user_id", models.CharField(db_index=True, max_length=64)),
                ("name", models.CharField(default="默认凭证", max_length=128)),
                ("token_prefix", models.CharField(max_length=16)),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={
                "db_table": "user_api_tokens",
            },
        ),
        migrations.AddIndex(
            model_name="userapitoken",
            index=models.Index(fields=["user_id", "revoked_at"], name="uat_user_revoked_idx"),
        ),
    ]
