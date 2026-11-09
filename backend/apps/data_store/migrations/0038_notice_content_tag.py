from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0037_mcp_log_permission_nav"),
    ]

    operations = [
        migrations.AddField(
            model_name="noticeresulttag",
            name="content_tag",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
    ]
