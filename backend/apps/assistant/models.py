from django.db import models


class AssistantConversation(models.Model):
    """助手会话。user_id 对应 ERP UserRecord.id（非 Django auth.User）。"""

    user_id = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=200, blank=True, default="")
    context_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "assistant_conversation"
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return f"Conversation<{self.id}:{self.title or 'untitled'}>"


class AssistantMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_TOOL = "tool"
    ROLE_CHOICES = (
        (ROLE_USER, "用户"),
        (ROLE_ASSISTANT, "助手"),
        (ROLE_SYSTEM, "系统"),
        (ROLE_TOOL, "工具"),
    )

    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    message_type = models.CharField(max_length=32, blank=True, default="text")
    payload_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assistant_message"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Message<{self.id}:{self.role}>"


class AssistantToolExecution(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_PENDING, "待执行"),
        (STATUS_RUNNING, "执行中"),
        (STATUS_AWAITING_CONFIRMATION, "待确认"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
        (STATUS_CANCELLED, "已取消"),
    )

    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="tool_executions",
        null=True,
        blank=True,
    )
    user_id = models.CharField(max_length=64, db_index=True)
    tool_name = models.CharField(max_length=64, db_index=True)
    parameters_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    result_summary = models.TextField(blank=True, default="")
    result_json = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    confirmation_token_hash = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "assistant_tool_execution"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"ToolExec<{self.id}:{self.tool_name}:{self.status}>"
