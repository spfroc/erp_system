from __future__ import annotations

from typing import Any

from apps.assistant.permissions import user_has_permission
from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS


def _navigation_find(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    keyword = str(params.get("keyword") or params.get("search") or params.get("query") or "").strip().lower()
    matches = []
    for item in DEFAULT_NAV_ITEMS:
        if not item.get("enabled", True):
            continue
        permission = str(item.get("permission") or "")
        if permission and not user_has_permission(user_data, permission):
            continue
        hay = f"{item.get('label', '')} {item.get('viewId', '')} {item.get('groupKey', '')}".lower()
        if keyword and keyword not in hay:
            continue
        matches.append(
            {
                "id": item.get("viewId"),
                "viewId": item.get("viewId"),
                "label": item.get("label"),
                "permission": permission,
                "categoryKey": item.get("categoryKey"),
                "groupKey": item.get("groupKey"),
                "iconKey": item.get("iconKey"),
            }
        )
    return {
        "block_type": "navigation",
        "summary": f"找到 {len(matches)} 个可访问功能入口。",
        "content": f"找到 {len(matches)} 个可访问功能入口。",
        "data": {"items": matches[:30], "total": len(matches)},
    }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="navigation.find",
            description="查找后台功能菜单并返回可跳转入口",
            input_schema={
                "type": "object",
                "properties": {"keyword": {"type": "string"}},
            },
            permission="dashboard.view",
            risk_level="read",
            handler=_navigation_find,
        )
    )
