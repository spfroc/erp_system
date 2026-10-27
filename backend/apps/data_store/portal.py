from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password, is_password_usable
from django.core import signing
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerAccountRecord
from .notice_models import NoticeParsed, NoticeRaw
from .notice_tagging import DEAL_KINDS, normalize_stats_period, period_bounds, safe_stats
from .notice_views import NOTICE_TYPE_LABELS, SITE_LABELS, _raw_ids_for_kind, query_crawled_notices
from .notices import list_public_notices

PORTAL_COOKIE = "portal_session"
PORTAL_SALT = "portal-account"
PORTAL_MAX_AGE = 60 * 60 * 12
PORTAL_PERMISSIONS = (
    "portal.notice.view",
    "portal.notice.subscribe",
    "portal.stats.view",
)


def normalize_portal_permissions(value) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = set(PORTAL_PERMISSIONS)
    return [item for item in value if item in allowed]


def normalize_allowed_site_ids(value) -> list[str] | None:
    """None = 未配置（全部站点）；list = 白名单（空列表表示无站点）。"""
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    known = set(SITE_LABELS.keys())
    return [str(item).strip() for item in value if str(item).strip() in known]


def site_options(site_ids: list[str] | None = None) -> list[dict]:
    if site_ids is None:
        items = SITE_LABELS.items()
    else:
        items = ((sid, SITE_LABELS[sid]) for sid in site_ids if sid in SITE_LABELS)
    return [{"id": key, "label": label} for key, label in items]


def account_site_scope(account: dict) -> list[str] | None:
    """返回 None（不限）或站点 id 列表。"""
    if "allowedSiteIds" not in account:
        return None
    return normalize_allowed_site_ids(account.get("allowedSiteIds"))


def public_account(record: CustomerAccountRecord) -> dict:
    data = dict(record.data or {})
    data.pop("password", None)
    data["id"] = record.id
    data["name"] = record.name or data.get("name") or ""
    data["phone"] = record.phone or data.get("phone") or ""
    data["customerName"] = record.customer_name or data.get("customerName") or ""
    data["customerOrgId"] = record.customer_org_id or data.get("customerOrgId") or ""
    data["status"] = record.status or data.get("status") or "启用"
    data["permissions"] = normalize_portal_permissions(data.get("permissions"))
    subscription = data.get("subscription") if isinstance(data.get("subscription"), dict) else {}
    data["subscription"] = {
        "enabled": bool(subscription.get("enabled")),
        "keywords": str(subscription.get("keywords") or ""),
    }
    if "allowedSiteIds" in (record.data or {}):
        data["allowedSiteIds"] = normalize_allowed_site_ids((record.data or {}).get("allowedSiteIds"))
    else:
        data.pop("allowedSiteIds", None)
    scope = account_site_scope(data)
    data["allowedSites"] = site_options(scope)
    data["siteScope"] = "all" if scope is None else "limited"
    return data


def account_defaults(payload: dict) -> dict:
    permissions = normalize_portal_permissions(payload.get("permissions"))
    subscription = payload.get("subscription") if isinstance(payload.get("subscription"), dict) else {}
    data = {
        **payload,
        "permissions": permissions,
        "subscription": {
            "enabled": bool(subscription.get("enabled")),
            "keywords": str(subscription.get("keywords") or "").strip(),
        },
        "status": (payload.get("status") or "启用").strip() or "启用",
    }
    if "allowedSiteIds" in payload:
        raw = payload.get("allowedSiteIds")
        if raw is None:
            data.pop("allowedSiteIds", None)
        else:
            data["allowedSiteIds"] = normalize_allowed_site_ids(raw) or []
    data.pop("allowedSites", None)
    data.pop("siteScope", None)
    return {
        "data": data,
        "name": str(payload.get("name") or "").strip(),
        "phone": str(payload.get("phone") or "").strip(),
        "customer_name": str(payload.get("customerName") or "").strip(),
        "customer_org_id": str(payload.get("customerOrgId") or "").strip(),
        "status": data["status"],
    }


def _password_matches(stored_password: str, raw_password: str) -> bool:
    if not stored_password:
        return False
    if is_password_usable(stored_password):
        return check_password(raw_password, stored_password)
    return stored_password == raw_password


def find_portal_account(phone: str, password: str) -> CustomerAccountRecord | None:
    phone = phone.strip()
    if not phone or not password:
        return None
    for record in CustomerAccountRecord.objects.filter(is_deleted=False, phone=phone):
        if (record.status or (record.data or {}).get("status")) != "启用":
            continue
        if _password_matches(str((record.data or {}).get("password") or ""), password):
            return record
    return None


def issue_portal_cookie(response: JsonResponse, account_id: str) -> JsonResponse:
    token = signing.dumps(account_id, salt=PORTAL_SALT)
    response.set_cookie(
        PORTAL_COOKIE,
        token,
        max_age=PORTAL_MAX_AGE,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response


def clear_portal_cookie(response: JsonResponse) -> JsonResponse:
    response.delete_cookie(PORTAL_COOKIE, path="/")
    return response


def current_portal_account(request) -> CustomerAccountRecord | None:
    token = request.COOKIES.get(PORTAL_COOKIE)
    if not token:
        return None
    try:
        account_id = signing.loads(token, salt=PORTAL_SALT, max_age=PORTAL_MAX_AGE)
    except signing.BadSignature:
        return None
    record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not record or (record.status or "") != "启用":
        return None
    return record


def require_portal(request, permission: str | None = None):
    record = current_portal_account(request)
    if not record:
        return None, JsonResponse({"detail": "请先登录客户控制台。"}, status=401)
    account = public_account(record)
    if permission and permission not in account["permissions"]:
        return None, JsonResponse({"detail": "当前账号没有这项权限。", "permission": permission}, status=403)
    return record, None


PORTAL_NOTICE_KINDS = ["采购公告", "竞价公告", "询比公告", "成交公告", "终止公告", "失败公告", "废标公告"]


def _money(value) -> float:
    if value in (None, ""):
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _recent_month_keys(today: date, count: int = 6) -> list[str]:
    keys: list[str] = []
    year, month = today.year, today.month
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    keys.reverse()
    return keys


def _raw_base_qs(site_ids: list[str] | None = None):
    qs = NoticeRaw.objects.all()
    if site_ids is not None:
        qs = qs.filter(site_id__in=site_ids) if site_ids else qs.none()
    return qs


def _kind_amount(kind: str, field: str, start: date, end: date, site_ids: list[str] | None = None) -> float:
    raw_ids = _raw_base_qs(site_ids).filter(
        _raw_ids_for_kind(kind, ""),
        publish_time__date__gte=start,
        publish_time__date__lt=end,
    ).values("id")
    total = NoticeParsed.objects.filter(notice_raw_id__in=raw_ids).aggregate(total=Sum(field))["total"]
    return _money(total)


def _month_keys_between(start: date, end_exclusive: date) -> list[str]:
    if end_exclusive <= start:
        return []
    keys: list[str] = []
    cursor = start.replace(day=1)
    last = (end_exclusive - timedelta(days=1)).replace(day=1)
    while cursor <= last:
        keys.append(f"{cursor.year:04d}-{cursor.month:02d}")
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return keys


def _daily_keys_between(start: date, end_exclusive: date, *, max_days: int = 62) -> list[str]:
    if end_exclusive <= start:
        return []
    last = end_exclusive - timedelta(days=1)
    days = (last - start).days + 1
    if days > max_days:
        start = last - timedelta(days=max_days - 1)
    return [(start + timedelta(days=offset)).isoformat() for offset in range((last - start).days + 1)]


def _monthly_deal_amounts(
    site_ids: list[str] | None = None,
    *,
    start: date,
    end: date,
) -> list[dict]:
    keys = _month_keys_between(start, end) or _recent_month_keys(timezone.localdate(), 6)
    chart_start = date.fromisoformat(keys[0] + "-01")
    raw_ids = _raw_base_qs(site_ids).filter(
        _raw_ids_for_kind("成交公告", ""),
        publish_time__date__gte=start,
        publish_time__date__lt=end,
    ).values("id")
    rows = (
        NoticeParsed.objects.filter(
            notice_raw_id__in=raw_ids,
            publish_time__date__gte=start,
            publish_time__date__lt=end,
        )
        .annotate(month=TruncMonth("publish_time"))
        .values("month")
        .annotate(total=Sum("deal_amount"))
    )
    totals: dict[str, float] = {}
    for row in rows:
        month = row["month"]
        if not month:
            continue
        key = month.strftime("%Y-%m") if hasattr(month, "strftime") else str(month)[:7]
        totals[key] = _money(row["total"])
    # 保证横轴至少覆盖查询起点月份
    if keys and chart_start.isoformat()[:7] not in keys:
        keys = [chart_start.strftime("%Y-%m")] + keys
    return [{"month": key, "amount": totals.get(key, 0)} for key in keys]


def _empty_notice_stats(
    site_ids: list[str] | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    today = timezone.localdate()
    range_start = start or (today - timedelta(days=13))
    range_end = end or (today + timedelta(days=1))
    daily_keys = _daily_keys_between(range_start, range_end)
    month_keys = _month_keys_between(range_start, range_end) or _recent_month_keys(today, 6)
    return {
        "publicNoticeTotal": 0,
        "todayCount": 0,
        "weekCount": 0,
        "lastMonthPurchaseAmount": 0,
        "lastMonthDealAmount": 0,
        "purchaseAmount": 0,
        "dealAmount": 0,
        "bySite": [],
        "byKind": [],
        "daily": [{"date": key, "count": 0} for key in daily_keys],
        "monthlyDeal": [{"month": key, "amount": 0} for key in month_keys],
        "sites": site_options(site_ids),
        "noticeKinds": PORTAL_NOTICE_KINDS,
        "dealKinds": list(DEAL_KINDS),
        "startDate": range_start.isoformat(),
        "endDate": (range_end - timedelta(days=1)).isoformat(),
    }


def _kind_label(site_id: str | None, notice_type) -> str:
    code = str(notice_type).strip() if notice_type not in (None, "") else ""
    if not code:
        return "其他"
    return NOTICE_TYPE_LABELS.get(site_id or "", {}).get(code) or "其他"


def build_notice_stats(
    site_ids: list[str] | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """公告库汇总。start/end 为 [start, end) 的 date；缺省则按近况窗口。"""
    today = timezone.localdate()
    range_start = start or (today - timedelta(days=13))
    range_end = end or (today + timedelta(days=1))
    stats = _empty_notice_stats(site_ids, start=range_start, end=range_end)
    try:
        week_start = today - timedelta(days=6)
        raw_qs = _raw_base_qs(site_ids).filter(
            publish_time__date__gte=range_start,
            publish_time__date__lt=range_end,
        )
        stats["publicNoticeTotal"] = raw_qs.count()
        stats["todayCount"] = raw_qs.filter(publish_time__date=today).count()
        stats["weekCount"] = raw_qs.filter(publish_time__date__gte=week_start).count()
        purchase = _kind_amount("采购公告", "budget_amount", range_start, range_end, site_ids)
        deal = _kind_amount("成交公告", "deal_amount", range_start, range_end, site_ids)
        stats["purchaseAmount"] = purchase
        stats["dealAmount"] = deal
        # 兼容旧字段名（前端逐步改为区间语义标签）
        stats["lastMonthPurchaseAmount"] = purchase
        stats["lastMonthDealAmount"] = deal
        stats["monthlyDeal"] = _monthly_deal_amounts(site_ids, start=range_start, end=range_end)
        stats["bySite"] = [
            {
                "siteId": row["site_id"] or "",
                "label": SITE_LABELS.get(row["site_id"] or "", row["site_id"] or "未标注"),
                "count": row["count"],
            }
            for row in raw_qs.values("site_id").annotate(count=Count("id")).order_by("-count")
        ]
        kind_counts: dict[str, int] = {}
        for row in raw_qs.values("site_id", "notice_type").annotate(count=Count("id")):
            label = _kind_label(row["site_id"], row["notice_type"])
            kind_counts[label] = kind_counts.get(label, 0) + row["count"]
        stats["byKind"] = [
            {"kind": kind, "count": count}
            for kind, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        daily_map = {item["date"]: 0 for item in stats["daily"]}
        chart_start = date.fromisoformat(stats["daily"][0]["date"]) if stats["daily"] else range_start
        rows = (
            raw_qs.filter(publish_time__date__gte=chart_start)
            .annotate(day=TruncDate("publish_time"))
            .values("day")
            .annotate(count=Count("id"))
        )
        for row in rows:
            day = row["day"]
            if not day:
                continue
            key = day.isoformat() if hasattr(day, "isoformat") else str(day)[:10]
            if key in daily_map:
                daily_map[key] = row["count"]
        stats["daily"] = [{"date": key, "count": daily_map[key]} for key in daily_map]
        stats["startDate"] = range_start.isoformat()
        stats["endDate"] = (range_end - timedelta(days=1)).isoformat()
    except (ProgrammingError, OperationalError):
        return _empty_notice_stats(site_ids, start=range_start, end=range_end)
    return stats


@require_http_methods(["GET"])
def portal_notices(request):
    record, error = require_portal(request, "portal.notice.view")
    if error:
        return error
    account = public_account(record)
    scope = account_site_scope(account)
    page = int(request.GET.get("page") or 1)
    page_size = int(request.GET.get("page_size") or request.GET.get("pageSize") or 10)
    try:
        payload = query_crawled_notices(
            page=page,
            page_size=page_size,
            search=(request.GET.get("search") or "").strip(),
            site_id=(request.GET.get("siteId") or "").strip(),
            notice_kind=(request.GET.get("noticeKind") or "").strip(),
            site_ids=scope,
        )
    except (ProgrammingError, OperationalError):
        payload = {"items": [], "total": 0, "page": page, "page_size": page_size}
    payload["sites"] = site_options(scope)
    payload["noticeKinds"] = PORTAL_NOTICE_KINDS
    return JsonResponse(payload)


@csrf_exempt
@require_http_methods(["POST"])
def portal_login(request):
    try:
        import json

        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "请输入账号和密码。"}, status=400)
    phone = str(payload.get("phone") or payload.get("identifier") or "").strip()
    password = str(payload.get("password") or "")
    if not phone or not password:
        return JsonResponse({"detail": "请输入账号和密码。"}, status=400)
    record = find_portal_account(phone, password)
    if not record:
        disabled = CustomerAccountRecord.objects.filter(is_deleted=False, phone=phone, status="停用").exists()
        if disabled:
            return JsonResponse({"detail": "账号已停用，请联系管理员。"}, status=403)
        return JsonResponse({"detail": "账号或密码错误。"}, status=401)
    return issue_portal_cookie(JsonResponse({"data": public_account(record)}), record.id)


@csrf_exempt
@require_http_methods(["POST"])
def portal_logout(request):
    return clear_portal_cookie(JsonResponse({"ok": True}))


@require_http_methods(["GET"])
def portal_me(request):
    record, error = require_portal(request)
    if error:
        return error
    return JsonResponse({"data": public_account(record)})


@csrf_exempt
@require_http_methods(["PUT"])
def portal_subscription(request):
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    try:
        import json

        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "订阅内容无效。"}, status=400)
    data = dict(record.data or {})
    data["subscription"] = {
        "enabled": bool(payload.get("enabled")),
        "keywords": str(payload.get("keywords") or "").strip(),
    }
    record.data = data
    record.save(update_fields=["data", "updated_at"])
    return JsonResponse({"data": public_account(record)})


@require_http_methods(["GET"])
def portal_notices_view(request):
    return portal_notices(request)


@require_http_methods(["GET"])
def portal_stats_view(request):
    return portal_stats(request)


def portal_stats(request):
    record, error = require_portal(request, "portal.stats.view")
    if error:
        return error
    account = public_account(record)
    scope = account_site_scope(account)
    # 可选：只看某一授权站点（首页分平台卡片 / 下钻）
    focus_site = (request.GET.get("siteId") or "").strip()
    effective_scope = scope
    if focus_site:
        if scope is not None and focus_site not in scope:
            effective_scope = []
        else:
            effective_scope = [focus_site]
    start_date = (request.GET.get("startDate") or request.GET.get("start_date") or "").strip()
    end_date = (request.GET.get("endDate") or request.GET.get("end_date") or "").strip()
    period = normalize_stats_period(
        (request.GET.get("period") or "this_month").strip(),
        start_date,
        end_date,
    )
    bound_start, bound_end = period_bounds(period, start_date=start_date, end_date=end_date)
    range_start = bound_start.date()
    range_end = bound_end.date()
    stats = build_notice_stats(site_ids=effective_scope, start=range_start, end=range_end)
    if stats["publicNoticeTotal"] == 0 and effective_scope is None and period == "this_month":
        legacy_total = list_public_notices(page=1, page_size=1, search="", notice_kind="").get("total", 0)
        if legacy_total and not stats["bySite"]:
            stats["publicNoticeTotal"] = legacy_total
    tag_stats = safe_stats(
        period=period,
        province=(request.GET.get("province") or "").strip(),
        buyer=(request.GET.get("buyer") or "").strip(),
        deal_kind=(request.GET.get("deal_kind") or request.GET.get("dealKind") or "").strip(),
        site_ids=effective_scope,
        start_date=start_date,
        end_date=end_date,
    )
    payload = {
        "customerName": account["customerName"] or account["name"],
        "subscriptionEnabled": account["subscription"]["enabled"],
        "allowedSiteIds": account.get("allowedSiteIds"),
        "siteScope": account.get("siteScope") or "all",
        "period": period,
        **stats,
        "tagStats": tag_stats,
    }
    # 首页：附带各可查看平台的独立统计（单平台时前端只展示一块）
    if (request.GET.get("includeSites") or "") in {"1", "true", "yes"}:
        sites = site_options(scope)
        payload["siteStats"] = [
            {
                "siteId": site["id"],
                "label": site["label"],
                **build_notice_stats(site_ids=[site["id"]], start=range_start, end=range_end),
            }
            for site in sites
        ]
    return JsonResponse({"data": payload})
