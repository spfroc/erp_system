"""站点 / 映射分类：脚本目录数据、缓存查询、解析展示分类。"""

from __future__ import annotations

import threading
import time
from typing import Any

from django.db import DatabaseError, transaction
from django.db.models import Count, Q

# 与 notice_views.SITE_LABELS / NOTICE_TYPE_LABELS / 爬虫 CATEGORIES 对齐的默认值
DEFAULT_SITES: list[dict[str, Any]] = [
    {"siteId": "sd-ggzyjyzx", "label": "山东网上商城", "sortOrder": 10, "fixedRegion": ""},
    {"siteId": "sd-gpfa-frame", "label": "框架协议", "sortOrder": 20, "fixedRegion": ""},
    {"siteId": "sd-ccgp", "label": "山东政府采购网", "sortOrder": 30, "fixedRegion": ""},
    {"siteId": "jd-quan-yicai", "label": "京东泉易采", "sortOrder": 40, "fixedRegion": "济南"},
    {"siteId": "jd-qing-huicai", "label": "京东青慧采", "sortOrder": 50, "fixedRegion": "青岛"},
]

# site_id → [(channel_key, channel_label, notice_type, notice_type_label, default_category)]
DEFAULT_CHANNEL_MAPPINGS: dict[str, list[tuple[str, str, str, str, str]]] = {
    "sd-ggzyjyzx": [
        ("21", "标准品目竞价", "0", "采购公告", "采购公告"),
        ("21", "标准品目竞价", "1", "成交公告", "成交公告"),
        ("21", "标准品目竞价", "10", "终止公告", "终止公告"),
        ("1", "标准品目反拍", "0", "采购公告", "采购公告"),
        ("1", "标准品目反拍", "1", "成交公告", "成交公告"),
        ("1", "标准品目反拍", "10", "终止公告", "终止公告"),
        ("5", "标准品目直购", "1", "成交公告", "成交公告"),
        ("5", "标准品目直购", "10", "终止公告", "终止公告"),
        ("3", "定制品目竞价", "0", "采购公告", "采购公告"),
        ("3", "定制品目竞价", "1", "成交公告", "成交公告"),
        ("3", "定制品目竞价", "5", "终止公告", "终止公告"),
        ("12", "定制品目议价", "0", "采购公告", "采购公告"),
        ("12", "定制品目议价", "1", "成交公告", "成交公告"),
        ("12", "定制品目议价", "5", "终止公告", "终止公告"),
        ("10", "标准品目批量采购", "1", "成交公告", "成交公告"),
        ("10", "标准品目批量采购", "5", "终止公告", "终止公告"),
    ],
    "sd-gpfa-frame": [
        ("17", "二次竞价", "0", "采购公告", "采购公告"),
        ("17", "二次竞价", "1", "成交公告", "成交公告"),
        ("17", "二次竞价", "10", "终止公告", "终止公告"),
        ("35", "二次竞价", "0", "采购公告", "采购公告"),
        ("35", "二次竞价", "1", "成交公告", "成交公告"),
        ("35", "二次竞价", "10", "终止公告", "终止公告"),
        ("31", "直接选定", "0", "采购公告", "采购公告"),
        ("31", "直接选定", "1", "成交公告", "成交公告"),
        ("31", "直接选定", "10", "终止公告", "终止公告"),
        ("32", "直接选定", "0", "采购公告", "采购公告"),
        ("32", "直接选定", "1", "成交公告", "成交公告"),
        ("32", "直接选定", "10", "终止公告", "终止公告"),
        ("33", "顺序轮候", "0", "采购公告", "采购公告"),
        ("33", "顺序轮候", "1", "成交公告", "成交公告"),
        ("33", "顺序轮候", "10", "终止公告", "终止公告"),
    ],
    "sd-ccgp": [
        ("", "政府采购栏目", "2500", "意向公开", "意向公开"),
        ("", "政府采购栏目", "0301", "采购公告", "采购公告"),
        ("", "政府采购栏目", "0305", "更正公告", "更正公告"),
        ("", "政府采购栏目", "0302", "结果公告", "结果公告"),
        ("", "政府采购栏目", "0306", "终止公告", "终止公告"),
        ("", "政府采购栏目", "2502", "合同公告", "合同公告"),
        ("", "政府采购栏目", "2503", "验收公告", "验收公告"),
        ("", "政府采购栏目", "2102", "单一来源公示", "单一来源公示"),
    ],
    "jd-quan-yicai": [
        ("1", "普通竞价", "1", "竞价公告", "竞价公告"),
        ("1", "普通竞价", "2", "成交公告", "成交公告"),
        ("1", "普通竞价", "3", "终止公告", "终止公告"),
        ("1", "普通竞价", "4", "失败公告", "失败公告"),
        ("1", "普通竞价", "6", "废标公告", "废标公告"),
        ("2", "反拍竞价", "1", "竞价公告", "竞价公告"),
        ("2", "反拍竞价", "2", "成交公告", "成交公告"),
        ("2", "反拍竞价", "3", "终止公告", "终止公告"),
        ("2", "反拍竞价", "4", "失败公告", "失败公告"),
        ("2", "反拍竞价", "6", "废标公告", "废标公告"),
        ("3", "询比", "5", "询比公告", "询比公告"),
        ("3", "询比", "2", "成交公告", "成交公告"),
        ("3", "询比", "3", "终止公告", "终止公告"),
        ("3", "询比", "4", "失败公告", "失败公告"),
        ("3", "询比", "6", "废标公告", "废标公告"),
    ],
    "jd-qing-huicai": [],
}

DEFAULT_CHANNEL_MAPPINGS["jd-qing-huicai"] = list(DEFAULT_CHANNEL_MAPPINGS["jd-quan-yicai"])

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"ts": 0.0, "sites": None, "categories": None, "options": None, "links": None}
_CACHE_TTL = 30.0


def invalidate_notice_site_cache() -> None:
    with _cache_lock:
        _cache["ts"] = 0.0
        _cache["sites"] = None
        _cache["categories"] = None
        _cache["options"] = None
        _cache["links"] = None


def serialize_site(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "siteId": row.site_id,
        "label": row.label,
        "enabled": bool(row.enabled),
        "sortOrder": int(row.sort_order or 0),
        "fixedRegion": row.fixed_region or "",
        "updatedAt": row.updated_at.isoformat(sep=" ", timespec="seconds") if row.updated_at else "",
    }


def serialize_category(row, *, option_count: int | None = None) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "name": row.name,
        "enabled": bool(row.enabled),
        "sortOrder": int(row.sort_order or 0),
        "updatedAt": row.updated_at.isoformat(sep=" ", timespec="seconds") if row.updated_at else "",
    }
    if option_count is not None:
        payload["optionCount"] = int(option_count)
    return payload


def serialize_option(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "siteId": row.site_id,
        "channelKey": row.channel_key or "",
        "channelLabel": row.channel_label or "",
        "noticeType": row.notice_type,
        "noticeTypeLabel": row.notice_type_label or "",
        "enabled": bool(row.enabled),
        "sortOrder": int(row.sort_order or 0),
        "updatedAt": row.updated_at.isoformat(sep=" ", timespec="seconds") if row.updated_at else "",
    }


def channel_options_for_site(site_id: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for channel_key, channel_label, *_rest in DEFAULT_CHANNEL_MAPPINGS.get(site_id, []):
        key = channel_key or ""
        if key in seen:
            continue
        seen.add(key)
        out.append({"key": key, "label": channel_label or (key or "默认")})
    return out


def notice_type_options_for_channel(site_id: str, channel_key: str) -> list[dict[str, str]]:
    key = (channel_key or "").strip()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for ch_key, _ch_label, notice_type, notice_type_label, _cat in DEFAULT_CHANNEL_MAPPINGS.get(
        site_id, []
    ):
        if (ch_key or "") != key:
            continue
        if notice_type in seen:
            continue
        seen.add(notice_type)
        out.append({"key": notice_type, "label": notice_type_label or notice_type})
    return out


def seed_notice_sites_and_options(*, clear_mappings: bool = False) -> dict[str, int]:
    """脚本填充：只写站点 + 站点选项；不写映射分类/对照（由人工在页面配置）。"""
    from .notice_site_models import (
        NoticeCategoryOptionLink,
        NoticeCrawlSite,
        NoticeMappedCategory,
        NoticeSiteOption,
    )

    created_sites = 0
    updated_sites = 0
    created_options = 0
    cleared_links = 0
    cleared_categories = 0

    with transaction.atomic():
        if clear_mappings:
            cleared_links = NoticeCategoryOptionLink.objects.all().delete()[0]
            cleared_categories = NoticeMappedCategory.objects.all().delete()[0]

        for item in DEFAULT_SITES:
            _obj, created = NoticeCrawlSite.objects.update_or_create(
                site_id=item["siteId"],
                defaults={
                    "label": item["label"],
                    "sort_order": item["sortOrder"],
                    "fixed_region": item.get("fixedRegion") or "",
                    "enabled": True,
                },
            )
            if created:
                created_sites += 1
            else:
                updated_sites += 1

        for site_id, rows in DEFAULT_CHANNEL_MAPPINGS.items():
            for idx, (channel_key, channel_label, notice_type, notice_type_label, _category) in enumerate(
                rows
            ):
                _obj, created = NoticeSiteOption.objects.get_or_create(
                    site_id=site_id,
                    channel_key=channel_key or "",
                    notice_type=str(notice_type),
                    defaults={
                        "channel_label": channel_label or "",
                        "notice_type_label": notice_type_label or "",
                        "enabled": True,
                        "sort_order": (idx + 1) * 10,
                    },
                )
                if created:
                    created_options += 1

    invalidate_notice_site_cache()
    return {
        "createdSites": created_sites,
        "updatedSites": updated_sites,
        "createdOptions": created_options,
        "clearedLinks": cleared_links,
        "clearedCategories": cleared_categories,
    }


def _load_cache() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    now = time.monotonic()
    with _cache_lock:
        if _cache["sites"] is not None and now - float(_cache["ts"]) < _CACHE_TTL:
            return _cache["sites"], _cache["categories"], _cache["options"], _cache["links"]

    from .notice_site_models import (
        NoticeCategoryOptionLink,
        NoticeCrawlSite,
        NoticeMappedCategory,
        NoticeSiteOption,
    )

    try:
        sites = [serialize_site(row) for row in NoticeCrawlSite.objects.all()]
        categories = [
            serialize_category(row, option_count=getattr(row, "option_count", 0))
            for row in NoticeMappedCategory.objects.annotate(option_count=Count("option_links"))
        ]
        options = [serialize_option(row) for row in NoticeSiteOption.objects.all()]
        links = [
            {"categoryId": row.category_id, "optionId": row.option_id}
            for row in NoticeCategoryOptionLink.objects.all()
        ]
    except DatabaseError:
        sites, categories, options, links = [], [], [], []

    with _cache_lock:
        _cache["ts"] = time.monotonic()
        _cache["sites"] = sites
        _cache["categories"] = categories
        _cache["options"] = options
        _cache["links"] = links
    return sites, categories, options, links


def list_enabled_sites() -> list[dict[str, Any]]:
    sites, *_rest = _load_cache()
    return [item for item in sites if item.get("enabled")]


def site_label(site_id: str | None) -> str:
    sid = (site_id or "").strip()
    for item in list_enabled_sites():
        if item["siteId"] == sid:
            return item["label"]
    for item in DEFAULT_SITES:
        if item["siteId"] == sid:
            return item["label"]
    return sid


def list_enabled_categories() -> list[dict[str, Any]]:
    _sites, categories, _options, _links = _load_cache()
    return [item for item in categories if item.get("enabled")]


def list_enabled_options(site_id: str = "") -> list[dict[str, Any]]:
    _sites, _categories, options, _links = _load_cache()
    sid = (site_id or "").strip()
    out = []
    for item in options:
        if not item.get("enabled"):
            continue
        if sid and item.get("siteId") != sid:
            continue
        out.append(item)
    return out


def list_enabled_links() -> list[dict[str, Any]]:
    _sites, categories, options, links = _load_cache()
    enabled_cats = {item["id"] for item in categories if item.get("enabled")}
    enabled_opts = {item["id"] for item in options if item.get("enabled")}
    return [
        item
        for item in links
        if item.get("categoryId") in enabled_cats and item.get("optionId") in enabled_opts
    ]


def mapped_category_options(site_id: str = "") -> list[str]:
    """公告列表「全部类型」筛选项：启用的映射分类。

    有站点时优先只返回该站已对照的分类；该站尚无对照则回退为全部启用分类。
    没有任何映射分类时返回空列表，由调用方决定回退策略。
    """
    sid = (site_id or "").strip()
    categories = list_enabled_categories()
    if not categories:
        return []

    if sid:
        option_by_id = {item["id"]: item for item in list_enabled_options(sid)}
        linked_cat_ids = {
            int(link["categoryId"])
            for link in list_enabled_links()
            if link.get("optionId") in option_by_id
        }
        linked = [
            item
            for item in categories
            if int(item["id"]) in linked_cat_ids and str(item.get("name") or "").strip()
        ]
        if linked:
            categories = linked

    labels: list[str] = []
    seen: set[str] = set()
    for item in sorted(categories, key=lambda x: (x.get("sortOrder") or 0, x.get("id") or 0)):
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        labels.append(name)
    return labels


def resolve_mapped_category(
    site_id: str | None,
    auction_type: Any = None,
    notice_type: Any = None,
) -> str:
    """按站点+种类+方式找到选项，再取对照的映射分类（排序最前）。"""
    sid = (site_id or "").strip()
    nt = str(notice_type).strip() if notice_type not in (None, "") else ""
    ch = str(auction_type).strip() if auction_type not in (None, "") else ""
    if not sid or not nt:
        return ""

    options = list_enabled_options(sid)
    matched: list[dict[str, Any]] = []
    for item in options:
        if item.get("noticeType") != nt:
            continue
        item_ch = str(item.get("channelKey") or "")
        if item_ch == ch:
            matched.append(item)
    if not matched:
        for item in options:
            if item.get("noticeType") != nt:
                continue
            if not str(item.get("channelKey") or ""):
                matched.append(item)
    if not matched:
        same_type = [item for item in options if item.get("noticeType") == nt]
        if len(same_type) == 1:
            matched = same_type
    if not matched:
        return ""

    option_ids = {int(item["id"]) for item in matched}
    _sites, categories, _options, _links = _load_cache()
    cat_by_id = {item["id"]: item for item in categories if item.get("enabled")}
    hit_cats: list[dict[str, Any]] = []
    for link in list_enabled_links():
        if int(link["optionId"]) not in option_ids:
            continue
        cat = cat_by_id.get(link["categoryId"])
        if cat:
            hit_cats.append(cat)
    if not hit_cats:
        return ""
    hit_cats.sort(key=lambda x: (x.get("sortOrder") or 0, x.get("id") or 0))
    return str(hit_cats[0].get("name") or "").strip()


def q_for_mapped_category(category: str, site_id: str = "") -> Q:
    """筛选：命中对照到该映射分类的站点选项。"""
    cat_name = (category or "").strip()
    if not cat_name:
        return Q(pk__in=[])
    _sites, categories, options, _links = _load_cache()
    cat = next((item for item in categories if item.get("enabled") and item.get("name") == cat_name), None)
    if not cat:
        return Q(pk__in=[])
    option_by_id = {item["id"]: item for item in options if item.get("enabled")}
    q = Q()
    matched = False
    sid_filter = (site_id or "").strip()
    for link in list_enabled_links():
        if int(link["categoryId"]) != int(cat["id"]):
            continue
        opt = option_by_id.get(link["optionId"])
        if not opt:
            continue
        if sid_filter and opt.get("siteId") != sid_filter:
            continue
        sid = opt["siteId"]
        nt = opt["noticeType"]
        ch = str(opt.get("channelKey") or "")
        if ch:
            q |= Q(site_id=sid, notice_type=nt, auction_type=ch)
            q |= Q(site_id=sid, notice_type=nt, auction_type__in=["", None])
        else:
            q |= Q(site_id=sid, notice_type=nt)
        matched = True
    return q if matched else Q(pk__in=[])
