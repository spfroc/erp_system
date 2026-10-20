from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import ProgrammingError
from django.db.models import Q, TextField
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_models import NoticeGoods, NoticeParsed, NoticeRaw
from .views import _require_permission

SITE_LABELS = {
    "sd-ggzyjyzx": "山东网上商城",
    "jd-quan-yicai": "京东泉易采",
    "jd-qing-huicai": "京东青慧采",
}

# 与京东公告页 tab 一致：竞价公告 / 询比公告 / 成交 / 终止 / 失败 / 废标
JD_NOTICE_TYPE_LABELS = {
    "1": "竞价公告",
    "2": "成交公告",
    "3": "终止公告",
    "4": "失败公告",
    "5": "询比公告",
    "6": "废标公告",
}
JD_SITE_IDS = frozenset({"jd-quan-yicai", "jd-qing-huicai"})

# 结果类公告一般不算「进行中」
CLOSED_NOTICE_KINDS = (
    "成交公告",
    "成交结果公告",
    "成交结果",
    "终止公告",
    "终止",
    "废标公告",
    "废标",
    "失败公告",
    "结果公告",
)
CLOSED_KIND_KEYWORDS = ("成交结果", "结果公告", "终止", "废标", "失败公告", "成交公告")
# 「进行中」不包含直接采购 / 直购
DIRECT_PURCHASE_KEYWORDS = ("直接采购", "直购")

# 列表接口按分类抓取时已写入 notice_raw.notice_type，未解析也能显示
NOTICE_TYPE_LABELS = {
    "jd-quan-yicai": JD_NOTICE_TYPE_LABELS,
    "jd-qing-huicai": JD_NOTICE_TYPE_LABELS,
    "sd-ggzyjyzx": {
        "0": "采购公告",
        "1": "成交公告",
        "5": "终止公告",
        "10": "终止公告",
        "13": "公示公告",
    },
    "sd-gpfa-frame": {
        "0": "采购公告",
        "1": "成交公告",
        "10": "终止公告",
    },
}


def _parse_dt(value: Any):
    """解析字符串 / 秒或毫秒时间戳为 aware datetime。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        num = float(value)
        # 13 位毫秒 / 10 位秒
        if num > 1e12:
            num = num / 1000.0
        try:
            return datetime.fromtimestamp(num, tz=timezone.get_current_timezone())
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip().replace("T", " ")
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            naive = datetime.strptime(s[:n], fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def _json_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _dig(data: dict, *paths: str):
    """按 a.b.c 路径取值，跳过空值。"""
    for path in paths:
        cur: Any = data
        ok = True
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                ok = False
                break
            cur = cur[part]
        if ok and cur not in (None, "", []):
            return cur
    return None


def _resolve_times(raw: NoticeRaw, parsed: NoticeParsed | None) -> tuple:
    """优先 parsed，回落到 list/detail JSON（含京东嵌套毫秒时间）。"""
    detail = _json_dict(raw.detail_json)
    list_item = _json_dict(raw.list_json)
    nested = _json_dict(detail.get("detail"))
    base = _json_dict(nested.get("auctionNoticeBaseInfo"))

    start = parsed.start_time if parsed and parsed.start_time else None
    end = parsed.end_time if parsed and parsed.end_time else None

    if not start:
        start = _parse_dt(
            _dig(detail, "startTime", "beginTime")
            or _dig(list_item, "startTime", "beginTime")
            or base.get("startTime")
            or base.get("beginTime")
        )
    if not end:
        end = _parse_dt(
            _dig(detail, "endTime", "closeTime", "deadline")
            or _dig(list_item, "endTime", "closeTime", "deadline")
            or base.get("endTime")
            or base.get("closeTime")
        )
    return start, end


def _kind_from_notice_type(site_id: str | None, notice_type: Any) -> str:
    code = str(notice_type).strip() if notice_type not in (None, "") else ""
    if not code:
        return ""
    return NOTICE_TYPE_LABELS.get(site_id or "", {}).get(code, "")


def _normalize_display_kind(site_id: str | None, kind: str) -> str:
    """把历史统一名改回各站原文（京东竞价页叫「竞价公告」不是「采购公告」）。"""
    text = (kind or "").strip()
    if not text or text.isdigit():
        return text
    if site_id in JD_SITE_IDS and text == "采购公告":
        return "竞价公告"
    return text


def _resolve_kind(raw: NoticeRaw, parsed: NoticeParsed | None) -> str:
    detail = _json_dict(raw.detail_json)
    list_item = _json_dict(raw.list_json)

    # 京东：优先用站点 notice_type 对应的原文 tab 名
    if raw.site_id in JD_SITE_IDS:
        mapped = _kind_from_notice_type(raw.site_id, raw.notice_type)
        if not mapped:
            mapped = _kind_from_notice_type(
                raw.site_id,
                detail.get("noticeType")
                if detail.get("noticeType") not in (None, "")
                else list_item.get("noticeType"),
            )
        if mapped:
            return mapped

    kind = (parsed.notice_kind if parsed and parsed.notice_kind else "") or ""
    kind = _normalize_display_kind(raw.site_id, kind)
    # 解析结果有时只落了接口里的数字编码
    if kind and not kind.isdigit():
        return kind
    for key in ("noticeTypeName", "noticeKind", "typeName"):
        for src in (detail, list_item):
            v = src.get(key)
            if v and not str(v).strip().isdigit():
                return _normalize_display_kind(raw.site_id, str(v))
    mapped = _kind_from_notice_type(raw.site_id, raw.notice_type)
    if not mapped:
        mapped = _kind_from_notice_type(
            raw.site_id,
            detail.get("noticeType") if detail.get("noticeType") not in (None, "") else list_item.get("noticeType"),
        )
    if mapped:
        return mapped
    title = (raw.title or "") + " " + (parsed.notice_title if parsed and parsed.notice_title else "")
    for token, label in (
        ("废标", "废标公告"),
        ("终止", "终止公告"),
        ("成交结果", "成交结果公告"),
        ("结果公告", "结果公告"),
        ("成交公告", "成交公告"),
        ("失败", "失败公告"),
        ("询比", "询比公告"),
        ("竞价公告", "竞价公告"),
    ):
        if token in title:
            return label
    return kind if kind and not kind.isdigit() else ""


def _raw_ids_for_kind(notice_kind: str, site_id: str) -> Q:
    """公告类型筛选：解析字段，或抓取时写入的 notice_type 编码。"""
    parsed_qs = NoticeParsed.objects.filter(notice_kind=notice_kind)
    if site_id:
        parsed_qs = parsed_qs.filter(site_id=site_id)
    q = Q(id__in=parsed_qs.values("notice_raw_id"))

    # 京东历史曾把竞价公告写成「采购公告」，筛选时兼容
    if notice_kind == "竞价公告":
        legacy = NoticeParsed.objects.filter(
            site_id__in=JD_SITE_IDS if not site_id else [site_id],
            notice_kind="采购公告",
        )
        if not site_id or site_id in JD_SITE_IDS:
            q |= Q(id__in=legacy.values("notice_raw_id"))

    for sid, mapping in NOTICE_TYPE_LABELS.items():
        if site_id and sid != site_id:
            continue
        codes = [code for code, label in mapping.items() if label == notice_kind]
        if codes:
            q |= Q(site_id=sid, notice_type__in=codes)
    return q


def _notice_kind_options(site_id: str) -> list[str]:
    labels: set[str] = set()
    kind_qs = NoticeParsed.objects.exclude(notice_kind__isnull=True).exclude(notice_kind="")
    if site_id:
        kind_qs = kind_qs.filter(site_id=site_id)
    for sid, kind in kind_qs.values_list("site_id", "notice_kind").distinct():
        if not kind or str(kind).strip().isdigit():
            continue
        labels.add(_normalize_display_kind(sid, str(kind)))

    raw_qs = NoticeRaw.objects.exclude(notice_type__isnull=True).exclude(notice_type="")
    if site_id:
        raw_qs = raw_qs.filter(site_id=site_id)
    for sid, code in raw_qs.values_list("site_id", "notice_type").distinct():
        label = _kind_from_notice_type(sid, code)
        if label:
            labels.add(label)
    return sorted(labels)


def _is_closed_kind(kind: str, title: str = "") -> bool:
    text = f"{kind} {title}".strip()
    if not text:
        return False
    if kind in CLOSED_NOTICE_KINDS:
        return True
    return any(k in text for k in CLOSED_KIND_KEYWORDS)


def _is_direct_purchase(raw: NoticeRaw, parsed: NoticeParsed | None, kind: str, title: str) -> bool:
    """直接采购 / 直购不计入「进行中」。"""
    mode = (parsed.procurement_mode if parsed and parsed.procurement_mode else "") or ""
    text = f"{kind} {mode} {title}".strip()
    if any(k in text for k in DIRECT_PURCHASE_KEYWORDS):
        return True
    list_item = _json_dict(raw.list_json)
    detail = _json_dict(raw.detail_json)
    for src in (list_item, detail):
        for key in ("procurementMode", "projectTypeName", "noticeTypeName", "title"):
            v = src.get(key)
            if v and any(k in str(v) for k in DIRECT_PURCHASE_KEYWORDS):
                return True
    return False


def _progress_status(raw: NoticeRaw, parsed: NoticeParsed | None, now=None) -> str:
    """ongoing=进行中 / upcoming=未开始 / ended=已截止 / unknown=未知。"""
    now = now or timezone.now()
    start, end = _resolve_times(raw, parsed)
    kind = _resolve_kind(raw, parsed)
    title = (parsed.notice_title if parsed and parsed.notice_title else None) or raw.title or ""
    if _is_closed_kind(kind, title):
        return "ended"
    if end and end < now:
        return "ended"
    if start and start > now:
        return "upcoming"
    # 直接采购即使未截止也不算进行中
    if _is_direct_purchase(raw, parsed, kind, title):
        return "unknown"
    if end and end >= now and (not start or start <= now):
        return "ongoing"
    # 有截止时间且未开始时间：视为进行中（常见于商城列表只带 endTime）
    if end and end >= now and not start:
        return "ongoing"
    if not end and start and start <= now and ("采购" in kind or "竞价" in kind or "反拍" in kind):
        return "ongoing"
    return "unknown"


def _dec(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dt(value) -> str | None:
    if not value:
        return None
    local = timezone.localtime(value) if timezone.is_aware(value) else value
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _serialize_list_item(raw: NoticeRaw, parsed: NoticeParsed | None, now=None) -> dict:
    start, end = _resolve_times(raw, parsed)
    progress = _progress_status(raw, parsed, now=now)
    progress_label = {
        "ongoing": "进行中",
        "upcoming": "未开始",
        "ended": "已截止",
        "unknown": "未知",
    }.get(progress, "未知")
    kind = _resolve_kind(raw, parsed) or (parsed.notice_kind if parsed else None)
    return {
        "id": raw.id,
        "siteId": raw.site_id,
        "siteLabel": SITE_LABELS.get(raw.site_id or "", raw.site_id or ""),
        "noticeKey": raw.notice_key,
        "title": (parsed.notice_title if parsed and parsed.notice_title else None) or raw.title,
        "projectCode": parsed.project_code if parsed else None,
        "projectName": parsed.project_name if parsed else None,
        "buyerName": parsed.buyer_name if parsed else None,
        "dealSupplier": parsed.deal_supplier if parsed else None,
        "dealAmount": _dec(parsed.deal_amount) if parsed else None,
        "budgetAmount": _dec(parsed.budget_amount) if parsed else None,
        "noticeKind": kind,
        "procurementMode": parsed.procurement_mode if parsed else None,
        "regionName": (parsed.region_name if parsed and parsed.region_name else None) or raw.region_name,
        "publishTime": _dt((parsed.publish_time if parsed and parsed.publish_time else None) or raw.publish_time),
        "startTime": _dt(start),
        "endTime": _dt(end),
        "progressStatus": progress,
        "progressLabel": progress_label,
        "crawlStatus": raw.crawl_status,
        "parseStatus": raw.parse_status,
        "sourceUrl": raw.source_url,
        "crawledAt": _dt(raw.crawled_at),
    }


def _serialize_detail(raw: NoticeRaw, parsed: NoticeParsed | None, goods: list[NoticeGoods]) -> dict:
    base = _serialize_list_item(raw, parsed)
    base.update(
        {
            "buyerContactName": parsed.buyer_contact_name if parsed else None,
            "buyerPhone": parsed.buyer_phone if parsed else None,
            "buyerAddress": parsed.buyer_address if parsed else None,
            "buyerContact": parsed.buyer_contact if parsed else None,
            "dealSupplierPhone": parsed.deal_supplier_phone if parsed else None,
            "dealSupplierAddress": parsed.deal_supplier_address if parsed else None,
            "deliveryAddress": parsed.delivery_address if parsed else None,
            "quoteCount": parsed.quote_count if parsed else None,
            "quotes": parsed.quotes_json if parsed else [],
            "suppliers": parsed.suppliers_json if parsed else [],
            "modelName": parsed.model_name if parsed else None,
            "confidence": _dec(parsed.confidence) if parsed else None,
            "contentText": (raw.content_text or "")[:20000],
            "goods": [
                {
                    "id": g.id,
                    "lineNo": g.line_no,
                    "productName": g.product_name,
                    "category": g.category,
                    "quantity": _dec(g.quantity),
                    "unit": g.unit,
                    "brand": g.brand,
                    "model": g.product_model,
                    "unitPrice": _dec(g.unit_price),
                    "spec": g.spec,
                    "amount": _dec(g.amount),
                }
                for g in goods
            ],
        }
    )
    return base


def _notice_field_filter_ids(
    *,
    project_code: str,
    project_name: str,
    buyer_name: str,
    supplier_name: str,
    goods_name: str,
) -> list[int] | None:
    """按项目编号、项目名称、采购单位、供应商、商品名称取交集。无筛选时返回 None。"""
    sets: list[set[int]] = []
    if project_code:
        sets.append(
            set(
                NoticeParsed.objects.filter(
                    Q(project_code__icontains=project_code) | Q(notice_key__icontains=project_code)
                ).values_list("notice_raw_id", flat=True)
            )
        )
    if project_name:
        sets.append(
            set(
                NoticeParsed.objects.filter(
                    Q(project_name__icontains=project_name) | Q(notice_title__icontains=project_name)
                ).values_list("notice_raw_id", flat=True)
            )
        )
    if buyer_name:
        sets.append(
            set(
                NoticeParsed.objects.filter(buyer_name__icontains=buyer_name).values_list(
                    "notice_raw_id", flat=True
                )
            )
        )
    if supplier_name:
        sets.append(
            set(
                NoticeParsed.objects.annotate(
                    quotes_text=Cast("quotes_json", TextField()),
                    suppliers_text=Cast("suppliers_json", TextField()),
                )
                .filter(
                    Q(deal_supplier__icontains=supplier_name)
                    | Q(quotes_text__icontains=supplier_name)
                    | Q(suppliers_text__icontains=supplier_name)
                )
                .values_list("notice_raw_id", flat=True)
            )
        )
    if goods_name:
        sets.append(
            set(
                NoticeGoods.objects.filter(product_name__icontains=goods_name).values_list(
                    "notice_raw_id", flat=True
                )
            )
        )
    if not sets:
        return None
    matched = sets[0]
    for extra in sets[1:]:
        matched &= extra
    return list(matched)


def _tables_missing_response():
    return JsonResponse(
        {
            "detail": "公告表尚未创建，请先在 notice_crawler 执行 python cli.py init-db",
            "items": [],
            "total": 0,
            "page": 1,
            "pageSize": 20,
            "noticeKinds": [],
        },
        status=503,
    )


def query_crawled_notices(*, page: int = 1, page_size: int = 20, search: str = "", site_id: str = "", notice_kind: str = "") -> dict:
    """客户控制台和后台列表共用的抓取公告查询。"""
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    qs = NoticeRaw.objects.all().order_by("-publish_time", "-id")
    if site_id:
        qs = qs.filter(site_id=site_id)
    if notice_kind and notice_kind != "全部":
        qs = qs.filter(_raw_ids_for_kind(notice_kind, site_id))
    keyword = (search or "").strip()
    if keyword:
        parsed_ids = list(
            NoticeParsed.objects.filter(
                Q(project_code__icontains=keyword)
                | Q(project_name__icontains=keyword)
                | Q(buyer_name__icontains=keyword)
                | Q(notice_title__icontains=keyword)
            ).values_list("notice_raw_id", flat=True)[:2000]
        )
        qs = qs.filter(Q(title__icontains=keyword) | Q(notice_key__icontains=keyword) | Q(id__in=parsed_ids))
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    parsed_map = {
        item.notice_raw_id: item
        for item in NoticeParsed.objects.filter(notice_raw_id__in=[row.id for row in rows])
    }
    return {
        "items": [_serialize_list_item(row, parsed_map.get(row.id)) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@csrf_exempt
@require_http_methods(["GET"])
def notice_list(request):
    _, error = _require_permission(request, "notice.view")
    if error:
        return error

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.GET.get("pageSize") or 20), 1), 100)
    except ValueError:
        page_size = 20

    site_id = (request.GET.get("siteId") or "").strip()
    parse_status = (request.GET.get("parseStatus") or "").strip()
    notice_kind = (request.GET.get("noticeKind") or "").strip()
    progress = (request.GET.get("progress") or "").strip().lower()
    search = (request.GET.get("search") or "").strip()
    project_code = (request.GET.get("projectCode") or "").strip()
    project_name = (request.GET.get("projectName") or "").strip()
    buyer_name = (request.GET.get("buyerName") or "").strip()
    supplier_name = (request.GET.get("supplierName") or "").strip()
    goods_name = (request.GET.get("goodsName") or "").strip()
    now = timezone.now()

    try:
        qs = NoticeRaw.objects.all().order_by("-id")
        if site_id:
            qs = qs.filter(site_id=site_id)
        if parse_status:
            qs = qs.filter(parse_status=parse_status)
        if search:
            parsed_ids = list(
                NoticeParsed.objects.filter(
                    Q(project_code__icontains=search)
                    | Q(project_name__icontains=search)
                    | Q(buyer_name__icontains=search)
                    | Q(deal_supplier__icontains=search)
                    | Q(notice_title__icontains=search)
                ).values_list("notice_raw_id", flat=True)[:2000]
            )
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(notice_key__icontains=search)
                | Q(region_name__icontains=search)
                | Q(id__in=parsed_ids)
            )
        if notice_kind:
            qs = qs.filter(_raw_ids_for_kind(notice_kind, site_id))
        field_ids = _notice_field_filter_ids(
            project_code=project_code,
            project_name=project_name,
            buyer_name=buyer_name,
            supplier_name=supplier_name,
            goods_name=goods_name,
        )
        if field_ids is not None:
            qs = qs.filter(id__in=field_ids)

        # 进度依赖 raw JSON 回落时间，数据量不大时在内存中判定，保证与列表展示一致
        progress_target = None
        if progress in {"ongoing", "in_progress", "进行中"}:
            progress_target = "ongoing"
        elif progress in {"upcoming", "未开始"}:
            progress_target = "upcoming"
        elif progress in {"ended", "已截止"}:
            progress_target = "ended"
        elif progress in {"unknown", "未知"}:
            progress_target = "unknown"

        if progress_target:
            candidates = list(qs[:8000])
            parsed_map = {
                p.notice_raw_id: p
                for p in NoticeParsed.objects.filter(
                    notice_raw_id__in=[r.id for r in candidates]
                )
            }
            rows = [
                r
                for r in candidates
                if _progress_status(r, parsed_map.get(r.id), now=now) == progress_target
            ]
            total = len(rows)
            offset = (page - 1) * page_size
            page_rows = rows[offset : offset + page_size]
            items = [
                _serialize_list_item(r, parsed_map.get(r.id), now=now) for r in page_rows
            ]
        else:
            total = qs.count()
            offset = (page - 1) * page_size
            page_rows = list(qs[offset : offset + page_size])
            parsed_map = {
                p.notice_raw_id: p
                for p in NoticeParsed.objects.filter(
                    notice_raw_id__in=[r.id for r in page_rows]
                )
            }
            items = [
                _serialize_list_item(r, parsed_map.get(r.id), now=now) for r in page_rows
            ]

        notice_kinds = _notice_kind_options(site_id)

        return JsonResponse(
            {
                "items": items,
                "total": total,
                "page": page,
                "pageSize": page_size,
                "sites": [
                    {"id": key, "label": label}
                    for key, label in SITE_LABELS.items()
                ],
                "noticeKinds": notice_kinds,
            }
        )
    except ProgrammingError:
        return _tables_missing_response()


@csrf_exempt
@require_http_methods(["GET"])
def notice_detail(request, notice_id: int):
    _, error = _require_permission(request, "notice.view")
    if error:
        return error
    try:
        raw = NoticeRaw.objects.filter(id=notice_id).first()
        if not raw:
            return JsonResponse({"detail": "公告不存在"}, status=404)
        parsed = NoticeParsed.objects.filter(notice_raw_id=raw.id).first()
        goods = list(
            NoticeGoods.objects.filter(notice_raw_id=raw.id).order_by("line_no", "id")
        )
        return JsonResponse(_serialize_detail(raw, parsed, goods))
    except ProgrammingError:
        return JsonResponse({"detail": "公告表尚未创建"}, status=503)
