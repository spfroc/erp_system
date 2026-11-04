"""平台账号：查询 / 识别添加 / 编辑。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.models import OrganizationRecord, PlatformAccountRecord
from apps.data_store.views import _ensure_platform_account_timestamps, _record_defaults

KNOWN_PLATFORMS = (
    "泉E采",
    "青慧采",
    "齐鲁云采",
    "政采云",
    "公采云",
    "国铁",
    "美云销",
    "渠道",
    "直客",
    "其他",
)

PUBLIC_FIELDS = (
    "id",
    "customerOrgId",
    "customerName",
    "platform",
    "accountName",
    "merchantId",
    "shopId",
    "shopName",
    "domain",
    "icpRecordNo",
    "cloudAccount",
    "currentStatus",
    "salesOwner",
    "serviceYears",
    "expireDate",
    "note",
    "caStatus",
    "licenseDisplayStatus",
    "publicSecurityStatus",
    "backendTemplateStatus",
    "projectId",
    "createdAt",
    "updatedAt",
)


def _page_params(params: dict[str, Any]) -> tuple[int, int]:
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    return page, page_size


def _data(record: PlatformAccountRecord) -> dict[str, Any]:
    return record.data if isinstance(getattr(record, "data", None), dict) else {}


def _org_name_map(org_ids: set[str] | list[str]) -> dict[str, str]:
    ids = [str(item) for item in org_ids if item]
    if not ids:
        return {}
    rows = OrganizationRecord.objects.filter(is_deleted=False, id__in=ids).only("id", "name")
    return {row.id: row.name or row.id for row in rows}


def _find_orgs(keyword: str, *, limit: int = 20) -> list[OrganizationRecord]:
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    return list(
        OrganizationRecord.objects.filter(is_deleted=False)
        .filter(Q(name__icontains=keyword) | Q(unified_credit_code__icontains=keyword) | Q(id=keyword))
        .order_by("name")[:limit]
    )


def _normalize_platform(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    for platform in KNOWN_PLATFORMS:
        if value == platform or platform in value or value in platform:
            return platform
    aliases = {
        "泉e采": "泉E采",
        "泉易采": "泉E采",
        "青慧": "青慧采",
        "齐鲁": "齐鲁云采",
        "政采": "政采云",
        "公采": "公采云",
    }
    lower = value.lower()
    for key, platform in aliases.items():
        if key in lower or key in value:
            return platform
    return value


def _parse_labeled_text(text: str) -> dict[str, str]:
    """从自由文本识别平台账号字段（键：值 / 键 值）。"""
    raw = (text or "").strip()
    if not raw:
        return {}
    patterns = {
        "customer": r"(?:客户|公司|单位|企业)\s*[:：]\s*(.+)",
        "platform": r"(?:平台|渠道)\s*[:：]\s*(.+)",
        "accountName": r"(?:登录账号|账号名|账号|用户名)\s*[:：]\s*(.+)",
        "accountPassword": r"(?:登录密码|账号密码|密码)\s*[:：]\s*(.+)",
        "merchantId": r"(?:商户号|商户ID|merchant(?:Id)?)\s*[:：]\s*(.+)",
        "shopId": r"(?:店铺号|店铺ID|shop(?:Id)?)\s*[:：]\s*(.+)",
        "shopName": r"(?:店铺名称|店铺名|店名)\s*[:：]\s*(.+)",
        "domain": r"(?:域名|domain)\s*[:：]\s*(.+)",
        "icpRecordNo": r"(?:备案号|ICP)\s*[:：]\s*(.+)",
        "cloudAccount": r"(?:云账号|云账户)\s*[:：]\s*(.+)",
        "currentStatus": r"(?:状态|当前状态)\s*[:：]\s*(.+)",
        "salesOwner": r"(?:业务员|销售|负责人)\s*[:：]\s*(.+)",
        "note": r"(?:备注|说明)\s*[:：]\s*(.+)",
        "id": r"(?:账号ID|记录ID|ID)\s*[:：]\s*(.+)",
    }
    parsed: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            parsed[key] = match.group(1).strip().strip("，,;；")
    return parsed


def _serialize(record: PlatformAccountRecord, names: dict[str, str], *, include_password: bool = False) -> dict[str, Any]:
    data = _data(record)
    item = {
        "id": record.id,
        "customerOrgId": record.customer_org_id or data.get("customerOrgId") or "",
        "customerName": names.get(record.customer_org_id) or "",
        "platform": record.platform or data.get("platform") or "",
        "accountName": record.account_name or data.get("accountName") or "",
        "merchantId": data.get("merchantId") or "",
        "shopId": data.get("shopId") or "",
        "shopName": data.get("shopName") or "",
        "domain": data.get("domain") or "",
        "icpRecordNo": data.get("icpRecordNo") or "",
        "cloudAccount": data.get("cloudAccount") or "",
        "currentStatus": record.current_status or data.get("currentStatus") or "",
        "salesOwner": data.get("salesOwner") or "",
        "serviceYears": data.get("serviceYears"),
        "expireDate": data.get("expireDate") or "",
        "note": data.get("note") or "",
        "caStatus": data.get("caStatus") or "",
        "licenseDisplayStatus": data.get("licenseDisplayStatus") or "",
        "publicSecurityStatus": data.get("publicSecurityStatus") or "",
        "backendTemplateStatus": data.get("backendTemplateStatus") or "",
        "projectId": data.get("projectId") or "",
        "createdAt": data.get("createdAt") or "",
        "updatedAt": data.get("updatedAt") or "",
        "hasPassword": bool(data.get("accountPasswordMasked")),
    }
    if include_password:
        item["accountPassword"] = data.get("accountPasswordMasked") or ""
    return item


def _format_confirm_lines(item: dict[str, Any]) -> str:
    lines = [
        f"ID：{item.get('id') or '—'}",
        f"客户：{item.get('customerName') or item.get('customerOrgId') or '—'}",
        f"平台：{item.get('platform') or '—'}",
        f"账号：{item.get('accountName') or '—'}",
    ]
    if item.get("accountPassword"):
        lines.append(f"密码：{item.get('accountPassword')}")
    elif item.get("hasPassword"):
        lines.append("密码：已设置")
    for label, key in (
        ("商户号", "merchantId"),
        ("店铺号", "shopId"),
        ("店铺名", "shopName"),
        ("域名", "domain"),
        ("备案号", "icpRecordNo"),
        ("云账号", "cloudAccount"),
        ("状态", "currentStatus"),
        ("业务员", "salesOwner"),
        ("备注", "note"),
    ):
        value = item.get(key)
        if value not in (None, ""):
            lines.append(f"{label}：{value}")
    return "\n".join(lines)


def _platform_account_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or params.get("customer") or "").strip()
    platform = _normalize_platform(str(params.get("platform") or "").strip())
    page, page_size = _page_params(params)

    qs = PlatformAccountRecord.objects.filter(is_deleted=False)
    if platform:
        qs = qs.filter(platform=platform)
    if keyword:
        org_ids = [org.id for org in _find_orgs(keyword, limit=50)]
        q = (
            Q(account_name__icontains=keyword)
            | Q(platform__icontains=keyword)
            | Q(current_status__icontains=keyword)
            | Q(data__merchantId__icontains=keyword)
            | Q(data__shopId__icontains=keyword)
            | Q(data__shopName__icontains=keyword)
            | Q(data__domain__icontains=keyword)
            | Q(data__note__icontains=keyword)
            | Q(id__icontains=keyword)
        )
        if org_ids:
            q |= Q(customer_org_id__in=org_ids)
        qs = qs.filter(q)

    total = qs.count()
    rows = list(qs.order_by("-created_at", "-id")[(page - 1) * page_size : page * page_size])
    names = _org_name_map({row.customer_org_id for row in rows})
    items = [_serialize(row, names) for row in rows]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 条平台账号。",
        "content": f"找到 {total} 条平台账号。"
        + (f"关键词「{keyword}」。" if keyword else "")
        + (f"平台「{platform}」。" if platform else ""),
        "data": {
            "collection": "platformAccounts",
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


def _resolve_customer_org(params: dict[str, Any], parsed: dict[str, str]) -> tuple[OrganizationRecord | None, dict[str, Any] | None]:
    customer_org_id = str(params.get("customer_org_id") or params.get("customerOrgId") or "").strip()
    customer = str(params.get("customer") or params.get("customer_name") or parsed.get("customer") or "").strip()
    if customer_org_id:
        org = OrganizationRecord.objects.filter(is_deleted=False, id=customer_org_id).first()
        if not org:
            return None, {
                "block_type": "clarification",
                "summary": "客户不存在",
                "content": f"未找到客户 ID「{customer_org_id}」。",
                "data": {},
            }
        return org, None
    if not customer:
        return None, {
            "block_type": "clarification",
            "summary": "请提供客户",
            "content": "请提供客户名称（或 customer_org_id）。也可在 text 中写「客户：xxx」。",
            "data": {},
        }
    orgs = _find_orgs(customer, limit=8)
    if not orgs:
        return None, {
            "block_type": "clarification",
            "summary": "未匹配到客户",
            "content": f"未找到名称包含「{customer}」的客户，请先在客户基础信息中建档，或提供更准确的名称。",
            "data": {"customer": customer},
        }
    exact = [org for org in orgs if (org.name or "") == customer]
    if len(exact) == 1:
        return exact[0], None
    if len(orgs) == 1:
        return orgs[0], None
    return None, {
        "block_type": "clarification",
        "summary": "客户不唯一",
        "content": f"「{customer}」匹配到多个客户，请改用更精确名称或传入 customer_org_id。",
        "data": {
            "candidates": [{"id": org.id, "name": org.name, "unifiedCreditCode": org.unified_credit_code} for org in orgs],
        },
    }


def _merge_create_params(params: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_labeled_text(str(params.get("text") or params.get("raw") or ""))
    merged = {
        "customer": params.get("customer") or params.get("customer_name") or parsed.get("customer") or "",
        "customer_org_id": params.get("customer_org_id") or params.get("customerOrgId") or "",
        "platform": params.get("platform") or parsed.get("platform") or "",
        "accountName": params.get("accountName") or params.get("account_name") or parsed.get("accountName") or "",
        "accountPassword": params.get("accountPassword")
        or params.get("account_password")
        or params.get("password")
        or parsed.get("accountPassword")
        or "",
        "merchantId": params.get("merchantId") or params.get("merchant_id") or parsed.get("merchantId") or "",
        "shopId": params.get("shopId") or params.get("shop_id") or parsed.get("shopId") or "",
        "shopName": params.get("shopName") or params.get("shop_name") or parsed.get("shopName") or "",
        "domain": params.get("domain") or parsed.get("domain") or "",
        "icpRecordNo": params.get("icpRecordNo") or params.get("icp") or parsed.get("icpRecordNo") or "",
        "cloudAccount": params.get("cloudAccount") or params.get("cloud_account") or parsed.get("cloudAccount") or "",
        "currentStatus": params.get("currentStatus") or params.get("status") or parsed.get("currentStatus") or "已付款待办理",
        "salesOwner": params.get("salesOwner") or params.get("sales_owner") or parsed.get("salesOwner") or "",
        "note": params.get("note") or parsed.get("note") or "",
        "serviceYears": params.get("serviceYears") or params.get("service_years") or 1,
        "projectId": params.get("projectId") or params.get("project_id") or "",
        "_parsed": parsed,
    }
    merged["platform"] = _normalize_platform(str(merged["platform"]))
    return merged


def _platform_account_create(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    merged = _merge_create_params(params)
    org, error = _resolve_customer_org(params, merged.get("_parsed") or {})
    if error:
        return error

    platform = str(merged.get("platform") or "").strip()
    account_name = str(merged.get("accountName") or "").strip()
    password = str(merged.get("accountPassword") or "").strip()
    missing = []
    if not platform:
        missing.append("平台")
    if not account_name:
        missing.append("账号")
    if not password:
        missing.append("密码")
    if missing:
        return {
            "block_type": "clarification",
            "summary": "缺少必填项",
            "content": f"添加平台账号还需：{'、'.join(missing)}。可直接传字段，或在 text 中写「平台：泉E采 / 账号：xx / 密码：xx」。",
            "data": {"parsed": {k: v for k, v in merged.items() if k != "_parsed" and v}},
        }

    assert org is not None
    now = timezone.now().isoformat()
    record_id = f"pa-{uuid.uuid4().hex[:12]}"
    payload = {
        "id": record_id,
        "customerOrgId": org.id,
        "platform": platform,
        "accountName": account_name,
        "accountPasswordMasked": password,
        "merchantId": str(merged.get("merchantId") or "").strip() or None,
        "shopId": str(merged.get("shopId") or "").strip() or None,
        "shopName": str(merged.get("shopName") or "").strip() or None,
        "domain": str(merged.get("domain") or "").strip() or None,
        "icpRecordNo": str(merged.get("icpRecordNo") or "").strip() or None,
        "cloudAccount": str(merged.get("cloudAccount") or "").strip() or None,
        "licenseDisplayStatus": "未处理",
        "publicSecurityStatus": "未处理",
        "backendTemplateStatus": "未录入",
        "caStatus": "未办理",
        "serviceYears": int(merged.get("serviceYears") or 1),
        "salesOwner": str(merged.get("salesOwner") or user_data.get("name") or "").strip() or None,
        "currentStatus": str(merged.get("currentStatus") or "已付款待办理").strip(),
        "note": str(merged.get("note") or "").strip() or None,
        "projectId": str(merged.get("projectId") or "").strip() or None,
        "createdAt": now,
        "updatedAt": now,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    payload = _ensure_platform_account_timestamps(payload)
    defaults = _record_defaults(PlatformAccountRecord, payload)
    record = PlatformAccountRecord.objects.create(id=record_id, is_deleted=False, **defaults)
    item = _serialize(record, {org.id: org.name or org.id}, include_password=True)
    confirm = _format_confirm_lines(item)
    return {
        "block_type": "tool_result",
        "summary": f"已添加平台账号：{org.name} / {platform} / {account_name}",
        "content": f"已添加平台账号，请核对：\n{confirm}",
        "data": {"created": True, "item": item},
    }


def _platform_account_update(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    parsed = _parse_labeled_text(str(params.get("text") or params.get("raw") or ""))
    record_id = str(params.get("id") or params.get("account_id") or parsed.get("id") or "").strip()
    record: PlatformAccountRecord | None = None
    if record_id:
        record = PlatformAccountRecord.objects.filter(is_deleted=False, id=record_id).first()
        if not record:
            return {
                "block_type": "clarification",
                "summary": "记录不存在",
                "content": f"未找到平台账号 ID「{record_id}」。可先用 erp.platform_account.search 查询。",
                "data": {},
            }
    else:
        customer = str(params.get("customer") or parsed.get("customer") or "").strip()
        platform = _normalize_platform(str(params.get("platform") or parsed.get("platform") or "").strip())
        account_name = str(params.get("accountName") or params.get("account_name") or parsed.get("accountName") or "").strip()
        qs = PlatformAccountRecord.objects.filter(is_deleted=False)
        if platform:
            qs = qs.filter(platform=platform)
        if account_name:
            qs = qs.filter(account_name=account_name)
        if customer:
            org_ids = [org.id for org in _find_orgs(customer, limit=20)]
            if org_ids:
                qs = qs.filter(customer_org_id__in=org_ids)
        matches = list(qs.order_by("-updated_at", "-id")[:5])
        if len(matches) == 1:
            record = matches[0]
        elif not matches:
            return {
                "block_type": "clarification",
                "summary": "未找到可编辑记录",
                "content": "请提供 id，或提供足够定位的客户+平台+账号。",
                "data": {},
            }
        else:
            names = _org_name_map({row.customer_org_id for row in matches})
            return {
                "block_type": "clarification",
                "summary": "匹配到多条",
                "content": "匹配到多条平台账号，请传入明确的 id 后再编辑。",
                "data": {"candidates": [_serialize(row, names) for row in matches]},
            }

    assert record is not None
    data = dict(_data(record))
    field_map = {
        "platform": ("platform", _normalize_platform),
        "accountName": ("accountName", str.strip),
        "account_name": ("accountName", str.strip),
        "accountPassword": ("accountPasswordMasked", str.strip),
        "account_password": ("accountPasswordMasked", str.strip),
        "password": ("accountPasswordMasked", str.strip),
        "merchantId": ("merchantId", str.strip),
        "merchant_id": ("merchantId", str.strip),
        "shopId": ("shopId", str.strip),
        "shop_id": ("shopId", str.strip),
        "shopName": ("shopName", str.strip),
        "shop_name": ("shopName", str.strip),
        "domain": ("domain", str.strip),
        "icpRecordNo": ("icpRecordNo", str.strip),
        "icp": ("icpRecordNo", str.strip),
        "cloudAccount": ("cloudAccount", str.strip),
        "cloud_account": ("cloudAccount", str.strip),
        "currentStatus": ("currentStatus", str.strip),
        "status": ("currentStatus", str.strip),
        "salesOwner": ("salesOwner", str.strip),
        "sales_owner": ("salesOwner", str.strip),
        "note": ("note", str.strip),
        "serviceYears": ("serviceYears", lambda v: int(v)),
        "service_years": ("serviceYears", lambda v: int(v)),
        "projectId": ("projectId", str.strip),
        "project_id": ("projectId", str.strip),
    }
    changed: list[str] = []
    source = {**parsed, **params}
    for src_key, (dest_key, transform) in field_map.items():
        if src_key not in source or source.get(src_key) in (None, ""):
            continue
        try:
            value = transform(str(source.get(src_key)))
        except (TypeError, ValueError):
            continue
        if data.get(dest_key) != value:
            data[dest_key] = value
            changed.append(dest_key)

    customer_org_id = str(params.get("customer_org_id") or params.get("customerOrgId") or "").strip()
    customer = str(params.get("customer") or parsed.get("customer") or "").strip()
    if customer_org_id or customer:
        org, error = _resolve_customer_org(params, parsed)
        if error:
            return error
        assert org is not None
        if data.get("customerOrgId") != org.id:
            data["customerOrgId"] = org.id
            changed.append("customerOrgId")

    if not changed:
        return {
            "block_type": "clarification",
            "summary": "没有可更新字段",
            "content": "请提供要修改的字段（如账号、密码、平台、商户号、店铺、状态、备注等）。",
            "data": {"id": record.id},
        }

    data["id"] = record.id
    data["updatedAt"] = timezone.now().isoformat()
    data = _ensure_platform_account_timestamps(data, record)
    for field, value in _record_defaults(PlatformAccountRecord, data).items():
        setattr(record, field, value)
    record.is_deleted = False
    record.deleted_at = None
    record.deleted_by = ""
    record.save()

    names = _org_name_map({record.customer_org_id})
    item = _serialize(record, names, include_password="accountPasswordMasked" in changed)
    confirm = _format_confirm_lines(item)
    return {
        "block_type": "tool_result",
        "summary": f"已更新平台账号 {record.id}",
        "content": f"已更新平台账号（改动：{'、'.join(changed)}），请核对：\n{confirm}",
        "data": {"updated": True, "changed": changed, "item": item},
    }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="erp.platform_account.search",
            description="模糊查询平台账号（客户名/账号/平台/商户号/店铺）",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "客户名、账号、商户号、店铺等模糊词"},
                    "search": {"type": "string"},
                    "customer": {"type": "string"},
                    "platform": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="platformAccount.view",
            risk_level="read",
            handler=_platform_account_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.platform_account.create",
            description="添加平台账号；可用 text 自由文本识别字段。添加成功后返回完整信息便于核对",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "自由文本，如「客户：济南xx\\n平台：泉E采\\n账号：a\\n密码：b」",
                    },
                    "customer": {"type": "string"},
                    "customer_org_id": {"type": "string"},
                    "platform": {"type": "string"},
                    "accountName": {"type": "string"},
                    "accountPassword": {"type": "string"},
                    "merchantId": {"type": "string"},
                    "shopId": {"type": "string"},
                    "shopName": {"type": "string"},
                    "domain": {"type": "string"},
                    "icpRecordNo": {"type": "string"},
                    "cloudAccount": {"type": "string"},
                    "currentStatus": {"type": "string"},
                    "salesOwner": {"type": "string"},
                    "note": {"type": "string"},
                    "serviceYears": {"type": "integer"},
                    "projectId": {"type": "string"},
                },
            },
            permission="platformAccount.manage",
            risk_level="write",
            mcp_expose=True,
            handler=_platform_account_create,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.platform_account.update",
            description="编辑平台账号；优先按 id，也可用客户+平台+账号定位。更新后返回最新信息",
            input_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string", "description": "可含 ID：xxx 及要改的字段"},
                    "customer": {"type": "string"},
                    "customer_org_id": {"type": "string"},
                    "platform": {"type": "string"},
                    "accountName": {"type": "string"},
                    "accountPassword": {"type": "string"},
                    "merchantId": {"type": "string"},
                    "shopId": {"type": "string"},
                    "shopName": {"type": "string"},
                    "domain": {"type": "string"},
                    "icpRecordNo": {"type": "string"},
                    "cloudAccount": {"type": "string"},
                    "currentStatus": {"type": "string"},
                    "salesOwner": {"type": "string"},
                    "note": {"type": "string"},
                    "serviceYears": {"type": "integer"},
                    "projectId": {"type": "string"},
                },
            },
            permission="platformAccount.manage",
            risk_level="write",
            mcp_expose=True,
            handler=_platform_account_update,
        )
    )
