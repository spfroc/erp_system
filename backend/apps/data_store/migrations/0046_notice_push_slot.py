from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0045_portal_account_action_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="noticepushlog",
            name="push_slot",
            field=models.CharField(blank=True, db_index=True, default="", max_length=5),
        ),
        migrations.RemoveConstraint(
            model_name="noticepushlog",
            name="uniq_notice_push_account_channel_date",
        ),
        migrations.AddConstraint(
            model_name="noticepushlog",
            constraint=models.UniqueConstraint(
                fields=("customer_account_id", "channel", "digest_date", "push_slot"),
                name="uniq_notice_push_account_channel_date_slot",
            ),
        ),
    ]
