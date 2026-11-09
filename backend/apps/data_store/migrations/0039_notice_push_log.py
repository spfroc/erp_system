from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0038_notice_content_tag"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticePushLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_account_id", models.CharField(db_index=True, max_length=64)),
                ("channel", models.CharField(db_index=True, default="wechat_mp", max_length=32)),
                ("digest_date", models.DateField(db_index=True)),
                ("openid", models.CharField(blank=True, default="", max_length=64)),
                ("filter_snapshot", models.JSONField(blank=True, default=dict)),
                ("notice_ids", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(db_index=True, default="pending", max_length=16)),
                ("errcode", models.IntegerField(default=0)),
                ("errmsg", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "notice_push_logs",
            },
        ),
        migrations.AddConstraint(
            model_name="noticepushlog",
            constraint=models.UniqueConstraint(
                fields=("customer_account_id", "channel", "digest_date"),
                name="uniq_notice_push_account_channel_date",
            ),
        ),
        migrations.AddIndex(
            model_name="noticepushlog",
            index=models.Index(fields=["digest_date", "status"], name="notice_push_date_status_idx"),
        ),
    ]
