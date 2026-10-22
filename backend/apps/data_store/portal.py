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


def _previous_month_range(today: date) -> tuple[date, date]:
    first_this_month = today.replace(day=1)
    first_last_month = (first_this_month - timedelta(days=1)).replace(day=1)
    return first_last_month, first_this_month


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


def _kind_amount(kind: str, field: str, start: date, end: date) -> float:
    raw_ids = NoticeRaw.objects.filter(
        _raw_ids_for_kind(kind, ""),
        publish_time__date__gte=start,
        publish_time__date__lt=end,
    ).values("id")
    total = NoticeParsed.objects.filter(notice_raw_id__in=raw_ids).aggregate(total=Sum(field))["total"]
    return _money(total)


def _monthly_deal_amounts(today: date) -> list[dict]:
    keys = _recent_month_keys(today, 6)
    start = date.fromisoformat(keys[0] + "-01")
    raw_ids = NoticeRaw.objects.filter(
        _raw_ids_for_kind("成交公告", ""),
        publish_time__date__gte=start,
    ).values("id")
    rows = (
        NoticeParsed.objects.filter(notice_raw_id__in=raw_ids, publish_time__date__gte=start)
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
    return [{"month": key, "amount": totals.get(key, 0)} for key in keys]


def _empty_notice_stats() -> dict:
    today = timezone.localdate()
    daily = [{"date": (today - timedelta(days=offset)).isoformat(), "count": 0} for offset in range(13, -1, -1)]
    return {
        "publicNoticeTotal": 0,
        "todayCount": 0,
        "weekCount": 0,
        "lastMonthPurchaseAmount": 0,
        "lastMonthDealAmount": 0,
        "bySite": [],
        "byKind": [],
        "daily": daily,
        "monthlyDeal": [{"month": key, "amount": 0} for key in _recent_month_keys(today, 6)],
        "sites": [{"id": key, "label": label} for key, label in SITE_LABELS.items()],
        "noticeKinds": PORTAL_NOTICE_KINDS,
    }


def _kind_label(site_id: str | None, notice_type) -> str:
    code = str(notice_type).strip() if notice_type not in (None, "") else ""
    if not code:
        return "其他"
    return NOTICE_TYPE_LABELS.get(site_id or "", {}).get(code) or "其他"


def build_notice_stats() -> dict:
    """公告库汇总。表不存在时返回空结构，避免门户整页失败。"""
    stats = _empty_notice_stats()
    try:
        today = timezone.localdate()
        week_start = today - timedelta(days=6)
        trend_start = today - timedelta(days=13)
        stats["publicNoticeTotal"] = NoticeRaw.objects.count()
        stats["todayCount"] = NoticeRaw.objects.filter(publish_time__date=today).count()
        stats["weekCount"] = NoticeRaw.objects.filter(publish_time__date__gte=week_start).count()
        last_start, last_end = _previous_month_range(today)
        stats["lastMonthPurchaseAmount"] = _kind_amount("采购公告", "budget_amount", last_start, last_end)
        stats["lastMonthDealAmount"] = _kind_amount("成交公告", "deal_amount", last_start, last_end)
        stats["monthlyDeal"] = _monthly_deal_amounts(today)
        stats["bySite"] = [
            {
                "siteId": row["site_id"] or "",
                "label": SITE_LABELS.get(row["site_id"] or "", row["site_id"] or "未标注"),
                "count": row["count"],
            }
            for row in NoticeRaw.objects.values("site_id").annotate(count=Count("id")).order_by("-count")
        ]
        kind_counts: dict[str, int] = {}
        for row in NoticeRaw.objects.values("site_id", "notice_type").annotate(count=Count("id")):
            label = _kind_label(row["site_id"], row["notice_type"])
            kind_counts[label] = kind_counts.get(label, 0) + row["count"]
        stats["byKind"] = [
            {"kind": kind, "count": count}
            for kind, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        daily_map = {item["date"]: 0 for item in stats["daily"]}
        rows = (
            NoticeRaw.objects.filter(publish_time__date__gte=trend_start)
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
    except (ProgrammingError, OperationalError):
        return _empty_notice_stats()
    return stats


@require_http_methods(["GET"])
def portal_notices(request):
    record, error = require_portal(request, "portal.notice.view")
    if error:
        return error
    page = int(request.GET.get("page") or 1)
    page_size = int(request.GET.get("page_size") or request.GET.get("pageSize") or 10)
    try:
        payload = query_crawled_notices(
            page=page,
            page_size=page_size,
            search=(request.GET.get("search") or "").strip(),
            site_id=(request.GET.get("siteId") or "").strip(),
            notice_kind=(request.GET.get("noticeKind") or "").strip(),
        )
    except (ProgrammingError, OperationalError):
        payload = {"items": [], "total": 0, "page": page, "page_size": page_size}
    payload["sites"] = [{"id": key, "label": label} for key, label in SITE_LABELS.items()]
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
    stats = build_notice_stats()
    if stats["publicNoticeTotal"] == 0:
        legacy_total = list_public_notices(page=1, page_size=1, search="", notice_kind="").get("total", 0)
        if legacy_total and not stats["bySite"]:
            stats["publicNoticeTotal"] = legacy_total
    return JsonResponse(
        {
            "data": {
                "customerName": account["customerName"] or account["name"],
                "subscriptionEnabled": account["subscription"]["enabled"],
                **stats,
            }
        }
    )
