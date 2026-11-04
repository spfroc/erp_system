from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0002_assistant_user_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistanttoolexecution",
            name="source",
            field=models.CharField(blank=True, db_index=True, default="assistant", max_length=32),
        ),
    ]
