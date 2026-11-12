"""微信认证服务号：access_token、模板消息、OAuth、服务器回调验签。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, Any] = {"token": "", "expires_at": 0.0}


def mp_configured() -> bool:
    return bool(getattr(settings, "WECHAT_MP_APP_ID", "") and getattr(settings, "WECHAT_MP_APP_SECRET", ""))


def _app_id() -> str:
    return str(getattr(settings, "WECHAT_MP_APP_ID", "") or "").strip()


def _app_secret() -> str:
    return str(getattr(settings, "WECHAT_MP_APP_SECRET", "") or "").strip()


def _token() -> str:
    return str(getattr(settings, "WECHAT_MP_TOKEN", "") or "").strip()


def _template_id() -> str:
    return str(getattr(settings, "WECHAT_MP_TEMPLATE_ID_NOTICE_DIGEST", "") or "").strip()


def oauth_redirect_uri() -> str:
    return str(getattr(settings, "WECHAT_MP_OAUTH_REDIRECT_URI", "") or "").strip()


def portal_base_url() -> str:
    configured = str(getattr(settings, "WECHAT_MP_PORTAL_NOTICE_URL", "") or "").strip()
    if configured:
        # 兼容旧配置写到了具体 hash；归一到门户根
        base = configured.split("#", 1)[0].rstrip("/")
        if base.endswith("/portal"):
            return base + "/"
        if "/portal/" in base:
            return base[: base.index("/portal/") + len("/portal/")]
        return base + ("/" if not base.endswith("/") else "")
    redirect = oauth_redirect_uri()
    if redirect:
        return redirect.rsplit("/api/", 1)[0].rstrip("/") + "/"
    return ""


def _portal_api_origin() -> str:
    """用于生成门户同域 /api/ 绝对地址（模板消息、静默登录入口）。"""
    redirect = oauth_redirect_uri()
    if redirect and "/api/" in redirect:
        return redirect.split("/api/", 1)[0].rstrip("/")
    base = portal_base_url().rstrip("/")
    if not base:
        return ""
    if "/portal" in base:
        return base[: base.index("/portal")].rstrip("/")
    return base


def portal_wechat_silent_login_url(*, next_tab: str = "messages") -> str:
    """微信内打开：snsapi_base 取 openid → 签发 portal_session → 进入门户 hash。"""
    origin = _portal_api_origin()
    if not origin:
        return ""
    tab = str(next_tab or "messages").strip() or "messages"
    return f"{origin}/api/portal/wechat/silent-login/?{urlencode({'next': tab})}"


def portal_notice_url() -> str:
    """兼容旧调用：默认跳门户消息列表（经微信静默登录）。"""
    return portal_messages_url()


def portal_messages_url() -> str:
    """模板消息点击地址：优先静默登录入口，失败时回退到门户 #messages。"""
    silent = portal_wechat_silent_login_url(next_tab="messages")
    if silent:
        return silent
    base = portal_base_url()
    if not base:
        return ""
    return f"{base.rstrip('/')}/#messages"


def _http_json(url: str, *, data: dict | None = None, method: str = "GET") -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        method = "POST"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        logger.warning("wechat_mp http error %s %s", exc.code, raw[:300])
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"errcode": exc.code, "errmsg": raw[:200]}
    except Exception as exc:  # noqa: BLE001
        logger.exception("wechat_mp request failed")
        return {"errcode": -1, "errmsg": str(exc)}
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"errcode": -1, "errmsg": "invalid json", "raw": raw[:200]}


def get_access_token(*, force: bool = False) -> str:
    now = time.time()
    if not force and _TOKEN_CACHE["token"] and _TOKEN_CACHE["expires_at"] > now + 60:
        return str(_TOKEN_CACHE["token"])
    if not mp_configured():
        return ""
    url = (
        "https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={_app_id()}&secret={_app_secret()}"
    )
    payload = _http_json(url)
    token = str(payload.get("access_token") or "")
    expires_in = int(payload.get("expires_in") or 0)
    if not token:
        logger.warning("wechat_mp token failed: %s", payload)
        return ""
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + max(expires_in, 60)
    return token


def build_oauth_url(*, state: str, scope: str = "snsapi_base") -> str:
    redirect = oauth_redirect_uri()
    if not mp_configured() or not redirect:
        return ""
    query = urlencode(
        {
            "appid": _app_id(),
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
    )
    return f"https://open.weixin.qq.com/connect/oauth2/authorize?{query}#wechat_redirect"


def exchange_oauth_code(code: str) -> dict[str, str]:
    code = (code or "").strip()
    if not code or not mp_configured():
        return {}
    query = urlencode(
        {
            "appid": _app_id(),
            "secret": _app_secret(),
            "code": code,
            "grant_type": "authorization_code",
        }
    )
    payload = _http_json(f"https://api.weixin.qq.com/sns/oauth2/access_token?{query}")
    openid = str(payload.get("openid") or "").strip()
    if not openid:
        logger.warning("wechat_mp oauth failed: %s", payload)
        return {}
    return {
        "openid": openid,
        "unionid": str(payload.get("unionid") or "").strip(),
        "access_token": str(payload.get("access_token") or "").strip(),
    }


def send_template_message(
    *,
    openid: str,
    data: dict[str, dict[str, str]],
    url: str = "",
    template_id: str = "",
    client_msg_id: str = "",
) -> dict[str, Any]:
    openid = (openid or "").strip()
    template_id = (template_id or _template_id()).strip()
    if not openid or not template_id:
        return {"ok": False, "errcode": -1, "errmsg": "missing openid or template_id"}
    token = get_access_token()
    if not token:
        return {"ok": False, "errcode": -1, "errmsg": "access_token unavailable"}
    body: dict[str, Any] = {
        "touser": openid,
        "template_id": template_id,
        "data": data,
    }
    if url:
        body["url"] = url
    if client_msg_id:
        body["client_msg_id"] = client_msg_id
    payload = _http_json(
        f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}",
        data=body,
    )
    errcode = int(payload.get("errcode") or 0)
    if errcode == 40001:  # invalid credential, retry once
        token = get_access_token(force=True)
        if token:
            payload = _http_json(
                f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}",
                data=body,
            )
            errcode = int(payload.get("errcode") or 0)
    return {
        "ok": errcode == 0,
        "errcode": errcode,
        "errmsg": str(payload.get("errmsg") or ""),
        "msgid": payload.get("msgid"),
        "raw": payload,
    }


def verify_callback_signature(*, signature: str, timestamp: str, nonce: str) -> bool:
    token = _token()
    if not token or not signature:
        return False
    parts = sorted([token, str(timestamp or ""), str(nonce or "")])
    digest = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, str(signature))


def parse_callback_xml(raw: bytes | str) -> dict[str, str]:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
    if not text.strip():
        return {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    result: dict[str, str] = {}
    for child in root:
        result[child.tag] = (child.text or "").strip()
    return result
