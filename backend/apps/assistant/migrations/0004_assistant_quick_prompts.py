from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0003_tool_execution_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistantusersettings",
            name="quick_prompts",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
