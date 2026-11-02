"""规则优先意图路由：能确定则直接选工具，否则要求澄清（P1 不调 LLM）。"""

from __future__ import annotations

import re
from typing import Any


_ORG_NAME_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()]{2,40}(?:财政局|教育局|卫健委|管理局|采购中心|医院|大学|小学|中学|学院|委员会|局|院|校|中心|公司|部|处|办))"
)
# 必须带「发布的/发布了」，且采购单位侧优先匹配机构后缀，避免「发布了多少成交公告」整句误抽
_BUYER_RELEASE_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()]{2,40}?(?:财政局|教育局|卫健委|管理局|采购中心|医院|大学|小学|中学|学院|委员会|局|院|校|中心|公司|部|处|办))"
    r"\s*(?:发布的|发布了|发布)\s*(?:的)?\s*(?:采购|成交)?公告"
)
_BUYER_NAME_NOISE = (
    "多少",
    "成交",
    "发布",
    "查询",
    "查找",
    "搜索",
    "今天",
    "今日",
    "昨天",
    "昨日",
    "前天",
    "最近",
    "公告",
    "采购",
    "中标",
    "条",
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

    # 多轮：若用户重新发起完整查询，不继承旧 search（避免脏条件 AND 成 0 条）
    fresh_notice_query = _has_any(text, ("查询", "查找", "搜索")) and _has_any(
        text, ("公告", "采购公告", "成交", "发布的")
    )
    # 统计/图表/金额汇总是新意图，绝不能被「近7天」里的「近」误收成 followup_refine
    analytics_query = _has_any(
        text,
        (
            "统计",
            "图表",
            "柱状",
            "柱状图",
            "折线",
            "概览",
            "分析",
            "汇总",
            "总金额",
            "合计",
            "销售情况",
            "类型和数量",
            "类型数量",
        ),
    )
    if (
        not fresh_notice_query
        and not analytics_query
        and last_intent in {"notice.search", "deal.search", "goods.search"}
        and _has_any(text, ("只看", "再筛", "追加", "预算", "两万元", "万元以上", "按时间", "倒序", "正序", "近"))
    ):
        params = dict(last_params)
        tool_name = (
            "deal.search"
            if last_intent == "deal.search"
            else ("goods.search" if last_intent == "goods.search" else "notice.search")
        )
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
            # 旧 search 若含整句/日期噪声，清掉，改由 buyer_name 精确筛
            params.pop("search", None)
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

    # 帮助
    if text in {"/help", "help", "帮助", "?", "？"} or _has_any(text, ("怎么用", "使用说明", "你会什么", "能做什么")):
        return {
            "intent": "help",
            "tool_name": None,
            "params": {},
            "confidence": 0.99,
            "needs_clarification": True,
            "reason": "help",
            "clarification": (
                "我可以帮你：\n"
                "1. 查询采购/成交公告，例如：查询昨天 平度市财政局 发布的公告\n"
                "2. 搜索公告商品明细，例如：查找惠普打印机相关采购记录\n"
                "3. 查询销售/采购/服务订单或 ERP 商品\n"
                "4. 查询客户到期时间、某客户购买的商品订单\n"
                "5. 按项目编号查开票状态，例如：2692… 查询该项目的开票状态\n"
                "6. 打开后台功能，例如：打开销售订单管理\n"
                "7. 查看采集/定时任务状态（只读）\n"
                "8. 删除发票（需点击确认后执行；已确认发票不可删）\n"
                "其他删除订单/用户等写操作暂不开放。"
            ),
        }

    # 删除发票（写操作，工具层强制确认）
    delete_invoice = re.search(r"(?:删除|删掉)\s*([A-Za-z0-9\-]{6,})\s*发票", text)
    if not delete_invoice:
        delete_invoice = re.search(r"(?:删除|删掉)\s*发票(?:号)?\s*([A-Za-z0-9\-]{6,})", text)
    if delete_invoice:
        return {
            "intent": "erp.invoice.delete",
            "tool_name": "erp.invoice.delete",
            "params": {"invoice_no": delete_invoice.group(1)},
            "confidence": 0.92,
            "needs_clarification": False,
            "reason": "invoice_delete",
        }

    # 明确拒绝其他危险写操作（避免落到模糊澄清）
    if _has_any(text, ("删除", "作废", "销毁")) and _has_any(text, ("订单", "公告", "用户", "账号")):
        return {
            "intent": "clarification",
            "tool_name": None,
            "params": {},
            "confidence": 0.95,
            "needs_clarification": True,
            "reason": "refuse_dangerous_write",
            "clarification": "助手当前不支持删除订单/公告/用户等写操作。删除发票请写「删除 发票号 发票」，确认后再执行。",
        }

    # 导航（避免把「过去」中的「去」误判为跳转）
    if _has_any(text, ("打开", "进入", "跳转", "前往", "查找后台", "后台功能")) and _has_any(
        text,
        (
            "订单",
            "公告",
            "商品",
            "财务",
            "菜单",
            "权限",
            "定时",
            "任务",
            "总览",
            "管理",
            "发票",
            "合同",
            "流水",
            "客户",
            "商机",
            "助手",
        ),
    ):
        keyword = re.sub(r"(打开|进入|跳转到?|前往|查找|后台|功能|页面|模块)", "", text).strip() or text
        keyword = re.sub(r"(管理|列表)$", "", keyword).strip() or keyword
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
    if _has_any(text, ("采集任务", "定时任务", "任务失败", "运行失败", "任务状态", "执行记录", "运行记录")):
        params: dict[str, Any] = {"failed_only": "失败" in text, "limit": 20}
        period = _extract_relative_period(text)
        if period:
            params["relative_period"] = period
        return {
            "intent": "devops.get_status",
            "tool_name": "devops.get_status",
            "params": params,
            "confidence": 0.85,
            "needs_clarification": False,
            "reason": "devops",
        }

    # 项目开票/状态（支持「编号 + 查询该项目的开票状态」）
    project_code = _extract_project_code(text)
    if project_code and _has_any(text, ("开票", "发票状态", "项目状态", "该项目", "付款状态", "到期")):
        return {
            "intent": "erp.project.status",
            "tool_name": "erp.project.status",
            "params": {"project_no": project_code},
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "project_status",
        }
    if _has_any(text, ("开票状态", "开票情况", "项目开票")):
        return {
            "intent": "erp.project.status",
            "tool_name": "erp.project.status",
            "params": {"project_no": project_code or _extract_keyword(text, ("查询", "查找", "项目", "的", "开票状态", "开票情况", "开票"))},
            "confidence": 0.8,
            "needs_clarification": False,
            "reason": "project_status",
        }

    # 客户/服务到期（含「一个月内过期的用户」）
    if _has_any(text, ("到期时间", "服务到期", "到期日", "续费时间", "过期", "到期")) and _has_any(
        text, ("客户", "用户", "服务", "项目", "月内", "天内")
    ):
        customer = _extract_customer_name(text)
        params: dict[str, Any] = {"customer": customer, "keyword": customer, "page": 1, "page_size": 20}
        within_months = _extract_within_months(text)
        if within_months:
            params["within_months"] = within_months
        within_days = _extract_within_days(text)
        if within_days:
            params["within_days"] = within_days
        # 「过期」默认带上同窗口内已过期；纯「到期」只看未来窗口
        if _has_any(text, ("过期", "已过期", "过期了")) or params.get("within_months") or params.get("within_days"):
            params["include_overdue"] = True
        return {
            "intent": "erp.customer.expiry",
            "tool_name": "erp.customer.expiry",
            "params": params,
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "customer_expiry",
        }

    # 订单/发票「总金额/统计/汇总」交给模型选 stats，禁止误走列表搜索（否则「未使用模型」+ 空列表）
    if _is_erp_amount_stats_query(text):
        return {
            "intent": "clarification",
            "tool_name": None,
            "params": {},
            "confidence": 0.2,
            "needs_clarification": True,
            "reason": "defer_erp_amount_stats_to_llm",
            "clarification": "",
        }

    # 服务订单
    if _has_any(text, ("服务订单",)):
        customer = _extract_customer_name(text)
        params = _order_params(text)
        if customer:
            params["customer"] = customer
            params["keyword"] = customer
        return {
            "intent": "erp.service_order.search",
            "tool_name": "erp.service_order.search",
            "params": params,
            "confidence": 0.88,
            "needs_clarification": False,
            "reason": "service_order",
        }

    # 客户购买的商品订单 / 销售订单
    if _has_any(text, ("商品订单", "购买的商品", "买过的商品", "客户购买")) or (
        "客户" in text and _has_any(text, ("销售订单", "商品项目"))
    ):
        customer = _extract_customer_name(text)
        params = _order_params(text)
        if customer:
            params["customer"] = customer
            params["keyword"] = customer
        return {
            "intent": "erp.sales_order.search",
            "tool_name": "erp.sales_order.search",
            "params": params,
            "confidence": 0.86,
            "needs_clarification": False,
            "reason": "customer_sales_orders",
        }

    # 采购人（公告侧，避免盖住「客户购买」）
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
        params = _order_params(text)
        customer = _extract_customer_name(text)
        if customer and "客户" in text:
            params["customer"] = customer
            params["keyword"] = customer
        return {
            "intent": "erp.sales_order.search",
            "tool_name": "erp.sales_order.search",
            "params": params,
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

    # 供应商名单（哪几家供应商 / 中标单位）
    if _has_any(text, ("供应商", "供货商", "中标单位", "中标供应商", "哪几家")) and _has_any(
        text, ("采购", "成交", "中标", "公告", "本月", "上月", "这个月", "上个月", "今天", "昨天")
    ):
        params = _extract_notice_params(text)
        params.pop("search", None)
        return {
            "intent": "deal.suppliers",
            "tool_name": "deal.suppliers",
            "params": params,
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "deal_suppliers",
        }

    # 成交金额 / 成交额统计（优先于列表，避免落到模型降级）
    if _has_any(text, ("成交金额", "成交额", "中标金额", "中标额")):
        params = _extract_notice_params(text)
        params.pop("search", None)
        return {
            "intent": "deal.stats",
            "tool_name": "deal.stats",
            "params": params,
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "deal_stats",
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

    # 采购公告列表（统计/图表类交给模型，避免误走列表搜索）
    if _has_any(text, ("公告", "采购公告", "竞价", "询比", "济南", "办公设备", "发布的")):
        if _has_any(
            text,
            ("统计", "图表", "柱状", "柱状图", "折线", "概览", "分析", "汇总", "类型和数量", "类型数量"),
        ):
            return {
                "intent": "clarification",
                "tool_name": None,
                "params": {},
                "confidence": 0.2,
                "needs_clarification": True,
                "reason": "defer_analytics_to_llm",
                "clarification": "",
            }
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
        "clarification": "我还不能确定要执行的操作。你可以试试：查询采购公告、客户到期时间、客户服务订单、某客户购买的商品订单、项目开票状态、打开某个后台功能。",
    }


def _is_erp_amount_stats_query(text: str) -> bool:
    """销售/采购/服务订单或发票的金额统计/汇总，勿命中列表搜索。"""
    has_metric = _has_any(
        text,
        (
            "统计",
            "总金额",
            "合计",
            "汇总",
            "总计",
            "多少钱",
            "金额是多少",
            "销售情况",
            "营收",
            "开完发票",
            "已开发票",
            "已开票",
            "发票金额",
            "开票金额",
            "发票总金额",
            "金额合计",
            "金额总和",
        ),
    )
    has_entity = _has_any(
        text,
        (
            "销售订单",
            "采购订单",
            "服务订单",
            "商品订单",
            "销订",
            "采订",
            "订单",
            "发票",
            "开票",
            "流水",
            "收款",
        ),
    )
    return has_metric and has_entity


def _extract_relative_period(text: str) -> str | None:
    if _has_any(text, ("昨天", "昨日")):
        return "yesterday"
    if _has_any(text, ("今天", "今日")):
        return "today"
    if "前天" in text:
        return "day_before_yesterday"
    days = re.search(r"(?:最近|近)\s*(\d+)\s*天", text)
    if days:
        return f"last_{int(days.group(1))}_days"
    if _has_any(text, ("上个月", "上月", "上一个月")):
        return "last_month"
    if _has_any(text, ("一个月", "近一个月", "最近一个月", "近30天", "最近三十天", "最近30天")):
        return "last_30_days"
    if _has_any(text, ("本周", "这周")):
        return "this_week"
    if _has_any(text, ("本月", "这个月")):
        return "this_month"
    return None


def _is_plausible_buyer_name(name: str) -> bool:
    value = (name or "").strip()
    if len(value) < 3 or len(value) > 40:
        return False
    if any(token in value for token in _BUYER_NAME_NOISE):
        return False
    if re.fullmatch(r"[0-9一二两三四五六七八九十百千万多少条了吗呢啊\s？?]+", value):
        return False
    return True


def _extract_buyer_name(text: str) -> str:
    org = _ORG_NAME_RE.search(text or "")
    if org:
        name = org.group(1).strip(" ：:，,。")
        if _is_plausible_buyer_name(name):
            return name
    released = _BUYER_RELEASE_RE.search(text or "")
    if released:
        name = released.group(1).strip(" ：:，,。")
        name = re.sub(r"^(查询|查找|搜索|昨天|昨日|今天|今日|前天|最近)", "", name)
        name = name.strip()[:40]
        if _is_plausible_buyer_name(name):
            return name
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
        "发布了",
        "发布",
        "本周",
        "本月",
        "近30天",
        "最近三十天",
        "最近30天",
        "成交公告",
        "成交记录",
        "历史成交",
        "成交金额",
        "成交额",
        "中标金额",
        "中标额",
        "供应商",
        "供货商",
        "中标单位",
        "中标供应商",
        "哪几家",
        "成交",
        "中标",
        "金额",
        "多少",
        "多少条",
        "一共",
        "总共",
        "上个月",
        "上一个月",
        "上月",
        "本月",
        "这个月",
        "采购了",
        "采购",
    )
    residual = _extract_keyword(text, stopwords)
    if buyer and buyer in residual:
        residual = residual.replace(buyer, " ")
    residual = re.sub(r"\s+", " ", residual).strip(" ，,。的了吗？?")
    if residual and residual not in {"的", "了", "吗", "呢", "啊", "条"}:
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
    keyword = _extract_keyword(
        text,
        (
            "查询",
            "查找",
            "最近",
            "三十天",
            "30天",
            "未完成",
            "采购订单",
            "销售订单",
            "服务订单",
            "商品订单",
            "订单",
            "客户",
            "的",
            "购买的",
            "买过的",
            "商品",
        ),
    )
    if keyword:
        params["keyword"] = keyword
    return params


def _extract_customer_name(text: str) -> str:
    value = _extract_keyword(
        text,
        (
            "查询",
            "查找",
            "搜索",
            "客户",
            "用户",
            "名称",
            "的",
            "服务订单",
            "销售订单",
            "商品订单",
            "采购订单",
            "订单",
            "到期时间",
            "到期日",
            "服务到期",
            "续费时间",
            "到期",
            "过期",
            "已过期",
            "购买的",
            "买过的",
            "商品",
            "项目",
            "开票状态",
            "开票情况",
            "一个月内",
            "六个月内",
            "三个月内",
            "两个月内",
            "近一个月",
            "近半年",
        ),
    )
    value = re.sub(
        r"[0-9一二两三四五六七八九十]+\s*个?\s*月\s*内|[0-9]+\s*天\s*内|近\s*[0-9]+\s*天",
        " ",
        value,
    )
    value = re.sub(r"\s+", " ", value).strip(" ，,。；;：:")
    if not value or value in {"用户名称", "名称", "用户", "客户"}:
        return ""
    if re.fullmatch(r"[0-9一二两三四五六七八九十个个月内过期用户名称近天\s]+", value):
        return ""
    return value[:40]


def _cn_num(token: str) -> int | None:
    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "半": 6,  # 近半年 → 按 6 个月
    }
    if token.isdigit():
        return int(token)
    return mapping.get(token)


def _extract_within_months(text: str) -> int | None:
    if "近半年" in text or "半年内" in text:
        return 6
    match = re.search(r"([0-9一二两三四五六七八九十半]+)\s*个?\s*月\s*内", text or "")
    if not match:
        match = re.search(r"近\s*([0-9一二两三四五六七八九十半]+)\s*个?\s*月", text or "")
    if not match:
        return None
    value = _cn_num(match.group(1))
    if value is None:
        return None
    return max(1, min(int(value), 36))


def _extract_within_days(text: str) -> int | None:
    match = re.search(r"(?:近\s*)?([0-9]+)\s*天\s*内?", text or "")
    if not match:
        return None
    return max(1, min(int(match.group(1)), 366))


def _extract_project_code(text: str) -> str:
    match = re.search(r"([0-9A-Za-z\-]{8,})", text or "")
    return match.group(1) if match else ""


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
