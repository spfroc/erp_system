"""MCP Streamable HTTP 入口（企业微信连接器）。"""

from __future__ import annotations

import json
import secrets

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.assistant.services.mcp_server import handle_jsonrpc, mcp_enabled, mcp_service_user, mcp_token


def _unauthorized() -> JsonResponse:
    return JsonResponse(
        {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}, "id": None},
        status=401,
    )


def _extract_bearer(request) -> str:
    auth = (request.META.get("HTTP_AUTHORIZATION") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # 兼容静态凭证放在自定义头
    return (request.META.get("HTTP_X_MCP_TOKEN") or request.headers.get("X-Api-Key") or "").strip()


def _authenticate(request) -> bool:
    expected = mcp_token()
    if not expected:
        return False
    provided = _extract_bearer(request)
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def mcp_endpoint(request):
    if not mcp_enabled():
        return JsonResponse({"detail": "MCP connector disabled"}, status=503)

    if not _authenticate(request):
        return _unauthorized()

    if request.method == "GET":
        # 本服务不推送长连接通知；企微/客户端只需 POST JSON-RPC
        return HttpResponse(status=405)

    if request.method == "DELETE":
        # 无状态会话，直接接受结束
        return HttpResponse(status=204)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status=400,
        )

    if isinstance(body, list):
        return JsonResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Batch requests are not supported"},
                "id": None,
            },
            status=400,
        )

    req_id = body.get("id") if isinstance(body, dict) else None
    try:
        response_body, status, extra_headers = handle_jsonrpc(body, user_data=mcp_service_user())
    except Exception as exc:  # noqa: BLE001 — 对企微始终返回 JSON-RPC，避免 HTML 500
        response = JsonResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": f"Internal error: {exc}"},
            },
            status=500,
            json_dumps_params={"ensure_ascii": False},
        )
        return response

    if response_body is None:
        response = HttpResponse(status=status)
    else:
        response = JsonResponse(response_body, status=status, json_dumps_params={"ensure_ascii": False})

    for key, value in extra_headers.items():
        response[key] = value
    return response
