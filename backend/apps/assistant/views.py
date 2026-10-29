"""助手 HTTP API。"""

from __future__ import annotations

import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.assistant.permissions import ASSISTANT_MANAGE, ASSISTANT_USE, ASSISTANT_VIEW, user_has_permission
from apps.assistant.services import conversation as conversation_service
from apps.assistant.services.orchestrator import handle_chat
from apps.assistant.services.tool_registry import list_tools
from apps.data_store.views import _require_login, _require_permission


def _llm_status() -> dict:
    enabled = (os.getenv("ASSISTANT_LLM_ENABLED") or "false").strip().lower() in {"1", "true", "yes"}
    base_url = (os.getenv("ASSISTANT_LLM_BASE_URL") or "").strip()
    return {
        "enabled": enabled,
        "configured": bool(base_url),
        "baseUrl": base_url or None,
        "model": (os.getenv("ASSISTANT_LLM_MODEL") or "").strip() or None,
        "online": False,
        "fallbackEnabled": (os.getenv("ASSISTANT_FALLBACK_ENABLED") or "true").strip().lower()
        not in {"0", "false", "no"},
    }


def _parse_json(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


@require_http_methods(["GET"])
def assistant_status(request):
    user_data, error = _require_login(request)
    if error:
        return error
    if not (
        user_has_permission(user_data, ASSISTANT_VIEW)
        or user_has_permission(user_data, ASSISTANT_USE)
        or user_has_permission(user_data, ASSISTANT_MANAGE)
    ):
        return JsonResponse({"detail": "当前账号没有执行此操作的权限。", "permission": ASSISTANT_VIEW}, status=403)
    return JsonResponse(
        {
            "enabled": (os.getenv("ASSISTANT_ENABLED") or "true").strip().lower()
            not in {"0", "false", "no"},
            "mode": "rule_only",
            "llm": _llm_status(),
            "permissions": {
                "view": user_has_permission(user_data, ASSISTANT_VIEW),
                "use": user_has_permission(user_data, ASSISTANT_USE),
                "manage": user_has_permission(user_data, ASSISTANT_MANAGE),
            },
        }
    )


@require_http_methods(["GET"])
def assistant_tools(request):
    user_data, error = _require_permission(request, ASSISTANT_VIEW)
    if error:
        return error

    def allowed(permission: str) -> bool:
        return user_has_permission(user_data, permission)

    tools = [tool.public_dict() for tool in list_tools(permission_filter=allowed)]
    return JsonResponse({"items": tools, "total": len(tools)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def assistant_conversations(request):
    if request.method == "GET":
        user_data, error = _require_permission(request, ASSISTANT_VIEW)
        if error:
            return error
        items = conversation_service.list_conversations(str(user_data["id"]))
        return JsonResponse({"items": items, "total": len(items)})

    user_data, error = _require_permission(request, ASSISTANT_USE)
    if error:
        return error
    payload = _parse_json(request)
    row = conversation_service.create_conversation(str(user_data["id"]), title=str(payload.get("title") or ""))
    return JsonResponse(
        {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "DELETE", "PATCH"])
def assistant_conversation_detail(request, conversation_id: int):
    user_data, error = _require_permission(request, ASSISTANT_VIEW)
    if error:
        return error
    user_id = str(user_data["id"])
    row = conversation_service.get_conversation(user_id, conversation_id)
    if not row:
        return JsonResponse({"detail": "会话不存在"}, status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "id": row.id,
                "title": row.title,
                "context": row.context_json or {},
                "messages": conversation_service.list_messages(row),
                "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            }
        )

    if request.method == "DELETE":
        _, error = _require_permission(request, ASSISTANT_USE)
        if error:
            return error
        conversation_service.soft_delete_conversation(user_id, conversation_id)
        return JsonResponse({"ok": True})

    _, error = _require_permission(request, ASSISTANT_USE)
    if error:
        return error
    payload = _parse_json(request)
    title = str(payload.get("title") or "").strip()
    if not title:
        return JsonResponse({"detail": "标题不能为空"}, status=400)
    updated = conversation_service.rename_conversation(user_id, conversation_id, title)
    if not updated:
        return JsonResponse({"detail": "会话不存在"}, status=404)
    return JsonResponse({"id": updated.id, "title": updated.title})


@csrf_exempt
@require_http_methods(["POST"])
def assistant_chat(request):
    user_data, error = _require_permission(request, ASSISTANT_USE)
    if error:
        return error
    payload = _parse_json(request)
    message = str(payload.get("message") or payload.get("content") or "").strip()
    conversation_id = payload.get("conversation_id") or payload.get("conversationId")
    try:
        conversation_id = int(conversation_id) if conversation_id not in (None, "") else None
    except (TypeError, ValueError):
        return JsonResponse({"detail": "conversation_id 无效"}, status=400)
    result = handle_chat(user_data=user_data, message=message, conversation_id=conversation_id)
    status_code = 200
    if result.get("status") == "error" and result.get("errors"):
        code = (result["errors"][0] or {}).get("code")
        if code == "conversation_not_found":
            status_code = 404
        elif code == "empty_message":
            status_code = 400
    return JsonResponse(result, status=status_code)
