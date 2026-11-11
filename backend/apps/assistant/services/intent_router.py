"""意图路由：规则优先，不确定时再调用 LLM；失败则降级澄清。"""

from __future__ import annotations

import json
from typing import Any

from apps.assistant.services.context_manager import build_tool_catalog_for_prompt, trim_context_for_llm
from apps.assistant.services.llm_adapter import LlmUnavailable, chat_completion_json, llm_config, probe_llm
from apps.assistant.services.rule_router import route_intent
from apps.assistant.services.tool_registry import get_tool, list_tools
from apps.assistant.services.user_settings import compose_system_prompt


SYSTEM_PROMPT = """ERP意图解析器。只输出JSON选一个工具。禁止SQL/代码。禁止无必要时澄清。
统计/概览/分析/总金额类必须选工具，不要澄清；禁止选 erp.sales_order.search 等列表工具：
- erp.sales.overview：销售/采购/服务订单总金额、已确认发票金额、收款流水（「统计销售/采购订单与已开发票总金额」「本月开票总金额」用这个）
- erp.transaction.stats：服务/商品项目流水合计
- notice.stats：公告按类型统计数量（近N天公告类型数量）
- deal.stats：成交金额
列表才用：erp.sales_order.search；erp.purchase_order.search；erp.service_order.search；deal.search；notice.search。
notice.search：若用户给出 SDGP/SCJJ 等项目编号，必须传 params.project_code=该编号（精确匹配），禁止空 search 扫全库。
平台账号：erp.platform_account.search（keyword=客户名；要密码时 include_password=true）；
erp.platform_account.create（可用 text 识别添加）；erp.platform_account.update。
客户基础信息：erp.customer.search；erp.customer.create（可用 text；重复时返回对照，确认后传 id+confirm_update=true 更新）。
其它：deal.suppliers；erp.customer.expiry；erp.project.status；navigation.find。
erp.customer.expiry 参数：within_months/within_days；include_overdue（仅用户说「过期」时 true）；
service_type=周期|按次；exclude_renewed=true 表示排除已续费客户；不要把整句说明塞进 customer/keyword。
params.relative_period：today|yesterday|this_month|last_month|last_7_days|last_30_days|last_N_days|all；
未指定时间的「总金额/累计」用 all；「本月销售情况」「本月开票」用 this_month。
金额/数量统计默认只返回数字，禁止默认带图表；仅当用户明确说「图表/柱状图/折线图/饼图」时才设 params.chart_type=bar|line|pie，否则不要传 chart_type。
JSON:{"tool_name":string|null,"params":{},"confidence":0-1,"clarification":string|null,"reason":string}
"""

# 有模型时默认全部走 LLM；仅危险拦截仍可跳过模型，避免误执行写操作
_RULE_FASTPATH_REASONS = frozenset(
    {
        "refuse_dangerous_write",
        # 项目编号公告查询必须精确，不交给模型以免漏参扫全库
        "notice_project_code",
    }
)


def _should_use_rule_fastpath(rule: dict[str, Any]) -> bool:
    if rule.get("needs_clarification") or not rule.get("tool_name"):
        return False
    reason = str(rule.get("reason") or "")
    return reason in _RULE_FASTPATH_REASONS


def _rule_as_fallback(
    rule: dict[str, Any],
    *,
    detail: str,
    reason: str,
    allowed_tool_names: set[str] | None,
) -> dict[str, Any]:
    """模型不可用时：有可用规则工具则降级执行，否则澄清。"""
    tool_name = rule.get("tool_name")
    can_run = bool(tool_name) and not rule.get("needs_clarification")
    if can_run and allowed_tool_names is not None and tool_name not in allowed_tool_names:
        can_run = False
    if can_run:
        return {
            **rule,
            "mode": "degraded",
            "reason": reason,
            "clarification": None,
            "needs_clarification": False,
        }
    return {
        **rule,
        "mode": "degraded",
        "reason": reason,
        "clarification": _degraded_clarification(rule, detail=detail),
        "needs_clarification": True,
        "tool_name": None,
    }


_UNRECOGNIZED_CLARIFICATION_PREFIX = "我还不能确定要执行的操作"
_DEFER_REASONS = frozenset(
    {
        "unrecognized",
        "defer_analytics_to_llm",
        "defer_erp_amount_stats_to_llm",
        "defer_customer_expiry_to_llm",
    }
)


def _is_placeholder_clarification(text: Any) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    return value.startswith(_UNRECOGNIZED_CLARIFICATION_PREFIX)


def _degraded_clarification(rule: dict[str, Any], *, detail: str) -> str:
    """LLM 不可用时的文案：不复用规则「我还不能确定…」，避免看起来像没走模型。"""
    reason = str(rule.get("reason") or "")
    rule_text = str(rule.get("clarification") or "").strip()
    if reason in _DEFER_REASONS or reason.startswith("defer_") or _is_placeholder_clarification(rule_text):
        return (
            f"这条问句需要模型解析，但模型暂时不可用（{detail}）。"
            "请稍后重试，或改用更明确的说法，例如：近7天采购公告类型统计、本月成交金额、客户服务订单。"
        )
    if rule_text:
        return f"模型暂时不可用（{detail}）。{rule_text}"
    return (
        f"当前需要模型协助解析，但模型不可用（{detail}）。"
        "请更明确地描述要查询的公告/商品/订单/平台账号。"
    )


def resolve_intent(
    message: str,
    context: dict[str, Any] | None = None,
    *,
    allowed_tool_names: set[str] | None = None,
    system_prompt_addon: str | None = None,
) -> dict[str, Any]:
    """返回 route 字典，额外含 mode: rule_only | llm_assisted | degraded。

    有模型时优先 LLM；规则仅作危险拦截快路径，以及模型不可用时的降级执行。
    """
    context = context or {}
    rule = route_intent(message, context)
    if _should_use_rule_fastpath(rule):
        if allowed_tool_names is None or rule["tool_name"] in allowed_tool_names:
            return {**rule, "mode": "rule_only"}

    cfg = llm_config()
    if not cfg["enabled"] or not cfg["base_url"]:
        return _rule_as_fallback(
            rule,
            detail="模型未启用",
            reason=str(rule.get("reason") or "llm_disabled"),
            allowed_tool_names=allowed_tool_names,
        )

    health = probe_llm()
    if not health.get("online"):
        detail = str(health.get("detail") or "offline")[:80]
        return _rule_as_fallback(
            rule,
            detail=detail,
            reason="llm_offline",
            allowed_tool_names=allowed_tool_names,
        )

    tools = [tool.public_dict() for tool in list_tools()]
    if allowed_tool_names is not None:
        tools = [tool for tool in tools if tool["name"] in allowed_tool_names]
    # 统计类工具描述放长一点，方便模型选对
    catalog = build_tool_catalog_for_prompt(tools, limit=22, compact=True, desc_limit=72)
    safe_context = trim_context_for_llm(context, max_ids=5)
    user_prompt = (
        f"用户：{message.strip()[:200]}\n"
        f"上下文：{json.dumps(safe_context, ensure_ascii=False)[:220]}\n"
        f"工具：{json.dumps(catalog, ensure_ascii=False)}"
    )
    system_prompt = compose_system_prompt(SYSTEM_PROMPT, system_prompt_addon)
    try:
        result = chat_completion_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout=int(cfg.get("intent_timeout") or 20),
            max_tokens=min(256, int(cfg.get("max_output_tokens") or 384)),
        )
        data = result.get("data") or {}
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else None
        llm_meta = {
            "llm_usage": usage,
            "llm_model": cfg.get("model") or None,
            "llm_duration_ms": result.get("duration_ms"),
        }
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
                "clarification": "模型选择了未注册工具，已拒绝执行。请换一种说法再试。",
                "mode": "llm_assisted",
                **llm_meta,
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
                **llm_meta,
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
                **llm_meta,
            }
        return {
            "intent": str(tool_name),
            "tool_name": str(tool_name),
            "params": params,
            "confidence": confidence,
            "needs_clarification": False,
            "reason": str(data.get("reason") or "llm"),
            "mode": "llm_assisted",
            **llm_meta,
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
        return _rule_as_fallback(
            rule,
            detail=exc.message,
            reason=str(exc.code or "llm_unavailable"),
            allowed_tool_names=allowed_tool_names,
        )
