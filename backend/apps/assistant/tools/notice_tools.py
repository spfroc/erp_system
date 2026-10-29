from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.assistant.services.notice_query import get_notice_detail, search_notice_goods, search_notices
from apps.assistant.services.tool_registry import ToolDefinition, register_tool


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
    noise = ("昨天", "昨日", "今天", "今日", "前天", "发布的", "发布", "公告", "查询", "查找", "搜索", "最近", "采购")
    for word in noise:
        text = text.replace(word, " ")
    if buyer_name:
        text = text.replace(buyer_name, " ")
    return " ".join(text.split()).strip(" ，,。的")


def _notice_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    publish_from, publish_to = _resolve_period(params)
    buyer_name = str(params.get("buyer_name") or params.get("buyerName") or "").strip()
    search = _clean_search(str(params.get("search") or params.get("keyword") or ""), buyer_name)
    result = search_notices(
        page=int(params.get("page") or 1),
        page_size=int(params.get("page_size") or params.get("pageSize") or 20),
        search=search,
        site_id=str(params.get("site_id") or params.get("siteId") or "").strip(),
        notice_kind=str(params.get("notice_kind") or params.get("noticeKind") or "").strip(),
        publish_date_from=publish_from,
        publish_date_to=publish_to,
        buyer_name=buyer_name,
    )
    total = int(result.get("total") or 0)
    return {
        "block_type": "notice_list",
        "summary": f"找到 {total} 条公告。",
        "content": f"找到 {total} 条公告。",
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
        "block_type": "notice_list",
        "summary": f"已打开公告：{title}",
        "content": f"已打开公告：{title}",
        "data": {"item": detail, "total": 1, "page": 1, "page_size": 1},
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


def register() -> None:
    register_tool(
        ToolDefinition(
            name="notice.search",
            description="搜索采购公告（关键词、采购单位、站点、类型、发布日期）",
            input_schema={
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "关键词"},
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
