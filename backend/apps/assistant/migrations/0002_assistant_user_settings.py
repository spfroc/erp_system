from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantUserSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.CharField(db_index=True, max_length=64, unique=True)),
                ("system_prompt_addon", models.TextField(blank=True, default="")),
                ("show_token_usage", models.BooleanField(default=True)),
                ("display_name", models.CharField(blank=True, default="", max_length=64)),
                ("display_avatar_url", models.CharField(blank=True, default="", max_length=512)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "assistant_user_settings",
            },
        ),
    ]
