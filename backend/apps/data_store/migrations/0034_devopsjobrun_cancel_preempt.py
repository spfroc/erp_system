from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_store", "0033_merge_mall_assistant_portal"),
    ]

    operations = [
        migrations.AddField(
            model_name="devopsjobrun",
            name="cancel_requested",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="devopsjobrun",
            name="preempted_by_run_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
