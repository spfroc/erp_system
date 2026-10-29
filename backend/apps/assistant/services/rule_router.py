"""规则优先意图路由：能确定则直接选工具，否则要求澄清（P1 不调 LLM）。"""

from __future__ import annotations

import re
from typing import Any


_ORG_NAME_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()]{2,40}(?:财政局|教育局|卫健委|管理局|采购中心|医院|大学|小学|中学|学院|委员会|局|院|校|中心|公司|部|处|办))"
)
_BUYER_RELEASE_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()]{2,40}?)\s*(?:发布的|发布|的)?\s*公告"
)


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(key in text for key in keywords)


def route_intent(message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回 {intent, tool_name, params, confidence, needs_clarification, reason}。"""
    context = context or {}
    text = (message or "").strip()
    recent_ids = list((context.get("recent_result_ids") or [])[:20])
    last_intent = str(context.get("intent") or "")
    last_params = dict(context.get("params") or {})

    # 多轮：打开第 N 条
    open_match = re.search(r"(打开|查看)第\s*([0-9一二三四五六七八九十]+)\s*条", text)
    if open_match and recent_ids:
        idx = _parse_ordinal(open_match.group(2)) - 1
        if 0 <= idx < len(recent_ids):
            return {
                "intent": "notice.get_detail",
                "tool_name": "notice.get_detail",
                "params": {"notice_id": int(recent_ids[idx])},
                "confidence": 0.95,
                "needs_clarification": False,
                "reason": "followup_open_nth",
            }

    # 打开指定公告 ID（来自结果卡片，禁止模型臆造）
    open_id = re.search(r"(?:打开|查看)\s*公告\s*(\d+)", text)
    if open_id:
        return {
            "intent": "notice.get_detail",
            "tool_name": "notice.get_detail",
            "params": {"notice_id": int(open_id.group(1))},
            "confidence": 0.95,
            "needs_clarification": False,
            "reason": "open_notice_id",
        }

    # 多轮：追加筛选 / 排序（继承上次公告搜索）
    if last_intent in {"notice.search", "deal.search", "goods.search"} and (
        _has_any(text, ("只看", "再筛", "追加", "预算", "两万元", "万元以上", "按时间", "倒序", "正序", "近", "昨天", "今天"))
    ):
        params = dict(last_params)
        tool_name = "deal.search" if last_intent == "deal.search" else ("goods.search" if last_intent == "goods.search" else "notice.search")
        if "倒序" in text:
            params["sort"] = "publish_time_desc"
        if "正序" in text:
            params["sort"] = "publish_time_asc"
        period = _extract_relative_period(text)
        if period:
            params["relative_period"] = period
        budget = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
        if budget:
            params["min_budget_wan"] = float(budget.group(1))
        buyer = _extract_buyer_name(text)
        if buyer:
            params["buyer_name"] = buyer
        if "济南" in text and "济南" not in str(params.get("search") or ""):
            params["search"] = f"{params.get('search') or ''} 济南".strip()
        return {
            "intent": tool_name,
            "tool_name": tool_name,
            "params": params,
            "confidence": 0.8,
            "needs_clarification": False,
            "reason": "followup_refine",
        }

    # 导航（避免把「过去」中的「去」误判为跳转）
    if _has_any(text, ("打开", "进入", "跳转", "前往", "查找后台", "后台功能")) and _has_any(
        text, ("订单", "公告", "商品", "财务", "菜单", "权限", "定时", "任务", "总览", "管理")
    ):
        keyword = re.sub(r"(打开|进入|跳转到?|前往|查找|后台|功能|页面|模块)", "", text).strip() or text
        return {
            "intent": "navigation.find",
            "tool_name": "navigation.find",
            "params": {"keyword": keyword},
            "confidence": 0.75,
            "needs_clarification": False,
            "reason": "navigation",
        }

    # 受控写操作：运行安全任务（需确认；仅白名单脚本）
    run_job = re.search(r"(?:运行|执行).{0,12}(?:任务|定时任务|打标).*?(?:id\s*[:=]?\s*|编号\s*)?(\d+)", text, re.I)
    if not run_job:
        run_job = re.search(r"(?:运行|执行)\s*(?:安全)?任务\s*(\d+)", text)
    if run_job and _has_any(text, ("运行", "执行")) and _has_any(text, ("任务", "打标", "定时")):
        return {
            "intent": "devops.run_safe_job",
            "tool_name": "devops.run_safe_job",
            "params": {"job_id": int(run_job.group(1))},
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "devops_run",
        }

    # 运维状态
    if _has_any(text, ("采集任务", "定时任务", "任务失败", "运行失败", "任务状态")):
        return {
            "intent": "devops.get_status",
            "tool_name": "devops.get_status",
            "params": {"failed_only": "失败" in text},
            "confidence": 0.85,
            "needs_clarification": False,
            "reason": "devops",
        }

    # 采购人
    if _has_any(text, ("采购人", "采购单位", "医院", "学校", "这家单位")) and _has_any(
        text, ("查", "分析", "画像", "买过", "采购过")
    ):
        name = text
        for token in ("查询", "分析", "采购人", "采购单位", "过去一年", "买过什么", "采购过什么", "商品"):
            name = name.replace(token, "")
        name = name.strip(" ：:，,。")
        if name and len(name) <= 40:
            return {
                "intent": "buyer.get_profile",
                "tool_name": "buyer.get_profile",
                "params": {"buyer_name": name},
                "confidence": 0.7,
                "needs_clarification": False,
                "reason": "buyer_profile",
            }
        return {
            "intent": "buyer.search",
            "tool_name": "buyer.search",
            "params": {"keyword": name or text},
            "confidence": 0.65,
            "needs_clarification": False,
            "reason": "buyer_search",
        }

    # ERP 订单
    if _has_any(text, ("销售订单", "销订")):
        return {
            "intent": "erp.sales_order.search",
            "tool_name": "erp.sales_order.search",
            "params": _order_params(text),
            "confidence": 0.85,
            "needs_clarification": False,
            "reason": "sales_order",
        }
    if _has_any(text, ("采购订单", "采订")) and not _has_any(text, ("采购公告", "公告")):
        return {
            "intent": "erp.purchase_order.search",
            "tool_name": "erp.purchase_order.search",
            "params": _order_params(text),
            "confidence": 0.85,
            "needs_clarification": False,
            "reason": "purchase_order",
        }

    # ERP 商品
    if _has_any(text, ("ERP商品", "商品名称", "商品及价格", "交换机", "库存商品")) or (
        "商品" in text and _has_any(text, ("ERP", "系统里", "我们的商品"))
    ):
        keyword = _extract_keyword(text, ("查找", "查询", "商品", "名称", "包含", "ERP", "系统"))
        return {
            "intent": "erp.product.search",
            "tool_name": "erp.product.search",
            "params": {"keyword": keyword or text, "page": 1, "page_size": 20},
            "confidence": 0.8,
            "needs_clarification": False,
            "reason": "erp_product",
        }

    # 成交
    if _has_any(text, ("成交公告", "历史成交", "成交记录", "中标")):
        params = _extract_notice_params(text)
        return {
            "intent": "deal.search",
            "tool_name": "deal.search",
            "params": params,
            "confidence": 0.85,
            "needs_clarification": False,
            "reason": "deal",
        }

    # 公告商品明细
    if _has_any(text, ("采购商品", "商品明细", "打印机", "惠普", "公告里的商品")):
        return {
            "intent": "goods.search",
            "tool_name": "goods.search",
            "params": {
                "keyword": _extract_keyword(text, ("查找", "查询", "搜索", "采购", "商品", "相关", "明细")),
                "page": 1,
                "page_size": 20,
            },
            "confidence": 0.8,
            "needs_clarification": False,
            "reason": "goods",
        }

    # 采购公告
    if _has_any(text, ("公告", "采购公告", "竞价", "询比", "济南", "办公设备", "发布的")):
        params = _extract_notice_params(text)
        if "成交" in text:
            return {
                "intent": "deal.search",
                "tool_name": "deal.search",
                "params": params,
                "confidence": 0.8,
                "needs_clarification": False,
                "reason": "deal_from_notice",
            }
        return {
            "intent": "notice.search",
            "tool_name": "notice.search",
            "params": params,
            "confidence": 0.8,
            "needs_clarification": False,
            "reason": "notice",
        }

    return {
        "intent": "clarification",
        "tool_name": None,
        "params": {},
        "confidence": 0.2,
        "needs_clarification": True,
        "reason": "unrecognized",
        "clarification": "我还不能确定要执行的操作。你可以试试：查询采购公告、搜索采购商品、查询销售/采购订单、打开某个后台功能。",
    }


def _extract_relative_period(text: str) -> str | None:
    if _has_any(text, ("昨天", "昨日")):
        return "yesterday"
    if _has_any(text, ("今天", "今日")):
        return "today"
    if "前天" in text:
        return "day_before_yesterday"
    days = re.search(r"最近\s*(\d+)\s*天", text)
    if days:
        return f"last_{int(days.group(1))}_days"
    if _has_any(text, ("一个月", "近一个月", "最近一个月", "近30天", "最近三十天", "最近30天")):
        return "last_30_days"
    if _has_any(text, ("本周", "这周")):
        return "this_week"
    if _has_any(text, ("本月", "这个月")):
        return "this_month"
    return None


def _extract_buyer_name(text: str) -> str:
    org = _ORG_NAME_RE.search(text or "")
    if org:
        return org.group(1).strip(" ：:，,。")
    released = _BUYER_RELEASE_RE.search(text or "")
    if released:
        name = released.group(1).strip(" ：:，,。")
        name = re.sub(r"^(查询|查找|搜索|昨天|昨日|今天|今日|前天|最近)", "", name)
        return name.strip()[:40]
    return ""


def _extract_notice_params(text: str) -> dict[str, Any]:
    """把自然语言拆成日期 / 采购单位 / 残余关键词，避免整句 LIKE。"""
    params: dict[str, Any] = {"page": 1, "page_size": 20}
    period = _extract_relative_period(text)
    if period:
        params["relative_period"] = period
    buyer = _extract_buyer_name(text)
    if buyer:
        params["buyer_name"] = buyer
    stopwords = (
        "查找",
        "查询",
        "搜索",
        "最近",
        "一个月",
        "采购",
        "公告",
        "昨天",
        "昨日",
        "今天",
        "今日",
        "前天",
        "发布的",
        "发布",
        "本周",
        "本月",
        "近30天",
        "最近三十天",
        "最近30天",
    )
    residual = _extract_keyword(text, stopwords)
    if buyer and buyer in residual:
        residual = residual.replace(buyer, " ")
    residual = re.sub(r"\s+", " ", residual).strip(" ，,。的")
    if residual and residual not in {"的", "了", "吗"}:
        params["search"] = residual[:80]
    return params


def _extract_keyword(text: str, stopwords: tuple[str, ...]) -> str:
    value = text
    for word in stopwords:
        value = value.replace(word, " ")
    value = re.sub(r"\s+", " ", value).strip(" ，,。；;：:")
    return value[:80]


def _order_params(text: str) -> dict[str, Any]:
    params: dict[str, Any] = {"page": 1, "page_size": 20}
    if "未完成" in text or "进行中" in text:
        params["status"] = ""  # 状态枚举因业务而异，留给列表侧筛选文案
        params["keyword"] = "未完成" if "未完成" in text else ""
    keyword = _extract_keyword(text, ("查询", "查找", "最近", "三十天", "30天", "未完成", "采购订单", "销售订单", "订单"))
    if keyword:
        params["keyword"] = keyword
    return params


def _parse_ordinal(token: str) -> int:
    mapping = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if token.isdigit():
        return int(token)
    return mapping.get(token, 1)
