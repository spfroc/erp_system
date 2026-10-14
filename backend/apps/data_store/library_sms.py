"""资料库与短信：字段归一化、center 发送对接。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from uuid import uuid4

from django.utils import timezone

LIBRARY_SIGNED = ("有效", "已签约", "无效")
LIBRARY_TYPES = ("超市电商", "定点供应商", "代理商", "经销商", "超市厂商", "其他")
LIBRARY_ORIGINS = (
    "百度",
    "公共资源",
    "招投标",
    "齐鲁云采",
    "青岛政采",
    "烟台政采",
    "滨州政采",
    "菏泽政采",
    "其他",
)
COMM_TYPES = ("电话", "拜访", "其他")


def _text(payload: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
    return []


def _now_iso() -> str:
    return timezone.now().isoformat()


def normalize_library_contact(payload: dict) -> dict:
    signed = _text(payload, "signed", "status", default="有效")
    if signed not in LIBRARY_SIGNED:
        signed_map = {"0": "有效", "1": "已签约", "2": "无效"}
        signed = signed_map.get(signed, "有效")
    contact_type = _text(payload, "type", "customerType", default="其他")
    if contact_type not in LIBRARY_TYPES:
        contact_type = "其他"
    origin = _text(payload, "origin", "source", default="其他")
    if origin not in LIBRARY_ORIGINS:
        # 原 admin CustomerService.originMap
        origin_map = {
            "1": "百度",
            "2": "公共资源",
            "3": "招投标",
            "4": "齐鲁云采",
            "5": "青岛政采",
            "6": "烟台政采",
            "7": "滨州政采",
            "8": "菏泽政采",
            "9": "其他",
            "10": "其他",
            "0": "其他",
        }
        origin = origin_map.get(origin, origin if origin else "其他")
        if origin not in LIBRARY_ORIGINS:
            origin = "其他"

    records = payload.get("communicationRecords") or payload.get("records") or []
    if not isinstance(records, list):
        records = []
    normalized_records = []
    for item in records:
        if not isinstance(item, dict):
            continue
        normalized_records.append(
            {
                "id": _text(item, "id") or f"lcr-{uuid4().hex[:10]}",
                "type": _text(item, "type", default="电话") if _text(item, "type") in COMM_TYPES else "其他",
                "price": _text(item, "price"),
                "renewPrice": _text(item, "renewPrice", "renew_price"),
                "intention": _text(item, "intention"),
                "term": _text(item, "term"),
                "remark": _text(item, "remark"),
                "createdAt": _text(item, "createdAt", "created_at") or _now_iso(),
                "createdBy": _text(item, "createdBy", "created_by"),
            }
        )

    tags = _tags(payload.get("tags") or payload.get("tag"))
    name = _text(payload, "name", "companyName", "company_name")
    mobile = _text(payload, "mobile", "phone", "tel")
    return {
        "id": _text(payload, "id") or f"lib-{uuid4().hex[:12]}",
        "name": name,
        "legalPerson": _text(payload, "legalPerson", "legal_person"),
        "mobile": mobile,
        "email": _text(payload, "email"),
        "licenseCode": _text(payload, "licenseCode", "license_code"),
        "address": _text(payload, "address"),
        "province": _text(payload, "province", default="山东省"),
        "city": _text(payload, "city", default="济南市"),
        "origin": origin,
        "signed": signed,
        "type": contact_type,
        "tags": tags,
        "sellUserId": _text(payload, "sellUserId", "sell_id", "sellId"),
        "sellUserName": _text(payload, "sellUserName", "sellName", "sell_name"),
        "communicationRecords": normalized_records,
        "createdAt": _text(payload, "createdAt", "created_at") or _now_iso(),
        "updatedAt": _text(payload, "updatedAt", "updated_at") or _now_iso(),
    }


def library_contact_defaults(data: dict) -> dict:
    return {
        "data": data,
        "name": data.get("name") or "",
        "mobile": data.get("mobile") or "",
        "license_code": data.get("licenseCode") or "",
        "signed": data.get("signed") or "有效",
        "origin": data.get("origin") or "其他",
        "customer_type": data.get("type") or "其他",
        "sell_user_id": data.get("sellUserId") or "",
        "created_at": timezone.now(),
    }


def normalize_sms_template(payload: dict) -> dict:
    return {
        "id": _text(payload, "id") or f"smt-{uuid4().hex[:12]}",
        "name": _text(payload, "name"),
        "content": _text(payload, "content", "noteContent"),
        "prefix": _text(payload, "prefix", default="壹知产"),
        "createdAt": _text(payload, "createdAt", "created_at") or _now_iso(),
        "updatedAt": _text(payload, "updatedAt", "updated_at") or _now_iso(),
    }


def sms_template_defaults(data: dict) -> dict:
    return {
        "data": data,
        "name": data.get("name") or "",
        "content": data.get("content") or "",
        "prefix": data.get("prefix") or "",
        "created_at": timezone.now(),
    }


def normalize_sms_record(payload: dict) -> dict:
    failed = payload.get("failedRecords") or payload.get("failed_records") or []
    if not isinstance(failed, list):
        failed = []
    return {
        "id": _text(payload, "id") or f"sms-{uuid4().hex[:12]}",
        "taskId": _text(payload, "taskId", "task_id"),
        "mobile": _text(payload, "mobile", "phone"),
        "content": _text(payload, "content", "noteContent"),
        "prefix": _text(payload, "prefix"),
        "type": _text(payload, "type", default="营销"),
        "source": _text(payload, "source", default="erp"),
        "result": _text(payload, "result", "status", default=""),
        "balance": payload.get("balance") if payload.get("balance") is not None else "",
        "failedRecords": failed,
        "createdAt": _text(payload, "createdAt", "created_at") or _now_iso(),
        "createdBy": _text(payload, "createdBy", "created_by"),
        "createdByUserId": _text(payload, "createdByUserId", "created_by_user_id"),
    }


def sms_record_defaults(data: dict) -> dict:
    balance = data.get("balance")
    try:
        balance_int = int(balance) if balance not in ("", None) else None
    except (TypeError, ValueError):
        balance_int = None
    return {
        "data": data,
        "task_id": data.get("taskId") or "",
        "mobile": data.get("mobile") or "",
        "content": data.get("content") or "",
        "sms_type": data.get("type") or "",
        "source": data.get("source") or "",
        "result": data.get("result") or "",
        "balance": balance_int,
        "created_at": timezone.now(),
    }


def center_sms_config() -> dict[str, str]:
    base = (os.getenv("CENTER_SMS_BASE_URL") or "").strip().rstrip("/")
    token = (os.getenv("CENTER_SMS_TOKEN") or "").strip()
    dry = (os.getenv("CENTER_SMS_DRY_RUN") or "").strip().lower() in {"1", "true", "yes"}
    return {"baseUrl": base, "token": token, "dryRun": "1" if dry or not base else "0"}


def _center_request(method: str, path: str, payload: dict | None = None, params: dict | None = None) -> tuple[dict | list | None, str]:
    cfg = center_sms_config()
    base = cfg["baseUrl"]
    if not base:
        return None, "未配置 CENTER_SMS_BASE_URL"
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, '')})}"
    body = None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if cfg["token"]:
        headers["Authorization"] = f"Bearer {cfg['token']}"
        headers["X-Token"] = cfg["token"]
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return {}, ""
            data = json.loads(raw)
            return data, ""
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        return None, f"center 返回 {exc.code}: {detail or exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return None, f"center 请求失败: {exc}"


def send_sms_via_center(*, mobile: str, content: str, prefix: str = "") -> tuple[dict, str]:
    """发送短信。未配置 center 时走本地记录模式。"""
    cfg = center_sms_config()
    full_content = f"【{prefix}】{content}" if prefix else content
    payload = {
        "mobile": mobile,
        "noteContent": content,
        "content": content,
        "prefix": prefix,
    }
    if cfg["dryRun"] == "1" or not cfg["baseUrl"]:
        return {
            "mode": "local",
            "taskId": f"local-{uuid4().hex[:10]}",
            "result": "本地记录（未对接 center）" if not cfg["baseUrl"] else "dry-run",
            "balance": "",
            "content": full_content,
            "raw": None,
        }, ""

    # 对齐原 admin：营销短信走 /marketing，普通走 /send
    data, error = _center_request("POST", "/marketing", payload)
    if error:
        data, error = _center_request("POST", "/send", payload)
    if error:
        return {}, error
    if isinstance(data, dict):
        code = data.get("code")
        if code not in (None, 0, "0", 200, "200"):
            return {}, str(data.get("msg") or data.get("message") or data.get("detail") or "发送失败")
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        return {
            "mode": "center",
            "taskId": str(inner.get("task_id") or inner.get("taskId") or ""),
            "result": str(inner.get("result") or inner.get("status") or "ok"),
            "balance": inner.get("balance", ""),
            "content": full_content,
            "raw": data,
        }, ""
    return {
        "mode": "center",
        "taskId": "",
        "result": "ok",
        "balance": "",
        "content": full_content,
        "raw": data,
    }, ""


def fetch_center_sms_records(params: dict) -> tuple[dict | None, str]:
    cfg = center_sms_config()
    if not cfg["baseUrl"] or cfg["dryRun"] == "1":
        return None, "center 未配置"
    data, error = _center_request("GET", "/records", params=params)
    if error:
        return None, error
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return {"items": data["data"], "total": int(data.get("total") or len(data["data"]))}, ""
    if isinstance(data, list):
        return {"items": data, "total": len(data)}, ""
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        inner = data["data"]
        items = inner.get("data") or inner.get("items") or []
        return {"items": items, "total": int(inner.get("total") or len(items))}, ""
    return {"items": [], "total": 0}, ""
