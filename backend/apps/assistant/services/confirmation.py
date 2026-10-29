"""写操作确认凭证：服务端哈希保存，客户端仅持有明文 token 一次。"""

from __future__ import annotations

import hashlib
from typing import Any

from django.utils import timezone

from apps.assistant.models import AssistantToolExecution
from apps.assistant.permissions import ASSISTANT_USE, user_has_permission
from apps.assistant.services.tool_executor import ToolExecutionError, execute_tool
from apps.assistant.services.tool_registry import get_tool


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def get_action(user_id: str, execution_id: int) -> AssistantToolExecution | None:
    return AssistantToolExecution.objects.filter(id=execution_id, user_id=user_id).first()


def confirm_action(
    *,
    user_data: dict,
    execution_id: int,
    confirmation_token: str,
) -> dict[str, Any]:
    user_id = str(user_data.get("id") or "")
    if not user_has_permission(user_data, ASSISTANT_USE):
        raise ToolExecutionError("forbidden", "无助手使用权限", status=403)

    record = get_action(user_id, execution_id)
    if not record:
        raise ToolExecutionError("not_found", "操作不存在", status=404)

    # 幂等：已完成则直接返回摘要
    if record.status == AssistantToolExecution.STATUS_COMPLETED:
        data = record.result_json if isinstance(record.result_json, dict) else {}
        return {
            "execution_id": record.id,
            "status": "completed",
            "tool_name": record.tool_name,
            "content": record.result_summary or "已执行完成。",
            "blocks": [
                {
                    "type": str(data.get("block_type") or "tool_result"),
                    "data": data.get("data") if isinstance(data.get("data"), dict) else data,
                }
            ],
            "idempotent": True,
        }

    if record.status != AssistantToolExecution.STATUS_AWAITING_CONFIRMATION:
        raise ToolExecutionError("invalid_state", f"当前状态不可确认：{record.status}", status=409)

    expected = record.confirmation_token_hash or ""
    if not expected or hash_token(confirmation_token) != expected:
        raise ToolExecutionError("invalid_token", "确认凭证无效", status=403)

    tool = get_tool(record.tool_name)
    if not tool:
        raise ToolExecutionError("unknown_tool", "工具未注册", status=404)
    if not user_has_permission(user_data, tool.permission):
        raise ToolExecutionError("forbidden", f"缺少业务权限：{tool.permission}", status=403)

    # 清空 token，避免重复提交；真正执行走 confirmed=True
    record.confirmation_token_hash = ""
    record.status = AssistantToolExecution.STATUS_RUNNING
    record.save(update_fields=["confirmation_token_hash", "status"])

    result = execute_tool(
        tool_name=record.tool_name,
        params=dict(record.parameters_json or {}),
        user_data=user_data,
        conversation_id=record.conversation_id,
        confirmed=True,
        reuse_execution_id=record.id,
    )
    return {
        "execution_id": result.get("execution_id") or record.id,
        "status": result.get("status") or "completed",
        "tool_name": record.tool_name,
        "content": str(result.get("content") or result.get("summary") or "已执行。"),
        "blocks": [
            {
                "type": str(result.get("block_type") or "tool_result"),
                "data": result.get("data") if isinstance(result.get("data"), dict) else {},
            }
        ],
        "idempotent": False,
        "completed_at": timezone.now().isoformat(),
    }
