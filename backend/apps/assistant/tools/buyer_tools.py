from __future__ import annotations

from typing import Any

from django.db import ProgrammingError
from django.db.models import Count, Q, Sum

from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.notice_models import NoticeParsed
from apps.data_store.notice_tag_models import NoticeBuyerProfile


BUYER_PUBLIC_FIELDS = (
    "id",
    "buyer_name",
    "org_type",
    "nature",
    "province",
    "city",
    "district",
    "source",
    "confidence",
)


def _buyer_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    try:
        qs = NoticeBuyerProfile.objects.all().order_by("-updated_at", "-id")
        if keyword:
            qs = qs.filter(Q(buyer_name__icontains=keyword) | Q(name_key__icontains=keyword) | Q(province__icontains=keyword) | Q(city__icontains=keyword))
        total = qs.count()
        rows = list(qs[(page - 1) * page_size : page * page_size])
        items = [{field: getattr(row, field) for field in BUYER_PUBLIC_FIELDS} for row in rows]
        # 无画像时回退到解析表采购人去重
        if total == 0 and keyword:
            parsed_qs = (
                NoticeParsed.objects.exclude(buyer_name__isnull=True)
                .exclude(buyer_name="")
                .filter(buyer_name__icontains=keyword)
                .values("buyer_name")
                .annotate(notice_count=Count("id"), deal_amount=Sum("deal_amount"))
                .order_by("-notice_count")
            )
            total = parsed_qs.count()
            page_rows = list(parsed_qs[(page - 1) * page_size : page * page_size])
            items = [
                {
                    "buyer_name": row["buyer_name"],
                    "notice_count": row["notice_count"],
                    "deal_amount": str(row["deal_amount"] or 0),
                    "source": "parsed",
                }
                for row in page_rows
            ]
        return {
            "block_type": "buyer_profile",
            "summary": f"找到 {total} 个采购人。",
            "content": f"找到 {total} 个采购人。",
            "data": {"items": items, "total": total, "page": page, "page_size": page_size},
        }
    except ProgrammingError:
        return {
            "block_type": "error",
            "summary": "采购人表尚未就绪",
            "content": "采购人表尚未就绪。",
            "data": {"items": [], "total": 0, "page": page, "page_size": page_size},
        }


def _buyer_get_profile(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    buyer_name = str(params.get("buyer_name") or params.get("name") or "").strip()
    if not buyer_name:
        return {
            "block_type": "clarification",
            "summary": "请提供采购人名称",
            "content": "请提供采购人名称。",
            "data": {},
        }
    try:
        profile = NoticeBuyerProfile.objects.filter(buyer_name=buyer_name).first()
        history = list(
            NoticeParsed.objects.filter(buyer_name__icontains=buyer_name)
            .order_by("-publish_time", "-id")
            .values(
                "notice_raw_id",
                "notice_title",
                "project_name",
                "notice_kind",
                "budget_amount",
                "deal_amount",
                "publish_time",
                "region_name",
            )[:30]
        )
        for row in history:
            if row.get("publish_time"):
                row["publish_time"] = row["publish_time"].isoformat(sep=" ", timespec="seconds")
            for money_key in ("budget_amount", "deal_amount"):
                if row.get(money_key) is not None:
                    row[money_key] = str(row[money_key])
        profile_data = (
            {field: getattr(profile, field) for field in BUYER_PUBLIC_FIELDS}
            if profile
            else {"buyer_name": buyer_name, "source": "parsed"}
        )
        return {
            "block_type": "buyer_profile",
            "summary": f"采购人「{buyer_name}」共 {len(history)} 条近期公告。",
            "content": f"采购人「{buyer_name}」共 {len(history)} 条近期公告。",
            "data": {"profile": profile_data, "notices": history, "total": len(history)},
        }
    except ProgrammingError:
        return {
            "block_type": "error",
            "summary": "采购人查询失败",
            "content": "相关表尚未创建。",
            "data": {},
        }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="buyer.search",
            description="搜索采购人/采购单位",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="notice.view",
            risk_level="read",
            handler=_buyer_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="buyer.get_profile",
            description="查看采购人画像及历史公告",
            input_schema={
                "type": "object",
                "properties": {"buyer_name": {"type": "string"}},
                "required": ["buyer_name"],
            },
            permission="notice.view",
            risk_level="read",
            handler=_buyer_get_profile,
        )
    )
