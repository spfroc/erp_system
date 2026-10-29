"""P1 编排：规则路由 → 权限/参数校验 → 工具执行 → 结构化 blocks。"""

from __future__ import annotations

import json
from typing import Any

from apps.assistant.models import AssistantMessage
from apps.assistant.services.conversation import (
    append_message,
    create_conversation,
    get_conversation,
    update_context,
)
from apps.assistant.permissions import user_has_permission
from apps.assistant.services.intent_router import resolve_intent
from apps.assistant.services.tool_executor import ToolExecutionError, execute_tool
from apps.assistant.services.tool_registry import list_tools


def handle_chat(
    *,
    user_data: dict,
    message: str,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    user_id = str(user_data.get("id") or "")
    text = (message or "").strip()
    if not text:
        return {
            "status": "error",
            "mode": "rule_only",
            "content": "请输入要办理的业务。",
            "blocks": [{"type": "error", "data": {"message": "空消息"}}],
            "errors": [{"code": "empty_message", "message": "空消息"}],
        }

    if conversation_id:
        conversation = get_conversation(user_id, conversation_id)
        if not conversation:
            return {
                "status": "error",
                "mode": "rule_only",
                "content": "会话不存在或无权访问。",
                "blocks": [{"type": "error", "data": {"message": "会话不存在"}}],
                "errors": [{"code": "conversation_not_found", "message": "会话不存在"}],
            }
    else:
        conversation = create_conversation(user_id, title=text[:40])

    append_message(conversation, role=AssistantMessage.ROLE_USER, content=text, message_type="text")
    context = dict(conversation.context_json or {})
    allowed = {
        tool.name
        for tool in list_tools()
        if user_has_permission(user_data, tool.permission)
    }
    routed = resolve_intent(text, context, allowed_tool_names=allowed)
    mode = str(routed.get("mode") or "rule_only")

    if routed.get("needs_clarification") or not routed.get("tool_name"):
        content = str(routed.get("clarification") or "请补充更具体的业务指令。")
        payload = {"blocks": [{"type": "clarification", "data": {"text": content}}], "route": routed}
        assistant_msg = append_message(
            conversation,
            role=AssistantMessage.ROLE_ASSISTANT,
            content=content,
            message_type="clarification",
            payload=payload,
        )
        update_context(conversation, {"mode": mode, "last_tool_status": "clarification"})
        return {
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "mode": mode,
            "intent": "clarification",
            "status": "completed",
            "content": content,
            "blocks": payload["blocks"],
            "errors": [],
            "context": conversation.context_json,
        }

    tool_name = str(routed["tool_name"])
    params = dict(routed.get("params") or {})
    try:
        result = execute_tool(
            tool_name=tool_name,
            params=params,
            user_data=user_data,
            conversation_id=conversation.id,
        )
    except ToolExecutionError as exc:
        content = exc.message
        blocks = [{"type": "error", "data": {"code": exc.code, "message": exc.message}}]
        assistant_msg = append_message(
            conversation,
            role=AssistantMessage.ROLE_ASSISTANT,
            content=content,
            message_type="error",
            payload={"blocks": blocks, "route": routed},
        )
        update_context(conversation, {"mode": mode, "last_tool_status": "failed", "intent": tool_name, "params": params})
        return {
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "mode": mode,
            "intent": tool_name,
            "status": "failed",
            "content": content,
            "blocks": blocks,
            "errors": [{"code": exc.code, "message": exc.message}],
            "context": conversation.context_json,
        }

    block_type = str(result.get("block_type") or "tool_result")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    content = str(result.get("content") or result.get("summary") or "已完成。")
    blocks = [{"type": block_type, "data": data}]
    status = str(result.get("status") or "completed")

    recent_ids = _extract_result_ids(block_type, data)
    update_context(
        conversation,
        {
            "mode": mode,
            "intent": tool_name,
            "params": params,
            "recent_result_ids": recent_ids or context.get("recent_result_ids") or [],
            "last_tool_status": status,
            "pending_execution_id": result.get("execution_id") if status == "awaiting_confirmation" else None,
        },
    )
    assistant_msg = append_message(
        conversation,
        role=AssistantMessage.ROLE_ASSISTANT,
        content=content,
        message_type=block_type,
        payload={"blocks": blocks, "route": routed, "execution_id": result.get("execution_id")},
    )
    return {
        "conversation_id": conversation.id,
        "message_id": assistant_msg.id,
        "mode": mode,
        "intent": tool_name,
        "status": status,
        "content": content,
        "blocks": blocks,
        "errors": [],
        "context": conversation.context_json,
        "execution_id": result.get("execution_id"),
    }


def _extract_result_ids(block_type: str, data: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    if block_type == "notice_list":
        for item in data.get("items") or []:
            value = item.get("id") or item.get("noticeRawId")
            if value is not None:
                try:
                    ids.append(int(value))
                except (TypeError, ValueError):
                    continue
        item = data.get("item")
        if isinstance(item, dict) and item.get("id") is not None:
            try:
                ids.append(int(item["id"]))
            except (TypeError, ValueError):
                pass
    if block_type == "goods_table":
        for item in data.get("items") or []:
            value = item.get("noticeRawId")
            if value is not None:
                try:
                    ids.append(int(value))
                except (TypeError, ValueError):
                    continue
    # 去重保序
    seen = set()
    ordered: list[int] = []
    for value in ids:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered[:30]
