"""会话上下文裁剪：只把必要信息送给模型。"""

from __future__ import annotations

from typing import Any


ALLOWED_CONTEXT_KEYS = (
    "intent",
    "params",
    "recent_result_ids",
    "sort",
    "selected_entity",
    "last_tool_status",
    "mode",
)


def trim_context_for_llm(context: dict[str, Any] | None, *, max_ids: int = 10) -> dict[str, Any]:
    context = context or {}
    params = context.get("params") if isinstance(context.get("params"), dict) else {}
    safe_params = {
        key: value
        for key, value in params.items()
        if isinstance(value, (str, int, float, bool)) and key.lower().find("password") < 0
    }
    ids = []
    for value in list(context.get("recent_result_ids") or [])[:max_ids]:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    selected = context.get("selected_entity") if isinstance(context.get("selected_entity"), dict) else {}
    safe_selected = {
        key: selected.get(key)
        for key in ("type", "id", "name")
        if selected.get(key) is not None
    }
    return {
        "intent": str(context.get("intent") or ""),
        "params": safe_params,
        "recent_result_ids": ids,
        "sort": str(context.get("sort") or ""),
        "selected_entity": safe_selected,
        "last_tool_status": str(context.get("last_tool_status") or ""),
    }


def build_tool_catalog_for_prompt(
    tools: list[dict[str, Any]],
    *,
    limit: int = 24,
    compact: bool = True,
    desc_limit: int = 40,
) -> list[dict[str, Any]]:
    """供意图模型使用的工具目录。默认精简，避免撑爆小模型 n_ctx。"""
    catalog = []
    cut = max(20, int(desc_limit))
    for tool in tools[:limit]:
        desc = str(tool.get("description") or "")
        if compact:
            catalog.append(
                {
                    "name": tool.get("name"),
                    "description": desc[:cut],
                }
            )
        else:
            catalog.append(
                {
                    "name": tool.get("name"),
                    "description": desc,
                    "permission": tool.get("permission"),
                    "input_schema": tool.get("input_schema") or {},
                }
            )
    return catalog
