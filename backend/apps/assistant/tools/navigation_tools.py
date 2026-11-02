from __future__ import annotations

import re
from typing import Any

from apps.assistant.permissions import user_has_permission
from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.nav_defaults import DEFAULT_NAV_ITEMS

_NOISE_RE = re.compile(
    r"(打开|进入|跳转到?|前往|查找|后台|功能|页面|模块|入口|菜单)"
)
_SUFFIX_RE = re.compile(r"(管理|列表|页面|模块|功能|入口)$")


def _normalize_keyword(raw: str) -> str:
    value = _NOISE_RE.sub(" ", (raw or "").strip().lower())
    value = re.sub(r"\s+", " ", value).strip()
    # 「销售订单管理」→「销售订单」
    trimmed = _SUFFIX_RE.sub("", value).strip()
    return trimmed or value


def _score_item(keyword: str, item: dict[str, Any]) -> int:
    """返回匹配分；0 表示不匹配。无关键词时全部可访问项记 1 分。"""
    label = str(item.get("label") or "").lower()
    view_id = str(item.get("viewId") or "").lower()
    group = str(item.get("groupKey") or "").lower()
    category = str(item.get("categoryKey") or "").lower()
    hay = f"{label} {view_id} {group} {category}"

    if not keyword:
        return 1
    if keyword == label or keyword == view_id:
        return 100
    if label and label in keyword:
        return 90
    if keyword in label or keyword in hay:
        return 80
    tokens = [token for token in re.split(r"[\s_/]+", keyword) if len(token) >= 2]
    if tokens and all(token in hay for token in tokens):
        return 60
    # 去掉「订单」等泛化词后再比一次，避免「销售订单」因多余噪声漏匹配
    compact = keyword.replace("的", "").strip()
    if compact and (compact in hay or (label and label in compact)):
        return 50
    return 0


def _navigation_find(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    raw_keyword = str(params.get("keyword") or params.get("search") or params.get("query") or "").strip()
    keyword = _normalize_keyword(raw_keyword)
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in DEFAULT_NAV_ITEMS:
        if not item.get("enabled", True):
            continue
        permission = str(item.get("permission") or "")
        if permission and not user_has_permission(user_data, permission):
            continue
        score = _score_item(keyword, item)
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "id": item.get("viewId"),
                    "viewId": item.get("viewId"),
                    "label": item.get("label"),
                    "permission": permission,
                    "categoryKey": item.get("categoryKey"),
                    "groupKey": item.get("groupKey"),
                    "iconKey": item.get("iconKey"),
                },
            )
        )
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("label") or "")))
    matches = [item for _, item in scored]
    # 有关键词且最高分明显高于其余时，视为唯一目标入口
    auto_open = False
    if keyword and matches:
        top = scored[0][0]
        auto_open = top >= 80 and (len(scored) == 1 or top > scored[1][0])
    return {
        "block_type": "navigation",
        "summary": f"找到 {len(matches)} 个可访问功能入口。",
        "content": f"找到 {len(matches)} 个可访问功能入口。"
        + (f"即将打开「{matches[0]['label']}」。" if auto_open else ""),
        "data": {
            "items": matches[:30],
            "total": len(matches),
            "keyword": keyword,
            "auto_open": auto_open,
        },
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
