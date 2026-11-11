"""客户基础信息：添加（判重后确认更新）。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.models import OrganizationRecord
from apps.data_store.views import _record_defaults

ENTITY_TYPES = ("企业", "个体户", "政府", "事业单位", "学校", "医院", "其他")
TAXPAYER_TYPES = ("一般纳税人", "小规模纳税人", "非企业单位")
ORG_ROLES = (
    "平台入驻商",
    "中间销售商",
    "上游供应商",
    "使用单位",
    "终端采购人",
    "自有主体",
    "客户",
    "供应商",
    "平台入驻客户",
    "本方主体",
)

COMPARE_FIELDS = (
    ("name", "名称"),
    ("unifiedCreditCode", "统一社会信用代码"),
    ("entityType", "实体类型"),
    ("taxpayerType", "纳税人类型"),
    ("roles", "业务身份"),
    ("legalPerson", "法人/负责人"),
    ("phone", "电话"),
    ("email", "邮箱"),
    ("address", "地址"),
    ("city", "城市"),
    ("district", "区县"),
    ("status", "状态"),
)


def _data(record: OrganizationRecord) -> dict[str, Any]:
    return record.data if isinstance(getattr(record, "data", None), dict) else {}


def _normalize_credit_code(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "")).upper()


def _normalize_name(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "")).lower()


def _today() -> str:
    return timezone.localdate().isoformat()


def _now_iso() -> str:
    return timezone.now().isoformat()


def _parse_labeled_text(text: str) -> dict[str, str]:
    raw = (text or "").strip()
    if not raw:
        return {}
    patterns = {
        "name": r"(?:客户名称|单位名称|公司名称|企业名称|名称|客户|公司|单位|企业)\s*[:：]\s*(.+)",
        "unifiedCreditCode": r"(?:统一社会信用代码|信用代码|税号|USCC)\s*[:：]\s*(.+)",
        "entityType": r"(?:实体类型|单位类型|组织类型)\s*[:：]\s*(.+)",
        "taxpayerType": r"(?:纳税人类型|纳税类型)\s*[:：]\s*(.+)",
        "roles": r"(?:业务身份|身份|角色)\s*[:：]\s*(.+)",
        "legalPerson": r"(?:法定代表人|法人代表|法人|负责人)\s*[:：]\s*(.+)",
        "phone": r"(?:联系电话|手机号|电话|手机)\s*[:：]\s*(.+)",
        "email": r"(?:邮箱|邮件|Email|email)\s*[:：]\s*(.+)",
        "address": r"(?:注册地址|地址|住所)\s*[:：]\s*(.+)",
        "city": r"(?:城市|市)\s*[:：]\s*(.+)",
        "district": r"(?:区县|区|县)\s*[:：]\s*(.+)",
        "status": r"(?:状态)\s*[:：]\s*(.+)",
        "id": r"(?:客户ID|组织ID|ID|id)\s*[:：]\s*(.+)",
    }
    out: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            out[key] = match.group(1).strip().strip("，,。；; ")
    return out


def _parse_roles(raw: Any) -> list[str]:
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
    else:
        text = str(raw or "").strip()
        if not text:
            return []
        items = [part.strip() for part in re.split(r"[、,，/|;；\s]+", text) if part.strip()]
    roles: list[str] = []
    for item in items:
        matched = next((role for role in ORG_ROLES if role == item or role in item or item in role), "")
        roles.append(matched or item)
    # 去重保序
    seen: set[str] = set()
    ordered: list[str] = []
    for role in roles:
        if role in seen:
            continue
        seen.add(role)
        ordered.append(role)
    return ordered


def _pick_entity_type(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return "企业"
    for item in ENTITY_TYPES:
        if value == item or item in value or value in item:
            return item
    return "企业"


def _pick_taxpayer_type(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return "一般纳税人"
    for item in TAXPAYER_TYPES:
        if value == item or item in value or value in item:
            return item
    return "一般纳税人"


def _merge_params(params: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_labeled_text(str(params.get("text") or params.get("raw") or ""))
    merged = {
        "id": str(params.get("id") or parsed.get("id") or "").strip(),
        "name": str(
            params.get("name")
            or params.get("customer")
            or params.get("customer_name")
            or parsed.get("name")
            or ""
        ).strip(),
        "unifiedCreditCode": _normalize_credit_code(
            str(
                params.get("unifiedCreditCode")
                or params.get("unified_credit_code")
                or params.get("credit_code")
                or parsed.get("unifiedCreditCode")
                or ""
            )
        ),
        "entityType": _pick_entity_type(
            str(params.get("entityType") or params.get("entity_type") or parsed.get("entityType") or "")
        ),
        "taxpayerType": _pick_taxpayer_type(
            str(params.get("taxpayerType") or params.get("taxpayer_type") or parsed.get("taxpayerType") or "")
        ),
        "roles": _parse_roles(params.get("roles") if "roles" in params else parsed.get("roles")),
        "legalPerson": str(
            params.get("legalPerson") or params.get("legal_person") or parsed.get("legalPerson") or ""
        ).strip(),
        "phone": str(params.get("phone") or params.get("mobile") or parsed.get("phone") or "").strip(),
        "email": str(params.get("email") or parsed.get("email") or "").strip(),
        "address": str(params.get("address") or parsed.get("address") or "").strip(),
        "city": str(params.get("city") or parsed.get("city") or "").strip(),
        "district": str(params.get("district") or parsed.get("district") or "").strip(),
        "status": str(params.get("status") or parsed.get("status") or "正常").strip() or "正常",
        "confirm_update": bool(
            params.get("confirm_update")
            or params.get("confirmUpdate")
            or params.get("force_update")
            or False
        ),
    }
    if not merged["roles"]:
        merged["roles"] = ["平台入驻商"]
    return merged


def _serialize(record: OrganizationRecord) -> dict[str, Any]:
    payload = dict(_data(record))
    return {
        "id": record.id,
        "name": record.name or payload.get("name") or "",
        "entityType": record.entity_type or payload.get("entityType") or "",
        "unifiedCreditCode": record.unified_credit_code or payload.get("unifiedCreditCode") or "",
        "roles": record.roles if isinstance(record.roles, list) else payload.get("roles") or [],
        "taxpayerType": payload.get("taxpayerType") or "",
        "legalPerson": payload.get("legalPerson") or "",
        "phone": payload.get("phone") or payload.get("mobile") or "",
        "email": payload.get("email") or "",
        "address": payload.get("address") or "",
        "city": payload.get("city") or "",
        "district": payload.get("district") or "",
        "status": record.status or payload.get("status") or "正常",
        "createdAt": payload.get("createdAt") or "",
        "updatedAt": payload.get("updatedAt") or "",
    }


def _format_lines(item: dict[str, Any]) -> str:
    roles = item.get("roles") or []
    role_text = "、".join(str(r) for r in roles) if isinstance(roles, list) else str(roles or "")
    lines = [
        f"- ID：{item.get('id') or ''}",
        f"- 名称：{item.get('name') or ''}",
        f"- 统一社会信用代码：{item.get('unifiedCreditCode') or ''}",
        f"- 实体类型：{item.get('entityType') or ''}",
        f"- 纳税人类型：{item.get('taxpayerType') or ''}",
        f"- 业务身份：{role_text or '未设置'}",
        f"- 法人/负责人：{item.get('legalPerson') or '未录入'}",
        f"- 电话：{item.get('phone') or '未录入'}",
        f"- 邮箱：{item.get('email') or '未录入'}",
        f"- 地址：{item.get('address') or '未录入'}",
        f"- 状态：{item.get('status') or ''}",
    ]
    return "\n".join(lines)


def _field_display(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "（空）"
    text = str(value or "").strip()
    return text or "（空）"


def _build_comparison(existing: dict[str, Any], proposed: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, label in COMPARE_FIELDS:
        old = existing.get(key)
        new = proposed.get(key)
        if key == "roles":
            old_norm = _parse_roles(old)
            new_norm = _parse_roles(new)
            changed = old_norm != new_norm
        else:
            changed = _field_display(old) != _field_display(new)
        rows.append(
            {
                "field": key,
                "label": label,
                "existing": _field_display(old),
                "proposed": _field_display(new),
                "changed": "是" if changed else "否",
            }
        )
    return rows


def _format_comparison(rows: list[dict[str, str]]) -> str:
    lines = ["字段 | 现有 | 拟写入 | 是否变化"]
    for row in rows:
        lines.append(
            f"- {row['label']}：{row['existing']} → {row['proposed']}（{row['changed']}）"
        )
    return "\n".join(lines)


def _find_duplicates(*, credit_code: str, name: str, exclude_id: str = "") -> list[OrganizationRecord]:
    qs = OrganizationRecord.objects.filter(is_deleted=False)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    matches: list[OrganizationRecord] = []
    seen: set[str] = set()

    if credit_code:
        for row in qs.filter(unified_credit_code__iexact=credit_code).order_by("-updated_at", "-id")[:10]:
            if row.id not in seen:
                matches.append(row)
                seen.add(row.id)
        # 兼容历史空格/大小写差异：再扫一圈规范化比对
        if not matches:
            for row in qs.exclude(unified_credit_code="").order_by("-updated_at", "-id")[:300]:
                if _normalize_credit_code(row.unified_credit_code) == credit_code and row.id not in seen:
                    matches.append(row)
                    seen.add(row.id)
                    if len(matches) >= 5:
                        break

    norm_name = _normalize_name(name)
    if norm_name:
        for row in qs.filter(name__iexact=name).order_by("-updated_at", "-id")[:10]:
            if row.id not in seen:
                matches.append(row)
                seen.add(row.id)
        if len(matches) < 5:
            for row in qs.filter(name__icontains=name[:20] if len(name) > 20 else name).order_by("-updated_at", "-id")[:40]:
                if _normalize_name(row.name) == norm_name and row.id not in seen:
                    matches.append(row)
                    seen.add(row.id)
                    if len(matches) >= 5:
                        break
    return matches


def _proposed_payload(merged: dict[str, Any], *, existing: OrganizationRecord | None = None) -> dict[str, Any]:
    if existing:
        current = _serialize(existing)
        payload = {
            "id": existing.id,
            "name": merged["name"] or current["name"],
            "entityType": merged["entityType"] or current["entityType"] or "企业",
            "unifiedCreditCode": merged["unifiedCreditCode"] or current["unifiedCreditCode"],
            "roles": merged["roles"] or current["roles"] or ["平台入驻商"],
            "taxpayerType": merged["taxpayerType"] or current["taxpayerType"] or "一般纳税人",
            "legalPerson": merged["legalPerson"] or current["legalPerson"] or None,
            "phone": merged["phone"] or current["phone"] or None,
            "email": merged["email"] or current["email"] or None,
            "address": merged["address"] or current["address"] or None,
            "city": merged["city"] or current["city"] or None,
            "district": merged["district"] or current["district"] or None,
            "status": merged["status"] or current["status"] or "正常",
            "createdAt": current.get("createdAt") or _today(),
            "updatedAt": _now_iso(),
        }
        history = list((_data(existing).get("taxpayerTypeHistory") or []))
        old_type = current.get("taxpayerType") or ""
        new_type = payload["taxpayerType"]
        if new_type and new_type != old_type:
            stamped = []
            for item in history:
                if isinstance(item, dict) and not item.get("endedAt"):
                    stamped.append({**item, "endedAt": _now_iso()})
                elif isinstance(item, dict):
                    stamped.append(item)
            stamped.append({"type": new_type, "effectiveAt": _today(), "changedAt": _now_iso()})
            payload["taxpayerTypeHistory"] = stamped
        elif history:
            payload["taxpayerTypeHistory"] = history
        # 保留执照等不在本次录入范围的字段
        for key in ("licenseFileId", "licenseFileName", "invoiceInfo", "bankInfo"):
            value = _data(existing).get(key)
            if value:
                payload[key] = value
        return {key: value for key, value in payload.items() if value is not None}

    record_id = f"org-{uuid.uuid4().hex[:12]}"
    payload = {
        "id": record_id,
        "name": merged["name"],
        "entityType": merged["entityType"] or "企业",
        "unifiedCreditCode": merged["unifiedCreditCode"],
        "roles": merged["roles"] or ["平台入驻商"],
        "taxpayerType": merged["taxpayerType"] or "一般纳税人",
        "taxpayerTypeHistory": [
            {
                "type": merged["taxpayerType"] or "一般纳税人",
                "effectiveAt": _today(),
                "changedAt": _now_iso(),
            }
        ],
        "legalPerson": merged["legalPerson"] or None,
        "phone": merged["phone"] or None,
        "email": merged["email"] or None,
        "address": merged["address"] or None,
        "city": merged["city"] or None,
        "district": merged["district"] or None,
        "status": merged["status"] or "正常",
        "createdAt": _today(),
        "updatedAt": _now_iso(),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _save_organization(payload: dict[str, Any], *, existing: OrganizationRecord | None = None) -> OrganizationRecord:
    defaults = _record_defaults(OrganizationRecord, payload)
    if existing is None:
        return OrganizationRecord.objects.create(id=payload["id"], is_deleted=False, **defaults)
    for field, value in defaults.items():
        setattr(existing, field, value)
    existing.is_deleted = False
    existing.deleted_at = None
    existing.deleted_by = ""
    existing.save()
    return existing


def _customer_create(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    merged = _merge_params(params)
    missing: list[str] = []
    if not merged["name"]:
        missing.append("名称")
    if not merged["unifiedCreditCode"]:
        missing.append("统一社会信用代码")
    if missing:
        return {
            "block_type": "clarification",
            "summary": "缺少必填项",
            "content": (
                f"添加客户基础信息还需：{'、'.join(missing)}。"
                "可直接传字段，或在 text 中写「名称：xx / 统一社会信用代码：xx / 法人：xx / 电话：xx」。"
            ),
            "data": {"parsed": {k: v for k, v in merged.items() if k != "confirm_update" and v}},
        }

    if merged["confirm_update"]:
        target_id = merged["id"]
        if not target_id:
            return {
                "block_type": "clarification",
                "summary": "缺少更新目标",
                "content": "确认更新时请传 id（来自判重返回的 existing.id），并设 confirm_update=true。",
                "data": {},
            }
        existing = OrganizationRecord.objects.filter(is_deleted=False, id=target_id).first()
        if not existing:
            return {
                "block_type": "clarification",
                "summary": "记录不存在",
                "content": f"未找到客户 ID「{target_id}」，无法更新。",
                "data": {},
            }
        before = _serialize(existing)
        payload = _proposed_payload(merged, existing=existing)
        # 若信用代码改成了别人的，拦截
        code = _normalize_credit_code(str(payload.get("unifiedCreditCode") or ""))
        if code:
            conflict = (
                OrganizationRecord.objects.filter(is_deleted=False)
                .exclude(id=existing.id)
                .filter(unified_credit_code__iexact=code)
                .first()
            )
            if conflict is None:
                for row in OrganizationRecord.objects.filter(is_deleted=False).exclude(id=existing.id).exclude(
                    unified_credit_code=""
                )[:300]:
                    if _normalize_credit_code(row.unified_credit_code) == code:
                        conflict = row
                        break
            if conflict is not None:
                return {
                    "block_type": "clarification",
                    "summary": "信用代码冲突",
                    "content": (
                        f"统一社会信用代码 {code} 已被「{conflict.name}」（{conflict.id}）占用，"
                        "请核对后再更新。"
                    ),
                    "data": {"conflict": _serialize(conflict)},
                }
        record = _save_organization(payload, existing=existing)
        after = _serialize(record)
        comparison = _build_comparison(before, after)
        return {
            "block_type": "tool_result",
            "summary": f"已更新客户：{after['name']}",
            "content": f"已按确认更新客户基础信息：\n{_format_lines(after)}\n\n变更对照：\n{_format_comparison(comparison)}",
            "data": {
                "updated": True,
                "created": False,
                "item": after,
                "comparison": comparison,
            },
        }

    duplicates = _find_duplicates(credit_code=merged["unifiedCreditCode"], name=merged["name"])
    if duplicates:
        proposed = {
            "name": merged["name"],
            "unifiedCreditCode": merged["unifiedCreditCode"],
            "entityType": merged["entityType"],
            "taxpayerType": merged["taxpayerType"],
            "roles": merged["roles"],
            "legalPerson": merged["legalPerson"],
            "phone": merged["phone"],
            "email": merged["email"],
            "address": merged["address"],
            "city": merged["city"],
            "district": merged["district"],
            "status": merged["status"],
        }
        primary = _serialize(duplicates[0])
        comparison = _build_comparison(primary, proposed)
        candidates = [_serialize(row) for row in duplicates]
        return {
            "block_type": "clarification",
            "summary": "发现重复客户，待确认更新",
            "content": (
                f"已存在疑似重复客户「{primary['name']}」（{primary['id']}）。"
                "未写入。请核对下方对照；若确认覆盖更新，请再次调用本工具并传 "
                f"id={primary['id']} 且 confirm_update=true。\n\n"
                f"现有资料：\n{_format_lines(primary)}\n\n"
                f"拟写入：\n{_format_lines({**proposed, 'id': '(新建未写入)'})}\n\n"
                f"对照：\n{_format_comparison(comparison)}"
            ),
            "data": {
                "duplicate": True,
                "requires_confirm_update": True,
                "existing": primary,
                "proposed": proposed,
                "comparison": comparison,
                "candidates": candidates,
            },
        }

    payload = _proposed_payload(merged)
    record = _save_organization(payload)
    item = _serialize(record)
    return {
        "block_type": "tool_result",
        "summary": f"已添加客户：{item['name']}",
        "content": f"未发现重复，已直接添加客户基础信息：\n{_format_lines(item)}",
        "data": {"created": True, "updated": False, "item": item},
    }


def _customer_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(
        params.get("keyword")
        or params.get("search")
        or params.get("name")
        or params.get("customer")
        or ""
    ).strip()
    credit = _normalize_credit_code(
        str(params.get("unifiedCreditCode") or params.get("unified_credit_code") or params.get("credit_code") or "")
    )
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    qs = OrganizationRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if credit:
        qs = qs.filter(unified_credit_code__iexact=credit)
    elif keyword:
        qs = qs.filter(
            Q(name__icontains=keyword) | Q(unified_credit_code__icontains=keyword) | Q(id=keyword)
        )
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    items = [_serialize(row) for row in rows]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 个客户。",
        "content": f"找到 {total} 个客户基础信息。",
        "data": {
            "collection": "organizations",
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "keyword": keyword,
            "unifiedCreditCode": credit,
        },
    }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="erp.customer.search",
            description="查询客户基础信息（名称/统一社会信用代码）",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "客户名、信用代码模糊词"},
                    "search": {"type": "string"},
                    "name": {"type": "string"},
                    "customer": {"type": "string"},
                    "unifiedCreditCode": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="entity.view",
            risk_level="read",
            mcp_expose=True,
            handler=_customer_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.customer.create",
            description=(
                "添加客户基础信息。按统一社会信用代码/名称判重："
                "无重复直接新增；有重复则返回现有与拟写入对照，需再次调用并传 id + confirm_update=true 才更新。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "自由文本，如「名称：济南xx\\n统一社会信用代码：9137...\\n法人：张三\\n电话：138...」",
                    },
                    "name": {"type": "string", "description": "客户/单位名称"},
                    "unifiedCreditCode": {"type": "string", "description": "统一社会信用代码（必填）"},
                    "entityType": {"type": "string", "description": "企业/个体户/政府/事业单位/学校/医院/其他"},
                    "taxpayerType": {"type": "string", "description": "一般纳税人/小规模纳税人/非企业单位"},
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "业务身份，默认平台入驻商",
                    },
                    "legalPerson": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                    "address": {"type": "string"},
                    "city": {"type": "string"},
                    "district": {"type": "string"},
                    "status": {"type": "string"},
                    "id": {"type": "string", "description": "确认更新时传入已有客户 ID"},
                    "confirm_update": {
                        "type": "boolean",
                        "description": "判重后确认覆盖更新时设为 true，并传 id",
                    },
                },
            },
            permission="entity.create",
            risk_level="write",
            mcp_expose=True,
            handler=_customer_create,
        )
    )
