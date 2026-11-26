from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import hashlib
import html
import json
import os
import secrets
import threading
import time
import uuid
from urllib.parse import quote, urlencode
from typing import Any, Callable

from django.conf import settings
from django.contrib.auth.hashers import check_password, identify_hasher, is_password_usable, make_password
from django.core import signing
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError, connection
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerAccountRecord, OrganizationRecord, PlatformAccountRecord, ProjectRecord
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
from .notices import clamp_public_publish_date_from

PORTAL_COOKIE = "portal_session"
PORTAL_SALT = "portal-account"
PORTAL_MAX_AGE = 60 * 60 * 12
PORTAL_HANDOFF_SALT = "portal-handoff"
PORTAL_HANDOFF_MAX_AGE = 120
PORTAL_PERMISSIONS = (
    "portal.notice.view",
    "portal.notice.subscribe",
    "portal.stats.view",
    "portal.order.view",
    "portal.invoice.view",
    "portal.contract.view",
    "portal.account.view",
    "portal.account.create",
    "portal.account.edit",
    "portal.account.delete",
    "portal.account.manage",  # 兼容旧数据：蕴含 view/create/edit/delete
)
PORTAL_ACCOUNT_ACTION_PERMISSIONS = (
    "portal.account.create",
    "portal.account.edit",
    "portal.account.delete",
)
PORTAL_PLATFORM_DEFAULT_PERMISSIONS = tuple(PORTAL_PERMISSIONS)
SERVICE_PROJECT_INACTIVE_STATUSES = frozenset({"服务到期结束", "项目终止"})
# 兼容：服务商品未配置 portalEntitlements 时，有效服务项目仍按全部门户权限开放
PORTAL_ACTIVE_SERVICE_DEFAULT_PERMISSIONS = tuple(PORTAL_PERMISSIONS)
PORTAL_BASELINE_PERMISSIONS = ("portal.notice.view", "portal.notice.subscribe")


def normalize_portal_permissions(value) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = set(PORTAL_PERMISSIONS)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in value:
        key = str(item or "").strip()
        if key in allowed and key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def expand_portal_permissions(value) -> list[str]:
    """规范化并展开 manage → view/create/edit/delete；任一写操作蕴含 view。"""
    perms = set(normalize_portal_permissions(value))
    if "portal.account.manage" in perms:
        perms.update({"portal.account.view", *PORTAL_ACCOUNT_ACTION_PERMISSIONS})
    elif perms.intersection(PORTAL_ACCOUNT_ACTION_PERMISSIONS):
        perms.add("portal.account.view")
    return [key for key in PORTAL_PERMISSIONS if key in perms]


def portal_permission_granted(perms, permission: str) -> bool:
    expanded = set(expand_portal_permissions(list(perms) if not isinstance(perms, list) else perms))
    if not permission:
        return True
    if permission in expanded:
        return True
    if permission.endswith(".view"):
        manage_key = permission[: -len(".view")] + ".manage"
        if manage_key in expanded:
            return True
    if permission in PORTAL_ACCOUNT_ACTION_PERMISSIONS and "portal.account.manage" in expanded:
        return True
    return False


def _product_configured_entitlements(product_data: dict | None) -> list[str] | None:
    """None = 未配置（兼容旧商品按全开）；list = 已配置的权限包（可为空）。"""
    if not isinstance(product_data, dict) or "portalEntitlements" not in product_data:
        return None
    return normalize_portal_permissions(product_data.get("portalEntitlements"))


def iter_active_service_projects(customer_org_id: str):
    org_id = str(customer_org_id or "").strip()
    if not org_id:
        return
    today = timezone.localdate()
    qs = ProjectRecord.objects.filter(
        is_deleted=False,
        customer_org_id=org_id,
    ).filter(Q(type="服务项目") | Q(data__type="服务项目"))
    for project in qs.only("id", "status", "type", "data").iterator(chunk_size=100):
        status = str(project.status or (project.data or {}).get("status") or "").strip()
        if status in SERVICE_PROJECT_INACTIVE_STATUSES:
            continue
        end = _parse_service_end_date((project.data or {}).get("serviceEndDate"))
        if end is None or end < today:
            continue
        yield project


def org_active_service_product_ids(customer_org_id: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for project in iter_active_service_projects(customer_org_id):
        product_id = str((project.data or {}).get("serviceProductId") or "").strip()
        if product_id and product_id not in seen:
            seen.add(product_id)
            ids.append(product_id)
    return ids


_ORG_ENTITLEMENT_CACHE: dict[str, tuple[float, list[str]]] = {}
_ORG_ENTITLEMENT_TTL_SEC = 60.0
_ORG_ACTIVE_CACHE: dict[str, tuple[float, bool]] = {}


def _cache_get(cache: dict[str, tuple[float, object]], key: str, ttl: float):
    hit = cache.get(key)
    if not hit:
        return None
    expires, value = hit
    if expires < time.monotonic():
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: dict[str, tuple[float, object]], key: str, value, ttl: float) -> None:
    cache[key] = (time.monotonic() + ttl, value)
    if len(cache) > 512:
        now = time.monotonic()
        stale = [k for k, (exp, _) in cache.items() if exp < now]
        for k in stale[:256]:
            cache.pop(k, None)


def org_portal_entitlements(customer_org_id: str) -> list[str]:
    """组织因有效期内服务商品获得的权限并集；无有效项目则仅基线公告权限。"""
    org_id = str(customer_org_id or "").strip()
    if not org_id:
        return list(PORTAL_BASELINE_PERMISSIONS)
    cached = _cache_get(_ORG_ENTITLEMENT_CACHE, org_id, _ORG_ENTITLEMENT_TTL_SEC)
    if isinstance(cached, list):
        return list(cached)

    product_ids: list[str] = []
    seen: set[str] = set()
    has_active = False
    for project in iter_active_service_projects(org_id):
        has_active = True
        product_id = str((project.data or {}).get("serviceProductId") or "").strip()
        if product_id and product_id not in seen:
            seen.add(product_id)
            product_ids.append(product_id)

    if not has_active:
        result = list(PORTAL_BASELINE_PERMISSIONS)
        _cache_set(_ORG_ENTITLEMENT_CACHE, org_id, result, _ORG_ENTITLEMENT_TTL_SEC)
        _cache_set(_ORG_ACTIVE_CACHE, org_id, False, _ORG_ENTITLEMENT_TTL_SEC)
        return result

    _cache_set(_ORG_ACTIVE_CACHE, org_id, True, _ORG_ENTITLEMENT_TTL_SEC)
    if not product_ids:
        # 有有效项目但未挂商品时，仍按旧行为全开
        result = list(PORTAL_ACTIVE_SERVICE_DEFAULT_PERMISSIONS)
        _cache_set(_ORG_ENTITLEMENT_CACHE, org_id, result, _ORG_ENTITLEMENT_TTL_SEC)
        return result

    from .models import ProductRecord

    union: set[str] = set()
    saw_unconfigured = False
    products = {
        str(row.id): (row.data if isinstance(row.data, dict) else {})
        for row in ProductRecord.objects.filter(id__in=product_ids, is_deleted=False).only("id", "data")
    }
    for product_id in product_ids:
        configured = _product_configured_entitlements(products.get(product_id))
        if configured is None:
            saw_unconfigured = True
            continue
        union.update(configured)
    if saw_unconfigured:
        # 任一未配置商品 → 兼容旧套餐：全部门户权限
        result = list(PORTAL_ACTIVE_SERVICE_DEFAULT_PERMISSIONS)
    elif not union:
        result = list(PORTAL_BASELINE_PERMISSIONS)
    else:
        result = expand_portal_permissions([key for key in PORTAL_PERMISSIONS if key in union])
    _cache_set(_ORG_ENTITLEMENT_CACHE, org_id, result, _ORG_ENTITLEMENT_TTL_SEC)
    return list(result)


def clamp_portal_permissions_to_org(permissions, customer_org_id: str) -> list[str]:
    caps = set(org_portal_entitlements(customer_org_id))
    return [item for item in normalize_portal_permissions(permissions) if item in caps]


def default_portal_permissions_for_org(customer_org_id: str) -> list[str]:
    """新建客户账号默认权限：取组织有效服务商品权限并集。"""
    return org_portal_entitlements(customer_org_id)


def ensure_active_service_portal_defaults(
    record: CustomerAccountRecord,
    *,
    has_active_service: bool | None = None,
) -> CustomerAccountRecord:
    """有有效服务项目时开放全部平台公告；不再强制把账号权限改成全开。"""
    org_id = str(record.customer_org_id or (record.data or {}).get("customerOrgId") or "").strip()
    active = org_has_active_service_project(org_id) if has_active_service is None else bool(has_active_service)
    if not active:
        return record
    data = dict(record.data or {})
    if "allowedSiteIds" not in data:
        return record
    data.pop("allowedSiteIds", None)
    record.data = data
    record.save(update_fields=["data", "updated_at"])
    return record


def effective_portal_permissions(
    record: CustomerAccountRecord,
    *,
    org_caps: list[str] | None = None,
) -> list[str]:
    org_id = str(record.customer_org_id or (record.data or {}).get("customerOrgId") or "").strip()
    caps = expand_portal_permissions(list(org_caps) if org_caps is not None else org_portal_entitlements(org_id))
    assigned = normalize_portal_permissions((record.data or {}).get("permissions"))
    if not assigned:
        return list(caps)
    cap_set = set(caps)
    return expand_portal_permissions([item for item in assigned if item in cap_set])
def _known_site_ids() -> set[str]:
    known = set(SITE_LABELS.keys())
    try:
        from .notice_site_config import list_enabled_sites

        for item in list_enabled_sites():
            sid = str(item.get("siteId") or "").strip()
            if sid:
                known.add(sid)
    except Exception:
        pass
    return known


def normalize_allowed_site_ids(value) -> list[str] | None:
    """None = 未配置（全部站点）；list = 白名单（空列表表示无站点）。"""
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    known = _known_site_ids()
    return [str(item).strip() for item in value if str(item).strip() in known]


def site_options(site_ids: list[str] | None = None) -> list[dict]:
    """优先使用管理后台「站点管理」启用项（含自定义名称/排序），失败时回退内置标签。"""
    try:
        from .notice_site_config import DEFAULT_SITES, list_enabled_sites

        enabled = list_enabled_sites()
        if not enabled:
            enabled = [
                {
                    "siteId": item["siteId"],
                    "label": item["label"],
                    "sortOrder": item.get("sortOrder") or 0,
                }
                for item in DEFAULT_SITES
            ]
        rows = sorted(
            enabled,
            key=lambda item: (int(item.get("sortOrder") or 0), int(item.get("id") or 0), str(item.get("siteId") or "")),
        )
        if site_ids is not None:
            allow = set(site_ids)
            rows = [item for item in rows if item.get("siteId") in allow]
        return [{"id": item["siteId"], "label": item["label"]} for item in rows if item.get("siteId")]
    except Exception:
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


def public_account(
    record: CustomerAccountRecord,
    *,
    org_caps: list[str] | None = None,
    has_active_service: bool | None = None,
    skip_ensure: bool = False,
) -> dict:
    if not skip_ensure:
        record = ensure_active_service_portal_defaults(record, has_active_service=has_active_service)
    data = dict(record.data or {})
    data.pop("password", None)
    data["id"] = record.id
    data["name"] = record.name or data.get("name") or ""
    data["phone"] = record.phone or data.get("phone") or ""
    data["customerName"] = record.customer_name or data.get("customerName") or ""
    data["customerOrgId"] = record.customer_org_id or data.get("customerOrgId") or ""
    data["status"] = record.status or data.get("status") or "启用"
    org_id = str(data["customerOrgId"] or "").strip()
    caps = list(org_caps) if org_caps is not None else org_portal_entitlements(org_id)
    data["orgEntitlements"] = caps
    data["permissions"] = effective_portal_permissions(record, org_caps=caps)
    subscription = normalize_subscription(
        data.get("subscription") if isinstance(data.get("subscription"), dict) else {}
    )
    # keywords 为数组；keywordsText 兼容旧表单
    data["subscription"] = {
        **subscription,
        "keywords": list(subscription.get("keywords") or []),
        "keywordsText": subscription.get("keywordsText")
        or " ".join(subscription.get("keywords") or []),
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
    org_id = str(payload.get("customerOrgId") or "").strip()
    permissions = normalize_portal_permissions(payload.get("permissions"))
    if org_id:
        if not permissions:
            permissions = default_portal_permissions_for_org(org_id)
        else:
            permissions = clamp_portal_permissions_to_org(permissions, org_id)
    subscription = normalize_subscription(
        payload.get("subscription") if isinstance(payload.get("subscription"), dict) else {}
    )
    data = {
        **payload,
        "permissions": permissions,
        "subscription": {
            **subscription,
            "keywords": list(subscription.get("keywords") or []),
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


def _plain_secret_matches(stored: str, raw: str) -> bool:
    stored = str(stored or "")
    raw = str(raw or "")
    if not stored or not raw:
        return False
    try:
        return secrets.compare_digest(stored, raw)
    except (TypeError, ValueError):
        return stored == raw


def _parse_service_end_date(value) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def org_has_active_service_project(customer_org_id: str) -> bool:
    org_id = str(customer_org_id or "").strip()
    if not org_id:
        return False
    cached = _cache_get(_ORG_ACTIVE_CACHE, org_id, _ORG_ENTITLEMENT_TTL_SEC)
    if isinstance(cached, bool):
        return cached
    # 顺带填充权限缓存，避免列表页重复扫项目表
    org_portal_entitlements(org_id)
    cached = _cache_get(_ORG_ACTIVE_CACHE, org_id, _ORG_ENTITLEMENT_TTL_SEC)
    if isinstance(cached, bool):
        return cached
    active = any(True for _ in iter_active_service_projects(org_id))
    _cache_set(_ORG_ACTIVE_CACHE, org_id, active, _ORG_ENTITLEMENT_TTL_SEC)
    return active


def find_platform_account_for_login(account_name: str, password: str) -> PlatformAccountRecord | None:
    name = str(account_name or "").strip()
    if not name or not password:
        return None
    candidates = list(
        PlatformAccountRecord.objects.filter(is_deleted=False)
        .filter(Q(account_name=name) | Q(data__accountName=name))
        .order_by("created_at", "id")[:50]
    )
    matched: list[PlatformAccountRecord] = []
    for record in candidates:
        data = record.data if isinstance(record.data, dict) else {}
        stored_name = str(data.get("accountName") or record.account_name or "").strip()
        if stored_name != name:
            continue
        stored_password = str(data.get("accountPasswordMasked") or "")
        if _plain_secret_matches(stored_password, password):
            matched.append(record)
    if not matched:
        return None
    if len(matched) == 1:
        return matched[0]
    # 同名多条时优先所属公司仍有有效服务的账号
    for record in matched:
        if org_has_active_service_project(record.customer_org_id or (record.data or {}).get("customerOrgId") or ""):
            return record
    return matched[0]


def resolve_portal_account_for_platform(platform_account: PlatformAccountRecord) -> CustomerAccountRecord:
    pa_id = str(platform_account.id)
    org_id = str(platform_account.customer_org_id or (platform_account.data or {}).get("customerOrgId") or "").strip()
    data = platform_account.data if isinstance(platform_account.data, dict) else {}
    account_name = str(data.get("accountName") or platform_account.account_name or "").strip()

    linked = (
        CustomerAccountRecord.objects.filter(
            is_deleted=False,
            status="启用",
            data__platformAccountId=pa_id,
        )
        .order_by("created_at", "id")
        .first()
    )
    if linked:
        return linked

    if org_id:
        existing = (
            CustomerAccountRecord.objects.filter(is_deleted=False, status="启用", customer_org_id=org_id)
            .order_by("created_at", "id")
            .first()
        )
        if existing:
            payload = dict(existing.data or {})
            if not payload.get("platformAccountId"):
                payload["platformAccountId"] = pa_id
                payload["loginSource"] = payload.get("loginSource") or "platformAccount"
                existing.data = payload
                existing.save(update_fields=["data", "updated_at"])
            return existing

    org = OrganizationRecord.objects.filter(id=org_id, is_deleted=False).only("id", "name").first() if org_id else None
    customer_name = (org.name if org else "") or str(data.get("customerName") or "").strip() or account_name or "平台账号客户"
    display_name = account_name or customer_name
    phone = f"pa-{pa_id}"[:50]
    new_id = f"ca-{uuid.uuid4().hex[:12]}"
    now = timezone.now()
    payload = {
        "id": new_id,
        "name": display_name,
        "phone": phone,
        "password": make_password(secrets.token_urlsafe(24)),
        "customerName": customer_name,
        "customerOrgId": org_id,
        "status": "启用",
        "permissions": default_portal_permissions_for_org(org_id),
        "subscription": {"enabled": False, "keywords": []},
        "platformAccountId": pa_id,
        "loginSource": "platformAccount",
    }
    return CustomerAccountRecord.objects.create(
        id=new_id,
        name=display_name,
        phone=phone,
        customer_name=customer_name,
        customer_org_id=org_id,
        status="启用",
        data=payload,
        created_at=now,
    )


# 门户与同主域官网共享登录态（portal.qlyc.co ↔ preview.qlyc.co 等）
PORTAL_COOKIE_PARENT_DOMAINS = (
    ".qlyc.co",
    ".qinghuicai.cn",
    ".yizhichan.co",
    ".jinanyunji.com",
)


def _request_hostname(request) -> str:
    if request is None:
        return ""
    forwarded = (request.META.get("HTTP_X_FORWARDED_HOST") or "").split(",")[0].strip()
    if forwarded:
        return forwarded.split(":")[0].strip().lower()
    try:
        host = request.get_host() or ""
    except Exception:
        host = (request.META.get("HTTP_HOST") or "").strip()
    return host.split(":")[0].strip().lower()


def portal_cookie_domain(request=None) -> str | None:
    """按请求 Host 选择可跨子域共享的 Cookie Domain；可用环境变量强制覆盖。"""
    forced = (os.getenv("PORTAL_COOKIE_DOMAIN") or "").strip()
    if forced:
        return forced if forced.startswith(".") else f".{forced.lstrip('.')}"
    host = _request_hostname(request)
    if not host or host in {"localhost", "127.0.0.1"} or host.endswith(".local"):
        return None
    for parent in PORTAL_COOKIE_PARENT_DOMAINS:
        root = parent[1:]
        if host == root or host.endswith(parent):
            return parent
    return None


def portal_return_to_allowed(url: str) -> bool:
    """仅允许跳回已知官网主域，防止 open redirect。"""
    text = str(url or "").strip()
    if not text:
        return False
    try:
        from urllib.parse import urlparse

        parsed = urlparse(text)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1"} or host.endswith(".local"):
        return True
    for parent in PORTAL_COOKIE_PARENT_DOMAINS:
        root = parent[1:]
        if host == root or host.endswith(parent):
            return True
    return False


def create_portal_handoff_code(account_id: str) -> str:
    return signing.dumps({"aid": str(account_id)}, salt=PORTAL_HANDOFF_SALT)


def consume_portal_handoff_code(code: str) -> str | None:
    raw = str(code or "").strip()
    if not raw:
        return None
    try:
        payload = signing.loads(raw, salt=PORTAL_HANDOFF_SALT, max_age=PORTAL_HANDOFF_MAX_AGE)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    account_id = str(payload.get("aid") or "").strip()
    return account_id or None


def _portal_cookie_secure(request=None) -> bool:
    if request is not None and hasattr(request, "is_secure"):
        try:
            if request.is_secure():
                return True
        except Exception:
            pass
    if (os.getenv("PORTAL_COOKIE_SECURE") or "").strip() in {"1", "true", "True", "yes"}:
        return True
    return not bool(getattr(settings, "DEBUG", True))


def issue_portal_cookie(response: JsonResponse, account_id: str, request=None) -> JsonResponse:
    token = signing.dumps(account_id, salt=PORTAL_SALT)
    kwargs = {
        "max_age": PORTAL_MAX_AGE,
        "httponly": True,
        "samesite": "Lax",
        "path": "/",
        "secure": _portal_cookie_secure(request),
    }
    domain = portal_cookie_domain(request)
    if domain:
        kwargs["domain"] = domain
    response.set_cookie(PORTAL_COOKIE, token, **kwargs)
    return response


def clear_portal_cookie(response: JsonResponse, request=None) -> JsonResponse:
    """清除 portal_session。

    须与 issue_portal_cookie 属性一致（Secure + 父域），否则浏览器不会删除。
    Django 同名 Cookie 只能写一条 Set-Cookie，优先清当前主域共享 cookie。
    """
    domain = portal_cookie_domain(request)
    secure = _portal_cookie_secure(request)
    response.set_cookie(
        PORTAL_COOKIE,
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        path="/",
        domain=domain,
        secure=secure,
        httponly=True,
        samesite="Lax",
    )
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
    perms = account.get("permissions") or []
    if permission and not portal_permission_granted(perms, permission):
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


PUBLIC_CRAWLED_NOTICE_PAGE_SIZE_MAX = 50


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
        "startTime": item.get("startTime") or "",
        "endTime": item.get("endTime") or "",
        "budgetAmount": item.get("budgetAmount"),
        "dealAmount": item.get("dealAmount"),
        "procurementMode": item.get("procurementMode") or "",
    }


PUBLIC_CRAWLED_CACHE_SECONDS = 90


@require_http_methods(["GET"])
def public_crawled_notices(request):
    """匿名只读：爬虫公告列表，供官网首页田字格与壹采寻源。"""
    query = request.META.get("QUERY_STRING") or ""
    cache_key = "public_crawled_notices:" + hashlib.md5(query.encode("utf-8")).hexdigest()
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return JsonResponse(cached)

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(
            max(int(request.GET.get("page_size") or request.GET.get("pageSize") or 20), 1),
            PUBLIC_CRAWLED_NOTICE_PAGE_SIZE_MAX,
        )
    except (TypeError, ValueError):
        page_size = 20
    site_id = (request.GET.get("siteId") or "").strip()
    notice_kind = (request.GET.get("noticeKind") or "").strip()
    notice_kinds = (request.GET.get("noticeKinds") or request.GET.get("notice_kinds") or "").strip()
    # 官网壹采寻源 / 首页田字格：默认且最多看近三个月
    publish_date_from = clamp_public_publish_date_from(
        request.GET.get("publishDateFrom") or request.GET.get("publish_date_from") or ""
    )
    publish_date_to = (request.GET.get("publishDateTo") or request.GET.get("publish_date_to") or "").strip()
    try:
        payload = query_crawled_notices(
            page=page,
            page_size=page_size,
            search=(request.GET.get("search") or "").strip(),
            site_id=site_id,
            notice_kind=notice_kind,
            notice_kinds=notice_kinds,
            site_ids=None,
            publish_date_from=publish_date_from,
            publish_date_to=publish_date_to,
            buyer_name=(request.GET.get("buyerName") or "").strip(),
            project_code=(request.GET.get("projectCode") or "").strip(),
            project_name=(request.GET.get("projectName") or "").strip(),
            region_name=(request.GET.get("regionName") or request.GET.get("region") or "").strip(),
            progress=(request.GET.get("progress") or "").strip(),
            budget_min=(request.GET.get("budgetMin") or request.GET.get("budget_min") or "").strip(),
            budget_max=(request.GET.get("budgetMax") or request.GET.get("budget_max") or "").strip(),
            procurement_mode=(request.GET.get("procurementMode") or request.GET.get("procurement_mode") or "").strip(),
            sort=(request.GET.get("sort") or request.GET.get("orderBy") or "").strip(),
            exclude_notice_kinds=(
                request.GET.get("excludeNoticeKinds") or request.GET.get("exclude_notice_kinds") or ""
            ).strip(),
        )
    except (ProgrammingError, OperationalError):
        return JsonResponse(
            {
                "detail": "公告数据暂时不可用，请稍后重试。",
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "publishDateFrom": publish_date_from,
            },
            status=503,
        )
    body = {
        "items": [_public_crawled_notice_item(item) for item in payload.get("items") or []],
        "total": payload.get("total") or 0,
        "page": payload.get("page") or page,
        "page_size": payload.get("page_size") or page_size,
        "publishDateFrom": publish_date_from,
        "sites": site_options(None),
        "noticeKinds": PORTAL_NOTICE_KINDS + ["意向公开", "结果公告", "成交结果公告"],
    }
    cache.set(cache_key, body, PUBLIC_CRAWLED_CACHE_SECONDS)
    return JsonResponse(body)


# 默认首屏：硬 TTL 保底；软 TTL 过期后先返回旧值再后台刷新（抗长时间闲置后首屏）
PORTAL_NOTICES_DEFAULT_CACHE_SECONDS = 1800
PORTAL_NOTICES_SOFT_SECONDS = 120


def _portal_swr_unpack(raw: Any, *, soft_seconds: int) -> tuple[dict | None, bool]:
    """返回 (data, is_stale)。兼容旧版直接存 dict 的缓存。"""
    if not isinstance(raw, dict):
        return None, False
    if "data" in raw and isinstance(raw.get("data"), dict) and "ts" in raw:
        data = raw["data"]
        age = time.time() - float(raw.get("ts") or 0)
        return data, age > soft_seconds
    # 旧格式：整包即业务数据，视为已过软 TTL，触发后台刷新
    return raw, True


def _portal_swr_pack(data: dict) -> dict:
    return {"ts": time.time(), "data": data}


def _portal_swr_get_or_build(
    cache_key: str,
    *,
    hard_seconds: int,
    soft_seconds: int,
    builder: Callable[[], dict],
    lock_ttl: int = 120,
) -> dict:
    """硬缓存未命中同步计算；软过期则立刻返回旧值并单飞后台重建。"""
    packed = cache.get(cache_key)
    data, stale = _portal_swr_unpack(packed, soft_seconds=soft_seconds)
    if data is not None and not stale:
        return data

    lock_key = f"{cache_key}:lock"

    if data is not None and stale:
        if cache.add(lock_key, "1", lock_ttl):

            def _refresh() -> None:
                try:
                    fresh = builder()
                    cache.set(cache_key, _portal_swr_pack(fresh), hard_seconds)
                except Exception:
                    pass
                finally:
                    cache.delete(lock_key)

            threading.Thread(target=_refresh, daemon=True).start()
        return data

    # 硬未命中：单飞，避免并发冷启动打爆库
    if cache.add(lock_key, "1", lock_ttl):
        try:
            fresh = builder()
            cache.set(cache_key, _portal_swr_pack(fresh), hard_seconds)
            return fresh
        finally:
            cache.delete(lock_key)

    for _ in range(80):
        time.sleep(0.1)
        packed = cache.get(cache_key)
        data, _ = _portal_swr_unpack(packed, soft_seconds=soft_seconds)
        if data is not None:
            return data
    fresh = builder()
    cache.set(cache_key, _portal_swr_pack(fresh), hard_seconds)
    return fresh


@require_http_methods(["GET"])
def portal_notices(request):
    record, error = require_portal(request, "portal.notice.view")
    if error:
        return error
    account = public_account(record)
    scope = account_site_scope(account)
    page = int(request.GET.get("page") or 1)
    page_size = min(max(int(request.GET.get("page_size") or request.GET.get("pageSize") or 20), 1), 50)
    search = (request.GET.get("search") or "").strip()
    site_id = (request.GET.get("siteId") or "").strip()
    notice_kind = (request.GET.get("noticeKind") or "").strip()
    notice_kinds = (request.GET.get("noticeKinds") or request.GET.get("notice_kinds") or "").strip()
    publish_date_from = (request.GET.get("publishDateFrom") or request.GET.get("publish_date_from") or "").strip()
    publish_date_to = (request.GET.get("publishDateTo") or request.GET.get("publish_date_to") or "").strip()
    buyer_name = (request.GET.get("buyerName") or "").strip()
    project_code = (request.GET.get("projectCode") or "").strip()
    project_name = (request.GET.get("projectName") or "").strip()
    region_name = (request.GET.get("regionName") or request.GET.get("region") or "").strip()
    progress = (request.GET.get("progress") or "").strip()
    procurement_mode = (request.GET.get("procurementMode") or request.GET.get("procurement_mode") or "").strip()
    sort = (request.GET.get("sort") or request.GET.get("orderBy") or "").strip()
    # 默认首屏（无筛选）跨 worker 缓存 + SWR，躲开闲置后冷 COUNT
    default_first_page = (
        page == 1
        and page_size == 20
        and not any(
            [
                search,
                site_id,
                notice_kind,
                notice_kinds,
                publish_date_from,
                publish_date_to,
                buyer_name,
                project_code,
                project_name,
                region_name,
                progress,
                procurement_mode,
                sort,
            ]
        )
    )
    scope_key = "all" if scope is None else ",".join(scope)
    list_cache_key = f"portal_notices_default_v2:{scope_key}" if default_first_page else ""

    def _build_notice_payload() -> dict:
        try:
            body = query_crawled_notices(
                page=page,
                page_size=page_size,
                search=search,
                site_id=site_id,
                notice_kind=notice_kind,
                notice_kinds=notice_kinds,
                site_ids=scope,
                publish_date_from=publish_date_from,
                publish_date_to=publish_date_to,
                buyer_name=buyer_name,
                project_code=project_code,
                project_name=project_name,
                region_name=region_name,
                progress=progress,
                procurement_mode=procurement_mode,
                sort=sort,
            )
        except (ProgrammingError, OperationalError) as exc:
            raise exc
        body["sites"] = site_options(scope)
        body["noticeKinds"] = PORTAL_NOTICE_KINDS + ["意向公开", "结果公告", "成交结果公告"]
        return body

    if list_cache_key:
        try:
            payload = _portal_swr_get_or_build(
                list_cache_key,
                hard_seconds=PORTAL_NOTICES_DEFAULT_CACHE_SECONDS,
                soft_seconds=PORTAL_NOTICES_SOFT_SECONDS,
                builder=_build_notice_payload,
            )
            return JsonResponse(payload)
        except (ProgrammingError, OperationalError):
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

    try:
        payload = _build_notice_payload()
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


def _serialize_inbox_item(row: PortalNoticeInbox, *, highlight_terms: list[str] | None = None) -> dict:
    title = row.title or ""
    project_name = row.project_name or ""
    buyer_name = row.buyer_name or ""
    region_name = row.region_name or ""
    terms = [str(item or "").strip() for item in (highlight_terms or []) if str(item or "").strip()]
    matched = []
    haystack = f"{title}\n{project_name}\n{buyer_name}\n{region_name}".lower()
    for term in terms:
        if term.lower() in haystack and term not in matched:
            matched.append(term)
            if len(matched) >= 8:
                break
    return {
        "id": row.id,
        "noticeId": row.notice_raw_id,
        "digestDate": row.digest_date.isoformat() if row.digest_date else "",
        "title": title,
        "projectName": project_name,
        "buyerName": buyer_name,
        "regionName": region_name,
        "siteId": row.site_id or "",
        "siteLabel": SITE_LABELS.get(row.site_id or "", row.site_id or ""),
        "isRead": bool(row.is_read),
        "readAt": row.read_at.isoformat() if row.read_at else "",
        "createdAt": row.created_at.isoformat() if row.created_at else "",
        "matchedKeywords": matched,
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
    search = (request.GET.get("search") or "").strip()
    qs = PortalNoticeInbox.objects.filter(customer_account_id=record.id).order_by("-created_at", "-id")
    if unread_only:
        qs = qs.filter(is_read=False)
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(project_name__icontains=search)
            | Q(buyer_name__icontains=search)
            | Q(region_name__icontains=search)
            | Q(site_id__icontains=search)
        )
    total = qs.count()
    unread_total = PortalNoticeInbox.objects.filter(customer_account_id=record.id, is_read=False).count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    account = public_account(record)
    sub = account.get("subscription") if isinstance(account.get("subscription"), dict) else {}
    highlight_terms = list(sub.get("keywords") or [])
    if search:
        highlight_terms = [search, *highlight_terms]
    return JsonResponse(
        {
            "items": [_serialize_inbox_item(row, highlight_terms=highlight_terms) for row in rows],
            "total": total,
            "unreadTotal": unread_total,
            "page": page,
            "page_size": page_size,
            "search": search,
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
    return issue_portal_cookie(JsonResponse({"data": public_account(record)}), record.id, request=request)


@csrf_exempt
@require_http_methods(["POST"])
def portal_platform_login(request):
    """使用管理后台「平台账号」台账凭证登录门户；需所属公司有有效服务项目。"""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "请输入平台账号和密码。"}, status=400)
    account_name = str(payload.get("accountName") or payload.get("identifier") or payload.get("phone") or "").strip()
    password = str(payload.get("password") or "")
    if not account_name or not password:
        return JsonResponse({"detail": "请输入平台账号和密码。"}, status=400)

    platform_account = find_platform_account_for_login(account_name, password)
    if not platform_account:
        return JsonResponse({"detail": "账号或密码错误。"}, status=401)

    org_id = str(
        platform_account.customer_org_id
        or (platform_account.data or {}).get("customerOrgId")
        or ""
    ).strip()
    if not org_has_active_service_project(org_id):
        return JsonResponse({"detail": "服务已过期。"}, status=403)

    record = resolve_portal_account_for_platform(platform_account)
    if (record.status or "") != "启用":
        return JsonResponse({"detail": "账号已停用，请联系管理员。"}, status=403)
    return issue_portal_cookie(JsonResponse({"data": public_account(record)}), record.id, request=request)


@csrf_exempt
@require_http_methods(["POST"])
def portal_logout(request):
    return clear_portal_cookie(JsonResponse({"ok": True}), request=request)


@require_http_methods(["GET"])
def portal_me(request):
    record, error = require_portal(request)
    if error:
        return error
    return JsonResponse({"data": public_account(record)})


@csrf_exempt
@require_http_methods(["POST"])
def portal_handoff_create(request):
    """在已登录域签发短时移交码，供其它官网主域兑换本地 portal_session。"""
    record, error = require_portal(request)
    if error:
        return error
    return JsonResponse(
        {
            "code": create_portal_handoff_code(record.id),
            "expiresIn": PORTAL_HANDOFF_MAX_AGE,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def portal_handoff_claim(request):
    """用移交码在当前请求 Host 对应主域写入 portal_session。"""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    account_id = consume_portal_handoff_code(payload.get("code") or request.GET.get("code") or "")
    if not account_id:
        return JsonResponse({"detail": "登录移交已失效，请重新登录。"}, status=400)
    record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not record or (record.status or "") != "启用":
        return JsonResponse({"detail": "账号不可用。"}, status=403)
    return issue_portal_cookie(JsonResponse({"data": public_account(record)}), record.id, request=request)


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
        "keywords": list(normalized.get("keywords") or []),
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

    cache_key = "portal_subscription_content_tags_v1"
    content_tags = cache.get(cache_key)
    if not isinstance(content_tags, list) or not content_tags:
        # 全量去重标签（按使用频次排序）；门户用搜索筛选，不再截断到几十个
        content_tags = list(
            NoticeResultTag.objects.exclude(content_tag="")
            .values("content_tag")
            .annotate(total=Count("id"))
            .order_by("-total", "content_tag")
            .values_list("content_tag", flat=True)
        )
        # 兜底：库空或极冷门时仍可勾选常用项
        for item in (
            "车辆",
            "汽车",
            "公务用车",
            "新能源汽车",
            "充电桩",
            "车辆加油",
            "油卡",
            "ETC",
            "车辆维保",
            "车辆保险",
            "车辆租赁",
            "客车",
            "货车",
            "轿车",
            "轮胎",
            "汽配",
            "汽车配件",
            "洗车",
            "停车",
            "印刷",
            "运维服务",
            "办公用品",
            "空调",
            "LED屏幕",
            "宣传项目",
            "家具",
            "计算机",
        ):
            if item not in content_tags:
                content_tags.append(item)
        cache.set(cache_key, content_tags, 300)
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


PORTAL_WECHAT_LOGIN_SALT = "portal-wechat-login"
PORTAL_WECHAT_NEXT_TABS = {"messages", "subscription", "notices", "home", "account"}
PORTAL_WX_SCAN_TTL = 180
PORTAL_WX_SCAN_PREFIX = "psl_"
PORTAL_WX_BIND_PREFIX = "psb_"
PORTAL_WX_SCAN_CACHE_PREFIX = "portal_wx_scan:"
PORTAL_WX_BIND_CACHE_PREFIX = "portal_wx_bind:"


def _portal_home_base() -> str:
    base = (wechat_mp.portal_base_url() or "/").rstrip("/") + "/"
    return base


def _wx_scan_cache_key(ticket: str) -> str:
    return f"{PORTAL_WX_SCAN_CACHE_PREFIX}{ticket}"


def _wx_bind_cache_key(ticket: str) -> str:
    return f"{PORTAL_WX_BIND_CACHE_PREFIX}{ticket}"


def _complete_portal_scan_login(*, ticket: str, openid: str) -> str:
    """根据扫码 openid 更新 ticket 状态，返回 status。"""
    ticket = str(ticket or "").strip()
    openid = str(openid or "").strip()
    if not ticket or not openid:
        return "fail"
    key = _wx_scan_cache_key(ticket)
    current = cache.get(key)
    if not isinstance(current, dict) or current.get("status") not in {"pending", "unbound", "disabled", "fail"}:
        return "expired" if not current else str(current.get("status") or "expired")
    record = _find_account_by_openid(openid)
    if not record:
        cache.set(key, {"status": "unbound"}, PORTAL_WX_SCAN_TTL)
        return "unbound"
    if (record.status or "") != "启用":
        cache.set(key, {"status": "disabled"}, PORTAL_WX_SCAN_TTL)
        return "disabled"
    cache.set(key, {"status": "ok", "account_id": str(record.id)}, PORTAL_WX_SCAN_TTL)
    return "ok"


def _complete_portal_scan_bind(*, ticket: str, openid: str) -> str:
    """PC 订阅页扫码绑定：将 openid 绑到 ticket 对应账号。"""
    ticket = str(ticket or "").strip()
    openid = str(openid or "").strip()
    if not ticket or not openid:
        return "fail"
    key = _wx_bind_cache_key(ticket)
    current = cache.get(key)
    if not isinstance(current, dict) or current.get("status") not in {"pending", "conflict", "fail"}:
        return "expired" if not current else str(current.get("status") or "expired")
    account_id = str(current.get("account_id") or "").strip()
    record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not record or (record.status or "") != "启用":
        cache.set(key, {"status": "fail", "account_id": account_id}, PORTAL_WX_SCAN_TTL)
        return "fail"
    existing = _find_account_by_openid(openid)
    if existing and existing.id != record.id:
        cache.set(key, {"status": "conflict", "account_id": account_id}, PORTAL_WX_SCAN_TTL)
        return "conflict"
    _set_account_wechat(record, openid=openid, follow_status="subscribed")
    cache.set(key, {"status": "ok", "account_id": str(record.id)}, PORTAL_WX_SCAN_TTL)
    return "ok"


def _portal_scan_result_page(*, status: str) -> HttpResponse:
    """手机扫码确认后的提示页（不在手机上写 PC 会话）。"""
    status = (status or "fail").strip() or "fail"
    messages = {
        "ok": ("操作成功", "请返回电脑，页面将自动继续。"),
        "unbound": ("尚未绑定", "当前微信未绑定会员账号。请先用手机号登录，在「订阅」页绑定微信后再扫码。"),
        "disabled": ("账号不可用", "该账号已停用，请联系管理员。"),
        "conflict": ("绑定冲突", "该微信已绑定其他账号，请换号扫码或先解绑。"),
        "expired": ("二维码已失效", "请返回电脑刷新二维码后重试。"),
        "fail": ("操作失败", "请返回电脑刷新二维码后重试。"),
    }
    if status not in messages:
        status = "fail"
    title, hint = messages[status]
    safe_title = html.escape(title)
    safe_hint = html.escape(hint)
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
  </style>
</head>
<body>
  <div class="box">
    <h1>{safe_title}</h1>
    <p>{safe_hint}</p>
  </div>
</body>
</html>"""
    return HttpResponse(page, content_type="text/html; charset=utf-8")


def _normalize_portal_next(next_tab: str) -> str:
    tab = str(next_tab or "messages").strip().lstrip("#") or "messages"
    if tab not in PORTAL_WECHAT_NEXT_TABS:
        return "messages"
    return tab


def _portal_js_redirect_page(
    *,
    title: str,
    hint: str,
    target: str,
    request=None,
    account_id: str | None = None,
) -> HttpResponse:
    """微信内 302 Location 带 #hash 常被剥掉；用中间页 + JS 跳转，并可附带 portal_session。"""
    safe_title = html.escape(title)
    safe_hint = html.escape(hint)
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
    <p>{safe_hint}</p>
    <p style="margin-top:12px"><a href="{safe_href}">如未自动跳转请点这里</a></p>
  </div>
  <script>location.replace({js_target});</script>
</body>
</html>"""
    response = HttpResponse(page, content_type="text/html; charset=utf-8")
    if account_id:
        issue_portal_cookie(response, account_id, request=request)
    return response


def _portal_bind_result_page(*, status: str) -> HttpResponse:
    """微信绑定结果中间页。"""
    status = (status or "fail").strip() or "fail"
    if status not in {"ok", "fail", "conflict"}:
        status = "fail"
    messages = {
        "ok": "微信绑定成功",
        "fail": "微信绑定失败，请重试",
        "conflict": "该微信已绑定其他账号",
    }
    title = messages[status]
    target = f"{_portal_home_base()}?{urlencode({'wechat': status})}#subscription"
    return _portal_js_redirect_page(
        title=title,
        hint="正在返回订阅页面…",
        target=target,
    )


def _portal_login_result_page(*, status: str, next_tab: str = "messages", request=None, account_id: str | None = None) -> HttpResponse:
    """微信静默登录结果中间页。"""
    status = (status or "fail").strip() or "fail"
    tab = _normalize_portal_next(next_tab)
    if status == "ok" and account_id:
        target = f"{_portal_home_base()}#{tab}"
        return _portal_js_redirect_page(
            title="登录成功",
            hint="正在进入消息中心…",
            target=target,
            request=request,
            account_id=account_id,
        )
    messages = {
        "fail": "微信登录失败，请重试或使用手机号登录",
        "unbound": "当前微信尚未绑定会员账号，请先登录后绑定",
        "disabled": "账号不可用，请联系管理员",
    }
    if status not in messages:
        status = "fail"
    target = f"{_portal_home_base()}?{urlencode({'wechat': status})}#login"
    return _portal_js_redirect_page(
        title=messages[status],
        hint="正在返回登录页…",
        target=target,
    )


@csrf_exempt
@require_http_methods(["GET"])
def portal_wechat_silent_login(request):
    """微信通知深链入口：已登录直接进目标页；否则 snsapi_base 静默取 openid 后登录。"""
    next_tab = _normalize_portal_next(request.GET.get("next") or "messages")
    existing = current_portal_account(request)
    if existing:
        return _portal_login_result_page(status="ok", next_tab=next_tab, request=request, account_id=existing.id)
    if not wechat_mp.mp_configured():
        return _portal_login_result_page(status="fail", next_tab=next_tab, request=request)
    state = signing.dumps(
        {"purpose": "login", "next": next_tab, "ts": timezone.now().timestamp()},
        salt=PORTAL_WECHAT_LOGIN_SALT,
    )
    url = wechat_mp.build_oauth_url(state=state, scope="snsapi_base")
    if not url:
        return _portal_login_result_page(status="fail", next_tab=next_tab, request=request)
    # 勿用 302 Location：URL 含 #wechat_redirect，部分代理会剥掉整个 Location
    return _portal_js_redirect_page(
        title="微信授权中",
        hint="正在打开微信授权…",
        target=url,
    )


@csrf_exempt
@require_http_methods(["POST"])
def portal_wechat_scan_login_start(request):
    """PC 登录页：签发扫码 ticket，返回微信临时二维码。"""
    if not wechat_mp.mp_configured():
        return JsonResponse({"detail": "微信登录暂不可用，请使用手机号登录。"}, status=503)
    ticket = secrets.token_urlsafe(16)
    scene = f"{PORTAL_WX_SCAN_PREFIX}{ticket}"
    cache.set(_wx_scan_cache_key(ticket), {"status": "pending"}, PORTAL_WX_SCAN_TTL)
    qr = wechat_mp.create_temp_scene_qrcode(scene_str=scene, expire_seconds=PORTAL_WX_SCAN_TTL)
    qr_image_url = str((qr or {}).get("qrImageUrl") or "").strip()
    mode = "scene"
    scan_url = ""
    if not qr_image_url:
        # 回退：生成授权链接二维码（需微信内打开）
        origin = ""
        redirect = wechat_mp.oauth_redirect_uri()
        if redirect and "/api/" in redirect:
            origin = redirect.split("/api/", 1)[0].rstrip("/")
        if origin:
            scan_url = f"{origin}/api/portal/wechat/scan-login/authorize/?ticket={quote(ticket)}"
            qr_image_url = (
                "https://api.qrserver.com/v1/create-qr-code/"
                f"?size=220x220&margin=8&data={quote(scan_url, safe='')}"
            )
            mode = "oauth"
        else:
            cache.delete(_wx_scan_cache_key(ticket))
            return JsonResponse({"detail": "无法创建登录二维码，请稍后重试。"}, status=503)
    return JsonResponse(
        {
            "ticket": ticket,
            "expiresIn": PORTAL_WX_SCAN_TTL,
            "qrImageUrl": qr_image_url,
            "mode": mode,
            "scanUrl": scan_url,
        }
    )


@csrf_exempt
@require_http_methods(["GET"])
def portal_wechat_scan_login_authorize(request):
    """回退模式：手机微信打开后走 snsapi_base，再回写 ticket。"""
    ticket = (request.GET.get("ticket") or "").strip()
    data = cache.get(_wx_scan_cache_key(ticket)) if ticket else None
    if not ticket or not isinstance(data, dict):
        return _portal_scan_result_page(status="expired")
    if data.get("status") == "ok":
        return _portal_scan_result_page(status="ok")
    if data.get("status") not in {"pending", "unbound", "disabled", "fail"}:
        return _portal_scan_result_page(status="expired")
    if not wechat_mp.mp_configured():
        return _portal_scan_result_page(status="fail")
    state = signing.dumps(
        {"purpose": "scan_login", "ticket": ticket, "ts": timezone.now().timestamp()},
        salt=PORTAL_WECHAT_LOGIN_SALT,
    )
    url = wechat_mp.build_oauth_url(state=state, scope="snsapi_base")
    if not url:
        return _portal_scan_result_page(status="fail")
    return _portal_js_redirect_page(
        title="微信授权中",
        hint="正在确认身份…",
        target=url,
    )


@csrf_exempt
@require_http_methods(["GET"])
def portal_wechat_scan_login_status(request):
    """PC 轮询扫码结果；成功时在当前域写入 portal_session。"""
    ticket = (request.GET.get("ticket") or "").strip()
    if not ticket:
        return JsonResponse({"status": "expired"})
    key = _wx_scan_cache_key(ticket)
    data = cache.get(key)
    if not isinstance(data, dict):
        return JsonResponse({"status": "expired"})
    status = str(data.get("status") or "pending")
    if status != "ok":
        return JsonResponse({"status": status})
    account_id = str(data.get("account_id") or "").strip()
    cache.delete(key)
    if not account_id:
        return JsonResponse({"status": "fail"})
    record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not record or (record.status or "") != "启用":
        return JsonResponse({"status": "disabled"})
    return issue_portal_cookie(
        JsonResponse({"status": "ok", "data": public_account(record)}),
        record.id,
        request=request,
    )


@csrf_exempt
@require_http_methods(["POST"])
def portal_wechat_scan_bind_start(request):
    """PC 订阅页：签发扫码绑定 ticket，返回临时二维码。"""
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    if not wechat_mp.mp_configured():
        return JsonResponse({"detail": "微信服务号尚未配置，请联系管理员。"}, status=503)
    if public_account(record).get("wechatBound"):
        return JsonResponse({"detail": "当前账号已绑定微信。", "wechatBound": True}, status=400)
    ticket = secrets.token_urlsafe(16)
    scene = f"{PORTAL_WX_BIND_PREFIX}{ticket}"
    cache.set(
        _wx_bind_cache_key(ticket),
        {"status": "pending", "account_id": str(record.id)},
        PORTAL_WX_SCAN_TTL,
    )
    qr = wechat_mp.create_temp_scene_qrcode(scene_str=scene, expire_seconds=PORTAL_WX_SCAN_TTL)
    qr_image_url = str((qr or {}).get("qrImageUrl") or "").strip()
    mode = "scene"
    scan_url = ""
    if not qr_image_url:
        origin = ""
        redirect = wechat_mp.oauth_redirect_uri()
        if redirect and "/api/" in redirect:
            origin = redirect.split("/api/", 1)[0].rstrip("/")
        if origin:
            scan_url = f"{origin}/api/portal/wechat/scan-bind/authorize/?ticket={quote(ticket)}"
            qr_image_url = (
                "https://api.qrserver.com/v1/create-qr-code/"
                f"?size=220x220&margin=8&data={quote(scan_url, safe='')}"
            )
            mode = "oauth"
        else:
            cache.delete(_wx_bind_cache_key(ticket))
            return JsonResponse({"detail": "无法创建绑定二维码，请稍后重试。"}, status=503)
    return JsonResponse(
        {
            "ticket": ticket,
            "expiresIn": PORTAL_WX_SCAN_TTL,
            "qrImageUrl": qr_image_url,
            "mode": mode,
            "scanUrl": scan_url,
        }
    )


@csrf_exempt
@require_http_methods(["GET"])
def portal_wechat_scan_bind_authorize(request):
    """回退模式：手机微信打开后走 snsapi_base，再完成绑定。"""
    ticket = (request.GET.get("ticket") or "").strip()
    data = cache.get(_wx_bind_cache_key(ticket)) if ticket else None
    if not ticket or not isinstance(data, dict):
        return _portal_scan_result_page(status="expired")
    if data.get("status") == "ok":
        return _portal_scan_result_page(status="ok")
    if data.get("status") not in {"pending", "conflict", "fail"}:
        return _portal_scan_result_page(status="expired")
    if not wechat_mp.mp_configured():
        return _portal_scan_result_page(status="fail")
    state = signing.dumps(
        {"purpose": "scan_bind", "ticket": ticket, "ts": timezone.now().timestamp()},
        salt=PORTAL_WECHAT_LOGIN_SALT,
    )
    url = wechat_mp.build_oauth_url(state=state, scope="snsapi_base")
    if not url:
        return _portal_scan_result_page(status="fail")
    return _portal_js_redirect_page(
        title="微信授权中",
        hint="正在绑定账号…",
        target=url,
    )


@csrf_exempt
@require_http_methods(["GET"])
def portal_wechat_scan_bind_status(request):
    """PC 轮询扫码绑定结果。"""
    record, error = require_portal(request, "portal.notice.subscribe")
    if error:
        return error
    ticket = (request.GET.get("ticket") or "").strip()
    if not ticket:
        return JsonResponse({"status": "expired"})
    key = _wx_bind_cache_key(ticket)
    data = cache.get(key)
    if not isinstance(data, dict):
        return JsonResponse({"status": "expired"})
    if str(data.get("account_id") or "") != str(record.id):
        return JsonResponse({"status": "fail"})
    status = str(data.get("status") or "pending")
    if status != "ok":
        return JsonResponse({"status": status})
    cache.delete(key)
    refreshed = CustomerAccountRecord.objects.filter(id=record.id, is_deleted=False).first() or record
    return JsonResponse({"status": "ok", "data": public_account(refreshed)})


@csrf_exempt
@require_http_methods(["GET"])
def wechat_mp_oauth_callback(request):
    try:
        code = (request.GET.get("code") or "").strip()
        state = (request.GET.get("state") or "").strip()
        if not code or not state:
            return _portal_bind_result_page(status="fail")

        login_payload = None
        bind_payload = None
        try:
            login_payload = signing.loads(state, salt=PORTAL_WECHAT_LOGIN_SALT, max_age=600)
        except signing.BadSignature:
            login_payload = None
        if login_payload is None:
            try:
                bind_payload = signing.loads(state, salt="portal-wechat-bind", max_age=600)
            except signing.BadSignature:
                return _portal_bind_result_page(status="fail")

        exchanged = wechat_mp.exchange_oauth_code(code)
        openid = exchanged.get("openid") or ""
        if not openid:
            if login_payload is not None:
                return _portal_login_result_page(
                    status="fail",
                    next_tab=(login_payload or {}).get("next") or "messages",
                    request=request,
                )
            return _portal_bind_result_page(status="fail")

        # —— 登录类 state：静默登录 / PC 扫码登录 / PC 扫码绑定 ——
        if login_payload is not None:
            purpose = str((login_payload or {}).get("purpose") or "login").strip() or "login"
            if purpose == "scan_login":
                ticket = str((login_payload or {}).get("ticket") or "").strip()
                status = _complete_portal_scan_login(ticket=ticket, openid=openid)
                return _portal_scan_result_page(status=status)
            if purpose == "scan_bind":
                ticket = str((login_payload or {}).get("ticket") or "").strip()
                status = _complete_portal_scan_bind(ticket=ticket, openid=openid)
                return _portal_scan_result_page(status=status)

            next_tab = _normalize_portal_next((login_payload or {}).get("next") or "messages")
            record = _find_account_by_openid(openid)
            if not record:
                return _portal_login_result_page(status="unbound", next_tab=next_tab, request=request)
            if (record.status or "") != "启用":
                return _portal_login_result_page(status="disabled", next_tab=next_tab, request=request)
            return _portal_login_result_page(
                status="ok",
                next_tab=next_tab,
                request=request,
                account_id=record.id,
            )

        # —— 绑定微信（需 state 内账号） ——
        account_id = str((bind_payload or {}).get("aid") or "").strip()
        record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
        if not record or (record.status or "") != "启用":
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
        # 临时场景码扫码 / 带参关注 → PC 扫码登录或绑定
        if event_name in {"scan", "subscribe"}:
            event_key = (event.get("EventKey") or "").strip()
            scene = event_key[8:] if event_key.startswith("qrscene_") else event_key
            if scene.startswith(PORTAL_WX_SCAN_PREFIX):
                ticket = scene[len(PORTAL_WX_SCAN_PREFIX) :]
                _complete_portal_scan_login(ticket=ticket, openid=openid)
            elif scene.startswith(PORTAL_WX_BIND_PREFIX):
                ticket = scene[len(PORTAL_WX_BIND_PREFIX) :]
                _complete_portal_scan_bind(ticket=ticket, openid=openid)

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


PORTAL_STATS_CACHE_SECONDS = 1800  # 硬 TTL；配合 SWR 抗闲置首屏
PORTAL_STATS_SOFT_SECONDS = 180


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
    # 全量站点视角下统计与账号无关，跨账号共享缓存，避免重复 8s 计算
    scope_part = "all" if effective_scope is None else ",".join(sorted(effective_scope))
    account_part = "*" if effective_scope is None else str(account_id)
    raw = "|".join(
        [
            account_part,
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
    return "portal_stats_v2:" + hashlib.md5(raw.encode("utf-8")).hexdigest()


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

    def _with_account_fields(body: dict) -> dict:
        return {
            **body,
            "customerName": account["customerName"] or account["name"],
            "subscriptionEnabled": account["subscription"]["enabled"],
            "allowedSiteIds": account.get("allowedSiteIds"),
            "siteScope": account.get("siteScope") or "all",
        }

    def _build_stats_payload() -> dict:
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
        body = {
            "period": period,
            **stats,
            "tagStats": tag_stats,
        }
        # 首页：附带各可查看平台的独立统计（单平台时复用主汇总，避免二次全量查询）
        if include_sites:
            if len(sites) <= 1:
                body["siteStats"] = [
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
                body["siteStats"] = build_site_metric_stats(
                    sites,
                    start=range_start,
                    end=range_end,
                    range_counts=(site_maps or {}).get("range_counts"),
                    today_counts=(site_maps or {}).get("today_counts"),
                    week_counts=(site_maps or {}).get("week_counts"),
                    purchase_map=(site_maps or {}).get("purchase_map"),
                    deal_map=(site_maps or {}).get("deal_map"),
                )
        return body

    payload = _portal_swr_get_or_build(
        cache_key,
        hard_seconds=PORTAL_STATS_CACHE_SECONDS,
        soft_seconds=PORTAL_STATS_SOFT_SECONDS,
        builder=_build_stats_payload,
    )
    return JsonResponse({"data": _with_account_fields(payload)})
