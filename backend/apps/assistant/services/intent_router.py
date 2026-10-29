"""意图路由：规则优先，不确定时再调用 LLM；失败则降级澄清。"""

from __future__ import annotations

import json
from typing import Any

from apps.assistant.services.context_manager import build_tool_catalog_for_prompt, trim_context_for_llm
from apps.assistant.services.llm_adapter import LlmUnavailable, chat_completion_json, llm_config, probe_llm
from apps.assistant.services.rule_router import route_intent
from apps.assistant.services.tool_registry import get_tool, list_tools


SYSTEM_PROMPT = """你是 ERP 业务助手的意图解析器。
只能从给定工具列表中选择一个 tool_name，或返回需要澄清。
禁止生成 SQL、Shell、HTTP、代码。
禁止猜测业务记录 ID；若用户说「打开第N条」，使用 context.recent_result_ids。
输出严格 JSON：
{"tool_name": string|null, "params": object, "confidence": number, "clarification": string|null, "reason": string}
"""


def resolve_intent(
    message: str,
    context: dict[str, Any] | None = None,
    *,
    allowed_tool_names: set[str] | None = None,
) -> dict[str, Any]:
    """返回 route 字典，额外含 mode: rule_only | llm_assisted | degraded。"""
    context = context or {}
    rule = route_intent(message, context)
    if not rule.get("needs_clarification") and rule.get("tool_name"):
        if allowed_tool_names is None or rule["tool_name"] in allowed_tool_names:
            return {**rule, "mode": "rule_only"}

    cfg = llm_config()
    if not cfg["enabled"] or not cfg["base_url"]:
        return {
            **rule,
            "mode": "degraded",
            "reason": rule.get("reason") or "llm_disabled",
            "clarification": rule.get("clarification")
            or "当前为规则模式且模型未启用。请使用快捷提示，或更明确地描述要查询的公告/商品/订单。",
            "needs_clarification": True,
            "tool_name": None,
        }

    health = probe_llm()
    if not health.get("online"):
        return {
            **rule,
            "mode": "degraded",
            "reason": "llm_offline",
            "clarification": rule.get("clarification")
            or "本地模型离线，已降级为规则模式。请改用快捷功能或更明确的查询语句。",
            "needs_clarification": True,
            "tool_name": None,
        }

    tools = [tool.public_dict() for tool in list_tools()]
    if allowed_tool_names is not None:
        tools = [tool for tool in tools if tool["name"] in allowed_tool_names]
    catalog = build_tool_catalog_for_prompt(tools)
    safe_context = trim_context_for_llm(context)
    user_prompt = (
        f"用户输入：{message.strip()[:800]}\n"
        f"上下文：{json.dumps(safe_context, ensure_ascii=False)}\n"
        f"可用工具：{json.dumps(catalog, ensure_ascii=False)}"
    )
    try:
        result = chat_completion_json(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        data = result.get("data") or {}
        tool_name = data.get("tool_name")
        if tool_name in ("", None, "null"):
            tool_name = None
        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        clarification = data.get("clarification")
        confidence = float(data.get("confidence") or 0)
        if tool_name and get_tool(str(tool_name)) is None:
            return {
                "intent": "clarification",
                "tool_name": None,
                "params": {},
                "confidence": confidence,
                "needs_clarification": True,
                "reason": "llm_unknown_tool",
                "clarification": "模型选择了未注册工具，已拒绝执行。请换一种说法或使用快捷提示。",
                "mode": "llm_assisted",
            }
        if allowed_tool_names is not None and tool_name and tool_name not in allowed_tool_names:
            return {
                "intent": "clarification",
                "tool_name": None,
                "params": {},
                "confidence": confidence,
                "needs_clarification": True,
                "reason": "llm_tool_not_allowed",
                "clarification": "当前账号无权使用模型选择的工具。",
                "mode": "llm_assisted",
            }
        if not tool_name:
            return {
                "intent": "clarification",
                "tool_name": None,
                "params": {},
                "confidence": confidence,
                "needs_clarification": True,
                "reason": str(data.get("reason") or "llm_clarification"),
                "clarification": str(clarification or "请补充更具体的业务指令。"),
                "mode": "llm_assisted",
            }
        return {
            "intent": str(tool_name),
            "tool_name": str(tool_name),
            "params": params,
            "confidence": confidence,
            "needs_clarification": False,
            "reason": str(data.get("reason") or "llm"),
            "mode": "llm_assisted",
        }
    except LlmUnavailable as exc:
        if not cfg["fallback_enabled"]:
            return {
                "intent": "clarification",
                "tool_name": None,
                "params": {},
                "confidence": 0.1,
                "needs_clarification": True,
                "reason": exc.code,
                "clarification": f"模型不可用（{exc.message}），且未开启降级。",
                "mode": "degraded",
            }
        return {
            **rule,
            "mode": "degraded",
            "reason": exc.code,
            "clarification": rule.get("clarification")
            or f"模型暂时不可用（{exc.message}）。请使用快捷提示或更明确的查询语句。",
            "needs_clarification": True,
            "tool_name": None,
        }
