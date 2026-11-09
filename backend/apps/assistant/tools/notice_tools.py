from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum

from apps.assistant.services.chart_params import resolve_chart_type
from apps.assistant.services.notice_query import get_notice_detail, search_notice_goods, search_notices
from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.notice_models import NoticeParsed


def _resolve_period(params: dict[str, Any]) -> tuple[str, str]:
    publish_from = str(params.get("publish_date_from") or params.get("publishDateFrom") or "").strip()
    publish_to = str(params.get("publish_date_to") or params.get("publishDateTo") or "").strip()
    if publish_from or publish_to:
        return publish_from, publish_to
    period = str(params.get("relative_period") or "").strip()
    today = date.today()
    if period == "yesterday":
        day = today - timedelta(days=1)
        return day.isoformat(), day.isoformat()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "day_before_yesterday":
        day = today - timedelta(days=2)
        return day.isoformat(), day.isoformat()
    if period == "last_30_days":
        return (today - timedelta(days=30)).isoformat(), today.isoformat()
    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    if period == "this_month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()
    if period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.isoformat(), last_prev.isoformat()
    m = period.startswith("last_") and period.endswith("_days")
    if m:
        try:
            days = int(period[len("last_") : -len("_days")])
            days = max(1, min(days, 365))
            return (today - timedelta(days=days)).isoformat(), today.isoformat()
        except ValueError:
            pass
    return "", ""


def _clean_search(search: str, buyer_name: str = "") -> str:
    """去掉日期/发布等噪声，以及与 buyer_name 重复的片段。"""
    text = (search or "").strip()
    if not text:
        return ""
    noise = (
        "昨天",
        "昨日",
        "今天",
        "今日",
        "前天",
        "发布的",
        "发布了",
        "发布",
        "公告",
        "查询",
        "查找",
        "搜索",
        "最近",
        "采购",
        "成交公告",
        "成交记录",
        "历史成交",
        "成交",
        "中标",
        "多少",
        "多少条",
        "一共",
        "总共",
    )
    for word in noise:
        text = text.replace(word, " ")
    if buyer_name:
        text = text.replace(buyer_name, " ")
    return " ".join(text.split()).strip(" ，,。的了吗？?")


def _sanitize_buyer_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        return ""
    junk = ("多少", "成交", "发布", "查询", "查找", "今天", "今日", "昨天", "昨日", "公告", "采购")
    if any(token in value for token in junk):
        return ""
    return value


def _notice_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    from apps.data_store.notice_views import extract_gov_project_codes

    publish_from, publish_to = _resolve_period(params)
    buyer_name = _sanitize_buyer_name(str(params.get("buyer_name") or params.get("buyerName") or "").strip())
    raw_search = str(
        params.get("search")
        or params.get("keyword")
        or params.get("project_code")
        or params.get("projectCode")
        or ""
    ).strip()
    # 编排层可能注入用户原话，避免模型漏传项目编号时扫全库
    user_message = str(params.get("_user_message") or params.get("user_message") or "").strip()
    project_code = str(params.get("project_code") or params.get("projectCode") or "").strip()
    if not project_code:
        codes = extract_gov_project_codes(raw_search) or extract_gov_project_codes(user_message)
        if codes:
            project_code = codes[0]
    search = _clean_search(raw_search, buyer_name)
    if project_code:
        # 精确编号查询时不要残留「项目相关的」等中文拖累过滤
        search = project_code
    result = search_notices(
        page=int(params.get("page") or 1),
        page_size=int(params.get("page_size") or params.get("pageSize") or 20),
        search=search,
        site_id=str(params.get("site_id") or params.get("siteId") or "").strip(),
        notice_kind=str(params.get("notice_kind") or params.get("noticeKind") or "").strip(),
        publish_date_from=publish_from,
        publish_date_to=publish_to,
        buyer_name=buyer_name,
        project_code=project_code,
    )
    total = int(result.get("total") or 0)
    if project_code:
        summary = f"按项目编号「{project_code}」找到 {total} 条公告。"
    else:
        summary = f"找到 {total} 条公告。"
    return {
        "block_type": "notice_list",
        "summary": summary,
        "content": summary,
        "data": result,
    }


def _notice_get_detail(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    notice_id = int(params.get("notice_id") or params.get("id") or 0)
    detail = get_notice_detail(notice_id)
    if not detail:
        return {
            "block_type": "error",
            "summary": "公告不存在",
            "content": "公告不存在或表未就绪。",
            "data": {"notice_id": notice_id},
        }
    title = detail.get("title") or detail.get("noticeTitle") or f"公告 #{notice_id}"
    return {
        "block_type": "notice_detail",
        "summary": f"已打开公告：{title}",
        "content": f"已打开公告：{title}",
        "data": {"item": detail, "notice_id": notice_id, "open_modal": True},
    }


def _goods_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    result = search_notice_goods(
        keyword=str(params.get("keyword") or params.get("search") or "").strip(),
        page=int(params.get("page") or 1),
        page_size=int(params.get("page_size") or 20),
        site_id=str(params.get("site_id") or "").strip(),
    )
    total = int(result.get("total") or 0)
    return {
        "block_type": "goods_table",
        "summary": f"找到 {total} 条采购商品明细。",
        "content": f"找到 {total} 条采购商品明细。",
        "data": result,
    }


def _deal_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """成交公告：复用 notice.search + notice_kind=成交公告。"""
    merged = dict(params)
    merged["notice_kind"] = "成交公告"
    return _notice_search(params=merged, user_data=user_data)


def _money(value: Any) -> str:
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _deal_filtered_qs(params: dict[str, Any]):
    publish_from, publish_to = _resolve_period(params)
    buyer_name = _sanitize_buyer_name(str(params.get("buyer_name") or params.get("buyerName") or "").strip())
    qs = NoticeParsed.objects.filter(Q(notice_kind__icontains="成交") | Q(notice_kind__icontains="中标"))
    if buyer_name:
        qs = qs.filter(buyer_name__icontains=buyer_name)
    if publish_from:
        qs = qs.filter(publish_time__gte=f"{publish_from} 00:00:00")
    if publish_to:
        qs = qs.filter(publish_time__lt=f"{(date.fromisoformat(publish_to) + timedelta(days=1)).isoformat()} 00:00:00")
    return qs, buyer_name, publish_from, publish_to


def _notice_kind_stats(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """按公告类型统计数量；仅显式 chart_type 时附带图表。"""
    del user_data
    chart_type = resolve_chart_type(params)
    publish_from, publish_to = _resolve_period(params)
    if not publish_from and not publish_to:
        publish_from, publish_to = _resolve_period({"relative_period": "last_7_days"})

    qs = NoticeParsed.objects.all()
    if publish_from:
        qs = qs.filter(publish_time__gte=f"{publish_from} 00:00:00")
    if publish_to:
        qs = qs.filter(
            publish_time__lt=f"{(date.fromisoformat(publish_to) + timedelta(days=1)).isoformat()} 00:00:00"
        )

    rows = list(
        qs.values("notice_kind")
        .annotate(count=Count("id"))
        .order_by("-count", "notice_kind")
    )
    items = []
    categories: list[str] = []
    values: list[int] = []
    total = 0
    for row in rows:
        kind = str(row.get("notice_kind") or "").strip() or "未分类"
        count = int(row.get("count") or 0)
        total += count
        categories.append(kind)
        values.append(count)
        items.append({"label": kind, "value": f"{count} 条"})

    period_label = f"{publish_from} ~ {publish_to}" if publish_from and publish_to else "全部时间"
    content = f"{period_label} 公告按类型共 {total} 条、{len(categories)} 类。"
    data: dict[str, Any] = {
        "title": "公告类型统计",
        "publish_date_from": publish_from,
        "publish_date_to": publish_to,
        "total": total,
        "items": [
            {"label": "时间范围", "value": period_label},
            {"label": "公告总数", "value": f"{total} 条"},
            {"label": "类型数", "value": str(len(categories))},
            *items,
        ],
    }
    if chart_type:
        data["charts"] = [
            {
                "type": chart_type if chart_type in {"bar", "line", "pie"} else "bar",
                "title": "公告类型数量",
                "categories": categories,
                "series": [{"name": "数量(条)", "data": values}],
            }
        ]
    return {
        "block_type": "statistics",
        "summary": content,
        "content": content,
        "data": data,
    }


def _deal_stats(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """按采购单位 / 时间窗汇总成交金额。"""
    del user_data
    qs, buyer_name, publish_from, publish_to = _deal_filtered_qs(params)

    agg = qs.aggregate(
        notice_count=Count("id"),
        deal_amount_sum=Sum("deal_amount"),
        budget_amount_sum=Sum("budget_amount"),
    )
    notice_count = int(agg.get("notice_count") or 0)
    deal_sum = _money(agg.get("deal_amount_sum"))
    budget_sum = _money(agg.get("budget_amount_sum"))
    scope = buyer_name or "全部采购单位"
    period_label = publish_from and publish_to and f"{publish_from} ~ {publish_to}" or "全部时间"
    content = (
        f"「{scope}」在 {period_label} 共 {notice_count} 条成交/中标公告，"
        f"成交金额合计 {deal_sum} 元（预算合计 {budget_sum} 元）。"
    )
    return {
        "block_type": "statistics",
        "summary": content,
        "content": content,
        "data": {
            "title": "成交金额统计",
            "buyer_name": buyer_name,
            "publish_date_from": publish_from,
            "publish_date_to": publish_to,
            "notice_count": notice_count,
            "deal_amount_sum": deal_sum,
            "budget_amount_sum": budget_sum,
            "items": [
                {"label": "采购单位", "value": scope},
                {"label": "时间范围", "value": period_label},
                {"label": "公告条数", "value": str(notice_count)},
                {"label": "成交金额合计", "value": f"{deal_sum} 元"},
                {"label": "预算合计", "value": f"{budget_sum} 元"},
            ],
        },
    }


def _deal_suppliers(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """按采购单位 / 时间窗列出成交供应商。"""
    del user_data
    qs, buyer_name, publish_from, publish_to = _deal_filtered_qs(params)
    rows = list(
        qs.exclude(deal_supplier__isnull=True)
        .exclude(deal_supplier="")
        .values("deal_supplier")
        .annotate(notice_count=Count("id"), deal_amount_sum=Sum("deal_amount"))
        .order_by("-deal_amount_sum", "-notice_count")[:50]
    )
    items = [
        {
            "name": row["deal_supplier"],
            "notice_count": int(row["notice_count"] or 0),
            "deal_amount_sum": _money(row["deal_amount_sum"]),
            "summary": (
                f"公告 {int(row['notice_count'] or 0)} 条 · 成交额 {_money(row['deal_amount_sum'])} 元"
            ),
        }
        for row in rows
    ]
    scope = buyer_name or "全部采购单位"
    period_label = publish_from and publish_to and f"{publish_from} ~ {publish_to}" or "全部时间"
    content = f"「{scope}」在 {period_label} 共采购/成交 {len(items)} 家供应商。"
    return {
        "block_type": "erp_record_list",
        "summary": content,
        "content": content,
        "data": {
            "collection": "dealSuppliers",
            "items": items,
            "total": len(items),
            "buyer_name": buyer_name,
            "publish_date_from": publish_from,
            "publish_date_to": publish_to,
        },
    }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="notice.search",
            description="搜索采购公告。有项目编号（如 SDGP…）时必须传 project_code，做精确匹配，禁止空搜扫全库。",
            input_schema={
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "关键词；若已有项目编号可与 project_code 相同"},
                    "project_code": {
                        "type": "string",
                        "description": "政府采购项目编号，如 SDGP371400000202601002301_A；精确查询必填",
                    },
                    "buyer_name": {"type": "string", "description": "采购单位"},
                    "site_id": {"type": "string"},
                    "notice_kind": {"type": "string"},
                    "publish_date_from": {"type": "string"},
                    "publish_date_to": {"type": "string"},
                    "relative_period": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_notice_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="notice.get_detail",
            description="按 ID 查看公告详情",
            input_schema={
                "type": "object",
                "properties": {"notice_id": {"type": "integer"}},
                "required": ["notice_id"],
            },
            permission="notice.view",
            risk_level="read",
            handler=_notice_get_detail,
        )
    )
    register_tool(
        ToolDefinition(
            name="goods.search",
            description="搜索公告商品明细",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "site_id": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_goods_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="deal.search",
            description="搜索成交公告及成交信息",
            input_schema={
                "type": "object",
                "properties": {
                    "search": {"type": "string"},
                    "buyer_name": {"type": "string"},
                    "site_id": {"type": "string"},
                    "publish_date_from": {"type": "string"},
                    "publish_date_to": {"type": "string"},
                    "relative_period": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_deal_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="notice.stats",
            description="按公告类型统计数量（近7天/本月等；默认仅数字，要图表才传 chart_type）",
            input_schema={
                "type": "object",
                "properties": {
                    "relative_period": {"type": "string"},
                    "publish_date_from": {"type": "string"},
                    "publish_date_to": {"type": "string"},
                    "chart_type": {
                        "type": "string",
                        "description": "仅用户明确要图表时传 bar|line|pie；默认不传",
                    },
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_notice_kind_stats,
        )
    )
    register_tool(
        ToolDefinition(
            name="deal.stats",
            description="统计成交金额/成交额（可按采购单位与时间窗）",
            input_schema={
                "type": "object",
                "properties": {
                    "buyer_name": {"type": "string"},
                    "publish_date_from": {"type": "string"},
                    "publish_date_to": {"type": "string"},
                    "relative_period": {"type": "string"},
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_deal_stats,
        )
    )
    register_tool(
        ToolDefinition(
            name="deal.suppliers",
            description="查询某采购单位在时间窗内成交的供应商名单",
            input_schema={
                "type": "object",
                "properties": {
                    "buyer_name": {"type": "string"},
                    "publish_date_from": {"type": "string"},
                    "publish_date_to": {"type": "string"},
                    "relative_period": {"type": "string"},
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_deal_suppliers,
        )
    )
