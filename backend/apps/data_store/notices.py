"""Notice upsert helpers and collection runners."""

from __future__ import annotations

import json
import re
import uuid
from decimal import Decimal
from typing import Any
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import NoticeCollectionRunRecord, NoticeCollectionSourceRecord, NoticeRecord, WebsiteLeadRecord

_MASK_TOKEN = "登录可见"
_ATTACHMENT_LOCKED = "登录后可下载附件"
_GUEST_CONTENT_LINES = 10
_MOBILE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
# 未标注固话要求带分隔符，避免误伤项目编号中的连续数字
_LANDLINE_RE = re.compile(r"(?<!\d)(0\d{2,3}-\d{7,8})(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_CONTACT_LABEL_RE = re.compile(
    r"((?:项目|采购人|采购单位)?联系人|联系方式|联系电话|手机号码?|电话(?:号码)?)\s*[:：]\s*"
    r"([^\n\r<，,；;。、]{1,30})"
)
_ATTACHMENT_HREF_RE = re.compile(
    r"\.(?:pdf|docx?|xlsx?|xls|zip|rar|7z|wps|ofd|csv|pptx?)(?:\?|#|$)",
    re.I,
)
_HTML_ANCHOR_RE = re.compile(
    r"<a\b([^>]*?)href\s*=\s*(['\"])(.*?)\2([^>]*)>([\s\S]*?)</a>",
    re.I,
)
_HTML_BLOCK_SPLIT_RE = re.compile(
    r"(?i)((?:</(?:p|div|tr|li|h[1-6]|table|section|article|br)\s*>)|(?:<br\s*/?>)|(?:\n+))"
)


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


# 官网筛选：与爬虫/门户类型对齐（旧 CMS「竞价项目」仍兼容兜底列表）
PUBLIC_NOTICE_KINDS = [
    "采购公告",
    "竞价公告",
    "询比公告",
    "意向公开",
    "成交公告",
    "结果公告",
    "终止公告",
    "失败公告",
    "废标公告",
    "更正公告",
    "合同公告",
    "验收公告",
    "单一来源公示",
    "竞价项目",
    "其他",
]


def public_notice_payload(record: NoticeRecord) -> dict[str, Any]:
    data = dict(record.data or {})
    return {
        "id": record.id,
        "title": record.title or data.get("title") or "",
        "projectNumber": record.project_number or data.get("projectNumber") or "",
        "department": record.department or data.get("department") or "",
        "category": record.category or data.get("category") or "",
        "noticeKind": record.notice_kind or data.get("noticeKind") or "其他",
        "bidStatus": record.bid_status or data.get("bidStatus") or "",
        "amount": float(record.amount or 0),
        "contactName": data.get("contactName") or "",
        "contactPhone": data.get("contactPhone") or "",
        "detailUrl": data.get("detailUrl") or "",
        "content": data.get("content") or "",
        "publisher": data.get("publisher") or "",
        "supplierName": record.supplier_name or data.get("supplierName") or "",
        "startAt": data.get("startAt") or "",
        "endAt": data.get("endAt") or "",
        "publishedAt": record.published_at or data.get("publishedAt") or "",
    }


def _money_float(value) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def mask_sensitive_notice_text(value: str, *, extras: list[str] | None = None) -> str:
    """遮蔽正文中的联系人/电话/邮箱等敏感片段。"""
    text = str(value or "")
    if not text:
        return text
    text = _CONTACT_LABEL_RE.sub(lambda m: f"{m.group(1)}：{_MASK_TOKEN}", text)
    text = _MOBILE_RE.sub(_MASK_TOKEN, text)
    text = _LANDLINE_RE.sub(_MASK_TOKEN, text)
    text = _EMAIL_RE.sub(_MASK_TOKEN, text)
    for extra in extras or []:
        token = str(extra or "").strip()
        if len(token) < 2:
            continue
        text = text.replace(token, _MASK_TOKEN)
    return text


def neutralize_notice_attachment_links(value: str) -> str:
    """未登录：去掉可下载附件链接，避免前端隐藏后仍能直链下载。"""
    text = str(value or "")
    if not text:
        return text

    def _replace(match: re.Match[str]) -> str:
        href = str(match.group(3) or "")
        inner = str(match.group(5) or "")
        label = re.sub(r"<[^>]+>", "", inner)
        if _ATTACHMENT_HREF_RE.search(href) or ("附件" in label):
            return f'<span class="attachment-locked">{_ATTACHMENT_LOCKED}</span>'
        return match.group(0)

    if "<a" in text.lower():
        text = _HTML_ANCHOR_RE.sub(_replace, text)
    # 纯文本里的附件直链也抹掉
    text = re.sub(
        r"https?://[^\s<>'\"]+\.(?:pdf|docx?|xlsx?|xls|zip|rar|7z|wps|ofd|csv|pptx?)(?:\?[^\s<>'\"]*)?",
        _ATTACHMENT_LOCKED,
        text,
        flags=re.I,
    )
    return text


def truncate_notice_content_preview(value: str, *, max_lines: int = _GUEST_CONTENT_LINES) -> str:
    """未登录正文预览：约保留前 N 个块/行，供详情渐变遮罩。"""
    text = str(value or "").strip()
    if not text or max_lines <= 0:
        return text
    # 泉E采/青慧采组装正文：按完整区块截断，避免半截 HTML
    if 'class="jd-notice-body"' in text or "class='jd-notice-body'" in text:
        chunks = re.findall(
            r'(?:<div class="jd-meta-grid">[\s\S]*?</div>)|(?:<section class="jd-notice-section">[\s\S]*?</section>)',
            text,
        )
        if chunks:
            kept = chunks[: max(2, min(max_lines, 4))]
            return '<div class="jd-notice-body">' + "".join(kept) + "</div>"
    parts = _HTML_BLOCK_SPLIT_RE.split(text)
    if len(parts) <= 1:
        lines = [line for line in re.split(r"\r\n|\r|\n", text) if line.strip()]
        if len(lines) <= max_lines:
            return text
        return "\n".join(lines[:max_lines])

    kept: list[str] = []
    blocks = 0
    for part in parts:
        kept.append(part)
        if _HTML_BLOCK_SPLIT_RE.fullmatch(part or ""):
            blocks += 1
            if blocks >= max_lines:
                break
    preview = "".join(kept).strip()
    if len(preview) > 2500:
        preview = preview[:2500]
    return preview or text[:1200]


def mask_public_notice_sensitive(item: dict[str, Any]) -> dict[str, Any]:
    """未登录公开详情：正文仅预览、去附件链，并遮蔽联系方式。"""
    data = dict(item or {})
    extras = [
        data.get("contactName") or "",
        data.get("buyerContactName") or "",
        data.get("contactPhone") or "",
        data.get("buyerPhone") or "",
    ]
    for key in ("content", "contentText", "contentHtml"):
        if data.get(key):
            value = neutralize_notice_attachment_links(str(data.get(key) or ""))
            value = mask_sensitive_notice_text(value, extras=extras)
            data[key] = truncate_notice_content_preview(value)
    for key in ("contactName", "contactPhone", "buyerContactName", "buyerPhone"):
        if data.get(key):
            data[key] = _MASK_TOKEN
    # 未登录不返回可下载附件清单
    if "attachments" in data:
        data["attachments"] = []
    data["contentPreviewOnly"] = True
    data["attachmentsLocked"] = True
    return data


def _public_payload_from_crawled(item: dict[str, Any]) -> dict[str, Any]:
    """把爬虫列表/详情字段映射成官网 notices 页使用的结构。"""
    amount = item.get("dealAmount")
    if amount in (None, ""):
        amount = item.get("budgetAmount")
    published = item.get("publishTime") or item.get("publishedAt") or ""
    content_text = item.get("contentText") or ""
    content_html = item.get("contentHtml") or ""
    return {
        "id": str(item.get("id") or ""),
        "title": item.get("title") or "",
        "projectNumber": item.get("projectCode") or "",
        "projectCode": item.get("projectCode") or "",
        "projectName": item.get("projectName") or "",
        "department": item.get("buyerName") or "",
        "buyerName": item.get("buyerName") or "",
        "category": item.get("procurementMode") or item.get("siteLabel") or "",
        "noticeKind": item.get("noticeKind") or "其他",
        "bidStatus": item.get("progressLabel") or "",
        "progressLabel": item.get("progressLabel") or "",
        "progressStatus": item.get("progressStatus") or "",
        "amount": _money_float(amount),
        "budgetAmount": item.get("budgetAmount"),
        "dealAmount": item.get("dealAmount"),
        "contactName": item.get("buyerContactName") or item.get("contactName") or "",
        "contactPhone": item.get("buyerPhone") or item.get("contactPhone") or "",
        "buyerContactName": item.get("buyerContactName") or "",
        "buyerPhone": item.get("buyerPhone") or "",
        "detailUrl": item.get("sourceUrl") or "",
        "sourceUrl": item.get("sourceUrl") or "",
        "content": content_text or "",
        "contentText": content_text or "",
        "contentHtml": content_html or "",
        "publisher": item.get("siteLabel") or "",
        "supplierName": item.get("dealSupplier") or "",
        "startAt": item.get("startTime") or "",
        "endAt": item.get("endTime") or "",
        "startTime": item.get("startTime") or "",
        "endTime": item.get("endTime") or "",
        "publishTime": published,
        "publishedAt": published,
        "regionName": item.get("regionName") or "",
        "procurementMode": item.get("procurementMode") or "",
        "siteId": item.get("siteId") or "",
        "siteLabel": item.get("siteLabel") or "",
    }


def _list_public_notices_from_crawler(
    *,
    page: int,
    page_size: int,
    search: str,
    notice_kind: str,
) -> dict[str, Any] | None:
    """优先读爬虫公告；表不存在或不可用时返回 None，走 CMS 兜底。"""
    try:
        from django.db.utils import OperationalError, ProgrammingError

        from .notice_views import query_crawled_notices
    except Exception:
        return None
    try:
        payload = query_crawled_notices(
            page=page,
            page_size=page_size,
            search=search,
            notice_kind=notice_kind if notice_kind and notice_kind != "全部" else "",
            site_ids=None,
        )
    except (ProgrammingError, OperationalError):
        return None
    total = int(payload.get("total") or 0)
    if total <= 0 and not (search or (notice_kind and notice_kind != "全部")):
        # 空库时仍允许 CMS 样例公告，避免开发/测试环境完全空白
        return None
    return {
        "items": [_public_payload_from_crawled(item) for item in (payload.get("items") or [])],
        "total": total,
        "page": int(payload.get("page") or page),
        "page_size": int(payload.get("page_size") or page_size),
        "kinds": PUBLIC_NOTICE_KINDS,
        "source": "crawler",
    }


def _get_public_notice_from_crawler(notice_id: str) -> dict[str, Any] | None:
    try:
        raw_id = int(str(notice_id).strip())
    except (TypeError, ValueError):
        return None
    try:
        from django.db.utils import OperationalError, ProgrammingError

        from .notice_models import NoticeGoods, NoticeParsed, NoticeRaw
        from .notice_views import _serialize_detail
    except Exception:
        return None
    try:
        raw = NoticeRaw.objects.filter(id=raw_id).first()
        if not raw:
            return None
        parsed = NoticeParsed.objects.filter(notice_raw_id=raw.id).first()
        goods = list(NoticeGoods.objects.filter(notice_raw_id=raw.id).order_by("line_no", "id"))
        return _public_payload_from_crawled(_serialize_detail(raw, parsed, goods))
    except (ProgrammingError, OperationalError):
        return None


def list_public_notices(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    notice_kind: str = "",
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = min(50, max(1, int(page_size or 20)))
    crawled = _list_public_notices_from_crawler(
        page=page,
        page_size=page_size,
        search=search,
        notice_kind=notice_kind,
    )
    if crawled is not None:
        return crawled

    queryset = NoticeRecord.objects.filter(is_deleted=False, is_public=True)
    kind = (notice_kind or "").strip()
    if kind and kind != "全部":
        queryset = queryset.filter(notice_kind=kind)
    keyword = (search or "").strip()
    if keyword:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(project_number__icontains=keyword)
            | Q(department__icontains=keyword)
            | Q(supplier_name__icontains=keyword)
            | Q(category__icontains=keyword)
            | Q(notice_kind__icontains=keyword)
            | Q(data__content__icontains=keyword)
        )
    total = queryset.count()
    rows = queryset.order_by("-published_at", "-updated_at", "-id")[(page - 1) * page_size : page * page_size]
    return {
        "items": [public_notice_payload(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "kinds": PUBLIC_NOTICE_KINDS,
        "source": "cms",
    }


def get_public_notice(notice_id: str) -> dict[str, Any] | None:
    crawled = _get_public_notice_from_crawler(notice_id)
    if crawled is not None:
        return crawled
    record = NoticeRecord.objects.filter(id=notice_id, is_deleted=False, is_public=True).first()
    if not record:
        return None
    return public_notice_payload(record)


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
