"""MCP 调用日志列表（仅 mcpLog.view）。"""

from __future__ import annotations

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.assistant.models import AssistantToolExecution
from apps.data_store.models import UserRecord
from apps.data_store.views import _require_permission


MCP_LOG_VIEW = "mcpLog.view"


def _user_name_map(user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = UserRecord.objects.filter(id__in=user_ids, is_deleted=False).only("id", "name")
    return {row.id: row.name or row.id for row in rows}


def _serialize(row: AssistantToolExecution, names: dict[str, str]) -> dict:
    params = row.parameters_json if isinstance(row.parameters_json, dict) else {}
    return {
        "id": row.id,
        "userId": row.user_id,
        "userName": names.get(row.user_id) or row.user_id,
        "toolName": row.tool_name,
        "status": row.status,
        "summary": row.result_summary or "",
        "errorCode": row.error_code or "",
        "durationMs": row.duration_ms,
        "parameters": params,
        "createdAt": row.created_at.isoformat() if row.created_at else "",
        "completedAt": row.completed_at.isoformat() if row.completed_at else "",
    }


@require_http_methods(["GET"])
def mcp_call_logs(request):
    _, error = _require_permission(request, MCP_LOG_VIEW)
    if error:
        return error

    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    try:
        page_size = min(100, max(1, int(request.GET.get("page_size") or 20)))
    except ValueError:
        page_size = 20

    search = (request.GET.get("search") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = AssistantToolExecution.objects.filter(source="mcp")
    if status:
        qs = qs.filter(status=status)
    if search:
        user_ids = list(
            UserRecord.objects.filter(is_deleted=False, name__icontains=search).values_list("id", flat=True)[:50]
        )
        q = Q(tool_name__icontains=search) | Q(user_id__icontains=search) | Q(result_summary__icontains=search)
        if user_ids:
            q |= Q(user_id__in=user_ids)
        qs = qs.filter(q)

    total = qs.count()
    offset = (page - 1) * page_size
    rows = list(qs.order_by("-id")[offset : offset + page_size])
    names = _user_name_map({row.user_id for row in rows})
    return JsonResponse(
        {
            "items": [_serialize(row, names) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
