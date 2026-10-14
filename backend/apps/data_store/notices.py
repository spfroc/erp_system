"""Notice upsert helpers and collection runners."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import NoticeCollectionRunRecord, NoticeCollectionSourceRecord, NoticeRecord, WebsiteLeadRecord


def _now_iso() -> str:
    return timezone.now().isoformat()


def _text(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _num(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_notice_payload(payload: dict[str, Any], *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(defaults or {})
    base.update(payload or {})
    notice_id = _text(base, "id") or f"notice-{uuid.uuid4().hex[:12]}"
    title = _text(base, "title", "name")
    now = _now_iso()
    return {
        **base,
        "id": notice_id,
        "title": title,
        "projectNumber": _text(base, "projectNumber", "project_number"),
        "planNumber": _text(base, "planNumber", "plan_number"),
        "supplierName": _text(base, "supplierName", "supplier_name"),
        "department": _text(base, "department"),
        "category": _text(base, "category"),
        "noticeKind": _text(base, "noticeKind", "notice_kind") or "竞价项目",
        "bidStatus": _text(base, "bidStatus", "bid_status", "status"),
        "amount": float(_num(base.get("amount") if base.get("amount") is not None else base.get("total"))),
        "contactName": _text(base, "contactName", "contact_name", "contract"),
        "contactPhone": _text(base, "contactPhone", "contact_phone", "tel"),
        "detailUrl": _text(base, "detailUrl", "detail_url", "detail_page_link"),
        "content": _text(base, "content"),
        "publisher": _text(base, "publisher", "userName"),
        "startAt": _text(base, "startAt", "start_time", "start_at"),
        "endAt": _text(base, "endAt", "end_time", "end_at"),
        "publishedAt": _text(base, "publishedAt", "published_at", "date") or now,
        "isPublic": _bool(base.get("isPublic", base.get("is_public")), False),
        "source": _text(base, "source") or "manual",
        "externalId": _text(base, "externalId", "external_id"),
        "sourceId": _text(base, "sourceId", "source_id"),
        "matchedKeywords": list(base.get("matchedKeywords") or base.get("matched_keywords") or []),
        "createdAt": _text(base, "createdAt", "created_at") or now,
        "updatedAt": now,
    }


def notice_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    data = normalize_notice_payload(payload)
    return {
        "data": data,
        "title": data.get("title", ""),
        "project_number": data.get("projectNumber", "") or "",
        "supplier_name": data.get("supplierName", "") or "",
        "department": data.get("department", "") or "",
        "category": data.get("category", "") or "",
        "notice_kind": data.get("noticeKind", "") or "竞价项目",
        "bid_status": data.get("bidStatus", "") or "",
        "amount": _num(data.get("amount")),
        "is_public": bool(data.get("isPublic")),
        "source": data.get("source", "") or "manual",
        "external_id": data.get("externalId", "") or "",
        "published_at": data.get("publishedAt", "") or "",
    }


def upsert_notice(payload: dict[str, Any]) -> tuple[NoticeRecord, bool]:
    data = normalize_notice_payload(payload)
    external_id = data.get("externalId") or ""
    existing = None
    if external_id:
        existing = NoticeRecord.objects.filter(is_deleted=False, external_id=external_id).first()
    if not existing:
        existing = NoticeRecord.objects.filter(id=data["id"]).first()
    if existing:
        merged = normalize_notice_payload({**existing.data, **data, "id": existing.id, "createdAt": existing.data.get("createdAt") or data["createdAt"]})
        defaults = notice_defaults(merged)
        defaults["is_deleted"] = False
        defaults["deleted_at"] = None
        defaults["deleted_by"] = ""
        for key, value in defaults.items():
            setattr(existing, key, value)
        existing.save()
        return existing, False
    defaults = notice_defaults(data)
    record = NoticeRecord.objects.create(id=data["id"], **defaults)
    return record, True


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    haystack = (text or "").lower()
    hits = []
    for keyword in keywords:
        key = str(keyword or "").strip()
        if key and key.lower() in haystack:
            hits.append(key)
    return hits


def _create_lead_from_notice(notice: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return False
    company = notice.get("department") or notice.get("supplierName") or notice.get("publisher") or "公告命中"
    phone = notice.get("contactPhone") or "未提供"
    contact = notice.get("contactName") or ""
    remark = (
        f"公告采集命中关键字：{', '.join(keywords)}；"
        f"标题：{notice.get('title', '')}；"
        f"项目编号：{notice.get('projectNumber', '')}；"
        f"详情：{notice.get('detailUrl', '')}"
    )
    external_key = notice.get("externalId") or notice.get("id")
    existing = WebsiteLeadRecord.objects.filter(
        is_deleted=False,
        data__remark__icontains=f"标题：{notice.get('title', '')}",
    ).first()
    if existing:
        return False
    lead_id = f"lead-notice-{uuid.uuid4().hex[:10]}"
    now = _now_iso()
    payload = {
        "id": lead_id,
        "companyName": company,
        "phone": phone,
        "contactName": contact,
        "platform": "其他",
        "remark": remark,
        "status": "未跟进",
        "createdAt": now,
        "source": "公告采集",
        "noticeId": notice.get("id"),
        "externalKey": external_key,
        "matchedKeywords": keywords,
    }
    WebsiteLeadRecord.objects.create(
        id=lead_id,
        data=payload,
        company_name=payload["companyName"],
        phone=payload["phone"],
        contact_name=payload["contactName"],
        platform=payload["platform"],
        status=payload["status"],
        created_at=timezone.now(),
    )
    return True


def _sample_notices() -> list[dict[str, Any]]:
    now = _now_iso()
    return [
        {
            "externalId": "sample-notice-1",
            "title": "济南市某单位办公设备采购竞价",
            "projectNumber": "JN-SAMPLE-001",
            "planNumber": "PLAN-001",
            "supplierName": "示例供应商A",
            "department": "济南市示例采购单位",
            "category": "办公设备",
            "noticeKind": "竞价项目",
            "bidStatus": "竞价中",
            "amount": 128000,
            "contactName": "王采购",
            "contactPhone": "13800001111",
            "detailUrl": "https://www.qlyc.co/",
            "publishedAt": now,
            "isPublic": True,
            "source": "collect",
        },
        {
            "externalId": "sample-notice-2",
            "title": "山东省某厅信息化服务意向公开",
            "projectNumber": "SD-SAMPLE-002",
            "department": "山东省示例厅局",
            "category": "信息化服务",
            "noticeKind": "意向公开",
            "bidStatus": "",
            "amount": 0,
            "publisher": "山东省公共资源交易中心",
            "content": "拟采购信息化运维服务，欢迎具备齐鲁云采入驻资质的供应商关注。",
            "detailUrl": "https://www.qlyc.co/",
            "publishedAt": now,
            "isPublic": True,
            "source": "collect",
        },
    ]


def _fetch_http_json(url: str) -> list[dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "yzc-erp-notice-collector/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "list", "records"):
            value = payload.get(key)
            if isinstance(value, dict) and isinstance(value.get("data"), list):
                return [item for item in value["data"] if isinstance(item, dict)]
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def run_collection_source(source: NoticeCollectionSourceRecord) -> NoticeCollectionRunRecord:
    started = _now_iso()
    run_id = f"ncr-{uuid.uuid4().hex[:12]}"
    source_data = dict(source.data or {})
    keywords = [str(item).strip() for item in (source_data.get("keywords") or []) if str(item).strip()]
    run_data = {
        "id": run_id,
        "sourceId": source.id,
        "sourceName": source.name,
        "status": "进行中",
        "fetchedCount": 0,
        "createdCount": 0,
        "updatedCount": 0,
        "leadCount": 0,
        "startedAt": started,
        "createdAt": started,
    }
    run = NoticeCollectionRunRecord.objects.create(
        id=run_id,
        data=run_data,
        source_id=source.id,
        source_name=source.name,
        status="进行中",
        started_at=started,
        created_at=timezone.now(),
    )
    created = updated = leads = 0
    error_message = ""
    try:
        kind = source.kind or source_data.get("kind") or ""
        if kind == "sample":
            items = _sample_notices()
        elif kind == "http_json":
            url = _text(source_data, "endpointUrl", "endpoint_url")
            if not url:
                raise ValueError("http_json 来源需要配置 endpointUrl")
            items = _fetch_http_json(url)
        else:
            raise ValueError(f"暂不支持的采集类型：{kind or '未设置'}")

        for raw in items:
            payload = normalize_notice_payload(
                {
                    **raw,
                    "source": "collect",
                    "sourceId": source.id,
                    "isPublic": raw.get("isPublic", source_data.get("defaultIsPublic", False)),
                }
            )
            text = " ".join(
                [
                    payload.get("title", ""),
                    payload.get("department", ""),
                    payload.get("category", ""),
                    payload.get("content", ""),
                    payload.get("supplierName", ""),
                ]
            )
            matched = _match_keywords(text, keywords)
            payload["matchedKeywords"] = matched
            record, was_created = upsert_notice(payload)
            if was_created:
                created += 1
            else:
                updated += 1
            if matched and _create_lead_from_notice(record.data, matched):
                leads += 1

        status = "成功"
        finished = _now_iso()
        run_data.update(
            {
                "status": status,
                "fetchedCount": len(items),
                "createdCount": created,
                "updatedCount": updated,
                "leadCount": leads,
                "finishedAt": finished,
                "updatedAt": finished,
            }
        )
        run.data = run_data
        run.status = status
        run.fetched_count = len(items)
        run.created_count = created
        run.updated_count = updated
        run.lead_count = leads
        run.finished_at = finished
        run.save()

        source_data.update({"lastRunAt": finished, "lastStatus": status})
        source.data = source_data
        source.last_run_at = finished
        source.last_status = status
        source.save(update_fields=["data", "last_run_at", "last_status", "updated_at"])
        return run
    except Exception as exc:  # noqa: BLE001 - surface collector failures to UI
        error_message = str(exc)
        finished = _now_iso()
        run_data.update(
            {
                "status": "失败",
                "errorMessage": error_message,
                "fetchedCount": 0,
                "createdCount": created,
                "updatedCount": updated,
                "leadCount": leads,
                "finishedAt": finished,
                "updatedAt": finished,
            }
        )
        run.data = run_data
        run.status = "失败"
        run.finished_at = finished
        run.save()
        source_data.update({"lastRunAt": finished, "lastStatus": "失败", "lastError": error_message})
        source.data = source_data
        source.last_run_at = finished
        source.last_status = "失败"
        source.save(update_fields=["data", "last_run_at", "last_status", "updated_at"])
        return run


def ensure_default_sample_source() -> NoticeCollectionSourceRecord:
    existing = NoticeCollectionSourceRecord.objects.filter(is_deleted=False, kind="sample").first()
    if existing:
        return existing
    now = _now_iso()
    source_id = "ncs-sample"
    data = {
        "id": source_id,
        "name": "示例采集源",
        "kind": "sample",
        "enabled": True,
        "keywords": ["齐鲁云采", "办公设备", "信息化"],
        "defaultIsPublic": True,
        "createdAt": now,
        "updatedAt": now,
    }
    return NoticeCollectionSourceRecord.objects.create(
        id=source_id,
        data=data,
        name=data["name"],
        kind=data["kind"],
        enabled=True,
        created_at=timezone.now(),
    )
