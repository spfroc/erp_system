from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AssistantConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.CharField(db_index=True, max_length=64)),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("context_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
            ],
            options={
                "db_table": "assistant_conversation",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AssistantMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("user", "用户"),
                            ("assistant", "助手"),
                            ("system", "系统"),
                            ("tool", "工具"),
                        ],
                        max_length=16,
                    ),
                ),
                ("content", models.TextField(blank=True, default="")),
                ("message_type", models.CharField(blank=True, default="text", max_length=32)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="assistant.assistantconversation",
                    ),
                ),
            ],
            options={
                "db_table": "assistant_message",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="AssistantToolExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.CharField(db_index=True, max_length=64)),
                ("tool_name", models.CharField(db_index=True, max_length=64)),
                ("parameters_json", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "待执行"),
                            ("running", "执行中"),
                            ("awaiting_confirmation", "待确认"),
                            ("completed", "已完成"),
                            ("failed", "失败"),
                            ("cancelled", "已取消"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("result_summary", models.TextField(blank=True, default="")),
                ("result_json", models.JSONField(blank=True, default=dict)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("confirmation_token_hash", models.CharField(blank=True, default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tool_executions",
                        to="assistant.assistantconversation",
                    ),
                ),
            ],
            options={
                "db_table": "assistant_tool_execution",
                "ordering": ["-id"],
            },
        ),
    ]
