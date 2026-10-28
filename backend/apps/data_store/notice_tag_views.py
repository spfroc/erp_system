from __future__ import annotations

import json

from django.db import DatabaseError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_models import NoticeParsed
from .notice_tag_models import NoticeProductTag, NoticeResultTag
from .notice_dict import KIND_NATURE, KIND_ORG_TYPE, list_dict_names
from .notice_tagging import (
    DEAL_KINDS,
    batch_correct_notice_tags,
    correct_notice_tag,
    retag_notice,
    safe_stats,
    tag_result_notices,
)
from .notice_views import _parse_notice_kinds
from .views import _require_permission


def _page(request) -> tuple[int, int]:
    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except ValueError:
        page_size = 20
    return page, min(max(page_size, 1), 50)


def _serialize_tag(tag: NoticeResultTag, parsed: NoticeParsed | None, product_count: int) -> dict:
    profile = tag.buyer_profile
    return {
        "id": tag.notice_raw_id,
        "title": (parsed.notice_title if parsed else "") or "",
        "buyerName": (profile.buyer_name if profile else "") or ((parsed.buyer_name if parsed else "") or ""),
        "orgType": profile.org_type if profile else "",
        "nature": profile.nature if profile else "",
        "dealKind": (tag.deal_kind or "") or "",
        "province": profile.province if profile else "",
        "city": profile.city if profile else "",
        "district": profile.district if profile else "",
        "regionName": (parsed.region_name if parsed else "") or "",
        "dealAmount": str(parsed.deal_amount) if parsed and parsed.deal_amount is not None else "",
        "publishTime": parsed.publish_time.isoformat() if parsed and parsed.publish_time else "",
        "locked": tag.locked or bool(profile and profile.locked),
        "source": tag.source,
        "productCount": product_count,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def notice_tag_list(request):
    permission = "notice.tag.manage" if request.method == "POST" else "notice.tag.view"
    _user, error = _require_permission(request, permission)
    if error:
        return error
    if request.method == "POST":
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            body = {}
        try:
            limit = max(1, min(int(body.get("limit") or 200), 500))
            result = tag_result_notices(limit=limit, rebuild=bool(body.get("rebuild")))
        except DatabaseError:
            return JsonResponse({"detail": "公告表或标签表不可用。"}, status=503)
        return JsonResponse(result)
    try:
        page, page_size = _page(request)
        search = (request.GET.get("search") or "").strip()
        org_type = (request.GET.get("org_type") or "").strip()
        nature = (request.GET.get("nature") or "").strip()
        deal_kind = (request.GET.get("deal_kind") or "").strip()
        province = (request.GET.get("province") or "").strip()
        qs = NoticeResultTag.objects.select_related("buyer_profile").order_by("-updated_at")
        if org_type:
            qs = qs.filter(buyer_profile__org_type=org_type)
        if nature:
            qs = qs.filter(buyer_profile__nature=nature)
        if deal_kind in DEAL_KINDS:
            if deal_kind == "未识别":
                qs = qs.filter(Q(deal_kind="") | Q(deal_kind=deal_kind))
            else:
                qs = qs.filter(deal_kind=deal_kind)
        if province:
            region_ids = NoticeParsed.objects.filter(region_name__icontains=province).values("notice_raw_id")
            qs = qs.filter(
                Q(buyer_profile__province__icontains=province)
                | Q(buyer_profile__city__icontains=province)
                | Q(buyer_profile__district__icontains=province)
                | Q(notice_raw_id__in=region_ids)
            )
        if search:
            title_ids = NoticeParsed.objects.filter(
                Q(notice_title__icontains=search) | Q(buyer_name__icontains=search)
            ).values("notice_raw_id")
            qs = qs.filter(Q(buyer_profile__buyer_name__icontains=search) | Q(notice_raw_id__in=title_ids))
        total = qs.count()
        rows = list(qs[(page - 1) * page_size : page * page_size])
        raw_ids = [row.notice_raw_id for row in rows]
        parsed_map = {item.notice_raw_id: item for item in NoticeParsed.objects.filter(notice_raw_id__in=raw_ids)}
        counts = {
            item["notice_raw_id"]: item["total"]
            for item in NoticeProductTag.objects.filter(notice_raw_id__in=raw_ids).values("notice_raw_id").annotate(total=Count("id"))
        }
        return JsonResponse({
            "items": [_serialize_tag(row, parsed_map.get(row.notice_raw_id), counts.get(row.notice_raw_id, 0)) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "orgTypes": list(list_dict_names(KIND_ORG_TYPE, enabled_only=True)),
            "natures": list(list_dict_names(KIND_NATURE, enabled_only=True)),
            "dealKinds": list(DEAL_KINDS),
        })
    except DatabaseError:
        return JsonResponse({
            "items": [],
            "total": 0,
            "page": 1,
            "pageSize": 20,
            "orgTypes": list(list_dict_names(KIND_ORG_TYPE, enabled_only=True)),
            "natures": list(list_dict_names(KIND_NATURE, enabled_only=True)),
            "dealKinds": list(DEAL_KINDS),
            "detail": "标签表尚未创建",
        }, status=503)


@csrf_exempt
@require_http_methods(["POST"])
def notice_tag_batch(request):
    _user, error = _require_permission(request, "notice.tag.manage")
    if error:
        return error
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "请求格式不正确。"}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"detail": "请求格式不正确。"}, status=400)
    ids = body.get("ids") or body.get("noticeIds") or []
    if not isinstance(ids, list) or not ids:
        return JsonResponse({"detail": "请先勾选要修正的公告。"}, status=400)
    try:
        result = batch_correct_notice_tags(ids, body)
    except DatabaseError:
        return JsonResponse({"detail": "标签表不可用。"}, status=503)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def notice_tag_detail(request, notice_id: int):
    permission = "notice.tag.manage" if request.method == "PATCH" else "notice.tag.view"
    _user, error = _require_permission(request, permission)
    if error:
        return error
    try:
        tag = NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id=notice_id).first()
    except DatabaseError:
        return JsonResponse({"detail": "标签表尚未创建"}, status=503)
    if not tag:
        return JsonResponse({"detail": "还没有这条公告的标签。"}, status=404)
    if request.method == "PATCH":
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"detail": "请求格式不正确。"}, status=400)
        updated = correct_notice_tag(notice_id, payload if isinstance(payload, dict) else {})
        if not updated:
            return JsonResponse({"detail": "无法保存标签。"}, status=400)
        tag = updated
    parsed = NoticeParsed.objects.filter(notice_raw_id=notice_id).first()
    products = [
        {
            "goodsId": item.goods_id,
            "category": item.category,
            "productName": item.product_name,
            "brand": item.brand,
            "locked": item.locked,
        }
        for item in NoticeProductTag.objects.filter(notice_raw_id=notice_id).order_by("id")
    ]
    data = _serialize_tag(tag, parsed, len(products))
    data["products"] = products
    data["orgTypes"] = list(list_dict_names(KIND_ORG_TYPE, enabled_only=True))
    data["natures"] = list(list_dict_names(KIND_NATURE, enabled_only=True))
    data["dealKinds"] = list(DEAL_KINDS)
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
def notice_tag_identify(request, notice_id: int):
    _user, error = _require_permission(request, "notice.tag.manage")
    if error:
        return error
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    force = bool(body.get("force")) if isinstance(body, dict) else False
    try:
        result = retag_notice(notice_id, force=force)
    except DatabaseError:
        return JsonResponse({"detail": "标签表不可用。"}, status=503)
    if not result.get("ok"):
        status = 409 if result.get("locked") else 400
        return JsonResponse(result, status=status)
    tag = NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id=notice_id).first()
    if not tag:
        return JsonResponse({"detail": "识别后未找到标签。"}, status=500)
    parsed = NoticeParsed.objects.filter(notice_raw_id=notice_id).first()
    product_count = NoticeProductTag.objects.filter(notice_raw_id=notice_id).count()
    data = _serialize_tag(tag, parsed, product_count)
    data["ok"] = True
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["GET"])
def notice_result_stats(request):
    _user, error = _require_permission(request, "notice.stats.view")
    if error:
        return error
    start_date = (request.GET.get("startDate") or request.GET.get("start_date") or "").strip()
    end_date = (request.GET.get("endDate") or request.GET.get("end_date") or "").strip()
    period = request.GET.get("period") or "last_30_days"
    notice_kinds = _parse_notice_kinds(
        request.GET.get("noticeKinds") or request.GET.get("notice_kinds") or "",
        request.GET.get("noticeKind") or "",
    )
    return JsonResponse(
        safe_stats(
            period=period,
            province=request.GET.get("province") or "",
            buyer=request.GET.get("buyer") or "",
            deal_kind=request.GET.get("deal_kind") or request.GET.get("dealKind") or "",
            start_date=start_date,
            end_date=end_date,
            publish_date_from=(request.GET.get("publishDateFrom") or request.GET.get("publish_date_from") or "").strip(),
            publish_date_to=(request.GET.get("publishDateTo") or request.GET.get("publish_date_to") or "").strip(),
            start_date_from=(request.GET.get("startDateFrom") or request.GET.get("start_date_from") or "").strip(),
            start_date_to=(request.GET.get("startDateTo") or request.GET.get("start_date_to") or "").strip(),
            end_date_from=(request.GET.get("endDateFrom") or request.GET.get("end_date_from") or "").strip(),
            end_date_to=(request.GET.get("endDateTo") or request.GET.get("end_date_to") or "").strip(),
            notice_kinds=notice_kinds,
        )
    )
