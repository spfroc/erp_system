"""公告查询服务：复用 notice_views 已有逻辑，禁止在助手内复制 SQL。"""

from __future__ import annotations

from typing import Any

from django.db import ProgrammingError

from apps.data_store.notice_models import NoticeGoods, NoticeParsed, NoticeRaw
from apps.data_store.notice_views import (
    _serialize_detail,
    query_crawled_notices,
)


def search_notices(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    site_id: str = "",
    notice_kind: str = "",
    publish_date_from: str = "",
    publish_date_to: str = "",
    buyer_name: str = "",
    project_code: str = "",
    site_ids: list[str] | None = None,
) -> dict[str, Any]:
    """搜索公告列表（真实 ORM 查询）。"""
    try:
        return query_crawled_notices(
            page=page,
            page_size=page_size,
            search=search,
            site_id=site_id,
            notice_kind=notice_kind,
            site_ids=site_ids,
            publish_date_from=publish_date_from,
            publish_date_to=publish_date_to,
            buyer_name=buyer_name,
            project_code=project_code,
        )
    except ProgrammingError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "detail": "公告表尚未创建"}


def get_notice_detail(notice_id: int) -> dict[str, Any] | None:
    """公告详情；不存在返回 None。"""
    try:
        raw = NoticeRaw.objects.filter(id=notice_id).first()
        if not raw:
            return None
        parsed = NoticeParsed.objects.filter(notice_raw_id=raw.id).first()
        goods = list(NoticeGoods.objects.filter(notice_raw_id=raw.id).order_by("line_no", "id"))
        return _serialize_detail(raw, parsed, goods)
    except ProgrammingError:
        return None


def search_notice_goods(
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    site_id: str = "",
) -> dict[str, Any]:
    """按商品名/品牌/型号搜索公告明细行。"""
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    try:
        qs = NoticeGoods.objects.all().order_by("-id")
        if site_id:
            qs = qs.filter(site_id=site_id)
        keyword = (keyword or "").strip()
        if keyword:
            from django.db.models import Q

            qs = qs.filter(
                Q(product_name__icontains=keyword)
                | Q(brand__icontains=keyword)
                | Q(product_model__icontains=keyword)
                | Q(category__icontains=keyword)
                | Q(spec__icontains=keyword)
            )
        total = qs.count()
        rows = list(qs[(page - 1) * page_size : page * page_size])
        items = [
            {
                "id": row.id,
                "noticeRawId": row.notice_raw_id,
                "siteId": row.site_id,
                "noticeKey": row.notice_key,
                "lineNo": row.line_no,
                "productName": row.product_name or "",
                "category": row.category or "",
                "brand": row.brand or "",
                "model": row.product_model or "",
                "quantity": str(row.quantity) if row.quantity is not None else "",
                "unit": row.unit or "",
                "unitPrice": str(row.unit_price) if row.unit_price is not None else "",
                "amount": str(row.amount) if row.amount is not None else "",
                "spec": row.spec or "",
            }
            for row in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    except ProgrammingError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "detail": "公告商品表尚未创建"}
