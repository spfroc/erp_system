"""爬虫站点管理 / 映射分类与站点选项对照 CRUD。"""

from __future__ import annotations

import json

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_site_config import (
    channel_options_for_site,
    invalidate_notice_site_cache,
    notice_type_options_for_channel,
    serialize_category,
    serialize_option,
    serialize_site,
)
from .notice_site_models import (
    NoticeCategoryOptionLink,
    NoticeCrawlSite,
    NoticeMappedCategory,
    NoticeSiteOption,
)
from .views import _require_permission


def _page(request) -> tuple[int, int]:
    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or 50)
    except ValueError:
        page_size = 50
    return page, min(max(page_size, 1), 200)


def _body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


@csrf_exempt
@require_http_methods(["GET", "POST"])
def notice_site_list(request):
    if request.method == "GET":
        _user, error = _require_permission(request, "notice.site.view")
        if error:
            return error
        page, page_size = _page(request)
        search = (request.GET.get("search") or "").strip()
        try:
            qs = NoticeCrawlSite.objects.all()
            if search:
                qs = qs.filter(Q(site_id__icontains=search) | Q(label__icontains=search))
            total = qs.count()
            start = (page - 1) * page_size
            items = [serialize_site(row) for row in qs.order_by("sort_order", "id")[start : start + page_size]]
        except DatabaseError:
            return JsonResponse({"detail": "站点表尚未创建", "items": [], "total": 0}, status=503)
        return JsonResponse({"items": items, "total": total, "page": page, "pageSize": page_size})

    _user, error = _require_permission(request, "notice.site.manage")
    if error:
        return error
    payload = _body(request)
    site_id = str(payload.get("siteId") or "").strip()[:64]
    label = str(payload.get("label") or "").strip()[:64]
    if not site_id or not label:
        return JsonResponse({"detail": "siteId / label 不能为空"}, status=400)
    try:
        sort_order = int(payload.get("sortOrder") if payload.get("sortOrder") is not None else 0)
    except (TypeError, ValueError):
        sort_order = 0
    enabled = bool(payload.get("enabled", True))
    fixed_region = str(payload.get("fixedRegion") or "").strip()[:32]
    try:
        row = NoticeCrawlSite.objects.create(
            site_id=site_id,
            label=label,
            enabled=enabled,
            sort_order=sort_order,
            fixed_region=fixed_region,
        )
    except IntegrityError:
        return JsonResponse({"detail": "站点已存在"}, status=409)
    except DatabaseError:
        return JsonResponse({"detail": "站点表尚未创建"}, status=503)
    invalidate_notice_site_cache()
    return JsonResponse({"item": serialize_site(row)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def notice_site_detail(request, site_pk: int):
    write = request.method != "GET"
    _user, error = _require_permission(
        request, "notice.site.manage" if write else "notice.site.view"
    )
    if error:
        return error
    try:
        row = NoticeCrawlSite.objects.filter(pk=site_pk).first()
    except DatabaseError:
        return JsonResponse({"detail": "站点表尚未创建"}, status=503)
    if row is None:
        return JsonResponse({"detail": "未找到"}, status=404)

    if request.method == "GET":
        return JsonResponse({"item": serialize_site(row)})

    if request.method == "DELETE":
        if row.site_id in {
            "sd-ggzyjyzx",
            "sd-gpfa-frame",
            "sd-ccgp",
            "jd-quan-yicai",
            "jd-qing-huicai",
        }:
            return JsonResponse({"detail": "内置抓取站点不可删除，可改为禁用"}, status=400)
        row.delete()
        invalidate_notice_site_cache()
        return JsonResponse({"ok": True})

    payload = _body(request)
    if "label" in payload:
        label = str(payload.get("label") or "").strip()[:64]
        if not label:
            return JsonResponse({"detail": "label 不能为空"}, status=400)
        row.label = label
    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))
    if "sortOrder" in payload:
        try:
            row.sort_order = int(payload.get("sortOrder") or 0)
        except (TypeError, ValueError):
            pass
    if "fixedRegion" in payload:
        row.fixed_region = str(payload.get("fixedRegion") or "").strip()[:32]
    row.save()
    invalidate_notice_site_cache()
    return JsonResponse({"item": serialize_site(row)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def notice_mapped_category_list(request):
    if request.method == "GET":
        _user, error = _require_permission(request, "notice.categoryMap.view")
        if error:
            return error
        page, page_size = _page(request)
        search = (request.GET.get("search") or "").strip()
        try:
            qs = NoticeMappedCategory.objects.annotate(option_count=Count("option_links"))
            if search:
                qs = qs.filter(name__icontains=search)
            total = qs.count()
            start = (page - 1) * page_size
            items = [
                serialize_category(row, option_count=row.option_count)
                for row in qs.order_by("sort_order", "id")[start : start + page_size]
            ]
        except DatabaseError:
            return JsonResponse({"detail": "映射分类表尚未创建", "items": [], "total": 0}, status=503)
        return JsonResponse({"items": items, "total": total, "page": page, "pageSize": page_size})

    _user, error = _require_permission(request, "notice.categoryMap.manage")
    if error:
        return error
    payload = _body(request)
    name = str(payload.get("name") or "").strip()[:64]
    if not name:
        return JsonResponse({"detail": "name 不能为空"}, status=400)
    try:
        sort_order = int(payload.get("sortOrder") if payload.get("sortOrder") is not None else 0)
    except (TypeError, ValueError):
        sort_order = 0
    enabled = bool(payload.get("enabled", True))
    try:
        row = NoticeMappedCategory.objects.create(name=name, enabled=enabled, sort_order=sort_order)
    except IntegrityError:
        return JsonResponse({"detail": "分类名称已存在"}, status=409)
    except DatabaseError:
        return JsonResponse({"detail": "映射分类表尚未创建"}, status=503)
    invalidate_notice_site_cache()
    return JsonResponse({"item": serialize_category(row, option_count=0)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def notice_mapped_category_detail(request, category_pk: int):
    write = request.method != "GET"
    _user, error = _require_permission(
        request, "notice.categoryMap.manage" if write else "notice.categoryMap.view"
    )
    if error:
        return error
    try:
        row = (
            NoticeMappedCategory.objects.filter(pk=category_pk)
            .annotate(option_count=Count("option_links"))
            .first()
        )
    except DatabaseError:
        return JsonResponse({"detail": "映射分类表尚未创建"}, status=503)
    if row is None:
        return JsonResponse({"detail": "未找到"}, status=404)

    if request.method == "GET":
        return JsonResponse({"item": serialize_category(row, option_count=row.option_count)})

    if request.method == "DELETE":
        row.delete()
        invalidate_notice_site_cache()
        return JsonResponse({"ok": True})

    payload = _body(request)
    if "name" in payload:
        name = str(payload.get("name") or "").strip()[:64]
        if not name:
            return JsonResponse({"detail": "name 不能为空"}, status=400)
        row.name = name
    if "enabled" in payload:
        row.enabled = bool(payload.get("enabled"))
    if "sortOrder" in payload:
        try:
            row.sort_order = int(payload.get("sortOrder") or 0)
        except (TypeError, ValueError):
            pass
    try:
        row.save()
    except IntegrityError:
        return JsonResponse({"detail": "分类名称已存在"}, status=409)
    invalidate_notice_site_cache()
    row = (
        NoticeMappedCategory.objects.filter(pk=category_pk)
        .annotate(option_count=Count("option_links"))
        .first()
    )
    return JsonResponse({"item": serialize_category(row, option_count=row.option_count)})


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def notice_mapped_category_options(request, category_pk: int):
    write = request.method == "PUT"
    _user, error = _require_permission(
        request, "notice.categoryMap.manage" if write else "notice.categoryMap.view"
    )
    if error:
        return error
    try:
        category = NoticeMappedCategory.objects.filter(pk=category_pk).first()
    except DatabaseError:
        return JsonResponse({"detail": "映射分类表尚未创建"}, status=503)
    if category is None:
        return JsonResponse({"detail": "未找到"}, status=404)

    if request.method == "GET":
        option_ids = list(
            NoticeCategoryOptionLink.objects.filter(category_id=category_pk).values_list(
                "option_id", flat=True
            )
        )
        return JsonResponse({"categoryId": category_pk, "optionIds": option_ids})

    payload = _body(request)
    raw_ids = payload.get("optionIds")
    if not isinstance(raw_ids, list):
        return JsonResponse({"detail": "optionIds 必须是数组"}, status=400)
    option_ids: list[int] = []
    seen: set[int] = set()
    for value in raw_ids:
        try:
            oid = int(value)
        except (TypeError, ValueError):
            continue
        if oid in seen:
            continue
        seen.add(oid)
        option_ids.append(oid)
    try:
        with transaction.atomic():
            valid_ids = set(
                NoticeSiteOption.objects.filter(id__in=option_ids).values_list("id", flat=True)
            )
            NoticeCategoryOptionLink.objects.filter(category_id=category_pk).exclude(
                option_id__in=valid_ids
            ).delete()
            existing = set(
                NoticeCategoryOptionLink.objects.filter(category_id=category_pk).values_list(
                    "option_id", flat=True
                )
            )
            to_create = [
                NoticeCategoryOptionLink(category_id=category_pk, option_id=oid)
                for oid in option_ids
                if oid in valid_ids and oid not in existing
            ]
            if to_create:
                NoticeCategoryOptionLink.objects.bulk_create(to_create, ignore_conflicts=True)
    except DatabaseError:
        return JsonResponse({"detail": "保存对照失败"}, status=503)
    invalidate_notice_site_cache()
    saved_ids = list(
        NoticeCategoryOptionLink.objects.filter(category_id=category_pk).values_list(
            "option_id", flat=True
        )
    )
    return JsonResponse({"categoryId": category_pk, "optionIds": saved_ids})


@csrf_exempt
@require_http_methods(["GET"])
def notice_site_option_list(request):
    _user, error = _require_permission(request, "notice.categoryMap.view")
    if error:
        return error
    site_id = (request.GET.get("siteId") or "").strip()
    search = (request.GET.get("search") or "").strip()
    page, page_size = _page(request)
    try:
        qs = NoticeSiteOption.objects.all()
        if site_id:
            qs = qs.filter(site_id=site_id)
        if search:
            qs = qs.filter(
                Q(channel_label__icontains=search)
                | Q(notice_type_label__icontains=search)
                | Q(notice_type__icontains=search)
                | Q(channel_key__icontains=search)
            )
        total = qs.count()
        start = (page - 1) * page_size
        items = [
            serialize_option(row)
            for row in qs.order_by("site_id", "sort_order", "id")[start : start + page_size]
        ]
    except DatabaseError:
        return JsonResponse({"detail": "站点选项表尚未创建", "items": [], "total": 0}, status=503)
    return JsonResponse({"items": items, "total": total, "page": page, "pageSize": page_size})


@csrf_exempt
@require_http_methods(["GET"])
def notice_site_meta(request):
    """下拉元数据：站点 + 映射分类 + 站点选项。"""
    _user, error = _require_permission(request, "notice.categoryMap.view")
    if error:
        _user, error = _require_permission(request, "notice.view")
        if error:
            return error
    site_id = (request.GET.get("siteId") or "").strip()
    channel_key = (request.GET.get("channelKey") or "").strip()
    category_id = request.GET.get("categoryId")
    try:
        sites = [serialize_site(row) for row in NoticeCrawlSite.objects.filter(enabled=True)]
        categories = [
            serialize_category(row, option_count=row.option_count)
            for row in NoticeMappedCategory.objects.filter(enabled=True).annotate(
                option_count=Count("option_links")
            )
        ]
        options_qs = NoticeSiteOption.objects.filter(enabled=True)
        if site_id:
            options_qs = options_qs.filter(site_id=site_id)
        options = [serialize_option(row) for row in options_qs.order_by("site_id", "sort_order", "id")]
        selected_option_ids: list[int] = []
        if category_id not in (None, ""):
            try:
                cid = int(category_id)
                selected_option_ids = list(
                    NoticeCategoryOptionLink.objects.filter(category_id=cid).values_list(
                        "option_id", flat=True
                    )
                )
            except (TypeError, ValueError):
                selected_option_ids = []
    except DatabaseError:
        from .notice_site_config import DEFAULT_SITES

        sites = [
            {
                "id": 0,
                "siteId": item["siteId"],
                "label": item["label"],
                "enabled": True,
                "sortOrder": item["sortOrder"],
                "fixedRegion": item.get("fixedRegion") or "",
                "updatedAt": "",
            }
            for item in DEFAULT_SITES
        ]
        categories = []
        options = []
        selected_option_ids = []
    return JsonResponse(
        {
            "sites": sites,
            "categories": categories,
            "options": options,
            "selectedOptionIds": selected_option_ids,
            "channelOptions": channel_options_for_site(site_id) if site_id else [],
            "noticeTypeOptions": (
                notice_type_options_for_channel(site_id, channel_key) if site_id else []
            ),
        }
    )


# 兼容旧前端路径：重定向语义到映射分类列表
@csrf_exempt
@require_http_methods(["GET", "POST"])
def notice_category_map_list(request):
    return notice_mapped_category_list(request)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def notice_category_map_detail(request, map_pk: int):
    return notice_mapped_category_detail(request, map_pk)
