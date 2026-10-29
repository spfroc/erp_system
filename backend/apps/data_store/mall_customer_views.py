"""mall_customer 资料库展示列表 API（表由 notice_crawler / 导入脚本维护）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from django.db import ProgrammingError
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_models import MallCustomer
from .views import _require_permission

ORIGIN_LABELS = {
    "1": "百度",
    "2": "公共资源",
    "3": "招投标",
    "4": "齐鲁云采",
    "5": "青岛政采",
    "6": "烟台政采",
    "7": "滨州政采",
    "8": "菏泽政采",
    "9": "其他",
    "10": "新齐鲁云采",
    "0": "其他",
}

SIGNED_LABELS = {"0": "有效", "1": "已签约", "2": "无效"}

def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _origin_label(code: str | None) -> str:
    raw = (code or "").strip()
    if not raw:
        return "其他"
    # 可能是 "4,10" 这类
    parts = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
    if not parts:
        return "其他"
    labels = [ORIGIN_LABELS.get(p, p) for p in parts]
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for label in labels:
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
    return "、".join(out) if out else "其他"


def _signed_label(code: str | None) -> str:
    raw = (code or "0").strip()
    return SIGNED_LABELS.get(raw, raw or "有效")


def _serialize(row: MallCustomer) -> dict[str, Any]:
    origin = row.origin or ""
    signed = row.signed or "0"
    return {
        "id": row.id,
        "name": row.name or "",
        "platformCustomerId": row.platform_customer_id or "",
        "type": row.type or "",
        "address": row.address or "",
        "province": row.province or "",
        "city": row.city or "",
        "license": row.license or "",
        "licenseCode": row.license_code or "",
        "businessScope": row.business_scope or "",
        "enterTime": row.enter_time or "",
        "legalPerson": row.legal_person or "",
        "mobile": row.mobile or "",
        "newMobile": row.new_mobile or "",
        "email": row.email or "",
        "origin": origin,
        "originLabel": _origin_label(origin),
        "signed": signed,
        "signedLabel": _signed_label(signed),
        "tag": row.tag or "",
        "sellId": row.sell_id or 0,
        "sellUserId": row.sell_user_id or "",
        "sellUserName": row.sell_user_name or "",
        "remark": row.remark or "",
        "agentShopProductNumber": row.agent_shop_product_number,
        "onlineShopProductNumber": row.online_shop_product_number,
        "manufacturerShopProductNumber": row.manufacturer_shop_product_number,
        "enteringOrigin": row.entering_origin or 0,
        "legacyCustomerId": row.legacy_customer_id,
        "crawledAt": _iso(row.crawled_at),
        "updatedAt": _iso(row.updated_at),
    }


def _parse_body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8-sig") or "{}")
    except json.JSONDecodeError:
        return {}


@csrf_exempt
@require_http_methods(["GET"])
def mall_customer_list(request):
    user, error = _require_permission(request, "mallCustomer.view")
    if error:
        return error
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    try:
        page_size = min(100, max(1, int(request.GET.get("page_size") or 20)))
    except ValueError:
        page_size = 20
    search = (request.GET.get("search") or "").strip()
    signed = (request.GET.get("signed") or "").strip()
    origin = (request.GET.get("origin") or "").strip()

    try:
        qs = MallCustomer.objects.all()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(mobile__icontains=search)
                | Q(new_mobile__icontains=search)
                | Q(legal_person__icontains=search)
                | Q(license_code__icontains=search)
                | Q(city__icontains=search)
                | Q(tag__icontains=search)
            )
        if signed:
            qs = qs.filter(signed=signed)
        if origin:
            qs = qs.filter(Q(origin=origin) | Q(origin__startswith=f"{origin},") | Q(origin__endswith=f",{origin}") | Q(origin__contains=f",{origin},"))
        total = qs.count()
        start = (page - 1) * page_size
        rows = list(qs.order_by("-id")[start : start + page_size])
    except ProgrammingError:
        return JsonResponse(
            {
                "detail": "mall_customer 表不存在或未迁移，请先执行 notice_crawler init-db / import-customers。",
                "items": [],
                "total": 0,
                "page": page,
                "pageSize": page_size,
            },
            status=503,
        )

    return JsonResponse(
        {
            "items": [_serialize(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "originOptions": [{"value": k, "label": v} for k, v in ORIGIN_LABELS.items() if k not in {"0"}],
            "signedOptions": [{"value": k, "label": v} for k, v in SIGNED_LABELS.items()],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def mall_customer_detail(request, customer_id: int):
    if request.method == "GET":
        user, error = _require_permission(request, "mallCustomer.view")
    else:
        user, error = _require_permission(request, "mallCustomer.manage")
    if error:
        return error

    try:
        row = MallCustomer.objects.filter(id=customer_id).first()
    except ProgrammingError:
        return JsonResponse({"detail": "mall_customer 表不可用"}, status=503)
    if row is None:
        return JsonResponse({"detail": "记录不存在"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize(row))

    payload = _parse_body(request)
    field_map = {
        "name": ("name", 256),
        "legalPerson": ("legal_person", 128),
        "mobile": ("mobile", 512),
        "newMobile": ("new_mobile", 512),
        "email": ("email", 256),
        "type": ("type", 128),
        "address": ("address", None),
        "province": ("province", 64),
        "city": ("city", 64),
        "licenseCode": ("license_code", 128),
        "origin": ("origin", 64),
        "signed": ("signed", 32),
        "tag": ("tag", 191),
        "sellUserId": ("sell_user_id", 64),
        "sellUserName": ("sell_user_name", 128),
        "remark": ("remark", None),
        "enterTime": ("enter_time", 64),
    }
    changed = False
    for key, (column, max_len) in field_map.items():
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            value = ""
        text = str(value).strip()
        if max_len is not None:
            text = text[:max_len]
        if key == "name" and not text:
            return JsonResponse({"detail": "公司名称不能为空"}, status=400)
        if getattr(row, column) != text:
            setattr(row, column, text)
            changed = True
    if changed:
        row.updated_at = timezone.now()
        try:
            row.save()
        except Exception as exc:  # noqa: BLE001
            return JsonResponse({"detail": f"保存失败：{exc}"}, status=400)
    return JsonResponse(_serialize(row))
