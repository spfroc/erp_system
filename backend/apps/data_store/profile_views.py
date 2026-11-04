"""个人中心：资料、改密、连接器凭证。"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid

from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.data_store.models import UserApiToken, UserRecord
from apps.data_store.views import (
    _active_user_queryset,
    _find_user_data_by_id,
    _patch_app_state_snapshot,
    _password_matches,
    _public_user,
    _read_body,
    _require_login,
    _text,
)


PHONE_RE = re.compile(r"^1\d{10}$")


def _load_user_record(user_id: str) -> UserRecord | None:
    return _active_user_queryset().filter(id=user_id).first()


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _issue_token() -> tuple[str, str, str]:
    raw = f"yzc_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    return raw, prefix, _token_hash(raw)


def _serialize_token(row: UserApiToken, *, include_secret: str | None = None) -> dict:
    payload = {
        "id": row.id,
        "name": row.name,
        "tokenPrefix": row.token_prefix,
        "createdAt": row.created_at.isoformat() if row.created_at else "",
        "lastUsedAt": row.last_used_at.isoformat() if row.last_used_at else "",
        "hasToken": True,
    }
    if include_secret:
        payload["token"] = include_secret
    return payload


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def auth_profile(request):
    user_data, error = _require_login(request)
    if error:
        return error
    user_id = str(user_data.get("id") or "")
    record = _load_user_record(user_id)
    if not record:
        return JsonResponse({"detail": "用户不存在或已停用。"}, status=404)

    if request.method == "GET":
        return JsonResponse({"data": _public_user(record)})

    payload, body_error = _read_body(request)
    if body_error:
        return body_error

    name = _text(payload, "name").strip()
    phone = _text(payload, "phone").strip()
    if not name:
        return JsonResponse({"detail": "请填写姓名。"}, status=400)
    if phone and not PHONE_RE.match(phone):
        return JsonResponse({"detail": "手机号格式不正确。"}, status=400)
    if phone:
        conflict = _active_user_queryset().filter(phone=phone).exclude(id=user_id).exists()
        if conflict:
            return JsonResponse({"detail": "该手机号已被其他账号使用。"}, status=400)

    data = dict(record.data or {})
    data["name"] = name
    data["phone"] = phone
    data["id"] = record.id
    data["status"] = record.status or data.get("status") or "启用"
    data["roleIds"] = list(data.get("roleIds") or [])
    if "createdAt" not in data:
        data["createdAt"] = timezone.now().isoformat()

    record.name = name
    record.phone = phone
    record.data = data
    record.save(update_fields=["name", "phone", "data", "updated_at"])
    _patch_app_state_snapshot("users", record.id, data)

    request.session["user_name"] = name
    return JsonResponse({"data": _public_user(record)})


@csrf_exempt
@require_http_methods(["POST"])
def auth_change_password(request):
    user_data, error = _require_login(request)
    if error:
        return error
    payload, body_error = _read_body(request)
    if body_error:
        return body_error

    current_password = str(payload.get("currentPassword") or payload.get("oldPassword") or "")
    new_password = str(payload.get("newPassword") or "")
    confirm_password = str(payload.get("confirmPassword") or new_password)
    if not current_password or not new_password:
        return JsonResponse({"detail": "请填写当前密码和新密码。"}, status=400)
    if len(new_password) < 6:
        return JsonResponse({"detail": "新密码至少 6 位。"}, status=400)
    if new_password != confirm_password:
        return JsonResponse({"detail": "两次输入的新密码不一致。"}, status=400)

    user_id = str(user_data.get("id") or "")
    record = _load_user_record(user_id)
    if not record:
        return JsonResponse({"detail": "用户不存在或已停用。"}, status=404)

    stored = str((record.data or {}).get("password") or "")
    if not _password_matches(stored, current_password):
        return JsonResponse({"detail": "当前密码不正确。"}, status=400)

    data = dict(record.data or {})
    data["password"] = make_password(new_password)
    record.data = data
    record.save(update_fields=["data", "updated_at"])
    _patch_app_state_snapshot("users", record.id, data)
    return JsonResponse({"data": {"ok": True}})


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def auth_api_token(request):
    user_data, error = _require_login(request)
    if error:
        return error
    user_id = str(user_data.get("id") or "")

    if request.method == "GET":
        row = (
            UserApiToken.objects.filter(user_id=user_id, revoked_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not row:
            return JsonResponse({"data": {"hasToken": False}})
        return JsonResponse({"data": _serialize_token(row)})

    if request.method == "DELETE":
        now = timezone.now()
        UserApiToken.objects.filter(user_id=user_id, revoked_at__isnull=True).update(revoked_at=now)
        return JsonResponse({"data": {"hasToken": False}})

    payload, body_error = _read_body(request)
    if body_error:
        return body_error
    name = (_text(payload, "name") or "默认凭证").strip()[:128] or "默认凭证"

    # 重新生成：吊销旧凭证
    now = timezone.now()
    UserApiToken.objects.filter(user_id=user_id, revoked_at__isnull=True).update(revoked_at=now)

    raw, prefix, digest = _issue_token()
    row = UserApiToken.objects.create(
        id=f"uat-{uuid.uuid4().hex[:16]}",
        user_id=user_id,
        name=name,
        token_prefix=prefix,
        token_hash=digest,
    )
    return JsonResponse({"data": _serialize_token(row, include_secret=raw)}, status=201)


@require_http_methods(["GET"])
def auth_my_permissions(request):
    user_data, error = _require_login(request)
    if error:
        return error
    from apps.data_store.views import _user_permissions

    keys = sorted(_user_permissions(user_data))
    return JsonResponse({"data": {"permissions": keys}})


def resolve_user_data_for_api_token(raw_token: str) -> dict | None:
    """供 MCP 等服务校验个人凭证，返回与登录态一致的 user_data。"""
    raw = (raw_token or "").strip()
    if not raw:
        return None
    digest = _token_hash(raw)
    row = UserApiToken.objects.filter(token_hash=digest, revoked_at__isnull=True).first()
    if not row:
        return None
    user_data = _find_user_data_by_id(row.user_id)
    if not user_data or user_data.get("status") != "启用":
        return None
    UserApiToken.objects.filter(id=row.id).update(last_used_at=timezone.now())
    return user_data
