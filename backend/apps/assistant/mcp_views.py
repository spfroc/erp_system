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
    return (request.META.get("HTTP_X_MCP_TOKEN") or request.headers.get("X-Api-Key") or "").strip()


def _authenticate_user(request) -> dict | None:
    """优先匹配环境级服务 Token；否则校验个人中心签发的凭证。"""
    provided = _extract_bearer(request)
    if not provided:
        return None
    expected = mcp_token()
    if expected and secrets.compare_digest(provided, expected):
        return mcp_service_user()
    try:
        from apps.data_store.profile_views import resolve_user_data_for_api_token
    except Exception:  # noqa: BLE001
        return None
    return resolve_user_data_for_api_token(provided)


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def mcp_endpoint(request):
    if not mcp_enabled():
        return JsonResponse({"detail": "MCP connector disabled"}, status=503)

    user_data = _authenticate_user(request)
    if not user_data:
        return _unauthorized()

    if request.method == "GET":
        return HttpResponse(status=405)

    if request.method == "DELETE":
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
        response_body, status, extra_headers = handle_jsonrpc(body, user_data=user_data)
    except Exception as exc:  # noqa: BLE001
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
