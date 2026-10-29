"""会话读写与上下文裁剪。"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.assistant.models import AssistantConversation, AssistantMessage


def list_conversations(user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    qs = AssistantConversation.objects.filter(user_id=user_id, is_deleted=False).order_by("-updated_at", "-id")[:limit]
    return [
        {
            "id": row.id,
            "title": row.title or "新会话",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in qs
    ]


def get_conversation(user_id: str, conversation_id: int) -> AssistantConversation | None:
    return AssistantConversation.objects.filter(id=conversation_id, user_id=user_id, is_deleted=False).first()


def create_conversation(user_id: str, *, title: str = "") -> AssistantConversation:
    return AssistantConversation.objects.create(
        user_id=user_id,
        title=(title or "新会话")[:200],
        context_json={},
    )


def soft_delete_conversation(user_id: str, conversation_id: int) -> bool:
    row = get_conversation(user_id, conversation_id)
    if not row:
        return False
    row.is_deleted = True
    row.save(update_fields=["is_deleted", "updated_at"])
    return True


def rename_conversation(user_id: str, conversation_id: int, title: str) -> AssistantConversation | None:
    row = get_conversation(user_id, conversation_id)
    if not row:
        return None
    row.title = (title or row.title or "新会话")[:200]
    row.save(update_fields=["title", "updated_at"])
    return row


def list_messages(conversation: AssistantConversation, *, limit: int = 200) -> list[dict[str, Any]]:
    rows = conversation.messages.order_by("id")[:limit]
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "message_type": row.message_type,
            "payload": row.payload_json or {},
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


def append_message(
    conversation: AssistantConversation,
    *,
    role: str,
    content: str,
    message_type: str = "text",
    payload: dict[str, Any] | None = None,
) -> AssistantMessage:
    message = AssistantMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content or "",
        message_type=message_type,
        payload_json=payload or {},
    )
    conversation.updated_at = timezone.now()
    if role == AssistantMessage.ROLE_USER and (not conversation.title or conversation.title == "新会话"):
        conversation.title = (content or "新会话").strip()[:40] or "新会话"
        conversation.save(update_fields=["title", "updated_at"])
    else:
        conversation.save(update_fields=["updated_at"])
    return message


def update_context(conversation: AssistantConversation, patch: dict[str, Any]) -> dict[str, Any]:
    context = dict(conversation.context_json or {})
    context.update(patch or {})
    # 裁剪：只保留必要字段
    trimmed = {
        "intent": context.get("intent") or "",
        "params": context.get("params") or {},
        "recent_result_ids": list(context.get("recent_result_ids") or [])[:30],
        "sort": context.get("sort") or "",
        "selected_entity": context.get("selected_entity") or {},
        "last_tool_status": context.get("last_tool_status") or "",
        "mode": context.get("mode") or "rule_only",
    }
    conversation.context_json = trimmed
    conversation.save(update_fields=["context_json", "updated_at"])
    return trimmed
