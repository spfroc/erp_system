"""公告类型 / 性质字典 CRUD。"""

from __future__ import annotations

import json

from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_dict import (
    KIND_NATURE,
    KIND_ORG_TYPE,
    ensure_notice_dict_defaults,
    list_dict_names,
    serialize_dict_item,
)
from .notice_tag_models import NoticeDictItem
from .views import _require_permission

_KIND_PERM = {
    KIND_ORG_TYPE: ("notice.orgType.view", "notice.orgType.manage"),
    KIND_NATURE: ("notice.nature.view", "notice.nature.manage"),
}


def _page(request) -> tuple[int, int]:
    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except ValueError:
        page_size = 20
    return page, min(max(page_size, 1), 100)


def _parse_kind(raw: str | None) -> str | None:
    kind = (raw or "").strip()
    if kind in {KIND_ORG_TYPE, KIND_NATURE}:
        return kind
    return None


def _require_kind_permission(request, kind: str, *, write: bool):
    view_perm, manage_perm = _KIND_PERM[kind]
    return _require_permission(request, manage_perm if write else view_perm)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def notice_dict_list(request):
    kind = _parse_kind(request.GET.get("kind") if request.method == "GET" else None)
    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"detail": "无效 JSON"}, status=400)
        kind = _parse_kind(payload.get("kind"))
        if not kind:
            return JsonResponse({"detail": "kind 须为 org_type 或 nature"}, status=400)
        _user, error = _require_kind_permission(request, kind, write=True)
        if error:
            return error
        name = str(payload.get("name") or "").strip()[:32]
        if not name:
            return JsonResponse({"detail": "名称不能为空"}, status=400)
        try:
            sort_order = int(payload.get("sortOrder") if payload.get("sortOrder") is not None else 0)
        except (TypeError, ValueError):
            sort_order = 0
        enabled = bool(payload.get("enabled", True))
        try:
            ensure_notice_dict_defaults()
            item = NoticeDictItem.objects.create(kind=kind, name=name, sort_order=sort_order, enabled=enabled)
        except IntegrityError:
            return JsonResponse({"detail": "同名项已存在"}, status=409)
        except DatabaseError:
            return JsonResponse({"detail": "字典表尚未创建"}, status=503)
        return JsonResponse({"item": serialize_dict_item(item)}, status=201)

    if not kind:
        return JsonResponse({"detail": "缺少 kind=org_type|nature"}, status=400)
    _user, error = _require_kind_permission(request, kind, write=False)
    if error:
        return error
    page, page_size = _page(request)
    search = (request.GET.get("search") or "").strip()
    try:
        ensure_notice_dict_defaults()
        qs = NoticeDictItem.objects.filter(kind=kind)
        if search:
            qs = qs.filter(Q(name__icontains=search))
        total = qs.count()
        start = (page - 1) * page_size
        items = [serialize_dict_item(row) for row in qs.order_by("sort_order", "id")[start : start + page_size]]
    except DatabaseError:
        return JsonResponse({"items": [], "total": 0, "page": page, "pageSize": page_size, "detail": "字典表尚未创建"}, status=503)
    return JsonResponse({"items": items, "total": total, "page": page, "pageSize": page_size})


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def notice_dict_detail(request, item_id: int):
    try:
        item = NoticeDictItem.objects.get(pk=item_id)
    except NoticeDictItem.DoesNotExist:
        return JsonResponse({"detail": "不存在"}, status=404)
    except DatabaseError:
        return JsonResponse({"detail": "字典表尚未创建"}, status=503)

    write = request.method in {"PATCH", "DELETE"}
    _user, error = _require_kind_permission(request, item.kind, write=write)
    if error:
        return error

    if request.method == "GET":
        return JsonResponse({"item": serialize_dict_item(item)})

    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "无效 JSON"}, status=400)
    if "name" in payload:
        name = str(payload.get("name") or "").strip()[:32]
        if not name:
            return JsonResponse({"detail": "名称不能为空"}, status=400)
        item.name = name
    if "sortOrder" in payload:
        try:
            item.sort_order = int(payload.get("sortOrder") or 0)
        except (TypeError, ValueError):
            return JsonResponse({"detail": "sortOrder 无效"}, status=400)
    if "enabled" in payload:
        item.enabled = bool(payload.get("enabled"))
    try:
        item.save()
    except IntegrityError:
        return JsonResponse({"detail": "同名项已存在"}, status=409)
    return JsonResponse({"item": serialize_dict_item(item)})


@require_http_methods(["GET"])
def notice_dict_options(request):
    """标签修正等下拉：启用中的名称列表。有标签查看权即可读。"""
    kind = _parse_kind(request.GET.get("kind"))
    if not kind:
        return JsonResponse({"detail": "缺少 kind"}, status=400)
    _user, error = _require_permission(request, "notice.tag.view")
    if error:
        view_perm, _manage = _KIND_PERM[kind]
        _user, error = _require_permission(request, view_perm)
        if error:
            return error
    try:
        names = list(list_dict_names(kind, enabled_only=True))
    except DatabaseError:
        names = []
    return JsonResponse({"kind": kind, "items": names})
