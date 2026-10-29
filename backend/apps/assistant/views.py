"""助手 HTTP API。P0 提供 status/tools；chat/会话在 P1 补齐。"""

from __future__ import annotations

import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.assistant.permissions import ASSISTANT_MANAGE, ASSISTANT_USE, ASSISTANT_VIEW, user_has_permission
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
        "online": False,  # P2 接入探测；P0 明确不连模型
        "fallbackEnabled": (os.getenv("ASSISTANT_FALLBACK_ENABLED") or "true").strip().lower()
        not in {"0", "false", "no"},
    }


@require_http_methods(["GET"])
def assistant_status(request):
    user_data, error = _require_permission(request, ASSISTANT_VIEW)
    if error:
        # 兼容：仅有 use/manage 时也应能看状态
        user_data, error2 = _require_login(request)
        if error2:
            return error2
        if not (
            user_has_permission(user_data, ASSISTANT_VIEW)
            or user_has_permission(user_data, ASSISTANT_USE)
            or user_has_permission(user_data, ASSISTANT_MANAGE)
        ):
            return error
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
    user_data, error = _require_permission(request, ASSISTANT_USE)
    if error:
        # view 也可浏览工具清单（只读）
        user_data, error = _require_permission(request, ASSISTANT_VIEW)
        if error:
            return error

    def allowed(permission: str) -> bool:
        return user_has_permission(user_data, permission)

    tools = [tool.public_dict() for tool in list_tools(permission_filter=allowed)]
    return JsonResponse({"items": tools, "total": len(tools)})


@csrf_exempt
@require_http_methods(["POST"])
def assistant_chat(request):
    """P0 占位：提示使用工具直调；P1 实现完整编排。"""
    _, error = _require_permission(request, ASSISTANT_USE)
    if error:
        return error
    return JsonResponse(
        {
            "detail": "聊天编排将在 P1 提供。当前可通过 /api/assistant/tools/ 查看可用工具。",
            "status": "not_implemented",
            "mode": "rule_only",
        },
        status=501,
    )
