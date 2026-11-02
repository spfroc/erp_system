from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        # one 环境未合入 mall merge(0033)；与 0032 对齐即可，0033 为空 merge 可并存为另一 head
        ("data_store", "0032_portal_enterprise_permissions"),
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
