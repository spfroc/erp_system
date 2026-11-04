"""工具执行：权限二次校验 + Schema 粗校验 + 审计落库。"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from django.utils import timezone

from apps.assistant.models import AssistantToolExecution
from apps.assistant.permissions import ASSISTANT_USE, user_has_permission
from apps.assistant.services.tool_registry import get_tool


def _issue_confirmation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, token_hash


def _preview_copy(tool_name: str, description: str, params: dict[str, Any]) -> tuple[str, str]:
    """返回 (content, description) 供确认卡片展示。"""
    if tool_name == "erp.invoice.delete":
        invoice_no = str(params.get("invoice_no") or params.get("invoice_id") or "").strip()
        label = f"发票「{invoice_no}」" if invoice_no else "该发票"
        description = f"删除{label}"
        content = f"即将删除{label}。请确认后执行（已确认状态的发票不可删除）。"
        return content, description
    description = description or tool_name
    return f"即将执行「{description}」，请确认后继续。", description


class ToolExecutionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _validate_params(schema: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """轻量 JSON Schema 子集校验：required + 未知字段剔除。"""
    props = schema.get("properties") or {}
    required = list(schema.get("required") or [])
    cleaned: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if key in props:
            cleaned[key] = value
    missing = [key for key in required if cleaned.get(key) in (None, "")]
    if missing:
        raise ToolExecutionError("invalid_params", f"缺少参数：{', '.join(missing)}")
    return cleaned


def execute_tool(
    *,
    tool_name: str,
    params: dict[str, Any] | None,
    user_data: dict,
    conversation_id: int | None = None,
    confirmed: bool = False,
    reuse_execution_id: int | None = None,
    source: str = "assistant",
) -> dict[str, Any]:
    if not user_has_permission(user_data, ASSISTANT_USE):
        raise ToolExecutionError("forbidden", "无助手使用权限", status=403)

    tool = get_tool(tool_name)
    if not tool:
        raise ToolExecutionError("unknown_tool", f"未注册工具：{tool_name}", status=404)

    if not user_has_permission(user_data, tool.permission):
        raise ToolExecutionError("forbidden", f"缺少业务权限：{tool.permission}", status=403)

    cleaned = _validate_params(tool.input_schema or {}, params or {})
    user_id = str(user_data.get("id") or "")

    if tool.requires_confirmation and not confirmed:
        token, token_hash = _issue_confirmation_token()
        preview_content, preview_description = _preview_copy(tool.name, tool.description, cleaned)
        record = AssistantToolExecution.objects.create(
            conversation_id=conversation_id,
            user_id=user_id,
            tool_name=tool.name,
            source=(source or "assistant")[:32],
            parameters_json=cleaned,
            status=AssistantToolExecution.STATUS_AWAITING_CONFIRMATION,
            confirmation_token_hash=token_hash,
            result_summary="等待用户确认",
            result_json={
                "preview": True,
                "risk_level": tool.risk_level,
                "description": preview_description,
            },
        )
        return {
            "execution_id": record.id,
            "tool_name": tool.name,
            "status": "awaiting_confirmation",
            "block_type": "tool_preview",
            "summary": preview_description,
            "content": preview_content,
            "data": {
                "tool_name": tool.name,
                "description": preview_description,
                "risk_level": tool.risk_level,
                "params": cleaned,
                "execution_id": record.id,
                "confirmation_token": token,
                "requires_confirmation": True,
            },
        }

    if reuse_execution_id:
        record = AssistantToolExecution.objects.filter(id=reuse_execution_id, user_id=user_id).first()
        if not record:
            raise ToolExecutionError("not_found", "执行记录不存在", status=404)
        record.parameters_json = cleaned
        record.status = AssistantToolExecution.STATUS_RUNNING
        record.error_code = ""
        record.save(update_fields=["parameters_json", "status", "error_code"])
    else:
        record = AssistantToolExecution.objects.create(
            conversation_id=conversation_id,
            user_id=user_id,
            tool_name=tool.name,
            source=(source or "assistant")[:32],
            parameters_json=cleaned,
            status=AssistantToolExecution.STATUS_RUNNING,
        )

    started = time.perf_counter()
    try:
        result = tool.handler(params=cleaned, user_data=user_data) or {}
        if not isinstance(result, dict):
            raise ToolExecutionError("invalid_result", "工具返回必须是对象")
        duration_ms = int((time.perf_counter() - started) * 1000)
        summary = str(result.get("summary") or result.get("content") or "")[:500]
        record.status = AssistantToolExecution.STATUS_COMPLETED
        record.result_summary = summary
        record.result_json = {
            "block_type": result.get("block_type"),
            "total": (result.get("data") or {}).get("total"),
            "keys": sorted(list((result.get("data") or {}).keys()))[:20],
            "data": result.get("data") if isinstance(result.get("data"), dict) else {},
        }
        record.duration_ms = duration_ms
        record.completed_at = timezone.now()
        record.save(
            update_fields=[
                "status",
                "result_summary",
                "result_json",
                "duration_ms",
                "completed_at",
            ]
        )
        return {
            "execution_id": record.id,
            "tool_name": tool.name,
            "status": "completed",
            "duration_ms": duration_ms,
            **result,
        }
    except ToolExecutionError as exc:
        record.status = AssistantToolExecution.STATUS_FAILED
        record.error_code = exc.code
        record.result_summary = exc.message
        record.duration_ms = int((time.perf_counter() - started) * 1000)
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_code", "result_summary", "duration_ms", "completed_at"])
        raise
    except Exception as exc:  # noqa: BLE001
        record.status = AssistantToolExecution.STATUS_FAILED
        record.error_code = "tool_failed"
        record.result_summary = str(exc)[:500]
        record.duration_ms = int((time.perf_counter() - started) * 1000)
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_code", "result_summary", "duration_ms", "completed_at"])
        raise ToolExecutionError("tool_failed", f"工具执行失败：{exc}", status=500) from exc
