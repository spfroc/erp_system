from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import hashlib
import html
import json
from urllib.parse import urlencode

from django.contrib.auth.hashers import check_password, identify_hasher, is_password_usable
from django.core import signing
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError, connection
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerAccountRecord
from .notice_inbox_models import PortalNoticeInbox
from .notice_models import NoticeGoods, NoticeParsed, NoticeRaw
from .notice_subscription import normalize_subscription, subscription_has_filters
from .notice_tagging import DEAL_KINDS, normalize_stats_period, period_bounds, safe_stats
from .notice_views import (
    NOTICE_TYPE_LABELS,
    SITE_LABELS,
    _serialize_detail,
    query_crawled_notices,
)
from . import wechat_mp
PORTAL_COOKIE = "portal_session"
PORTAL_SALT = "portal-account"
PORTAL_MAX_AGE = 60 * 60 * 12
PORTAL_PERMISSIONS = (
    "portal.notice.view",
    "portal.notice.subscribe",
    "portal.stats.view",
    "portal.order.view",
    "portal.invoice.view",
    "portal.contract.view",
    "portal.account.view",
    "portal.account.manage",
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
    subscription = normalize_subscription(
        data.get("subscription") if isinstance(data.get("subscription"), dict) else {}
    )
    # 兼容旧前端：keywords 仍可为字符串
    data["subscription"] = {
        **subscription,
        "keywords": subscription.get("keywordsText") or " ".join(subscription.get("keywords") or []),
    }
    wechat = data.get("wechat") if isinstance(data.get("wechat"), dict) else {}
    openid = str(wechat.get("openid") or "").strip()
    data["wechatBound"] = bool(openid)
    data["wechatFollowStatus"] = str(wechat.get("followStatus") or ("subscribed" if openid else "unknown"))
    data.pop("wechat", None)
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
    subscription = normalize_subscription(
        payload.get("subscription") if isinstance(payload.get("subscription"), dict) else {}
    )
    data = {
        **payload,
        "permissions": permissions,
        "subscription": {
            **subscription,
            "keywords": subscription.get("keywordsText") or " ".join(subscription.get("keywords") or []),
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
    data.pop("wechatBound", None)
    data.pop("wechatFollowStatus", None)
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
    if not is_password_usable(stored_password):
        return False
    try:
        identify_hasher(stored_password)
    except ValueError:
        return stored_password == raw_password
    return check_password(raw_password, stored_password)


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
    perms = set(account["permissions"] or [])
    if permission and permission not in perms:
        # manage 蕴含 view（如 portal.account.manage → portal.account.view）
        implied = False
        if permission.endswith(".view"):
            manage_key = permission[: -len(".view")] + ".manage"
            implied = manage_key in perms
        if not implied:
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


def _publish_dt_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """公告 publish_time 为上海墙钟 naive DATETIME。

    返回「墙钟数字 + UTC tzinfo」的 datetime，避免 USE_TZ 把 Asia/Shanghai 再减 8 小时后
    写出错误的 SQL 边界（并破坏索引范围）。
    """
    return (
        datetime(start.year, start.month, start.day, tzinfo=dt_timezone.utc),
        datetime(end.year, end.month, end.day, tzinfo=dt_timezone.utc),
    )


def _wall_sql(value: datetime | date | str) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return f"{value.isoformat()} 00:00:00"
    text = str(value).strip().replace("T", " ")
    return text[:19] if len(text) >= 19 else (text + " 00:00:00")[:19]


def _site_id_sql(site_ids: list[str] | None) -> tuple[str, list[str]]:
    """返回 (AND site_id IN (...), params)。site_ids is None 表示不限。"""
    if site_ids is None:
        return "", []
    if not site_ids:
        return " AND 1=0", []
    placeholders = ", ".join(["%s"] * len(site_ids))
    return f" AND site_id IN ({placeholders})", [str(sid) for sid in site_ids]


_MYSQL_INDEX_EXISTS_CACHE: dict[tuple[str, str], bool] = {}


def _mysql_index_exists(table: str, index_name: str) -> bool:
    """缓存 information_schema 查询；索引缺失时禁止 FORCE INDEX，避免统计整段被吞成空。"""
    key = (table, index_name)
    cached = _MYSQL_INDEX_EXISTS_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s "
                "LIMIT 1",
                [table, index_name],
            )
            exists = cursor.fetchone() is not None
    except (ProgrammingError, OperationalError):
        exists = False
    _MYSQL_INDEX_EXISTS_CACHE[key] = exists
    return exists


def _force_index_clause(table: str, *candidates: str) -> str:
    """返回 ' FORCE INDEX (name)'；候选均不存在时返回空串（让优化器自选）。"""
    for name in candidates:
        if name and _mysql_index_exists(table, name):
            return f" FORCE INDEX ({name})"
    return ""


def _parsed_force_index_clause(site_ids: list[str] | None = None) -> str:
    """优先覆盖索引，避免回表读大 JSON；不存在则逐级回退，最后不强制。"""
    preferred = "idx_parsed_stats_cover"
    if site_ids is not None:
        fallbacks = ("idx_parsed_site_publish", "idx_parsed_publish_time", "idx_parsed_publish_raw")
    else:
        fallbacks = ("idx_parsed_publish_raw", "idx_parsed_publish_time", "idx_parsed_site_publish")
    return _force_index_clause("notice_parsed", preferred, *fallbacks)


def _raw_force_index_clause(site_ids: list[str] | None = None) -> str:
    # 有 site 过滤时优先 (site_id, publish_time)；全站时优先 publish_time 系索引
    if site_ids is not None:
        return _force_index_clause(
            "notice_raw",
            "idx_raw_site_publish",
            "idx_raw_publish_id",
            "idx_publish_time",
        )
    return _force_index_clause(
        "notice_raw",
        "idx_publish_time",
        "idx_raw_publish_id",
        "idx_raw_site_publish",
    )


def _sql_raw_site_counts(
    site_ids: list[str] | None,
    *,
    lo: datetime,
    hi: datetime,
    today_lo: datetime,
    today_hi: datetime,
    week_lo: datetime,
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """一次按站点聚合：区间总量 / 今日 / 近 7 日。"""
    site_sql, site_params = _site_id_sql(site_ids)
    force = _raw_force_index_clause(site_ids)
    sql = (
        "SELECT site_id, "
        "COUNT(*), "
        "SUM(publish_time >= %s AND publish_time < %s), "
        "SUM(publish_time >= %s AND publish_time < %s) "
        f"FROM notice_raw{force} "
        f"WHERE publish_time >= %s AND publish_time < %s{site_sql} "
        "GROUP BY site_id"
    )
    params = [
        _wall_sql(today_lo),
        _wall_sql(today_hi),
        _wall_sql(week_lo),
        _wall_sql(today_hi),
        _wall_sql(lo),
        _wall_sql(hi),
        *site_params,
    ]
    range_counts: dict[str, int] = {}
    today_counts: dict[str, int] = {}
    week_counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        for sid, total, today_c, week_c in cursor.fetchall():
            key = str(sid or "")
            range_counts[key] = int(total or 0)
            today_counts[key] = int(today_c or 0)
            week_counts[key] = int(week_c or 0)
    return range_counts, today_counts, week_counts


def _sql_parsed_kind_rows(site_ids: list[str] | None, lo: datetime, hi: datetime):
    """按站点+类型聚合数量与金额；按是否限站点选择最优索引。"""
    site_sql, site_params = _site_id_sql(site_ids)
    force = _parsed_force_index_clause(site_ids)
    sql = (
        "SELECT site_id, notice_kind, COUNT(*), SUM(budget_amount), SUM(deal_amount) "
        f"FROM notice_parsed{force} "
        f"WHERE publish_time >= %s AND publish_time < %s{site_sql} "
        "GROUP BY site_id, notice_kind"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [_wall_sql(lo), _wall_sql(hi), *site_params])
        return cursor.fetchall()


def _sql_parsed_site_amounts(site_ids: list[str] | None, lo: datetime, hi: datetime) -> tuple[dict[str, float], dict[str, float]]:
    """分站点采购/成交金额（仅两类公告）。"""
    site_sql, site_params = _site_id_sql(site_ids)
    force = _parsed_force_index_clause(site_ids)
    sql = (
        "SELECT site_id, "
        "SUM(CASE WHEN notice_kind = '采购公告' THEN budget_amount ELSE 0 END), "
        "SUM(CASE WHEN notice_kind = '成交公告' THEN deal_amount ELSE 0 END) "
        f"FROM notice_parsed{force} "
        f"WHERE publish_time >= %s AND publish_time < %s "
        f"AND notice_kind IN ('采购公告', '成交公告'){site_sql} "
        "GROUP BY site_id"
    )
    purchase_map: dict[str, float] = {}
    deal_map: dict[str, float] = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, [_wall_sql(lo), _wall_sql(hi), *site_params])
        for sid, budget, deal in cursor.fetchall():
            key = str(sid or "")
            purchase_map[key] = _money(budget)
            deal_map[key] = _money(deal)
    return purchase_map, deal_map


def _sql_daily_counts(site_ids: list[str] | None, lo: datetime, hi: datetime) -> dict[str, int]:
    site_sql, site_params = _site_id_sql(site_ids)
    force = _raw_force_index_clause(site_ids)
    sql = (
        f"SELECT DATE(publish_time), COUNT(*) FROM notice_raw{force} "
        f"WHERE publish_time >= %s AND publish_time < %s{site_sql} "
        "GROUP BY DATE(publish_time)"
    )
    out: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, [_wall_sql(lo), _wall_sql(hi), *site_params])
        for day, count in cursor.fetchall():
            if not day:
                continue
            key = day.isoformat() if hasattr(day, "isoformat") else str(day)[:10]
            out[key] = int(count or 0)
    return out


def build_site_metric_stats(
    sites: list[dict],
    *,
    start: date,
    end: date,
    range_counts: dict[str, int] | None = None,
    today_counts: dict[str, int] | None = None,
    week_counts: dict[str, int] | None = None,
    purchase_map: dict[str, float] | None = None,
    deal_map: dict[str, float] | None = None,
) -> list[dict]:
    """分平台指标卡。可传入已算好的聚合结果，避免重复扫表。"""
    if not sites:
        return []
    today = timezone.localdate()
    lo, hi = _publish_dt_bounds(start, end)
    today_lo, today_hi = _publish_dt_bounds(today, today + timedelta(days=1))
    week_lo, _ = _publish_dt_bounds(today - timedelta(days=6), end)
    site_ids = [str(site["id"]) for site in sites]

    try:
        if range_counts is None or today_counts is None or week_counts is None:
            rc, tc, wc = _sql_raw_site_counts(
                site_ids, lo=lo, hi=hi, today_lo=today_lo, today_hi=today_hi, week_lo=week_lo
            )
            range_counts = range_counts if range_counts is not None else rc
            today_counts = today_counts if today_counts is not None else tc
            week_counts = week_counts if week_counts is not None else wc
        if purchase_map is None or deal_map is None:
            pm, dm = _sql_parsed_site_amounts(site_ids, lo, hi)
            purchase_map = purchase_map if purchase_map is not None else pm
            deal_map = deal_map if deal_map is not None else dm
    except (ProgrammingError, OperationalError):
        range_counts = range_counts or {}
        today_counts = today_counts or {}
        week_counts = week_counts or {}
        purchase_map = purchase_map or {}
        deal_map = deal_map or {}

    start_date = start.isoformat()
    end_date = (end - timedelta(days=1)).isoformat()
    result: list[dict] = []
    for site in sites:
        sid = str(site["id"])
        purchase = (purchase_map or {}).get(sid, 0.0)
        deal = (deal_map or {}).get(sid, 0.0)
        result.append(
            {
                "siteId": sid,
                "label": site.get("label") or SITE_LABELS.get(sid, sid),
                "publicNoticeTotal": (range_counts or {}).get(sid, 0),
                "todayCount": (today_counts or {}).get(sid, 0),
                "weekCount": (week_counts or {}).get(sid, 0),
                "purchaseAmount": purchase,
                "dealAmount": deal,
                "lastMonthPurchaseAmount": purchase,
                "lastMonthDealAmount": deal,
                "monthlyDeal": [],
                "daily": [],
                "bySite": [],
                "byKind": [],
                "startDate": start_date,
                "endDate": end_date,
            }
        )
    return result


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
    lo, hi = _publish_dt_bounds(start, end)
    site_sql, site_params = _site_id_sql(site_ids)
    force = _parsed_force_index_clause(site_ids)
    sql = (
        "SELECT LEFT(publish_time, 7), SUM(deal_amount) "
        f"FROM notice_parsed{force} "
        f"WHERE notice_kind = '成交公告' AND publish_time >= %s AND publish_time < %s{site_sql} "
        "GROUP BY LEFT(publish_time, 7)"
    )
    totals: dict[str, float] = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, [_wall_sql(lo), _wall_sql(hi), *site_params])
        for month_key, total in cursor.fetchall():
            if not month_key:
                continue
            totals[str(month_key)[:7]] = _money(total)
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
    light: bool = False,
    with_site_maps: bool = False,
) -> dict:
    """公告库汇总。start/end 为 [start, end) 的 date；缺省则按近况窗口。

    light=True：只算指标卡所需字段，跳过图表序列。
    with_site_maps=True：附带 _siteMaps 供分平台指标卡复用，避免二次扫表。
    """
    today = timezone.localdate()
    range_start = start or (today - timedelta(days=13))
    range_end = end or (today + timedelta(days=1))
    stats = _empty_notice_stats(site_ids, start=range_start, end=range_end)
    try:
        week_start = today - timedelta(days=6)
        lo, hi = _publish_dt_bounds(range_start, range_end)
        today_lo, today_hi = _publish_dt_bounds(today, today + timedelta(days=1))
        week_lo, _ = _publish_dt_bounds(week_start, today + timedelta(days=1))

        # 1) 一次按站点聚合：区间总量 + 今日 + 近7日
        range_counts, today_counts, week_counts = _sql_raw_site_counts(
            site_ids, lo=lo, hi=hi, today_lo=today_lo, today_hi=today_hi, week_lo=week_lo
        )
        stats["publicNoticeTotal"] = sum(range_counts.values())
        stats["todayCount"] = sum(today_counts.values())
        stats["weekCount"] = sum(week_counts.values())
        stats["bySite"] = [
            {
                "siteId": sid,
                "label": SITE_LABELS.get(sid, sid or "未标注"),
                "count": range_counts[sid],
            }
            for sid in sorted(range_counts.keys(), key=lambda key: (-range_counts[key], key))
        ]

        # 2) 解析表一次按站点+类型聚合：类型分布 + 采购/成交金额（FORCE INDEX publish）
        purchase = 0.0
        deal = 0.0
        purchase_map: dict[str, float] = {}
        deal_map: dict[str, float] = {}
        kind_counts: dict[str, int] = {}
        for sid_raw, kind_raw, count, budget, deal_sum in _sql_parsed_kind_rows(site_ids, lo, hi):
            sid = str(sid_raw or "")
            kind = (kind_raw or "").strip() or "其他"
            kind_counts[kind] = kind_counts.get(kind, 0) + int(count or 0)
            if kind == "采购公告":
                amount = _money(budget)
                purchase += amount
                purchase_map[sid] = purchase_map.get(sid, 0.0) + amount
            elif kind == "成交公告":
                amount = _money(deal_sum)
                deal += amount
                deal_map[sid] = deal_map.get(sid, 0.0) + amount

        stats["purchaseAmount"] = purchase
        stats["dealAmount"] = deal
        stats["lastMonthPurchaseAmount"] = purchase
        stats["lastMonthDealAmount"] = deal
        stats["startDate"] = range_start.isoformat()
        stats["endDate"] = (range_end - timedelta(days=1)).isoformat()
        stats["byKind"] = [
            {"kind": kind, "count": count}
            for kind, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        if with_site_maps:
            stats["_siteMaps"] = {
                "range_counts": range_counts,
                "today_counts": today_counts,
                "week_counts": week_counts,
                "purchase_map": purchase_map,
                "deal_map": deal_map,
            }

        if light:
            stats["monthlyDeal"] = []
            stats["daily"] = []
            return stats

        # 3) 日发布量
        daily_map = {item["date"]: 0 for item in stats["daily"]}
        for key, count in _sql_daily_counts(site_ids, lo, hi).items():
            if key in daily_map:
                daily_map[key] = count
        stats["daily"] = [{"date": key, "count": daily_map[key]} for key in daily_map]

        # 4) 月成交：单月窗口直接复用区间成交额，避免再扫解析表
        month_keys = _month_keys_between(range_start, range_end)
        if len(month_keys) == 1:
            stats["monthlyDeal"] = [{"month": month_keys[0], "amount": deal}]
        else:
            stats["monthlyDeal"] = _monthly_deal_amounts(site_ids, start=range_start, end=range_end)
    except (ProgrammingError, OperationalError):
        return _empty_notice_stats(site_ids, start=range_start, end=range_end)
    return stats


PUBLIC_CRAWLED_NOTICE_PAGE_SIZE_MAX = 20


def _public_crawled_notice_item(item: dict) -> dict:
    """官网公开列表/田字格字段；敏感详情仍需登录后查看。"""
    published = item.get("publishTime") or item.get("publishedAt") or ""
    return {
        "id": item.get("id"),
        "title": item.get("title") or "",
        "publishedAt": published,
        "publishTime": published,
        "noticeKind": item.get("noticeKind") or "",
        "siteId": item.get("siteId") or "",
        "siteLabel": item.get("siteLabel") or "",
        "regionName": item.get("regionName") or "",
        "buyerName": item.get("buyerName") or "",
        "projectName": item.get("projectName") or "",
        "projectCode": item.get("projectCode") or "",
        "progressStatus": item.get("progressStatus") or "",
        "progressLabel": item.get("progressLabel") or "",
        "budgetAmount": item.get("budgetAmount"),
        "dealAmount": item.get("dealAmount"),
    }


@require_http_methods(["GET"])
def public_crawled_notices(request):
    """匿名只读：爬虫公告列表，供官网首页田字格与壹采寻源。"""
    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(
            max(int(request.GET.get("page_size") or request.GET.get("pageSize") or 10), 1),
            PUBLIC_CRAWLED_NOTICE_PAGE_SIZE_MAX,
        )
    except (TypeError, ValueError):
        page_size = 10
    site_id = (request.GET.get("siteId") or "").strip()
    notice_kind = (request.GET.get("noticeKind") or "").strip()
    notice_kinds = (request.GET.get("noticeKinds") or request.GET.get("notice_kinds") or "").strip()
    try:
        payload = query_crawled_notices(
            page=page,
            page_size=page_size,
            search=(request.GET.get("search") or "").strip(),
            site_id=site_id,
            notice_kind=notice_kind,
            notice_kinds=notice_kinds,
            site_ids=None,
            publish_date_from=(request.GET.get("publishDateFrom") or request.GET.get("publish_date_from") or "").strip(),
            publish_date_to=(request.GET.get("publishDateTo") or request.GET.get("publish_date_to") or "").strip(),
            buyer_name=(request.GET.get("buyerName") or "").strip(),
            project_code=(request.GET.get("projectCode") or "").strip(),
            project_name=(request.GET.get("projectName") or "").strip(),
            region_name=(request.GET.get("regionName") or request.GET.get("region") or "").strip(),
            progress=(request.GET.get("progress") or "").strip(),
        )
    except (ProgrammingError, OperationalError):
        return JsonResponse(
            {
                "detail": "公告数据暂时不可用，请稍后重试。",
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            },
            status=503,
        )
    return JsonResponse(
        {
            "items": [_public_crawled_notice_item(item) for item in payload.get("items") or []],
            "total": payload.get("total") or 0,
            "page": payload.get("page") or page,
            "page_size": payload.get("page_size") or page_size,
            "sites": site_options(None),
            "noticeKinds": PORTAL_NOTICE_KINDS + ["意向公开", "结果公告", "成交结果公告"],
        }
    )


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
            notice_kinds=(request.GET.get("noticeKinds") or request.GET.get("notice_kinds") or "").strip(),
            site_ids=scope,
            publish_date_from=(request.GET.get("publishDateFrom") or request.GET.get("publish_date_from") or "").strip(),
            publish_date_to=(request.GET.get("publishDateTo") or request.GET.get("publish_date_to") or "").strip(),
            buyer_name=(request.GET.get("buyerName") or "").strip(),
            project_code=(request.GET.get("projectCode") or "").strip(),
            project_name=(request.GET.get("projectName") or "").strip(),
            region_name=(request.GET.get("regionName") or request.GET.get("region") or "").strip(),
            progress=(request.GET.get("progress") or "").strip(),
        )
    except (ProgrammingError, OperationalError):
        # 勿吞成空列表：前端会当成「无数据」，掩盖缺列/索引等真实故障
        return JsonResponse(
            {
                "detail": "公告数据暂时不可用，请稍后重试或联系管理员。",
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            },
            status=503,
        )
    payload["sites"] = site_options(scope)
    payload["noticeKinds"] = PORTAL_NOTICE_KINDS + ["意向公开", "结果公告", "成交结果公告"]
    return JsonResponse(payload)


@require_http_methods(["GET"])
def portal_notice_detail(request, notice_id: int):
    record, error = require_portal(request, "portal.notice.view")
    if error:
        return error
    account = public_account(record)
    scope = account_site_scope(account)
    try:
        raw = NoticeRaw.objects.filter(id=notice_id).first()
        if not raw:
            return JsonResponse({"detail": "公告不存在"}, status=404)
        if scope is not None and raw.site_id not in scope:
            return JsonResponse({"detail": "无权查看该公告"}, status=403)
        parsed = NoticeParsed.objects.filter(notice_raw_id=raw.id).first()
        goods = list(NoticeGoods.objects.filter(notice_raw_id=raw.id).order_by("line_no", "id"))
        return JsonResponse(_serialize_detail(raw, parsed, goods))
    except (ProgrammingError, OperationalError):
        return JsonResponse({"detail": "公告表尚未创建"}, status=503)


def _serialize_inbox_item(row: PortalNoticeInbox) -> dict:
    return {
        "id": row.id,
        "noticeId": row.notice_raw_id,
        "digestDate": row.digest_date.isoformat() if row.digest_date else "",
        "title": row.title or "",
        "projectName": row.project_name or "",
        "buyerName": row.buyer_name or "",
        "regionName": row.region_name or "",
        "siteId": row.site_id or "",
        "siteLabel": SITE_LABELS.get(row.site_id or "", row.site_id or ""),
        "isRead": bool(row.is_read),
        "readAt": row.read_at.isoformat() if row.read_at else "",
        "createdAt": row.created_at.isoformat() if row.created_at else "",
    }


@require_http_methods(["GET"])
def portal_messages(request):
    """订阅命中公告消息列表（微信推送跳转落地页）。"""
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    page = max(int(request.GET.get("page") or 1), 1)
    page_size = min(max(int(request.GET.get("page_size") or request.GET.get("pageSize") or 20), 1), 100)
    unread_only = str(request.GET.get("unread") or "").strip().lower() in {"1", "true", "yes"}
    qs = PortalNoticeInbox.objects.filter(customer_account_id=record.id).order_by("-created_at", "-id")
    if unread_only:
        qs = qs.filter(is_read=False)
    total = qs.count()
    unread_total = PortalNoticeInbox.objects.filter(customer_account_id=record.id, is_read=False).count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    return JsonResponse(
        {
            "items": [_serialize_inbox_item(row) for row in rows],
            "total": total,
            "unreadTotal": unread_total,
            "page": page,
            "page_size": page_size,
        }
    )


@csrf_exempt
@require_http_methods(["POST", "GET"])
def portal_message_detail(request, message_id: int):
    """查看消息：标记已读并返回关联公告详情。"""
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    row = PortalNoticeInbox.objects.filter(id=message_id, customer_account_id=record.id).first()
    if not row:
        return JsonResponse({"detail": "消息不存在"}, status=404)
    if not row.is_read:
        row.is_read = True
        row.read_at = timezone.now()
        row.save(update_fields=["is_read", "read_at", "updated_at"])

    account = public_account(record)
    notice_error = None
    detail = None
    if "portal.notice.view" in set(account.get("permissions") or []):
        scope = account_site_scope(account)
        try:
            raw = NoticeRaw.objects.filter(id=row.notice_raw_id).first()
            if not raw:
                notice_error = "公告不存在"
            elif scope is not None and raw.site_id not in scope:
                notice_error = "无权查看该公告"
            else:
                parsed = NoticeParsed.objects.filter(notice_raw_id=raw.id).first()
                goods = list(NoticeGoods.objects.filter(notice_raw_id=raw.id).order_by("line_no", "id"))
                detail = _serialize_detail(raw, parsed, goods)
        except (ProgrammingError, OperationalError):
            notice_error = "公告表尚未创建"
    else:
        notice_error = "无公告查看权限"

    return JsonResponse(
        {
            "message": _serialize_inbox_item(row),
            "notice": detail,
            "noticeError": notice_error,
        }
    )


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
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "订阅内容无效。"}, status=400)
    wanted_enabled = bool(payload.get("enabled"))
    normalized = normalize_subscription(payload)
    if wanted_enabled and not subscription_has_filters(normalized):
        return JsonResponse({"detail": "请至少设置标签、地区、关键词、采购人或单位中的一项。"}, status=400)
    account = public_account(record)
    if wanted_enabled and not account.get("wechatBound"):
        return JsonResponse({"detail": "请先绑定微信后再开启推送。"}, status=400)
    data = dict(record.data or {})
    data["subscription"] = {
        "enabled": normalized["enabled"],
        "keywords": normalized.get("keywordsText") or " ".join(normalized.get("keywords") or []),
        "contentTags": normalized.get("contentTags") or [],
        "regions": normalized.get("regions") or [],
        "buyers": normalized.get("buyers") or [],
        "orgTypes": normalized.get("orgTypes") or [],
    }
    record.data = data
    record.save(update_fields=["data", "updated_at"])
    return JsonResponse({"data": public_account(record)})


@require_http_methods(["GET"])
def portal_subscription_options(request):
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    from django.db.models import Count

    from .notice_dict import KIND_ORG_TYPE, list_dict_names
    from .notice_tag_models import NoticeResultTag

    content_tags = list(
        NoticeResultTag.objects.exclude(content_tag="")
        .values("content_tag")
        .annotate(total=Count("id"))
        .order_by("-total", "content_tag")
        .values_list("content_tag", flat=True)[:40]
    )
    # 兜底常用标签，避免库空时无法勾选
    for item in ("印刷", "运维服务", "办公用品", "空调", "LED屏幕", "车辆加油", "宣传项目", "家具", "计算机"):
        if item not in content_tags:
            content_tags.append(item)
    provinces = [
        "山东省",
        "北京市",
        "上海市",
        "天津市",
        "河北省",
        "河南省",
        "江苏省",
        "浙江省",
        "广东省",
        "四川省",
    ]
    return JsonResponse(
        {
            "contentTags": content_tags,
            "orgTypes": list(list_dict_names(KIND_ORG_TYPE, enabled_only=True))
            or ["机关", "教育", "医疗卫生", "公安系统", "事业单位", "其他"],
            "provinces": provinces,
            "wechatConfigured": wechat_mp.mp_configured(),
        }
    )


def _set_account_wechat(record: CustomerAccountRecord, *, openid: str, follow_status: str = "subscribed") -> None:
    data = dict(record.data or {})
    data["wechat"] = {
        "openid": openid,
        "boundAt": timezone.now().isoformat(),
        "followStatus": follow_status,
    }
    record.data = data
    record.save(update_fields=["data", "updated_at"])


def _clear_account_wechat(record: CustomerAccountRecord) -> None:
    data = dict(record.data or {})
    data.pop("wechat", None)
    record.data = data
    record.save(update_fields=["data", "updated_at"])


def _find_account_by_openid(openid: str) -> CustomerAccountRecord | None:
    openid = (openid or "").strip()
    if not openid:
        return None
    for record in CustomerAccountRecord.objects.filter(is_deleted=False).iterator(chunk_size=200):
        wechat = (record.data or {}).get("wechat") if isinstance(record.data, dict) else None
        if isinstance(wechat, dict) and str(wechat.get("openid") or "").strip() == openid:
            return record
    return None


@require_http_methods(["GET"])
def portal_wechat_bind_url(request):
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    if not wechat_mp.mp_configured():
        return JsonResponse({"detail": "微信服务号尚未配置，请联系管理员。"}, status=503)
    state = signing.dumps({"aid": record.id, "ts": timezone.now().timestamp()}, salt="portal-wechat-bind")
    url = wechat_mp.build_oauth_url(state=state)
    if not url:
        return JsonResponse({"detail": "无法生成微信授权链接，请检查回调域名配置。"}, status=503)
    return JsonResponse({"url": url, "wechatBound": public_account(record).get("wechatBound")})


@csrf_exempt
@require_http_methods(["POST"])
def portal_wechat_unbind(request):
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    data = dict(record.data or {})
    sub = data.get("subscription") if isinstance(data.get("subscription"), dict) else {}
    if sub:
        sub = dict(sub)
        sub["enabled"] = False
        data["subscription"] = sub
    data.pop("wechat", None)
    record.data = data
    record.save(update_fields=["data", "updated_at"])
    return JsonResponse({"data": public_account(record), "ok": True})


def _portal_bind_result_page(*, status: str) -> HttpResponse:
    """微信内 302 Location 带 #hash 常被代理剥掉，导致白页；改用结果页 + JS 跳转。"""
    status = (status or "fail").strip() or "fail"
    if status not in {"ok", "fail", "conflict"}:
        status = "fail"
    messages = {
        "ok": "微信绑定成功",
        "fail": "微信绑定失败，请重试",
        "conflict": "该微信已绑定其他账号",
    }
    title = messages[status]
    portal_home = (wechat_mp.portal_notice_url() or "/").rstrip("/") + "/"
    target = f"{portal_home}?{urlencode({'wechat': status})}#subscription"
    safe_title = html.escape(title)
    safe_href = html.escape(target, quote=True)
    js_target = json.dumps(target, ensure_ascii=False)
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f7f5; color: #17382d; }}
    .box {{ width: min(88vw, 360px); padding: 28px 22px; border-radius: 16px;
      background: #fff; box-shadow: 0 10px 30px rgba(23,56,45,.08); text-align: center; }}
    h1 {{ margin: 0 0 10px; font-size: 20px; }}
    p {{ margin: 0; color: #5b7368; font-size: 14px; line-height: 1.6; }}
    a {{ color: #1f7a57; }}
  </style>
</head>
<body>
  <div class="box">
    <h1>{safe_title}</h1>
    <p>正在返回订阅页面…</p>
    <p style="margin-top:12px"><a href="{safe_href}">如未自动跳转请点这里</a></p>
  </div>
  <script>location.replace({js_target});</script>
</body>
</html>"""
    return HttpResponse(page, content_type="text/html; charset=utf-8")


@csrf_exempt
@require_http_methods(["GET"])
def wechat_mp_oauth_callback(request):
    try:
        code = (request.GET.get("code") or "").strip()
        state = (request.GET.get("state") or "").strip()
        if not code or not state:
            return _portal_bind_result_page(status="fail")
        try:
            payload = signing.loads(state, salt="portal-wechat-bind", max_age=600)
        except signing.BadSignature:
            return _portal_bind_result_page(status="fail")
        account_id = str((payload or {}).get("aid") or "").strip()
        record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
        if not record or (record.status or "") != "启用":
            return _portal_bind_result_page(status="fail")
        exchanged = wechat_mp.exchange_oauth_code(code)
        openid = exchanged.get("openid") or ""
        if not openid:
            return _portal_bind_result_page(status="fail")
        existing = _find_account_by_openid(openid)
        if existing and existing.id != record.id:
            return _portal_bind_result_page(status="conflict")
        _set_account_wechat(record, openid=openid, follow_status="subscribed")
        return _portal_bind_result_page(status="ok")
    except Exception:  # noqa: BLE001
        return _portal_bind_result_page(status="fail")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def wechat_mp_callback(request):
    from django.http import HttpResponse

    signature = request.GET.get("signature") or ""
    timestamp = request.GET.get("timestamp") or ""
    nonce = request.GET.get("nonce") or ""
    echostr = request.GET.get("echostr") or ""
    if not wechat_mp.verify_callback_signature(signature=signature, timestamp=timestamp, nonce=nonce):
        return HttpResponse("invalid signature", status=403)
    if request.method == "GET":
        return HttpResponse(echostr)
    event = wechat_mp.parse_callback_xml(request.body or b"")
    msg_type = (event.get("MsgType") or "").lower()
    event_name = (event.get("Event") or "").lower()
    openid = (event.get("FromUserName") or "").strip()
    if msg_type == "event" and openid:
        record = _find_account_by_openid(openid)
        if record:
            data = dict(record.data or {})
            wechat = dict(data.get("wechat") or {})
            if event_name == "subscribe":
                wechat["followStatus"] = "subscribed"
                wechat["openid"] = openid
                data["wechat"] = wechat
                record.data = data
                record.save(update_fields=["data", "updated_at"])
            elif event_name == "unsubscribe":
                wechat["followStatus"] = "unsubscribed"
                data["wechat"] = wechat
                record.data = data
                record.save(update_fields=["data", "updated_at"])
    return HttpResponse("success")


@require_http_methods(["GET"])
def portal_notices_view(request):
    return portal_notices(request)


@require_http_methods(["GET"])
def portal_stats_view(request):
    return portal_stats(request)


PORTAL_STATS_CACHE_SECONDS = 60  # short TTL; LocMem per-process on one


def _portal_stats_cache_key(
    *,
    account_id: str,
    effective_scope: list[str] | None,
    period: str,
    start_date: str,
    end_date: str,
    include_notice: bool,
    include_tags: bool,
    include_sites: bool,
    province: str,
    buyer: str,
    deal_kind: str,
) -> str:
    scope_part = "all" if effective_scope is None else ",".join(sorted(effective_scope))
    raw = "|".join(
        [
            str(account_id),
            scope_part,
            period,
            start_date,
            end_date,
            "1" if include_notice else "0",
            "1" if include_tags else "0",
            "1" if include_sites else "0",
            province,
            buyer,
            deal_kind,
        ]
    )
    return "portal_stats:" + hashlib.md5(raw.encode("utf-8")).hexdigest()


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
        (request.GET.get("period") or "last_30_days").strip(),
        start_date,
        end_date,
    )
    bound_start, bound_end = period_bounds(period, start_date=start_date, end_date=end_date)
    range_start = bound_start.date()
    range_end = bound_end.date()
    include_notice = (request.GET.get("includeNoticeStats") or "1").strip().lower() not in {"0", "false", "no"}
    include_tags = (request.GET.get("includeTags") or "1").strip().lower() not in {"0", "false", "no"}
    include_sites = (request.GET.get("includeSites") or "") in {"1", "true", "yes"}
    province = (request.GET.get("province") or "").strip()
    buyer = (request.GET.get("buyer") or "").strip()
    deal_kind = (request.GET.get("deal_kind") or request.GET.get("dealKind") or "").strip()

    cache_key = _portal_stats_cache_key(
        account_id=str(record.id),
        effective_scope=effective_scope,
        period=period,
        start_date=start_date,
        end_date=end_date,
        include_notice=include_notice,
        include_tags=include_tags,
        include_sites=include_sites,
        province=province,
        buyer=buyer,
        deal_kind=deal_kind,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse({"data": cached})

    sites = site_options(scope)
    need_site_maps = include_sites and len(sites) > 1
    if include_notice:
        stats = build_notice_stats(
            site_ids=effective_scope,
            start=range_start,
            end=range_end,
            with_site_maps=need_site_maps,
        )
    else:
        stats = {
            **_empty_notice_stats(effective_scope, start=range_start, end=range_end),
            "sites": sites,
        }
    site_maps = stats.pop("_siteMaps", None) if isinstance(stats, dict) else None

    tag_stats = (
        safe_stats(
            period=period,
            province=province,
            buyer=buyer,
            deal_kind=deal_kind,
            site_ids=effective_scope,
            start_date=start_date,
            end_date=end_date,
        )
        if include_tags
        else {}
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
    # 首页：附带各可查看平台的独立统计（单平台时复用主汇总，避免二次全量查询）
    if include_sites:
        if len(sites) <= 1:
            payload["siteStats"] = [
                {
                    "siteId": site["id"],
                    "label": site["label"],
                    "publicNoticeTotal": stats.get("publicNoticeTotal", 0),
                    "todayCount": stats.get("todayCount", 0),
                    "weekCount": stats.get("weekCount", 0),
                    "purchaseAmount": stats.get("purchaseAmount", 0),
                    "dealAmount": stats.get("dealAmount", 0),
                    "lastMonthPurchaseAmount": stats.get("lastMonthPurchaseAmount", 0),
                    "lastMonthDealAmount": stats.get("lastMonthDealAmount", 0),
                    "monthlyDeal": stats.get("monthlyDeal") or [],
                    "daily": stats.get("daily") or [],
                    "bySite": stats.get("bySite") or [],
                    "byKind": stats.get("byKind") or [],
                    "startDate": stats.get("startDate"),
                    "endDate": stats.get("endDate"),
                }
                for site in sites
            ]
        else:
            payload["siteStats"] = build_site_metric_stats(
                sites,
                start=range_start,
                end=range_end,
                range_counts=(site_maps or {}).get("range_counts"),
                today_counts=(site_maps or {}).get("today_counts"),
                week_counts=(site_maps or {}).get("week_counts"),
                purchase_map=(site_maps or {}).get("purchase_map"),
                deal_map=(site_maps or {}).get("deal_map"),
            )
    cache.set(cache_key, payload, PORTAL_STATS_CACHE_SECONDS)
    return JsonResponse({"data": payload})
