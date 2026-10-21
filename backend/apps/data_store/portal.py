from django.contrib.auth.hashers import check_password, is_password_usable
from django.core import signing
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.db import ProgrammingError

from .models import CustomerAccountRecord
from .notice_models import NoticeRaw
from .notice_views import query_crawled_notices
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
    except ProgrammingError:
        payload = {"items": [], "total": 0, "page": page, "page_size": page_size}
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
    try:
        notice_total = NoticeRaw.objects.count()
    except ProgrammingError:
        notice_total = list_public_notices(page=1, page_size=1, search="", notice_kind="").get("total", 0)
    return JsonResponse(
        {
            "data": {
                "customerName": account["customerName"] or account["name"],
                "publicNoticeTotal": notice_total,
                "subscriptionEnabled": account["subscription"]["enabled"],
            }
        }
    )
