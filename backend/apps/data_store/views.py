import json
import re
import uuid
from decimal import Decimal
from urllib.parse import quote

from django.contrib.auth.hashers import check_password, identify_hasher, is_password_usable, make_password
from django.db import transaction
from django.db.models import CharField, Q, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce, Left, Replace
from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods

from .models import (
    AppState,
    InvoiceRecord,
    ManagedFile,
    NoticeCollectionRunRecord,
    NoticeCollectionSourceRecord,
    NoticeRecord,
    OfficialPageRecord,
    OfficialSiteRecord,
    OcrJobRecord,
    OnboardingRecord,
    OperationLogRecord,
    OptionGroupRecord,
    OrganizationRecord,
    PlatformAccountRecord,
    ProductRecord,
    ProjectItemRecord,
    ProjectRecord,
    ProjectMemoRecord,
    ProjectReminderRecord,
    PurchaseOrderRecord,
    RoleRecord,
    SalesOrderRecord,
    ServiceOrderRecord,
    SupplierPriceRecord,
    TrademarkCertificateRecord,
    TransactionRecord,
    UserRecord,
    WebsiteLeadRecord,
)
from .notices import (
    ensure_default_sample_source,
    get_public_notice,
    list_public_notices,
    normalize_notice_payload,
    notice_defaults,
    run_collection_source,
)
from .official_sites import (
    apply_official_seo_defaults,
    ensure_default_official_sites,
    find_official_site_by_host,
    normalize_page_payload,
    normalize_site_payload,
    page_defaults,
    public_seo_payload,
    resolve_public_site,
    site_defaults,
)

from .finance_statements import build_finance_statement_rows, orphaned_transaction_ids
from .service_contract import (
    apply_draft_overrides,
    build_default_draft,
    has_service_contract_template,
    missing_required_fields,
    normalize_contract_format,
    normalize_contract_platform,
    render_contract_file,
)


DEFAULT_KEY = "default"
LEAD_PLATFORMS = {"泉E采", "齐鲁云采", "青慧采", "政采云", "公采云", "国铁", "其他"}


COLLECTIONS = {
    "roles": RoleRecord,
    "users": UserRecord,
    "organizations": OrganizationRecord,
    "products": ProductRecord,
    "supplierPrices": SupplierPriceRecord,
    "projects": ProjectRecord,
    "projectItems": ProjectItemRecord,
    "salesOrders": SalesOrderRecord,
    "purchaseOrders": PurchaseOrderRecord,
    "serviceOrders": ServiceOrderRecord,
    "onboardingRecords": OnboardingRecord,
    "platformAccounts": PlatformAccountRecord,
    "websiteLeads": WebsiteLeadRecord,
    "projectReminders": ProjectReminderRecord,
    "projectMemos": ProjectMemoRecord,
    "optionGroups": OptionGroupRecord,
    "invoices": InvoiceRecord,
    "transactions": TransactionRecord,
    "operationLogs": OperationLogRecord,
    "ocrJobs": OcrJobRecord,
    "trademarkCertificates": TrademarkCertificateRecord,
    "notices": NoticeRecord,
    "noticeCollectionSources": NoticeCollectionSourceRecord,
    "noticeCollectionRuns": NoticeCollectionRunRecord,
    "officialSites": OfficialSiteRecord,
    "officialPages": OfficialPageRecord,
}

APP_DATA_OPERATION_LOG_LIMIT = 300

COLLECTION_PERMISSIONS = {
    "roles": {"read": "user.manage", "write": "user.manage"},
    "users": {"read": "user.manage", "write": "user.manage"},
    "organizations": {"read": "entity.view", "write": "entity.create"},
    "products": {"read": "product.view", "write": "product.manage"},
    "supplierPrices": {"read": "product.view", "write": "product.manage"},
    "projects": {"read": "project.view", "write": "project.edit"},
    "projectItems": {"read": "project.view", "write": "project.edit"},
    "salesOrders": {"read": "salesOrder.view", "write": "salesOrder.manage"},
    "purchaseOrders": {"read": "purchaseOrder.view", "write": "purchaseOrder.manage"},
    "serviceOrders": {"read": "serviceOrder.view", "write": "serviceOrder.manage"},
    "contracts": {"read": "project.view", "write": "project.edit"},
    "onboardingRecords": {"read": "onboarding.manage", "write": "onboarding.manage"},
    "platformAccounts": {"read": "platformAccount.view", "write": "platformAccount.manage"},
    "websiteLeads": {"read": "lead.manage", "write": "lead.manage"},
    "projectReminders": {"read": "dashboard.view", "write": "dashboard.view"},
    "projectMemos": {"read": "project.view", "write": "project.view"},
    "optionGroups": {"read": "user.manage", "write": "user.manage"},
    "invoices": {"read": "invoice.manage", "write": "invoice.manage"},
    "transactions": {"read": "finance.view", "write": "finance.manage"},
    "financeStatements": {"read": "finance.view", "write": "finance.view"},
    "operationLogs": {"read": "user.manage", "write": "user.manage"},
    "ocrJobs": {"read": "project.view", "write": "project.edit"},
    "trademarkCertificates": {"read": "trademarkCertificate.view", "write": "trademarkCertificate.manage"},
    "notices": {"read": "notice.view", "write": "notice.manage"},
    "noticeCollectionSources": {"read": "notice.view", "write": "notice.manage"},
    "noticeCollectionRuns": {"read": "notice.view", "write": "notice.manage"},
    "officialSites": {"read": "site.view", "write": "site.manage"},
    "officialPages": {"read": "site.view", "write": "site.manage"},
}


class ProtectedOrganizationError(ValueError):
    def __init__(self, organization_ids: set[str], references: dict[str, int]):
        self.organization_ids = organization_ids
        self.references = references
        super().__init__("Organization is still referenced by business data.")

PLATFORM_SENSITIVE_FIELDS = {
    "accountName",
    "accountPasswordMasked",
    "supplierAccount",
    "supplierPasswordMasked",
    "cloudAccount",
    "cloudPasswordMasked",
    "caAccount",
    "caPasswordMasked",
}
USER_SENSITIVE_FIELDS = {"password"}


def _num(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _text(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


LEAD_PLATFORM_ALIASES = (
    ("泉E采", ("泉E采", "泉E", "泉e", "泉易")),
    ("齐鲁云采", ("齐鲁云采", "齐鲁")),
    ("青慧采", ("青慧采", "青慧")),
    ("政采云", ("政采云",)),
    ("公采云", ("公采云",)),
    ("国铁", ("国铁",)),
)


def _normalize_lead_platform(raw: str) -> tuple[str, str]:
    platform = (raw or "").strip()
    if not platform:
        return "其他", ""
    if platform in LEAD_PLATFORMS:
        return platform, ""
    for canonical, keys in LEAD_PLATFORM_ALIASES:
        if any(key in platform for key in keys):
            return canonical, "" if platform == canonical else platform
    return "其他", platform


def _unwrap_lead_payload(payload: dict) -> dict:
    inner = payload.get("data")
    if isinstance(inner, dict) and not _text(payload, "phone", "mobile", "tel"):
        return inner
    return payload


def parse_website_lead_payload(payload: dict) -> tuple[dict | None, str]:
    if not isinstance(payload, dict):
        return None, "JSON body must be an object."

    payload = _unwrap_lead_payload(payload)
    company_name = _text(
        payload,
        "companyName",
        "company_name",
        "enterprise_name",
        "enterpriseName",
        "company",
    )
    dedicated_contact = _text(payload, "contactName", "contact_name", "contact", "联系人")
    contact_name = dedicated_contact or _text(payload, "name")
    if not company_name:
        company_name = _text(payload, "name")
        if company_name and not dedicated_contact:
            contact_name = ""

    phone = _text(payload, "phone", "mobile", "mobilePhone", "mobile_phone", "tel")
    platform, extra_platform = _normalize_lead_platform(
        _text(payload, "platform", "platform_name", "platformName", "平台")
    )
    remark = _text(payload, "remark", "requirement", "note", "message", "备注")
    if extra_platform:
        extra = f"平台：{extra_platform}"
        remark = f"{remark}；{extra}" if remark else extra

    if not company_name:
        return None, "companyName is required."
    if not phone:
        return None, "phone is required."
    return {
        "companyName": company_name,
        "phone": phone,
        "contactName": contact_name,
        "platform": platform,
        "remark": remark,
    }, ""


def _save_website_lead(parsed: dict) -> dict:
    now = timezone.now().isoformat()
    lead = {
        "id": f"lead-{uuid.uuid4().hex[:8]}",
        "companyName": parsed["companyName"],
        "phone": parsed["phone"],
        "contactName": parsed["contactName"],
        "platform": parsed["platform"],
        "remark": parsed["remark"] or None,
        "status": "未跟进",
        "createdAt": now,
    }
    log = {
        "id": f"log-{uuid.uuid4().hex[:8]}",
        "createdAt": now,
        "action": "新增官网留言",
        "targetType": "系统",
        "targetName": parsed["companyName"],
        "operator": "官网接口",
        "detail": f"{parsed['platform']} / {parsed['phone']}",
    }
    WebsiteLeadRecord.objects.update_or_create(
        id=lead["id"],
        defaults=_record_defaults(WebsiteLeadRecord, lead),
    )
    OperationLogRecord.objects.update_or_create(
        id=log["id"],
        defaults=_record_defaults(OperationLogRecord, log),
    )
    return lead


def _ingest_website_lead_request(request):
    try:
        payload = json.loads(request.body.decode("utf-8-sig") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON body.", "code": 40000, "message": "Invalid JSON body."}, status=400), None, {}

    parsed, error = parse_website_lead_payload(payload)
    echo = payload if isinstance(payload, dict) else {}
    if error:
        return JsonResponse({"detail": error, "code": 40000, "message": error}, status=400), None, echo
    return None, _save_website_lead(parsed), echo


def _public_user(user: UserRecord | dict) -> dict:
    data = dict(user.data if isinstance(user, UserRecord) else user)
    data.pop("password", None)
    return data


def _mask_value(value):
    if not value:
        return value
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"{text[:2]}***{text[-2:]}"


def _dt_iso(value) -> str:
    if not value:
        return ""
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value.isoformat()


def _parse_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(str(value).strip())
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _created_desc_order(queryset):
    json_created = Left(
        Replace(Replace(KeyTextTransform("createdAt", "data"), Value("T"), Value(" ")), Value("Z"), Value("")),
        19,
    )
    db_created = Left(Cast("created_at", CharField()), 19)
    db_updated = Left(Cast("updated_at", CharField()), 19)
    return queryset.annotate(
        _created_sort=Coalesce(json_created, db_created, db_updated, Value("")),
    ).order_by("-_created_sort", "-id")


def _ensure_platform_account_timestamps(data: dict, record=None) -> dict:
    payload = dict(data)
    db_created = _dt_iso(getattr(record, "created_at", None)) if record is not None else ""
    db_updated = _dt_iso(getattr(record, "updated_at", None)) if record is not None else ""
    updated = payload.get("updatedAt") or db_updated
    created = payload.get("createdAt") or db_created or updated
    if created and not payload.get("createdAt"):
        payload["createdAt"] = created
    if updated and not payload.get("updatedAt"):
        payload["updatedAt"] = updated
    elif not payload.get("updatedAt") and payload.get("createdAt"):
        payload["updatedAt"] = payload["createdAt"]
    return payload


def _backfill_platform_account_created_at() -> None:
    queryset = PlatformAccountRecord.objects.filter(is_deleted=False)
    if not queryset.filter(created_at__isnull=True).exists():
        return
    updates = []
    for record in queryset.iterator(chunk_size=200):
        original = dict(record.data or {})
        hydrated = _ensure_platform_account_timestamps(original, record)
        parsed = _parse_datetime(hydrated.get("createdAt"))
        changed = (
            hydrated.get("createdAt") != original.get("createdAt")
            or hydrated.get("updatedAt") != original.get("updatedAt")
            or (parsed and not record.created_at)
        )
        if not changed:
            continue
        record.data = hydrated
        if parsed and not record.created_at:
            record.created_at = parsed
        updates.append(record)
    if updates:
        PlatformAccountRecord.objects.bulk_update(updates, ["data", "created_at"], batch_size=200)


def _normalize_website_lead_status(status: str | None) -> str:
    mapping = {"未处理": "未跟进", "已处理": "已跟进"}
    text = (status or "").strip()
    return mapping.get(text, text) or "未跟进"


def _backfill_website_lead_statuses() -> None:
    queryset = WebsiteLeadRecord.objects.filter(is_deleted=False, status__in=["未处理", "已处理"])
    if not queryset.exists():
        return
    updates = []
    for record in queryset.iterator(chunk_size=200):
        data = dict(record.data or {})
        next_status = _normalize_website_lead_status(record.status or data.get("status"))
        if record.status == next_status and data.get("status") == next_status:
            continue
        record.status = next_status
        data["status"] = next_status
        record.data = data
        updates.append(record)
    if updates:
        WebsiteLeadRecord.objects.bulk_update(updates, ["status", "data"], batch_size=200)


def _restore_system_deleted_website_leads() -> None:
    queryset = WebsiteLeadRecord.objects.filter(is_deleted=True, deleted_by="system")
    if not queryset.exists():
        return
    updates = []
    for record in queryset.iterator(chunk_size=200):
        data = dict(record.data or {})
        data.pop("isDeleted", None)
        data.pop("deletedAt", None)
        data.pop("deletedBy", None)
        record.data = data
        record.is_deleted = False
        record.deleted_at = None
        record.deleted_by = ""
        updates.append(record)
    if updates:
        WebsiteLeadRecord.objects.bulk_update(
            updates,
            ["data", "is_deleted", "deleted_at", "deleted_by"],
            batch_size=200,
        )


def _backfill_website_lead_status_options() -> None:
    group = OptionGroupRecord.objects.filter(key="website_lead_status", is_deleted=False).first()
    if not group:
        return
    data = dict(group.data or {})
    items = data.get("items") if isinstance(data.get("items"), list) else []
    values = [str(item.get("value") or "") for item in items if isinstance(item, dict)]
    if "未跟进" in values and "已跟进" in values and "已成交" in values and "放弃" in values:
        return
    desired = ["未跟进", "已跟进", "已成交", "放弃"]
    rename = {"未处理": "未跟进", "已处理": "已跟进"}
    by_value = {str(item.get("value") or ""): item for item in items if isinstance(item, dict)}
    next_items = []
    for index, value in enumerate(desired, start=1):
        matched = by_value.get(value)
        if not matched:
            old = next((name for name, mapped in rename.items() if mapped == value), "")
            matched = by_value.get(old)
        if matched:
            next_items.append({**matched, "label": value, "value": value, "enabled": True, "sortOrder": index})
        else:
            next_items.append({
                "id": f"opt-lead-status-{index}",
                "label": value,
                "value": value,
                "enabled": True,
                "sortOrder": index,
            })
    data["items"] = next_items
    if isinstance(data.get("values"), list):
        data["values"] = desired
    group.data = data
    group.save(update_fields=["data"])


def _collection_public_data(collection: str, record) -> dict:
    if collection == "transactions":
        return _transaction_public_data(record)
    data = dict(record.data) if isinstance(record.data, dict) else {}
    if collection == "platformAccounts":
        data = _ensure_platform_account_timestamps(data, record)
    if collection == "websiteLeads":
        data.setdefault("id", record.id)
        if getattr(record, "company_name", ""):
            data.setdefault("companyName", record.company_name)
        if getattr(record, "phone", ""):
            data.setdefault("phone", record.phone)
        if getattr(record, "contact_name", ""):
            data.setdefault("contactName", record.contact_name)
        if getattr(record, "platform", ""):
            data.setdefault("platform", record.platform)
        data["status"] = _normalize_website_lead_status(data.get("status") or getattr(record, "status", ""))
        if not isinstance(data.get("memos"), list):
            data["memos"] = []
    return data


def _sanitize_record_data(collection: str, data: dict, can_view_sensitive: bool = False) -> dict:
    sanitized = dict(data)
    if collection == "users":
        for field in USER_SENSITIVE_FIELDS:
            sanitized.pop(field, None)
    if collection == "platformAccounts" and not can_view_sensitive:
        for field in PLATFORM_SENSITIVE_FIELDS:
            if sanitized.get(field):
                sanitized[field] = _mask_value(sanitized[field])
    return sanitized


def _sanitize_app_data(data: dict, user_data: dict | None = None) -> dict:
    can_view_sensitive = _can_view_sensitive(user_data)
    sanitized = {}
    for collection, value in data.items():
        if isinstance(value, list):
            sanitized[collection] = [
                _sanitize_record_data(collection, item, can_view_sensitive) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[collection] = value
    return sanitized


# Matches display masks from `_mask_value`: "****" or "{first2}***{last2}".
# Do not treat every value that merely contains "*" as masked, or real passwords
# such as "*F!lL3Z@" would be discarded on save.
_MASKED_SECRET_RE = re.compile(r"^(?:\*{4}|.{2}\*{3}.{2})$")
_MASKED_PLACEHOLDERS = {"已保存"}


def _is_masked_value(value) -> bool:
    if value in (None, ""):
        return True
    text = str(value)
    if text in _MASKED_PLACEHOLDERS:
        return True
    return _MASKED_SECRET_RE.fullmatch(text) is not None


def _preserve_sensitive_fields(collection: str, payload: dict, existing: dict | None) -> dict:
    merged = dict(payload)
    fields = USER_SENSITIVE_FIELDS if collection == "users" else PLATFORM_SENSITIVE_FIELDS if collection == "platformAccounts" else set()
    for field in fields:
        if field not in merged or _is_masked_value(merged.get(field)):
            if existing and existing.get(field):
                merged[field] = existing[field]
            else:
                merged.pop(field, None)
    if collection == "users" and merged.get("password"):
        password = str(merged["password"])
        try:
            identify_hasher(password)
        except ValueError:
            merged["password"] = make_password(password)
    return merged


def _legacy_record_data(collection: str, record_id: str) -> dict | None:
    for item in _legacy_state_data().get(collection, []):
        if isinstance(item, dict) and item.get("id") == record_id:
            return item
    return None


def _legacy_state_data() -> dict:
    state = AppState.objects.filter(key=DEFAULT_KEY).first()
    return state.data if state and isinstance(state.data, dict) else {}


def _find_user_data_by_id(user_id: str) -> dict | None:
    user = _active_user_queryset().filter(id=user_id).first()
    if user:
        return user.data
    for data in _legacy_state_data().get("users", []):
        if data.get("id") == user_id:
            return data
    return None


def _all_role_data() -> list[dict]:
    table_roles = [role.data for role in RoleRecord.objects.filter(is_deleted=False)]
    if table_roles:
        return table_roles
    return _legacy_state_data().get("roles", [])


def _user_permissions(user_data: dict | None) -> set[str]:
    if not user_data or user_data.get("status") != "启用":
        return set()
    role_ids = set(user_data.get("roleIds", []))
    permissions: set[str] = set()
    for role in _all_role_data():
        if role.get("id") in role_ids:
            permissions.update(role.get("permissions", []))
    return permissions


PERMISSION_ALIASES = {
    "platformAccount.view": ("platformAccount.view", "platformAccount.manage", "onboarding.manage"),
    "platformAccount.manage": ("platformAccount.manage", "onboarding.manage"),
    "trademarkCertificate.view": ("trademarkCertificate.view", "trademarkCertificate.manage"),
    "notice.view": ("notice.view", "notice.manage"),
    "site.view": ("site.view", "site.manage"),
    "salesOrder.view": ("salesOrder.view", "salesOrder.manage", "project.view"),
    "salesOrder.manage": ("salesOrder.manage", "project.edit", "finance.manage"),
    "purchaseOrder.view": ("purchaseOrder.view", "purchaseOrder.manage", "project.view", "purchase.manage"),
    "purchaseOrder.manage": ("purchaseOrder.manage", "purchase.manage"),
    "serviceOrder.view": ("serviceOrder.view", "serviceOrder.manage", "project.view", "onboarding.manage"),
    "serviceOrder.manage": ("serviceOrder.manage", "project.edit", "onboarding.manage", "finance.manage"),
}


def _has_permission(user_data: dict | None, permission: str) -> bool:
    permissions = _user_permissions(user_data)
    accepted = PERMISSION_ALIASES.get(permission, (permission,))
    return bool(permissions.intersection(accepted))


def _can_view_sensitive(user_data: dict | None) -> bool:
    permissions = _user_permissions(user_data)
    return bool({"sensitive.view", "onboarding.manage", "platformAccount.manage"} & permissions)


def _current_user_data(request) -> dict | None:
    user_id = request.session.get("user_id")
    return _find_user_data_by_id(user_id) if user_id else None


def _require_login(request):
    user_data = _current_user_data(request)
    if not user_data:
        return None, JsonResponse({"detail": "登录已过期，请重新登录。"}, status=401)
    return user_data, None


def _require_permission(request, permission: str):
    user_data, error = _require_login(request)
    if error:
        return None, error
    if not _has_permission(user_data, permission):
        return None, JsonResponse({"detail": "当前账号没有执行此操作的权限。", "permission": permission}, status=403)
    return user_data, None


def _collection_permission(collection: str, action: str) -> str:
    permissions = COLLECTION_PERMISSIONS.get(collection, {})
    return permissions.get(action, "user.manage")


def _password_matches(stored_password: str, raw_password: str) -> bool:
    if not stored_password:
        return raw_password == "123456"
    if is_password_usable(stored_password) and check_password(raw_password, stored_password):
        return True
    return stored_password == raw_password


def _active_user_queryset():
    return UserRecord.objects.filter(is_deleted=False)


def _find_login_user(identifier: str, password: str) -> UserRecord | dict | None:
    identifier = identifier.strip()
    for user in _active_user_queryset():
        data = user.data
        status = data.get("status") or user.status
        if status != "启用":
            continue
        candidates = {str(data.get("phone", "")).strip(), str(data.get("name", "")).strip(), user.phone.strip(), user.name.strip()}
        if identifier not in candidates:
            continue
        if _password_matches(str(data.get("password", "")), password):
            return user
    for data in _legacy_state_data().get("users", []):
        status = data.get("status")
        if status != "启用":
            continue
        candidates = {str(data.get("phone", "")).strip(), str(data.get("name", "")).strip()}
        if identifier in candidates and _password_matches(str(data.get("password", "")), password):
            return data
    return None


def _identifier_user_status(identifier: str) -> str | None:
    identifier = identifier.strip()
    for user in _active_user_queryset():
        data = user.data
        candidates = {str(data.get("phone", "")).strip(), str(data.get("name", "")).strip(), user.phone.strip(), user.name.strip()}
        if identifier in candidates:
            return str(data.get("status") or user.status)
    for data in _legacy_state_data().get("users", []):
        candidates = {str(data.get("phone", "")).strip(), str(data.get("name", "")).strip()}
        if identifier in candidates:
            return str(data.get("status", ""))
    return None


def _record_defaults(model, payload: dict) -> dict:
    defaults = {"data": payload}
    if model is RoleRecord:
        defaults["name"] = payload.get("name", "")
    elif model is UserRecord:
        defaults.update(
            name=payload.get("name", ""),
            phone=payload.get("phone", "") or "",
            status=payload.get("status", "启用"),
        )
    elif model is OrganizationRecord:
        defaults.update(
            name=payload.get("name", ""),
            entity_type=payload.get("entityType", ""),
            unified_credit_code=payload.get("unifiedCreditCode", "") or "",
            roles=payload.get("roles", []),
            status=payload.get("status", "正常"),
        )
    elif model is ProductRecord:
        defaults.update(
            code=payload.get("code", ""),
            name=payload.get("name", ""),
            kind=payload.get("kind", ""),
            category=payload.get("category", ""),
        )
    elif model is SupplierPriceRecord:
        defaults.update(
            product_id=payload.get("productId", ""),
            supplier_org_id=payload.get("supplierOrgId", ""),
            purchase_price=_num(payload.get("purchasePrice")),
            effective_date=payload.get("effectiveDate", "") or "",
        )
    elif model is ProjectRecord:
        defaults.update(
            project_no=payload.get("projectNo", ""),
            name=payload.get("name", ""),
            type=payload.get("type", ""),
            customer_org_id=payload.get("customerOrgId", ""),
            usage_unit_org_id=payload.get("usageUnitOrgId", "") or "",
            own_company_org_id=payload.get("ownCompanyOrgId", "") or "",
            status=payload.get("status", ""),
        )
    elif model is ProjectItemRecord:
        defaults.update(
            project_id=payload.get("projectId", ""),
            sales_order_id=payload.get("salesOrderId", "") or "",
            purchase_order_id=payload.get("purchaseOrderId", "") or "",
            product_id=payload.get("productId", ""),
            quantity=_num(payload.get("quantity")),
        )
    elif model is SalesOrderRecord:
        amount = _num(payload.get("amount"))
        defaults.update(
            project_id=payload.get("projectId", ""),
            order_no=payload.get("orderNo", ""),
            customer_org_id=payload.get("customerOrgId", ""),
            amount=amount,
            receivable_amount=_num(payload.get("receivableAmount", amount)),
            received_amount=_num(payload.get("receivedAmount")),
            status=payload.get("status", ""),
        )
    elif model is PurchaseOrderRecord:
        defaults.update(
            project_id=payload.get("projectId", ""),
            order_no=payload.get("orderNo", ""),
            supplier_org_id=payload.get("supplierOrgId", ""),
            amount=_num(payload.get("amount")),
            status=payload.get("status", ""),
        )
    elif model is ServiceOrderRecord:
        amount = _num(payload.get("amount"))
        defaults.update(
            project_id=payload.get("projectId", ""),
            order_no=payload.get("orderNo", ""),
            service_id=payload.get("serviceId", ""),
            customer_org_id=payload.get("customerOrgId", ""),
            amount=amount,
            receivable_amount=_num(payload.get("receivableAmount", amount)),
            received_amount=_num(payload.get("receivedAmount")),
            status=payload.get("status", ""),
        )
    elif model is OnboardingRecord:
        defaults.update(
            project_id=payload.get("projectId", ""),
            customer_org_id=payload.get("customerOrgId", ""),
            platform=payload.get("platform", ""),
            step=payload.get("step", ""),
        )
    elif model is PlatformAccountRecord:
        payload = _ensure_platform_account_timestamps(payload)
        defaults["data"] = payload
        defaults.update(
            customer_org_id=payload.get("customerOrgId", ""),
            platform=payload.get("platform", ""),
            account_name=payload.get("accountName", "") or "",
            current_status=payload.get("currentStatus", "") or "",
        )
        created_at = _parse_datetime(payload.get("createdAt") or payload.get("updatedAt"))
        if created_at:
            defaults["created_at"] = created_at
    elif model is WebsiteLeadRecord:
        defaults.update(
            company_name=payload.get("companyName", ""),
            phone=payload.get("phone", ""),
            contact_name=payload.get("contactName", "") or "",
            platform=payload.get("platform", ""),
            status=_normalize_website_lead_status(payload.get("status")),
        )
    elif model is ProjectReminderRecord:
        defaults.update(
            project_id=payload.get("projectId", ""),
            work_content=payload.get("workContent", ""),
            status=payload.get("status", ""),
            created_by_user_id=payload.get("createdByUserId", "") or "",
        )
    elif model is ProjectMemoRecord:
        defaults.update(
            project_id=payload.get("projectId", ""),
            content=(payload.get("content", "") or "")[:200],
            created_by=payload.get("createdBy", "") or "",
        )
    elif model is OptionGroupRecord:
        defaults.update(key=payload.get("key", ""), name=payload.get("name", ""))
    elif model is InvoiceRecord:
        defaults.update(
            invoice_no=payload.get("invoiceNo", "") or "",
            invoice_date=payload.get("invoiceDate", "") or payload.get("date", "") or "",
            type=payload.get("type", ""),
            amount=_num(payload.get("amount")),
            status=payload.get("status", ""),
        )
    elif model is TransactionRecord:
        defaults.update(
            project_id=payload.get("projectId", ""),
            type=payload.get("type", ""),
            amount=_num(payload.get("amount")),
            date=payload.get("date", ""),
            status=payload.get("status", ""),
        )
    elif model is OperationLogRecord:
        defaults.update(
            action=payload.get("action", ""),
            target_type=payload.get("targetType", ""),
            target_name=payload.get("targetName", "") or "",
            operator=payload.get("operator", "") or "",
        )
    elif model is OcrJobRecord:
        defaults.update(
            type=payload.get("type", ""),
            file_name=payload.get("fileName", ""),
            status=payload.get("status", ""),
        )
    elif model is TrademarkCertificateRecord:
        defaults.update(
            registration_no=_normalize_registration_no(payload.get("registrationNo")),
            registrant=(payload.get("registrant", "") or "").strip(),
            registrant_address=(payload.get("registrantAddress", "") or "").strip(),
            international_class=(payload.get("internationalClass", "") or "").strip(),
            registration_date=(payload.get("registrationDate", "") or "").strip(),
            valid_until=(payload.get("validUntil", "") or "").strip(),
        )
    elif model is NoticeRecord:
        data = normalize_notice_payload(payload)
        defaults = notice_defaults(data)
    elif model is NoticeCollectionSourceRecord:
        defaults.update(
            name=(payload.get("name", "") or "").strip(),
            kind=(payload.get("kind", "") or "").strip(),
            enabled=bool(payload.get("enabled", True)),
            last_run_at=(payload.get("lastRunAt", "") or "").strip(),
            last_status=(payload.get("lastStatus", "") or "").strip(),
        )
    elif model is NoticeCollectionRunRecord:
        defaults.update(
            source_id=(payload.get("sourceId", "") or "").strip(),
            source_name=(payload.get("sourceName", "") or "").strip(),
            status=(payload.get("status", "") or "").strip(),
            fetched_count=int(payload.get("fetchedCount") or 0),
            created_count=int(payload.get("createdCount") or 0),
            updated_count=int(payload.get("updatedCount") or 0),
            lead_count=int(payload.get("leadCount") or 0),
            started_at=(payload.get("startedAt", "") or "").strip(),
            finished_at=(payload.get("finishedAt", "") or "").strip(),
        )
    elif model is OfficialSiteRecord:
        data = normalize_site_payload(payload)
        defaults = site_defaults(data)
    elif model is OfficialPageRecord:
        data = normalize_page_payload(payload)
        defaults = page_defaults(data)
    return defaults


_RECORD_COLUMN_JSON = {
    "project_id": "projectId",
    "order_no": "orderNo",
    "customer_org_id": "customerOrgId",
    "supplier_org_id": "supplierOrgId",
    "sales_order_id": "salesOrderId",
    "purchase_order_id": "purchaseOrderId",
    "product_id": "productId",
    "invoice_no": "invoiceNo",
    "type": "type",
    "status": "status",
    "name": "name",
    "code": "code",
    "kind": "kind",
    "category": "category",
    "date": "date",
    "amount": "amount",
}


def _column_json_from_record(record) -> dict:
    payload = {}
    for attr, key in _RECORD_COLUMN_JSON.items():
        if not hasattr(record, attr):
            continue
        value = getattr(record, attr)
        if value in (None, ""):
            continue
        payload[key] = float(value) if isinstance(value, Decimal) else value
    return payload


def _restore_transaction_project_id(record: TransactionRecord) -> dict:
    data = dict(record.data) if isinstance(record.data, dict) else {}
    project_id = record.project_id or data.get("projectId") or ""
    sales_order_id = data.get("salesOrderId") or ""
    service_order_id = data.get("serviceOrderId") or ""
    purchase_order_id = data.get("purchaseOrderId") or ""

    if not project_id:
        related = (
            (sales_order_id, SalesOrderRecord),
            (service_order_id, ServiceOrderRecord),
            (purchase_order_id, PurchaseOrderRecord),
        )
        for related_id, model in related:
            if not related_id:
                continue
            other = model.objects.filter(id=related_id, is_deleted=False).first()
            if not other:
                continue
            other_data = other.data if isinstance(other.data, dict) else {}
            project_id = other.project_id or other_data.get("projectId") or ""
            if project_id:
                break

    if not project_id:
        remark = str(data.get("remark") or "")
        for prefix, model, id_key in (
            ("SV-", ServiceOrderRecord, "serviceOrderId"),
            ("SO-", SalesOrderRecord, "salesOrderId"),
            ("PO-", PurchaseOrderRecord, "purchaseOrderId"),
        ):
            if prefix not in remark:
                continue
            match = re.search(rf"({prefix}[A-Za-z0-9-]+)", remark)
            if not match:
                continue
            other = model.objects.filter(order_no=match.group(1), is_deleted=False).first()
            if not other:
                continue
            other_data = other.data if isinstance(other.data, dict) else {}
            project_id = other.project_id or other_data.get("projectId") or ""
            if id_key == "serviceOrderId" and not service_order_id:
                service_order_id = other.id
            elif id_key == "salesOrderId" and not sales_order_id:
                sales_order_id = other.id
            elif id_key == "purchaseOrderId" and not purchase_order_id:
                purchase_order_id = other.id
            if project_id:
                break

    changed = False
    if service_order_id and data.get("serviceOrderId") != service_order_id:
        data["serviceOrderId"] = service_order_id
        changed = True
    if sales_order_id and data.get("salesOrderId") != sales_order_id:
        data["salesOrderId"] = sales_order_id
        changed = True
    if purchase_order_id and data.get("purchaseOrderId") != purchase_order_id:
        data["purchaseOrderId"] = purchase_order_id
        changed = True
    if project_id and (record.project_id != project_id or data.get("projectId") != project_id):
        data["projectId"] = project_id
        record.project_id = project_id
        changed = True
    elif record.project_id and not data.get("projectId"):
        data["projectId"] = record.project_id
        changed = True
    if changed:
        record.data = data
        record.save(update_fields=["project_id", "data"] if hasattr(record, "project_id") else ["data"])
    return data


def _transaction_public_data(record: TransactionRecord) -> dict:
    data = dict(_restore_transaction_project_id(record))
    project_id = record.project_id or data.get("projectId") or ""
    project = ProjectRecord.objects.filter(id=project_id).first() if project_id else None
    if project and project.name:
        data["projectName"] = project.name
    return data


def _serialize_queryset(model):
    # values_list 只拉 JSON 列，避免把整行 ORM 实例物化进内存。
    if model is OptionGroupRecord:
        queryset = model.objects.filter(is_deleted=False).order_by("key")
        return list(queryset.values_list("data", flat=True))
    if model is OperationLogRecord:
        # 全量日志可达数 MB；列表页已走服务端分页，启动包只带最近一批。
        queryset = (
            model.objects.filter(is_deleted=False)
            .order_by("-created_at", "-id")[:APP_DATA_OPERATION_LOG_LIMIT]
        )
        return list(queryset.values_list("data", flat=True))
    if model is TransactionRecord:
        orphan_ids = orphaned_transaction_ids()
        rows = model.objects.filter(is_deleted=False).order_by("id").values_list("id", "data")
        if not orphan_ids:
            return [data for _id, data in rows]
        return [data for _id, data in rows if _id not in orphan_ids]
    queryset = model.objects.filter(is_deleted=False).order_by("id")
    return list(queryset.values_list("data", flat=True))


def _soft_delete_queryset(queryset, deleted_by: str = "system") -> int:
    """Logically delete active records while retaining their full audit data."""
    deleted_at = timezone.now()
    deleted_by = (deleted_by or "system")[:100]
    count = 0
    for record in queryset.filter(is_deleted=False).iterator():
        record.data = {
            **record.data,
            "isDeleted": True,
            "deletedAt": deleted_at.isoformat(),
            "deletedBy": deleted_by,
        }
        record.is_deleted = True
        record.deleted_at = deleted_at
        record.deleted_by = deleted_by
        record.save(update_fields=["data", "is_deleted", "deleted_at", "deleted_by", "updated_at"])
        count += 1
    return count


def _organization_reference_counts(organization_ids: set[str]) -> dict[str, int]:
    if not organization_ids:
        return {}
    reference_fields = {
        "supplierPrices": (SupplierPriceRecord, ("supplierOrgId",)),
        "projects": (ProjectRecord, ("customerOrgId", "usageUnitOrgId", "ownCompanyOrgId")),
        "salesOrders": (SalesOrderRecord, ("customerOrgId", "ownCompanyOrgId")),
        "purchaseOrders": (PurchaseOrderRecord, ("supplierOrgId", "ownCompanyOrgId")),
        "serviceOrders": (ServiceOrderRecord, ("customerOrgId",)),
        "onboardingRecords": (OnboardingRecord, ("customerOrgId",)),
        "platformAccounts": (PlatformAccountRecord, ("customerOrgId",)),
        "invoices": (InvoiceRecord, ("buyerOrgId", "sellerOrgId", "counterpartyOrgId")),
        "transactions": (TransactionRecord, ("counterpartyOrgId",)),
    }
    references = {}
    for name, (model, fields) in reference_fields.items():
        count = sum(
            1
            for record in model.objects.filter(is_deleted=False).only("data").iterator()
            if any(record.data.get(field) in organization_ids for field in fields)
        )
        if count:
            references[name] = count
    return references


def _protect_referenced_organizations(incoming_organization_ids: set[str]) -> None:
    removed_ids = set(
        OrganizationRecord.objects.filter(is_deleted=False)
        .exclude(id__in=incoming_organization_ids)
        .values_list("id", flat=True)
    )
    references = _organization_reference_counts(removed_ids)
    if references:
        raise ProtectedOrganizationError(removed_ids, references)


def load_app_data() -> dict | None:
    # 业务表有数据时以表为准，避免每次读写再解析/回写整份 app_state JSON。
    # 不先扫一遍 exists()：表都在时那是 N 次多余查询。
    payload = {key: _serialize_queryset(model) for key, model in COLLECTIONS.items()}
    if any(payload.values()):
        return payload
    legacy = _legacy_state_data()
    return legacy or None


def _normalize_delete_ids(delete_ids: dict | None) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, ids in (delete_ids or {}).items():
        if not isinstance(ids, (list, tuple, set)):
            continue
        cleaned = [str(item_id) for item_id in ids if item_id]
        if cleaned:
            normalized[str(key)] = cleaned
    return normalized


@transaction.atomic
def save_app_data(data: dict, partial: bool = False, delete_ids: dict | None = None) -> None:
    delete_ids = _normalize_delete_ids(delete_ids) if partial else {}
    if not partial:
        incoming_organizations = data.get("organizations", [])
        incoming_organization_ids = {
            item.get("id")
            for item in incoming_organizations
            if isinstance(item, dict) and item.get("id")
        }
        _protect_referenced_organizations(incoming_organization_ids)
    else:
        org_delete_ids = set(delete_ids.get("organizations") or [])
        if org_delete_ids:
            references = _organization_reference_counts(org_delete_ids)
            if references:
                raise ProtectedOrganizationError(org_delete_ids, references)

    keys = set(COLLECTIONS) if not partial else (set(data.keys()) | set(delete_ids.keys()))
    for key in keys:
        model = COLLECTIONS.get(key)
        if not model:
            continue
        incoming = data.get(key, []) if (not partial or key in data) else []
        if not isinstance(incoming, list):
            incoming = []
        ids_to_delete = set(delete_ids.get(key) or [])
        if not partial:
            incoming_ids = {item.get("id") for item in incoming if isinstance(item, dict) and item.get("id")}
            # 全量快照仍按「未出现即删除」。部分保存只 upsert 提交的记录，
            # 删除必须走 delete_ids 或单条 DELETE，避免浏览器滞后快照误删。
            _soft_delete_queryset(model.objects.exclude(id__in=incoming_ids))
        elif ids_to_delete:
            if key == "projects":
                _soft_delete_queryset(
                    TransactionRecord.objects.filter(is_deleted=False).filter(
                        Q(project_id__in=ids_to_delete) | Q(data__projectId__in=list(ids_to_delete))
                    ),
                )
            _soft_delete_queryset(model.objects.filter(id__in=ids_to_delete))
        if partial and key not in data:
            continue
        for item in incoming:
            if not isinstance(item, dict) or not item.get("id") or item["id"] in ids_to_delete:
                continue
            existing = model.objects.filter(id=item["id"]).first()
            # 部分保存不要去读整份 app_state：新建项目会连打多次约 1MB 的 JSON。
            existing_data = existing.data if existing else (None if partial else _legacy_record_data(key, item["id"]))
            item = _preserve_sensitive_fields(key, item, existing_data)
            model.objects.update_or_create(
                id=item["id"],
                defaults={**_record_defaults(model, item), "is_deleted": False, "deleted_at": None, "deleted_by": ""},
            )
    if not partial:
        _sync_app_state_snapshot()


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def app_data(request):
    if request.method == "GET":
        return JsonResponse({"data": _sanitize_app_data(load_app_data() or {}, _current_user_data(request))})

    user_data, auth_error = _require_login(request)
    if auth_error:
        return auth_error

    if request.method == "DELETE":
        if "user.manage" not in _user_permissions(user_data):
            return JsonResponse({"detail": "Permission denied.", "permission": "user.manage"}, status=403)
        for model in COLLECTIONS.values():
            _soft_delete_queryset(model.objects.all(), user_data.get("name", ""))
        _sync_app_state_snapshot()
        return JsonResponse({"data": None})

    try:
        payload = json.loads(request.body.decode("utf-8-sig") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return JsonResponse({"detail": "Data must be a JSON object."}, status=400)

    is_partial = payload.get("partial") is True
    raw_delete = payload.get("deleteIds", payload.get("delete_ids"))
    if not isinstance(raw_delete, dict):
        raw_delete = {}
    try:
        save_app_data(data, partial=is_partial, delete_ids=raw_delete if is_partial else None)
    except ProtectedOrganizationError as error:
        return JsonResponse(
            {
                "detail": "该企业/单位仍被业务数据引用，无法删除。",
                "organizationIds": sorted(error.organization_ids),
                "references": error.references,
            },
            status=409,
        )
    if is_partial:
        return JsonResponse({"ok": True, "partial": True})
    return JsonResponse({"data": _sanitize_app_data(load_app_data() or {}, user_data)})


def _read_body(request):
    try:
        payload = json.loads(request.body.decode("utf-8-sig") or "{}")
    except json.JSONDecodeError:
        return None, JsonResponse({"detail": "Invalid JSON body."}, status=400)
    if not isinstance(payload, dict):
        return None, JsonResponse({"detail": "JSON body must be an object."}, status=400)
    return payload, None


def _collection_model(collection: str):
    return COLLECTIONS.get(collection)


def _collection_queryset(model, include_deleted: bool = False):
    queryset = model.objects.all()
    if not include_deleted:
        queryset = queryset.filter(is_deleted=False)
    if model is OptionGroupRecord:
        return queryset.order_by("key")
    return queryset.order_by("id")


def _parse_page_params(request):
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or request.GET.get("pageSize") or 20)
    except (TypeError, ValueError):
        page_size = 20
    page_size = min(max(1, page_size), 100)
    return page, page_size


def _wants_paged_response(request) -> bool:
    if request.GET.get("paged") in {"1", "true", "True"}:
        return True
    return any(key in request.GET for key in ("page", "page_size", "pageSize", "search"))


def _org_ids_matching_name(keyword: str) -> list[str]:
    if not keyword:
        return []
    return list(
        OrganizationRecord.objects.filter(is_deleted=False, name__icontains=keyword).values_list("id", flat=True)[:500]
    )


def _project_ids_matching(keyword: str) -> list[str]:
    if not keyword:
        return []
    org_ids = _org_ids_matching_name(keyword)
    return list(
        ProjectRecord.objects.filter(is_deleted=False)
        .filter(
            Q(name__icontains=keyword)
            | Q(project_no__icontains=keyword)
            | Q(customer_org_id__in=org_ids)
            | Q(usage_unit_org_id__in=org_ids)
            | Q(data__sourcePlatform__icontains=keyword)
            | Q(data__serviceProductName__icontains=keyword)
        )
        .values_list("id", flat=True)[:500]
    )


def _product_ids_matching(keyword: str) -> list[str]:
    if not keyword:
        return []
    return list(
        ProductRecord.objects.filter(is_deleted=False)
        .filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
        .values_list("id", flat=True)[:500]
    )


def _project_ids_for_platform(platform: str) -> list[str]:
    if not platform:
        return []
    return list(
        ProjectRecord.objects.filter(is_deleted=False, data__sourcePlatform=platform)
        .values_list("id", flat=True)[:2000]
    )


def _apply_order_platform_filter(collection: str, queryset, platform: str):
    value = (platform or "").strip()
    if not value or value == "全部":
        return queryset
    project_ids = _project_ids_for_platform(value)
    if collection == "salesOrders":
        blank_order_platform = Q(data__platform__isnull=True) | Q(data__platform="")
        return queryset.filter(Q(data__platform=value) | (blank_order_platform & Q(project_id__in=project_ids)))
    return queryset.filter(project_id__in=project_ids)


_SALES_INVOICE_STATUS_KIND = {
    "未开票": "unpaid",
    "已开部分": "partial",
    "已开全部": "full",
}
_PURCHASE_INVOICE_STATUS_KIND = {
    "未收票": "unpaid",
    "已收部分": "partial",
    "已收全部": "full",
}


def _order_invoice_link_totals(order_key: str) -> tuple[set[str], dict[str, Decimal]]:
    linked: set[str] = set()
    totals: dict[str, Decimal] = {}
    invoices = InvoiceRecord.objects.filter(is_deleted=False).exclude(status="作废").only("amount", "data")
    for invoice in invoices.iterator():
        order_ids = (invoice.data or {}).get(order_key) or []
        if not isinstance(order_ids, list):
            continue
        amount = _amount(invoice.amount)
        for order_id in order_ids:
            if not order_id:
                continue
            key = str(order_id)
            linked.add(key)
            totals[key] = totals.get(key, Decimal("0.00")) + amount
    return linked, totals


def _apply_order_invoice_status_filter(collection: str, queryset, invoice_status: str):
    value = (invoice_status or "").strip()
    if not value or value == "全部":
        return queryset
    if collection == "salesOrders":
        kind = _SALES_INVOICE_STATUS_KIND.get(value)
        order_key = "salesOrderIds"
    elif collection == "purchaseOrders":
        kind = _PURCHASE_INVOICE_STATUS_KIND.get(value)
        order_key = "purchaseOrderIds"
    else:
        return queryset
    if not kind:
        return queryset

    linked_ids, totals = _order_invoice_link_totals(order_key)
    if kind == "unpaid":
        return queryset.exclude(id__in=linked_ids) if linked_ids else queryset

    if not linked_ids:
        return queryset.none()

    matching_ids: list[str] = []
    for order in queryset.filter(id__in=linked_ids).only("id", "amount").iterator():
        invoiced = totals.get(order.id, Decimal("0.00"))
        order_amount = _amount(order.amount)
        is_full = order_amount > Decimal("0.00") and invoiced + Decimal("0.009") >= order_amount
        if kind == "full" and is_full:
            matching_ids.append(order.id)
        elif kind == "partial" and not is_full:
            matching_ids.append(order.id)
    return queryset.filter(id__in=matching_ids) if matching_ids else queryset.none()


def _ids_matching_order_no(model, keyword: str):
    return list(
        model.objects.filter(is_deleted=False, order_no__icontains=keyword).values_list("id", flat=True)[:80]
    )


def _invoice_order_search_q(keyword: str) -> Q:
    query = Q()
    for order_id in _ids_matching_order_no(SalesOrderRecord, keyword):
        query |= Q(data__salesOrderIds__icontains=order_id)
        query |= Q(data__lineItems__icontains=order_id)
    for order_id in _ids_matching_order_no(PurchaseOrderRecord, keyword):
        query |= Q(data__purchaseOrderIds__icontains=order_id)
        query |= Q(data__lineItems__icontains=order_id)
    for order_id in _ids_matching_order_no(ServiceOrderRecord, keyword):
        query |= Q(data__serviceAllocations__icontains=order_id)
    return query


def _order_list_queryset(collection: str, queryset, search: str):
    keyword = (search or "").strip()
    if not keyword:
        return queryset
    org_ids = _org_ids_matching_name(keyword)
    project_ids = _project_ids_matching(keyword)
    product_ids = _product_ids_matching(keyword)
    if collection == "salesOrders":
        item_project_ids = list(
            ProjectItemRecord.objects.filter(is_deleted=False, product_id__in=product_ids)
            .exclude(sales_order_id="")
            .values_list("sales_order_id", flat=True)[:500]
        ) if product_ids else []
        return queryset.filter(
            Q(order_no__icontains=keyword)
            | Q(customer_org_id__in=org_ids)
            | Q(project_id__in=project_ids)
            | Q(id__in=item_project_ids)
            | Q(data__platformOrderNo__icontains=keyword)
            | Q(data__collectionAccount__icontains=keyword)
            | Q(data__purchaserCompany__icontains=keyword)
            | Q(data__purchaserName__icontains=keyword)
            | Q(data__purchaserPhone__icontains=keyword)
            | Q(data__purchaserAddress__icontains=keyword)
        )
    if collection == "purchaseOrders":
        item_order_ids = list(
            ProjectItemRecord.objects.filter(is_deleted=False, product_id__in=product_ids)
            .exclude(purchase_order_id="")
            .values_list("purchase_order_id", flat=True)[:500]
        ) if product_ids else []
        return queryset.filter(
            Q(order_no__icontains=keyword)
            | Q(supplier_org_id__in=org_ids)
            | Q(project_id__in=project_ids)
            | Q(id__in=item_order_ids)
            | Q(data__batchNo__icontains=keyword)
        )
    if collection == "serviceOrders":
        return queryset.filter(
            Q(order_no__icontains=keyword)
            | Q(customer_org_id__in=org_ids)
            | Q(project_id__in=project_ids)
            | Q(service_id__in=product_ids)
            | Q(data__paymentAccount__icontains=keyword)
            | Q(data__collectionAccount__icontains=keyword)
        )
    return queryset


def _apply_service_project_list_filters(queryset, get):
    own_company_org_id = (get("ownCompanyOrgId") or "").strip()
    if own_company_org_id and own_company_org_id != "全部":
        queryset = queryset.filter(own_company_org_id=own_company_org_id)

    status = (get("status") or "").strip()
    if status and status != "全部":
        queryset = queryset.filter(status=status)

    service_type = (get("serviceType") or "").strip()
    if service_type and service_type != "全部":
        if service_type == "周期":
            queryset = queryset.filter(
                Q(data__serviceType="周期") | Q(data__serviceType__isnull=True) | Q(data__serviceType="")
            )
        else:
            queryset = queryset.filter(data__serviceType=service_type)

    contract_status = (get("contractStatus") or "").strip()
    if contract_status and contract_status != "全部":
        queryset = queryset.filter(data__contractStatus=contract_status)

    invoice_status = (get("invoiceStatus") or "").strip()
    if invoice_status and invoice_status != "全部":
        invoice_aliases = {
            "待开": ["待开", "未开票"],
            "未开票": ["待开", "未开票"],
        }
        queryset = queryset.filter(data__invoiceStatus__in=invoice_aliases.get(invoice_status, [invoice_status]))

    sales_user_id = (get("serviceSalesUserId") or "").strip()
    if sales_user_id and sales_user_id != "全部":
        sales_q = Q(data__serviceSalesUserId=sales_user_id)
        user_row = UserRecord.objects.filter(id=sales_user_id, is_deleted=False).first()
        if user_row:
            name = (user_row.name or (user_row.data or {}).get("name") or "").strip()
            if name:
                sales_q |= Q(data__serviceSalesName=name) | Q(data__owner=name)
        queryset = queryset.filter(sales_q)
    return queryset


def _apply_collection_list_query(collection: str, queryset, request):
    search = (request.GET.get("search") or "").strip()
    get = request.GET.get

    if collection == "platformAccounts":
        _backfill_platform_account_created_at()
        platform = (get("platform") or "").strip()
        if platform and platform != "全部":
            queryset = queryset.filter(platform=platform)
        if search:
            org_ids = _org_ids_matching_name(search)
            queryset = queryset.filter(Q(customer_org_id__in=org_ids) | Q(account_name__icontains=search) | Q(data__merchantId__icontains=search) | Q(data__shopId__icontains=search) | Q(data__shopName__icontains=search))
    elif collection == "products":
        kind = (get("kind") or "").strip()
        if kind:
            queryset = queryset.filter(kind=kind)
        include_project = (get("includeProject") or "").strip() in {"1", "true", "True"}
        if not include_project:
            queryset = queryset.filter(Q(data__source__isnull=True) | ~Q(data__source="project"))
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(category__icontains=search))
    elif collection == "projects":
        project_type = (get("type") or "").strip()
        if project_type:
            queryset = queryset.filter(type=project_type)
        contract_list = (get("contractList") or "").strip()
        if contract_list in {"1", "true", "True"}:
            queryset = queryset.filter(Q(type="服务项目") | (~Q(data__contractFileId=None) & ~Q(data__contractFileId="")))
        queryset = _apply_service_project_list_filters(queryset, get)
        if search:
            keywords = [part for part in search.lower().split() if part]
            for keyword in keywords:
                org_ids = _org_ids_matching_name(keyword)
                queryset = queryset.filter(
                    Q(name__icontains=keyword)
                    | Q(project_no__icontains=keyword)
                    | Q(customer_org_id__in=org_ids)
                    | Q(usage_unit_org_id__in=org_ids)
                    | Q(own_company_org_id__in=org_ids)
                    | Q(data__sourcePlatform__icontains=keyword)
                    | Q(data__serviceProductName__icontains=keyword)
                    | Q(data__serviceCustomerKind__icontains=keyword)
                    | Q(data__serviceSalesName__icontains=keyword)
                    | Q(data__platformOrderNo__icontains=keyword)
                    | Q(data__contractFileName__icontains=keyword)
                    | Q(data__contractStatus__icontains=keyword)
                    | Q(status__icontains=keyword)
                )
    elif collection == "organizations":
        role = (get("role") or "").strip()
        if role and role != "全部":
            queryset = queryset.annotate(roles_text=Cast("roles", CharField())).filter(roles_text__icontains=f'"{role}"')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(unified_credit_code__icontains=search)
                | Q(data__legalPerson__icontains=search)
                | Q(data__phone__icontains=search)
                | Q(data__email__icontains=search)
            )
    elif collection == "websiteLeads":
        _restore_system_deleted_website_leads()
        _backfill_website_lead_statuses()
        _backfill_website_lead_status_options()
        status = (get("status") or "").strip()
        if status and status != "全部":
            aliases = {
                "未跟进": ["未跟进", "未处理"],
                "已跟进": ["已跟进", "已处理"],
            }
            queryset = queryset.filter(status__in=aliases.get(status, [status]))
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(contact_name__icontains=search)
                | Q(platform__icontains=search)
                | Q(data__remark__icontains=search)
            )
    elif collection == "projectReminders":
        status = (get("status") or "").strip()
        if status and status != "全部":
            queryset = queryset.filter(status=status)
        created_by = (get("createdByUserId") or "").strip()
        if created_by:
            queryset = queryset.filter(created_by_user_id=created_by)
        if search:
            project_ids = _project_ids_matching(search)
            queryset = queryset.filter(
                Q(work_content__icontains=search)
                | Q(data__createdByName__icontains=search)
                | Q(project_id__in=project_ids)
            )
    elif collection == "projectMemos":
        project_id = (get("projectId") or "").strip()
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if search:
            queryset = queryset.filter(Q(content__icontains=search) | Q(created_by__icontains=search))
    elif collection == "invoices":
        status = (get("status") or "").strip()
        if status and status != "全部":
            queryset = queryset.filter(status=status)
        if search:
            project_ids = _project_ids_matching(search)
            queryset = queryset.filter(
                Q(invoice_no__icontains=search)
                | Q(data__buyerName__icontains=search)
                | Q(data__sellerName__icontains=search)
                | Q(data__buyerTaxNo__icontains=search)
                | Q(data__sellerTaxNo__icontains=search)
                | Q(data__projectId__in=project_ids)
                | _invoice_order_search_q(search)
            )
    elif collection == "transactions":
        tx_type = (get("type") or "").strip()
        if tx_type:
            queryset = queryset.filter(type=tx_type)
        orphan_ids = orphaned_transaction_ids()
        if orphan_ids:
            queryset = queryset.exclude(id__in=orphan_ids)
        if search:
            project_ids = _project_ids_matching(search)
            queryset = queryset.filter(
                Q(project_id__in=project_ids)
                | Q(type__icontains=search)
                | Q(status__icontains=search)
                | Q(data__account__icontains=search)
                | Q(data__remark__icontains=search)
                | Q(data__transactionNo__icontains=search)
            )
    elif collection == "operationLogs":
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search)
                | Q(target_name__icontains=search)
                | Q(operator__icontains=search)
                | Q(target_type__icontains=search)
                | Q(data__detail__icontains=search)
            )
    elif collection == "users":
        status = (get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(phone__icontains=search))
    elif collection == "roles":
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(data__description__icontains=search))
    elif collection == "trademarkCertificates":
        if search:
            queryset = queryset.filter(
                Q(registration_no__icontains=search)
                | Q(registrant__icontains=search)
                | Q(registrant_address__icontains=search)
                | Q(international_class__icontains=search)
                | Q(registration_date__icontains=search)
                | Q(valid_until__icontains=search)
                | Q(data__approvedGoods__icontains=search)
                | Q(data__trademarkName__icontains=search)
                | Q(data__note__icontains=search)
            )
    elif collection == "notices":
        notice_kind = (get("noticeKind") or "").strip()
        if notice_kind and notice_kind != "全部":
            queryset = queryset.filter(notice_kind=notice_kind)
        bid_status = (get("bidStatus") or "").strip()
        if bid_status and bid_status != "全部":
            queryset = queryset.filter(bid_status=bid_status)
        is_public = (get("isPublic") or "").strip().lower()
        if is_public in {"1", "true", "yes"}:
            queryset = queryset.filter(is_public=True)
        elif is_public in {"0", "false", "no"}:
            queryset = queryset.filter(is_public=False)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(project_number__icontains=search)
                | Q(supplier_name__icontains=search)
                | Q(department__icontains=search)
                | Q(category__icontains=search)
                | Q(notice_kind__icontains=search)
                | Q(bid_status__icontains=search)
                | Q(data__content__icontains=search)
                | Q(data__contactName__icontains=search)
                | Q(data__contactPhone__icontains=search)
            )
    elif collection == "noticeCollectionSources":
        enabled = (get("enabled") or "").strip().lower()
        if enabled in {"1", "true", "yes"}:
            queryset = queryset.filter(enabled=True)
        elif enabled in {"0", "false", "no"}:
            queryset = queryset.filter(enabled=False)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(kind__icontains=search))
    elif collection == "noticeCollectionRuns":
        source_id = (get("sourceId") or "").strip()
        if source_id:
            queryset = queryset.filter(source_id=source_id)
        status = (get("status") or "").strip()
        if status and status != "全部":
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(source_name__icontains=search)
                | Q(status__icontains=search)
                | Q(data__errorMessage__icontains=search)
            )
    elif collection == "officialSites":
        status = (get("status") or "").strip()
        if status and status != "全部":
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(key__icontains=search)
                | Q(domain__icontains=search)
                | Q(brand__icontains=search)
                | Q(company_name__icontains=search)
                | Q(phone__icontains=search)
            )
    elif collection == "officialPages":
        site_id = (get("siteId") or "").strip()
        if site_id:
            queryset = queryset.filter(site_id=site_id)
        status = (get("status") or "").strip()
        if status and status != "全部":
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(slug__icontains=search)
                | Q(template__icontains=search)
                | Q(status__icontains=search)
            )
    elif collection in {"salesOrders", "purchaseOrders", "serviceOrders"}:
        status = (get("status") or "").strip()
        if status and status != "全部":
            queryset = queryset.filter(status=status)
        platform = (get("platform") or "").strip()
        queryset = _apply_order_platform_filter(collection, queryset, platform)
        invoice_status = (get("invoiceStatus") or "").strip()
        queryset = _apply_order_invoice_status_filter(collection, queryset, invoice_status)
        project_id = (get("projectId") or "").strip()
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        queryset = _order_list_queryset(collection, queryset, search)
    elif search:
        # Generic fallback for remaining collections: search common text columns / JSON blob.
        text_q = Q()
        for field in ("name", "code", "order_no", "project_no", "action", "target_name", "key"):
            if any(f.name == field for f in queryset.model._meta.fields):
                text_q |= Q(**{f"{field}__icontains": search})
        if text_q:
            queryset = queryset.filter(text_q)

    sort = (get("sort") or "").strip()
    if collection == "transactions" and sort == "occurred":
        queryset = queryset.order_by("-data__occurredAt", "-date", "-id")
    elif collection == "optionGroups":
        queryset = queryset.order_by("key")
    elif collection == "platformAccounts":
        queryset = _created_desc_order(queryset)
    else:
        # Prefer JSON createdAt (legacy payloads), then DB created_at, then id.
        queryset = queryset.order_by("-data__createdAt", "-created_at", "-id")
    return queryset


def _record_payload(payload: dict):
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else None


def _sync_app_state_snapshot():
    current = AppState.objects.filter(key=DEFAULT_KEY).first()
    legacy = current.data if current and isinstance(current.data, dict) else {}
    merged = dict(legacy)
    for key, model in COLLECTIONS.items():
        merged[key] = _serialize_queryset(model)
    AppState.objects.update_or_create(key=DEFAULT_KEY, defaults={"data": merged})


def _patch_app_state_collections(keys) -> None:
    current = AppState.objects.filter(key=DEFAULT_KEY).first()
    if not current or not isinstance(current.data, dict):
        _sync_app_state_snapshot()
        return
    merged = dict(current.data)
    for key in keys:
        model = COLLECTIONS.get(key)
        if not model:
            continue
        merged[key] = _serialize_queryset(model)
    current.data = merged
    current.save(update_fields=["data"])


def _merge_snapshot_collection(items: list, upserts: list[dict], delete_ids: set[str]) -> list:
    upsert_by_id = {
        item["id"]: item
        for item in upserts
        if isinstance(item, dict) and item.get("id")
    }
    next_items = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        record_id = item.get("id")
        if record_id in delete_ids:
            continue
        if record_id in upsert_by_id:
            next_items.append(upsert_by_id[record_id])
            seen.add(record_id)
        else:
            next_items.append(item)
    new_items = [
        item
        for item in upserts
        if isinstance(item, dict) and item.get("id") and item["id"] not in seen and item["id"] not in delete_ids
    ]
    return [*new_items, *next_items]


def _patch_app_state_records(upserts_by_collection: dict[str, list[dict]], delete_ids_by_collection: dict[str, set[str]]) -> None:
    if not upserts_by_collection and not delete_ids_by_collection:
        return
    current = AppState.objects.filter(key=DEFAULT_KEY).first()
    if not current or not isinstance(current.data, dict):
        _sync_app_state_snapshot()
        return
    merged = dict(current.data)
    keys = set(upserts_by_collection) | set(delete_ids_by_collection)
    for key in keys:
        items = merged.get(key) if isinstance(merged.get(key), list) else []
        merged[key] = _merge_snapshot_collection(
            items,
            upserts_by_collection.get(key, []),
            delete_ids_by_collection.get(key, set()),
        )
    current.data = merged
    current.save(update_fields=["data"])


def _patch_app_state_snapshot(collection: str, record_id: str, payload: dict | None) -> None:
    current = AppState.objects.filter(key=DEFAULT_KEY).first()
    if not current or not isinstance(current.data, dict):
        _sync_app_state_snapshot()
        return
    merged = dict(current.data)
    items = [item for item in (merged.get(collection) or []) if isinstance(item, dict)]
    if payload is None:
        merged[collection] = [item for item in items if item.get("id") != record_id]
    else:
        replaced = False
        next_items = []
        for item in items:
            if item.get("id") == record_id:
                next_items.append(payload)
                replaced = True
            else:
                next_items.append(item)
        if not replaced:
            next_items.append(payload)
        merged[collection] = next_items
    current.data = merged
    current.save(update_fields=["data"])


def _has_contract_file(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    file_id = str(payload.get("contractFileId") or "").strip()
    return bool(file_id)


def _contract_sort_key(payload: dict | None, fallback: str = "") -> str:
    """Contract list sort/display time: contract edits only, not business updatedAt."""
    if not isinstance(payload, dict):
        return fallback
    return str(payload.get("contractUpdatedAt") or payload.get("createdAt") or fallback or "")


def _project_ids_matching_contract_search(keyword: str) -> list[str]:
    if not keyword:
        return []
    org_ids = _org_ids_matching_name(keyword)
    return list(
        ProjectRecord.objects.filter(is_deleted=False)
        .filter(
            Q(name__icontains=keyword)
            | Q(project_no__icontains=keyword)
            | Q(customer_org_id__in=org_ids)
            | Q(usage_unit_org_id__in=org_ids)
            | Q(own_company_org_id__in=org_ids)
        )
        .values_list("id", flat=True)[:500]
    )


def _build_unified_contract_rows(search: str = "") -> list[dict]:
    """Merge project contracts and purchase-order contracts for 合同管理."""
    projects_qs = ProjectRecord.objects.filter(is_deleted=False).filter(
        Q(type="服务项目") | (~Q(data__contractFileId=None) & ~Q(data__contractFileId=""))
    )
    purchase_qs = PurchaseOrderRecord.objects.filter(is_deleted=False).exclude(
        Q(data__contractFileId=None) | Q(data__contractFileId="")
    )

    keywords = [part for part in (search or "").lower().split() if part]
    for keyword in keywords:
        org_ids = _org_ids_matching_name(keyword)
        projects_qs = projects_qs.filter(
            Q(name__icontains=keyword)
            | Q(project_no__icontains=keyword)
            | Q(customer_org_id__in=org_ids)
            | Q(usage_unit_org_id__in=org_ids)
            | Q(own_company_org_id__in=org_ids)
            | Q(data__sourcePlatform__icontains=keyword)
            | Q(data__serviceProductName__icontains=keyword)
            | Q(data__platformOrderNo__icontains=keyword)
            | Q(data__contractFileName__icontains=keyword)
            | Q(data__contractStatus__icontains=keyword)
            | Q(status__icontains=keyword)
        )
        matched_project_ids = _project_ids_matching_contract_search(keyword)
        purchase_qs = purchase_qs.filter(
            Q(order_no__icontains=keyword)
            | Q(supplier_org_id__in=org_ids)
            | Q(project_id__in=matched_project_ids)
            | Q(data__contractFileName__icontains=keyword)
            | Q(data__contractStatus__icontains=keyword)
            | Q(status__icontains=keyword)
        )

    # Load related projects for purchase-order rows (name/no/customer/type).
    purchase_orders = list(purchase_qs)
    related_project_ids = {record.project_id for record in purchase_orders if record.project_id}
    related_projects = {
        record.id: record
        for record in ProjectRecord.objects.filter(is_deleted=False, id__in=related_project_ids)
    }

    rows: list[dict] = []
    for record in projects_qs:
        payload = record.data if isinstance(record.data, dict) else {}
        contract_at = _contract_sort_key(payload)
        rows.append(
            {
                "id": f"project:{record.id}",
                "kind": "项目合同",
                "source": "project",
                "sourceId": record.id,
                "projectId": record.id,
                "projectName": record.name,
                "projectNo": record.project_no,
                "projectType": record.type,
                "customerOrgId": record.customer_org_id,
                "counterpartyOrgId": record.customer_org_id,
                "ownCompanyOrgId": record.own_company_org_id or payload.get("ownCompanyOrgId") or "",
                "orderNo": "",
                "contractStatus": payload.get("contractStatus") or "待签",
                "contractFileId": payload.get("contractFileId") or "",
                "contractFileName": payload.get("contractFileName") or "",
                "createdAt": payload.get("createdAt") or "",
                "updatedAt": contract_at,
                "_sortAt": contract_at,
            }
        )

    for record in purchase_orders:
        payload = record.data if isinstance(record.data, dict) else {}
        if not _has_contract_file(payload):
            continue
        project = related_projects.get(record.project_id)
        project_payload = project.data if project and isinstance(project.data, dict) else {}
        contract_at = _contract_sort_key(payload)
        rows.append(
            {
                "id": f"purchaseOrder:{record.id}",
                "kind": "采购合同",
                "source": "purchaseOrder",
                "sourceId": record.id,
                "projectId": record.project_id,
                "projectName": project.name if project else "",
                "projectNo": project.project_no if project else "",
                "projectType": project.type if project else "商品项目",
                "customerOrgId": project.customer_org_id if project else (project_payload.get("customerOrgId") or ""),
                "counterpartyOrgId": record.supplier_org_id,
                "ownCompanyOrgId": payload.get("ownCompanyOrgId") or (project.own_company_org_id if project else "") or "",
                "orderNo": record.order_no,
                "contractStatus": payload.get("contractStatus") or "待签",
                "contractFileId": payload.get("contractFileId") or "",
                "contractFileName": payload.get("contractFileName") or "",
                "createdAt": payload.get("createdAt") or "",
                "updatedAt": contract_at,
                "_sortAt": contract_at,
            }
        )

    rows.sort(key=lambda item: (item.get("_sortAt") or "", item.get("id") or ""), reverse=True)
    for item in rows:
        item.pop("_sortAt", None)
    return rows


def _contracts_collection_response(request):
    search = (request.GET.get("search") or "").strip()
    rows = _build_unified_contract_rows(search)
    if _wants_paged_response(request):
        page, page_size = _parse_page_params(request)
        total = len(rows)
        start = (page - 1) * page_size
        return JsonResponse(
            {
                "items": rows[start : start + page_size],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    return JsonResponse({"data": rows})


def _finance_statements_collection_response(request):
    rows = build_finance_statement_rows(
        {
            "businessKind": request.GET.get("businessKind") or "",
            "customerOrgId": request.GET.get("customerOrgId") or "",
            "ownCompanyOrgId": request.GET.get("ownCompanyOrgId") or "",
            "salesperson": request.GET.get("salesperson") or "",
            "collectionAccountId": request.GET.get("collectionAccountId") or "",
            "dateFrom": request.GET.get("dateFrom") or "",
            "dateTo": request.GET.get("dateTo") or "",
        }
    )
    if _wants_paged_response(request):
        page, page_size = _parse_page_params(request)
        total = len(rows)
        start = (page - 1) * page_size
        return JsonResponse(
            {
                "items": rows[start : start + page_size],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    return JsonResponse({"data": rows})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def collection_items(request, collection):
    if collection == "contracts":
        if request.method != "GET":
            return JsonResponse({"detail": "Method not allowed."}, status=405)
        user_data, permission_error = _require_permission(request, _collection_permission(collection, "read"))
        if permission_error:
            return permission_error
        return _contracts_collection_response(request)

    if collection == "financeStatements":
        if request.method != "GET":
            return JsonResponse({"detail": "Method not allowed."}, status=405)
        user_data, permission_error = _require_permission(request, _collection_permission(collection, "read"))
        if permission_error:
            return permission_error
        return _finance_statements_collection_response(request)

    model = _collection_model(collection)
    if not model:
        return JsonResponse({"detail": "Unknown collection."}, status=404)

    if request.method == "GET":
        user_data, permission_error = _require_permission(request, _collection_permission(collection, "read"))
        if permission_error:
            return permission_error
        if collection in {"officialSites", "officialPages"}:
            ensure_default_official_sites()
        include_deleted = request.GET.get("includeDeleted") == "1"
        can_view_sensitive = _can_view_sensitive(user_data)
        queryset = _collection_queryset(model, include_deleted)
        queryset = _apply_collection_list_query(collection, queryset, request)
        if _wants_paged_response(request):
            page, page_size = _parse_page_params(request)
            total = queryset.count()
            start = (page - 1) * page_size
            items = [
                _sanitize_record_data(
                    collection,
                    _collection_public_data(collection, item),
                    can_view_sensitive,
                )
                for item in queryset[start : start + page_size]
            ]
            return JsonResponse(
                {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                }
            )
        return JsonResponse({"data": [
            _sanitize_record_data(
                collection,
                _collection_public_data(collection, item),
                can_view_sensitive,
            )
            for item in queryset
        ]})

    if collection == "operationLogs":
        user_data, permission_error = _require_login(request)
    else:
        user_data, permission_error = _require_permission(request, _collection_permission(collection, "write"))
    if permission_error:
        return permission_error

    payload, error = _read_body(request)
    if error:
        return error
    data = _record_payload(payload)
    if not data or not data.get("id"):
        return JsonResponse({"detail": "Record data with id is required."}, status=400)

    existing = model.objects.filter(id=data["id"]).first()
    data = _preserve_sensitive_fields(collection, data, existing.data if existing else None)
    if collection == "platformAccounts":
        data = _ensure_platform_account_timestamps(data, existing)
    if collection == "trademarkCertificates":
        data = {**data, "registrationNo": _normalize_registration_no(data.get("registrationNo"))}
        conflict = _trademark_registration_conflict(data.get("registrationNo"), exclude_id=data.get("id"))
        if conflict:
            return conflict
    record, created = model.objects.update_or_create(
        id=data["id"],
        defaults={**_record_defaults(model, data), "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )
    can_view_sensitive = _can_view_sensitive(user_data)
    return JsonResponse({"data": _sanitize_record_data(collection, record.data, can_view_sensitive)}, status=201 if created else 200)


@csrf_exempt
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
def collection_item(request, collection, record_id):
    model = _collection_model(collection)
    if not model:
        return JsonResponse({"detail": "Unknown collection."}, status=404)

    action = "read" if request.method == "GET" else "write"
    user_data, permission_error = _require_permission(request, _collection_permission(collection, action))
    if permission_error:
        return permission_error

    record = model.objects.filter(id=record_id).first()
    if not record or (record.is_deleted and request.GET.get("includeDeleted") != "1"):
        return JsonResponse({"detail": "Record not found."}, status=404)

    if request.method == "GET":
        can_view_sensitive = _can_view_sensitive(user_data)
        return JsonResponse({"data": _sanitize_record_data(collection, record.data, can_view_sensitive)})

    if request.method == "DELETE":
        if model is OrganizationRecord:
            references = _organization_reference_counts({record.id})
            if references:
                return JsonResponse(
                    {
                        "detail": "该企业/单位仍被业务数据引用，无法删除。",
                        "references": references,
                    },
                    status=409,
                )
        deleted_by = request.headers.get("X-Operator", "") or user_data.get("name", "")
        if model is ProjectRecord:
            _soft_delete_queryset(
                TransactionRecord.objects.filter(is_deleted=False).filter(
                    Q(project_id=record.id) | Q(data__projectId=record.id)
                ),
                deleted_by,
            )
        _soft_delete_queryset(model.objects.filter(id=record.id), deleted_by)
        return JsonResponse({"data": None})

    payload, error = _read_body(request)
    if error:
        return error
    incoming = _record_payload(payload)
    if not incoming:
        return JsonResponse({"detail": "Record data is required."}, status=400)

    existing_data = record.data if isinstance(record.data, dict) else {}
    data = {**_column_json_from_record(record), **existing_data, **incoming} if request.method == "PATCH" else incoming
    data["id"] = record.id
    data = _preserve_sensitive_fields(collection, data, record.data)
    if collection == "platformAccounts":
        if request.method in {"PUT", "PATCH"} and not incoming.get("updatedAt"):
            data["updatedAt"] = timezone.now().isoformat()
        data = _ensure_platform_account_timestamps(data, record)
    if collection == "trademarkCertificates":
        data = {**data, "registrationNo": _normalize_registration_no(data.get("registrationNo"))}
        conflict = _trademark_registration_conflict(data.get("registrationNo"), exclude_id=record.id)
        if conflict:
            return conflict
    for field, value in _record_defaults(model, data).items():
        setattr(record, field, value)
    record.is_deleted = False
    record.deleted_at = None
    record.deleted_by = ""
    record.save()
    can_view_sensitive = _can_view_sensitive(user_data)
    return JsonResponse({"data": _sanitize_record_data(collection, record.data, can_view_sensitive)})


@csrf_exempt
@require_http_methods(["POST"])
def auth_login(request):
    payload, error = _read_body(request)
    if error:
        return error

    identifier = _text(payload, "identifier", "phone", "name", "username")
    password = str(payload.get("password", ""))
    if not identifier or not password:
        return JsonResponse({"detail": "请输入账号和密码。"}, status=400)

    user = _find_login_user(identifier, password)
    if not user:
        if _identifier_user_status(identifier) == "停用":
            return JsonResponse({"detail": "账号已停用，请联系管理员启用。"}, status=403)
        return JsonResponse({"detail": "账号或密码错误，请重新输入。"}, status=401)

    user_data = _public_user(user)
    request.session["user_id"] = user.id if isinstance(user, UserRecord) else user_data.get("id")
    request.session["user_name"] = user.name if isinstance(user, UserRecord) else user_data.get("name")
    request.session.set_expiry(60 * 60 * 12)
    return JsonResponse({"data": user_data})


@require_http_methods(["GET"])
def auth_me(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JsonResponse({"detail": "Not authenticated."}, status=401)
    user = _active_user_queryset().filter(id=user_id).first()
    if user:
        return JsonResponse({"data": _public_user(user)})
    state = AppState.objects.filter(key=DEFAULT_KEY).first()
    legacy_user = next((item for item in (state.data.get("users", []) if state and isinstance(state.data, dict) else []) if item.get("id") == user_id), None)
    if not legacy_user:
        # 不在此处 flush：短暂查库失败/快照滞后时 flush 会把仍有效的登录态永久清掉，
        # 表现为「上传/保存成功后立刻要重新登录」。显式 logout 才会清 session。
        return JsonResponse({"detail": "Not authenticated."}, status=401)
    return JsonResponse({"data": _public_user(legacy_user)})


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout(request):
    request.session.flush()
    return JsonResponse({"data": None})


@csrf_exempt
@require_http_methods(["POST"])
def audit_sensitive_access(request):
    user_data, auth_error = _require_login(request)
    if auth_error:
        return auth_error
    if not _can_view_sensitive(user_data):
        return JsonResponse({"detail": "Permission denied.", "permission": "sensitive.view"}, status=403)

    payload, error = _read_body(request)
    if error:
        return error

    now = timezone.now().isoformat()
    target_name = _text(payload, "targetName", "customerName", "platform") or "敏感信息"
    field_label = _text(payload, "fieldLabel", "label", "field") or "敏感字段"
    log = {
        "id": f"log-{uuid.uuid4().hex[:8]}",
        "createdAt": now,
        "action": "查看/复制敏感信息",
        "targetType": "系统",
        "targetName": target_name,
        "operator": user_data.get("name", "未知用户"),
        "detail": f"{field_label} / {payload.get('platform', '')} / {payload.get('source', '')}",
    }
    OperationLogRecord.objects.update_or_create(
        id=log["id"],
        defaults={**_record_defaults(OperationLogRecord, log), "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )
    return JsonResponse({"data": log}, status=201)


@require_http_methods(["GET"])
def platform_account_sensitive_value(request, record_id, field):
    user_data, auth_error = _require_login(request)
    if auth_error:
        return auth_error
    if not _can_view_sensitive(user_data):
        return JsonResponse({"detail": "Permission denied.", "permission": "sensitive.view"}, status=403)
    if field not in PLATFORM_SENSITIVE_FIELDS:
        return JsonResponse({"detail": "Unknown sensitive field."}, status=404)

    record = PlatformAccountRecord.objects.filter(id=record_id, is_deleted=False).first()
    if not record:
        return JsonResponse({"detail": "Record not found."}, status=404)
    return JsonResponse({"data": {"value": record.data.get(field)}})


DOCUMENT_PERMISSIONS = {
    "business_license": {"read": "entity.view", "write": "entity.create"},
    "invoice": {"read": "invoice.manage", "write": "invoice.manage"},
    "payment_voucher": {"read": "finance.view", "write": "finance.manage"},
    "contract": {"read": "project.view", "write": "project.edit"},
    "trademark_certificate": {"read": "trademarkCertificate.view", "write": "trademarkCertificate.manage"},
    "trademark_attachment": {"read": "trademarkCertificate.view", "write": "trademarkCertificate.manage"},
}

# These types keep one file per owner (upsert). Others always create a new ManagedFile.
SINGLE_FILE_DOCUMENT_TYPES = {
    "business_license",
    "invoice",
    "payment_voucher",
    "contract",
    "trademark_certificate",
}


def _normalize_registration_no(value) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def _trademark_registration_conflict(registration_no, exclude_id: str | None = None):
    normalized = _normalize_registration_no(registration_no)
    if not normalized:
        return JsonResponse({"detail": "商标注册号不能为空。"}, status=400)
    queryset = TrademarkCertificateRecord.objects.filter(is_deleted=False, registration_no__iexact=normalized)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    if queryset.exists():
        return JsonResponse({"detail": f"商标注册号「{normalized}」已存在，请勿重复添加。"}, status=409)
    return None


ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


@csrf_exempt
@require_http_methods(["POST"])
def upload_document(request):
    document_type = request.POST.get("documentType", "").strip()
    owner_id = request.POST.get("ownerId", "").strip()
    permissions = DOCUMENT_PERMISSIONS.get(document_type)
    if not permissions:
        return JsonResponse({"detail": "不支持的文件类型。"}, status=400)
    user_data, permission_error = _require_permission(request, permissions["write"])
    if permission_error:
        return permission_error
    uploaded = request.FILES.get("file")
    if not owner_id or not uploaded:
        return JsonResponse({"detail": "ownerId 和 file 为必填项。"}, status=400)
    content_type = (uploaded.content_type or "").lower()
    if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
        return JsonResponse({"detail": "仅支持 PDF 和常见图片格式。"}, status=400)
    if uploaded.size > 25 * 1024 * 1024:
        return JsonResponse({"detail": "文件不能超过 25MB。"}, status=400)

    record = None
    if document_type in SINGLE_FILE_DOCUMENT_TYPES:
        record = ManagedFile.objects.filter(document_type=document_type, owner_id=owner_id).first()
    if record:
        old_file = record.file
        record.original_name = uploaded.name[:255]
        record.content_type = content_type
        record.size = uploaded.size
        record.uploaded_by = user_data.get("name", "")
        record.file = uploaded
        record.save()
        if old_file and old_file.name != record.file.name:
            old_file.storage.delete(old_file.name)
    else:
        record = ManagedFile.objects.create(
            id=f"file-{uuid.uuid4().hex}",
            document_type=document_type,
            owner_id=owner_id,
            original_name=uploaded.name[:255],
            content_type=content_type,
            size=uploaded.size,
            uploaded_by=user_data.get("name", ""),
            file=uploaded,
        )
    return JsonResponse({
        "data": {
            "id": record.id,
            "fileName": record.original_name,
            "contentType": record.content_type,
            "size": record.size,
            "url": f"/api/documents/{record.id}/",
        }
    }, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_document(request, file_id):
    record = ManagedFile.objects.filter(id=file_id).first()
    if not record:
        return JsonResponse({"detail": "文件不存在。"}, status=404)
    permissions = DOCUMENT_PERMISSIONS.get(record.document_type)
    if not permissions:
        return JsonResponse({"detail": "文件类型无效。"}, status=404)
    _, permission_error = _require_permission(request, permissions["write"])
    if permission_error:
        return permission_error
    storage_name = record.file.name if record.file else ""
    storage = record.file.storage if record.file else None
    record.delete()
    if storage_name and storage is not None:
        try:
            storage.delete(storage_name)
        except Exception:
            pass
    return JsonResponse({"data": {"id": file_id}})


@require_http_methods(["GET"])
@xframe_options_sameorigin
def download_document(request, file_id):
    record = ManagedFile.objects.filter(id=file_id).first()
    if not record:
        return JsonResponse({"detail": "文件不存在。"}, status=404)
    permissions = DOCUMENT_PERMISSIONS.get(record.document_type)
    if not permissions:
        return JsonResponse({"detail": "文件类型无效。"}, status=404)
    _, permission_error = _require_permission(request, permissions["read"])
    if permission_error:
        return permission_error
    response = FileResponse(record.file.open("rb"), content_type=record.content_type or "application/octet-stream")
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(record.original_name)}"
    response["X-Original-Filename"] = record.original_name
    return response


def _amount(value) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _order_amount(order: dict) -> Decimal:
    """订单金额用应收，不用商品明细价（amount 常来自报价/单价×数量）。"""
    if order.get("receivableAmount") not in (None, ""):
        return _amount(order.get("receivableAmount"))
    return _amount(order.get("amount"))


def _org_name(orgs_by_id: dict[str, dict], org_id) -> str:
    if not org_id:
        return ""
    org = orgs_by_id.get(org_id) or {}
    return str(org.get("name") or "").strip()


def _compact_details(details: dict) -> dict:
    compact = {}
    for key, value in details.items():
        if value in (None, ""):
            continue
        compact[key] = value
    return compact


def _issue(
    level: str,
    code: str,
    message: str,
    target_type: str,
    target_id: str = "",
    target_name: str = "",
    diff: Decimal | None = None,
    details: dict | None = None,
):
    item = {
        "level": level,
        "code": code,
        "message": message,
        "targetType": target_type,
        "targetId": target_id,
        "targetName": target_name,
    }
    if diff is not None:
        item["diff"] = float(diff)
    if details:
        item["details"] = _compact_details(details)
    return item


def _order_issue_details(
    order: dict,
    projects_by_id: dict[str, dict],
    orgs_by_id: dict[str, dict],
    *,
    kind: str,
    tx_total: Decimal | None = None,
    invoiced: Decimal | None = None,
) -> dict:
    project = projects_by_id.get(order.get("projectId")) or {}
    details = {
        "orderNo": order.get("orderNo") or "",
        "orderStatus": order.get("status") or "",
        "projectName": project.get("name") or "",
        "projectNo": project.get("projectNo") or "",
    }
    if kind == "purchase":
        details["buyerName"] = _org_name(orgs_by_id, order.get("ownCompanyOrgId") or project.get("ownCompanyOrgId"))
        details["sellerName"] = _org_name(orgs_by_id, order.get("supplierOrgId"))
        details["orderAmount"] = float(_amount(order.get("amount")))
    else:
        details["buyerName"] = _org_name(orgs_by_id, order.get("customerOrgId") or project.get("customerOrgId"))
        details["sellerName"] = _org_name(orgs_by_id, order.get("ownCompanyOrgId") or project.get("ownCompanyOrgId"))
        details["orderAmount"] = float(_order_amount(order))
        details["receivedAmount"] = float(_amount(order.get("receivedAmount")))
        if tx_total is not None:
            details["txTotal"] = float(tx_total)
    if invoiced is not None:
        details["invoicedAmount"] = float(invoiced)
    return details


def _project_issue_details(
    project: dict,
    orgs_by_id: dict[str, dict],
    *,
    order_total: Decimal | None = None,
    purchase_total: Decimal | None = None,
) -> dict:
    details = {
        "projectName": project.get("name") or "",
        "projectNo": project.get("projectNo") or "",
        "projectId": project.get("id") or "",
        "buyerName": _org_name(orgs_by_id, project.get("customerOrgId")),
        "sellerName": _org_name(orgs_by_id, project.get("ownCompanyOrgId")),
        "orderStatus": project.get("status") or "",
        "projectAmount": float(_amount(project.get("totalAmount"))),
        "projectCost": float(purchase_total if purchase_total is not None else _amount(project.get("totalCost"))),
    }
    if order_total is not None:
        details["orderTotal"] = float(order_total)
    if purchase_total is not None:
        details["purchaseTotal"] = float(purchase_total)
    return details


def _project_order_total(
    project: dict,
    sales_by_project: dict[str, Decimal],
    service_by_project: dict[str, Decimal],
) -> Decimal:
    """服务项目只计服务订单，商品项目只计销售订单，避免历史遗留双订单重复加总。"""
    project_id = project.get("id")
    project_type = project.get("type")
    if project_type == "服务项目":
        return service_by_project.get(project_id, Decimal("0.00"))
    if project_type == "商品项目":
        return sales_by_project.get(project_id, Decimal("0.00"))
    if project_id in service_by_project:
        return service_by_project.get(project_id, Decimal("0.00"))
    return sales_by_project.get(project_id, Decimal("0.00"))


def _invoice_line_gross(item: dict) -> Decimal:
    return _amount(item.get("amount")) + _amount(item.get("taxAmount"))


def _invoice_order_ids(invoice: dict, order_type: str) -> list[str]:
    header_key = "salesOrderIds" if order_type == "sales" else "purchaseOrderIds"
    line_key = "salesOrderId" if order_type == "sales" else "purchaseOrderId"
    ids: list[str] = []
    for order_id in invoice.get(header_key) or []:
        if order_id and order_id not in ids:
            ids.append(order_id)
    for line in invoice.get("lineItems") or []:
        if not isinstance(line, dict):
            continue
        order_id = line.get(line_key)
        if order_id and order_id not in ids:
            ids.append(order_id)
    return ids


def _invoice_amount_for_order(invoice: dict, order_id: str, order_type: str) -> Decimal:
    line_key = "salesOrderId" if order_type == "sales" else "purchaseOrderId"
    lines = [item for item in (invoice.get("lineItems") or []) if isinstance(item, dict)]
    allocated = [item for item in lines if item.get(line_key) == order_id]
    if allocated:
        if len(allocated) == len(lines):
            return _amount(invoice.get("amount"))
        return sum((_invoice_line_gross(item) for item in allocated), Decimal("0.00"))
    ids = invoice.get("salesOrderIds" if order_type == "sales" else "purchaseOrderIds") or []
    if order_id in ids and len(ids) == 1:
        return _amount(invoice.get("amount"))
    return Decimal("0.00")


def _invoice_unallocated_amount(invoice: dict, order_type: str) -> Decimal:
    line_key = "salesOrderId" if order_type == "sales" else "purchaseOrderId"
    lines = [item for item in (invoice.get("lineItems") or []) if isinstance(item, dict)]
    if not lines:
        return Decimal("0.00")
    leftover = Decimal("0.00")
    for line in lines:
        if not line.get(line_key):
            leftover += _invoice_line_gross(line)
    return leftover


def _linked_invoice_amounts(invoices: list[dict], order_type: str) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for invoice in invoices:
        if invoice.get("status") == "作废":
            continue
        for order_id in _invoice_order_ids(invoice, order_type):
            amount = _invoice_amount_for_order(invoice, order_id, order_type)
            if amount:
                totals[order_id] = totals.get(order_id, Decimal("0.00")) + amount
    return totals


FINANCE_VALIDATION_IGNORES_KEY = "finance_validation_ignores"


def _finance_issue_ignore_key(code: str, target_type: str, target_id: str) -> str:
    return f"{code}:{target_type}:{target_id}"


def _finance_ignored_keys(data: dict) -> set[str]:
    keys: set[str] = set()
    for group in data.get("optionGroups") or []:
        if not isinstance(group, dict) or group.get("key") != FINANCE_VALIDATION_IGNORES_KEY:
            continue
        for item in group.get("items") or []:
            if not isinstance(item, dict):
                continue
            value = item.get("value") or item.get("id")
            if value:
                keys.add(str(value))
    return keys


def _upsert_finance_validation_ignore(payload: dict) -> dict:
    code = str(payload.get("code") or "").strip()
    target_type = str(payload.get("targetType") or "").strip()
    target_id = str(payload.get("targetId") or "").strip()
    if not code or not target_type or not target_id:
        raise ValueError("ignore key incomplete")
    key = _finance_issue_ignore_key(code, target_type, target_id)
    record = OptionGroupRecord.objects.filter(key=FINANCE_VALIDATION_IGNORES_KEY, is_deleted=False).first()
    if record and isinstance(record.data, dict):
        data = dict(record.data)
        items = [item for item in (data.get("items") or []) if isinstance(item, dict)]
    else:
        data = {
            "id": f"optgrp-{FINANCE_VALIDATION_IGNORES_KEY}",
            "key": FINANCE_VALIDATION_IGNORES_KEY,
            "name": "财务校验忽略项",
            "description": "被忽略的财务一致性提醒，下次校验不再显示",
            "usages": ["财务一致性校验"],
            "items": [],
        }
        items = []
    if not any((item.get("value") or item.get("id")) == key for item in items):
        items.append({
            "id": key,
            "label": str(payload.get("targetName") or payload.get("message") or key),
            "value": key,
            "enabled": True,
            "sortOrder": len(items) + 1,
            "note": str(payload.get("message") or ""),
        })
    data["items"] = items
    data["id"] = data.get("id") or f"optgrp-{FINANCE_VALIDATION_IGNORES_KEY}"
    data["key"] = FINANCE_VALIDATION_IGNORES_KEY
    data["name"] = data.get("name") or "财务校验忽略项"
    record, _created = OptionGroupRecord.objects.update_or_create(
        id=data["id"],
        defaults={**_record_defaults(OptionGroupRecord, data), "is_deleted": False, "deleted_at": None, "deleted_by": ""},
    )
    _patch_app_state_collections(["optionGroups"])
    return record.data if isinstance(record.data, dict) else data


def _finance_validation(data: dict) -> dict:
    issues = []
    sales_orders = data.get("salesOrders", [])
    service_orders = data.get("serviceOrders", [])
    purchase_orders = data.get("purchaseOrders", [])
    projects = data.get("projects", [])
    invoices = data.get("invoices", [])
    transactions = [tx for tx in data.get("transactions", []) if tx.get("status") != "作废"]
    orgs_by_id = {item["id"]: item for item in data.get("organizations", []) if item.get("id")}
    projects_by_id = {item["id"]: item for item in projects if item.get("id")}

    tx_by_sales: dict[str, Decimal] = {}
    tx_by_service: dict[str, Decimal] = {}
    for tx in transactions:
        if tx.get("type") != "收款":
            continue
        if tx.get("salesOrderId"):
            tx_by_sales[tx["salesOrderId"]] = tx_by_sales.get(tx["salesOrderId"], Decimal("0.00")) + _amount(tx.get("amount"))
        if tx.get("serviceOrderId"):
            tx_by_service[tx["serviceOrderId"]] = tx_by_service.get(tx["serviceOrderId"], Decimal("0.00")) + _amount(tx.get("amount"))

    def validate_receivable_order(order: dict, tx_total: Decimal, target_type: str, kind: str):
        status = order.get("status")
        if status in {"取消", "退款"}:
            return
        order_amount = _order_amount(order)
        received = _amount(order.get("receivedAmount"))
        order_tx_diff = order_amount - tx_total
        details = _order_issue_details(order, projects_by_id, orgs_by_id, kind=kind, tx_total=tx_total)
        if status == "已付款" and abs(order_tx_diff) > Decimal("0.01"):
            issues.append(_issue(
                "error",
                "order_amount_transaction_mismatch",
                "已付款订单的收款流水合计与订单金额不一致",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                order_tx_diff,
                details,
            ))
        if status == "部分付款" and not (Decimal("0.00") < tx_total < order_amount):
            issues.append(_issue(
                "warning",
                "partial_order_tx_invalid",
                "部分付款订单的收款流水合计应大于 0 且小于订单金额",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                order_tx_diff,
                details,
            ))
        if status == "待付款" and tx_total > Decimal("0.00"):
            issues.append(_issue(
                "warning",
                "pending_order_has_transaction",
                "待付款订单仍有收款流水",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                tx_total,
                details,
            ))
        received_tx_diff = received - tx_total
        received_aligned_with_order = abs(received - order_amount) <= Decimal("0.01")
        # 实收已与订单金额对齐时，这条与「流水 vs 订单金额」是同一件事
        if abs(received_tx_diff) > Decimal("0.01") and not (received_aligned_with_order and abs(order_tx_diff) > Decimal("0.01")):
            issues.append(_issue(
                "error",
                "received_transaction_mismatch",
                "订单实收金额与收款流水合计不一致",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                received_tx_diff,
                details,
            ))
        if status == "已付款" and received + Decimal("0.01") < order_amount:
            issues.append(_issue(
                "error",
                "paid_order_under_received",
                "订单状态为已付款，但实收金额小于订单金额",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                order_amount - received,
                details,
            ))
        if status == "部分付款" and not (Decimal("0.00") < received < order_amount):
            issues.append(_issue(
                "warning",
                "partial_order_amount_invalid",
                "订单状态为部分付款，但实收金额不在 0 到订单金额之间",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                details=details,
            ))
        if status == "待付款" and received > Decimal("0.00"):
            issues.append(_issue(
                "warning",
                "pending_order_has_received",
                "订单状态为待付款，但已有实收金额",
                target_type,
                order.get("id", ""),
                order.get("orderNo", ""),
                details=details,
            ))

    for order in sales_orders:
        validate_receivable_order(order, tx_by_sales.get(order.get("id"), Decimal("0.00")), "销售订单", "sales")
    for order in service_orders:
        validate_receivable_order(order, tx_by_service.get(order.get("id"), Decimal("0.00")), "服务订单", "service")

    sales_by_id = {item.get("id"): item for item in sales_orders if item.get("id")}
    purchase_by_id = {item.get("id"): item for item in purchase_orders if item.get("id")}
    sales_invoice_totals = _linked_invoice_amounts([invoice for invoice in invoices if invoice.get("type") == "销项"], "sales")
    purchase_invoice_totals = _linked_invoice_amounts([invoice for invoice in invoices if invoice.get("type") == "进项"], "purchase")
    for order in sales_orders:
        invoiced = sales_invoice_totals.get(order.get("id"), Decimal("0.00"))
        amount = _order_amount(order)
        if invoiced > amount + Decimal("0.01"):
            issues.append(_issue(
                "error",
                "sales_invoice_over_order",
                "销项发票金额超过销售订单金额",
                "销售订单",
                order.get("id", ""),
                order.get("orderNo", ""),
                invoiced - amount,
                _order_issue_details(order, projects_by_id, orgs_by_id, kind="sales", invoiced=invoiced),
            ))
    for order in purchase_orders:
        invoiced = purchase_invoice_totals.get(order.get("id"), Decimal("0.00"))
        amount = _amount(order.get("amount"))
        if invoiced > amount + Decimal("0.01"):
            issues.append(_issue(
                "error",
                "purchase_invoice_over_order",
                "进项发票金额超过采购订单金额",
                "采购订单",
                order.get("id", ""),
                order.get("orderNo", ""),
                invoiced - amount,
                _order_issue_details(order, projects_by_id, orgs_by_id, kind="purchase", invoiced=invoiced),
            ))
    for invoice in invoices:
        if invoice.get("status") == "作废":
            continue
        invoice_type = "sales" if invoice.get("type") == "销项" else "purchase"
        order_ids = _invoice_order_ids(invoice, invoice_type)
        if len(order_ids) <= 1:
            continue
        orders_by_id = sales_by_id if invoice_type == "sales" else purchase_by_id
        allocations = []
        allocated_total = Decimal("0.00")
        for order_id in order_ids:
            order = orders_by_id.get(order_id) or {}
            allocated = _invoice_amount_for_order(invoice, order_id, invoice_type)
            allocated_total += allocated
            order_amount = _order_amount(order) if invoice_type == "sales" else _amount(order.get("amount"))
            project = projects_by_id.get(order.get("projectId")) or {}
            allocations.append({
                "orderId": order_id,
                "orderNo": order.get("orderNo") or order_id,
                "orderAmount": float(order_amount),
                "allocatedAmount": float(allocated),
                "projectName": project.get("name") or "",
                "projectNo": project.get("projectNo") or "",
                "projectId": project.get("id") or "",
            })
        unallocated = _invoice_unallocated_amount(invoice, invoice_type)
        invoice_amount = _amount(invoice.get("amount"))
        if unallocated <= Decimal("0.01") and abs(allocated_total - invoice_amount) <= Decimal("0.01"):
            continue
        project_names = list(dict.fromkeys(row["projectName"] for row in allocations if row["projectName"]))
        first_project = next((projects_by_id.get(row["projectId"]) for row in allocations if row.get("projectId")), None) or projects_by_id.get(invoice.get("projectId")) or {}
        issues.append(_issue(
            "warning",
            "invoice_multi_order_allocation_missing",
            "发票已关联多个订单，但仍有商品未分摊到具体订单，无法按订单精确核对开票金额",
            "发票",
            invoice.get("id", ""),
            invoice.get("invoiceNo", ""),
            details={
                "projectName": " / ".join(project_names) or first_project.get("name") or "",
                "projectNo": first_project.get("projectNo") or "",
                "projectId": first_project.get("id") or invoice.get("projectId") or "",
                "buyerName": invoice.get("buyerName") or _org_name(orgs_by_id, invoice.get("buyerOrgId") or invoice.get("counterpartyOrgId")),
                "sellerName": invoice.get("sellerName") or _org_name(orgs_by_id, invoice.get("sellerOrgId")),
                "invoiceAmount": float(invoice_amount),
                "orderAmount": float(invoice_amount),
                "orderStatus": invoice.get("status") or "",
                "orderAllocations": allocations,
                "unallocatedAmount": float(unallocated),
            },
        ))

    sales_by_project: dict[str, Decimal] = {}
    service_by_project: dict[str, Decimal] = {}
    purchase_by_project: dict[str, Decimal] = {}
    for order in sales_orders:
        if order.get("status") in {"取消", "退款"}:
            continue
        project_id = order.get("projectId")
        sales_by_project[project_id] = sales_by_project.get(project_id, Decimal("0.00")) + _order_amount(order)
    for order in service_orders:
        if order.get("status") in {"取消", "退款"}:
            continue
        project_id = order.get("projectId")
        service_by_project[project_id] = service_by_project.get(project_id, Decimal("0.00")) + _order_amount(order)
    for order in purchase_orders:
        if order.get("status") == "已取消":
            continue
        project_id = order.get("projectId")
        purchase_by_project[project_id] = purchase_by_project.get(project_id, Decimal("0.00")) + _amount(order.get("amount"))
    for project in projects:
        project_id = project.get("id")
        order_total = _project_order_total(project, sales_by_project, service_by_project)
        purchase_total = purchase_by_project.get(project_id, Decimal("0.00"))
        amount_diff = _amount(project.get("totalAmount")) - order_total
        details = _project_issue_details(project, orgs_by_id, order_total=order_total, purchase_total=purchase_total)
        if abs(amount_diff) > Decimal("0.01"):
            issues.append(_issue(
                "warning",
                "project_amount_mismatch",
                "项目金额与所属订单金额合计不一致",
                "项目",
                project_id,
                project.get("name", ""),
                amount_diff,
                details,
            ))

    ignored = _finance_ignored_keys(data)
    if ignored:
        issues = [
            item for item in issues
            if _finance_issue_ignore_key(item.get("code", ""), item.get("targetType", ""), item.get("targetId", "")) not in ignored
        ]

    return {
        "summary": {
            "errors": sum(1 for item in issues if item["level"] == "error"),
            "warnings": sum(1 for item in issues if item["level"] == "warning"),
            "checkedAt": timezone.now().isoformat(),
        },
        "issues": issues,
    }


@require_http_methods(["GET"])
def finance_validation(request):
    _, permission_error = _require_permission(request, "finance.view")
    if permission_error:
        return permission_error
    return JsonResponse({"data": _finance_validation(load_app_data() or {})})


@csrf_exempt
@require_http_methods(["POST"])
def finance_validation_ignore(request):
    _, permission_error = _require_permission(request, "finance.view")
    if permission_error:
        return permission_error
    payload, error = _read_body(request)
    if error:
        return error
    try:
        saved = _upsert_finance_validation_ignore(payload)
    except ValueError:
        return JsonResponse({"detail": "忽略项不完整。"}, status=400)
    return JsonResponse({"data": saved})


@csrf_exempt
@require_http_methods(["POST"])
def website_leads(request):
    error, lead, _echo = _ingest_website_lead_request(request)
    if error:
        return error
    return JsonResponse({"code": 20000, "message": "success", "data": lead}, status=201)


@require_http_methods(["GET"])
def public_official_site(request):
    host = (request.GET.get("host") or request.META.get("HTTP_X_FORWARDED_HOST") or request.get_host() or "").strip()
    slug = (request.GET.get("slug") or "home").strip() or "home"
    resolved = resolve_public_site(host, slug=slug)
    if not resolved:
        return JsonResponse({"detail": "Site not found."}, status=404)
    return JsonResponse({"data": resolved})


@require_http_methods(["GET"])
def public_official_seo(request):
    host = (request.GET.get("host") or request.META.get("HTTP_X_FORWARDED_HOST") or request.get_host() or "").strip()
    site = find_official_site_by_host(host)
    if not site:
        return JsonResponse({"detail": "Site not found."}, status=404)
    return JsonResponse({"data": public_seo_payload(site.data or {})})


@csrf_exempt
@require_http_methods(["POST"])
def import_official_seo(request):
    _, permission_error = _require_permission(request, "site.manage")
    if permission_error:
        return permission_error
    overwrite = str(request.GET.get("overwrite") or "").strip().lower() in {"1", "true", "yes"}
    if request.body:
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}
        if isinstance(body, dict) and body.get("overwrite") is not None:
            overwrite = bool(body.get("overwrite"))
    items = apply_official_seo_defaults(overwrite=overwrite)
    return JsonResponse({"items": items, "total": len(items), "overwrite": overwrite})


@require_http_methods(["GET"])
def public_notices(request):
    page, page_size = _parse_page_params(request)
    payload = list_public_notices(
        page=page,
        page_size=page_size,
        search=(request.GET.get("search") or "").strip(),
        notice_kind=(request.GET.get("noticeKind") or request.GET.get("kind") or "").strip(),
    )
    return JsonResponse(payload)


@require_http_methods(["GET"])
def public_notice_detail(request, notice_id: str):
    item = get_public_notice(notice_id)
    if not item:
        return JsonResponse({"detail": "Notice not found."}, status=404)
    return JsonResponse({"data": item})


@csrf_exempt
@require_http_methods(["POST"])
def official_site_inquiry(request):
    error, lead, echo = _ingest_website_lead_request(request)
    if error:
        return error
    data = dict(echo) if isinstance(echo, dict) else {}
    data.update(lead)
    return JsonResponse({"code": 20000, "message": "success", "data": data}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def run_notice_collection(request):
    _, permission_error = _require_permission(request, "notice.manage")
    if permission_error:
        return permission_error
    payload, error = _read_body(request)
    if error:
        return error
    source_id = str((payload or {}).get("sourceId") or "").strip()
    ensure_sample = bool((payload or {}).get("ensureSample"))
    if ensure_sample and not source_id:
        source = ensure_default_sample_source()
        source_id = source.id
    if not source_id:
        return JsonResponse({"detail": "sourceId is required."}, status=400)
    source = NoticeCollectionSourceRecord.objects.filter(id=source_id, is_deleted=False).first()
    if not source:
        return JsonResponse({"detail": "采集源不存在。"}, status=404)
    if not source.enabled and not (payload or {}).get("force"):
        return JsonResponse({"detail": "采集源已停用。"}, status=400)
    run = run_collection_source(source)
    return JsonResponse({"data": run.data}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def generate_service_contract(request, project_id):
    _, permission_error = _require_permission(request, "project.edit")
    if permission_error:
        return permission_error
    payload, error = _read_body(request)
    if error:
        return error
    project = ProjectRecord.objects.filter(id=project_id, is_deleted=False).first()
    if not project:
        return JsonResponse({"detail": "项目不存在。"}, status=404)
    project_data = project.data if isinstance(project.data, dict) else {}
    if project_data.get("type") != "服务项目":
        return JsonResponse({"detail": "仅服务项目可以生成合同。"}, status=400)
    platform = normalize_contract_platform(str(project_data.get("sourcePlatform") or ""))
    if not has_service_contract_template(platform):
        return JsonResponse({"detail": "当前入驻平台没有可用的合同模板。"}, status=400)
    customer = OrganizationRecord.objects.filter(id=project_data.get("customerOrgId") or "", is_deleted=False).first()
    own_company = OrganizationRecord.objects.filter(id=project_data.get("ownCompanyOrgId") or "", is_deleted=False).first()
    service_orders = [
        item.data for item in ServiceOrderRecord.objects.filter(project_id=project_id, is_deleted=False)
        if isinstance(item.data, dict)
    ]
    option_group = OptionGroupRecord.objects.filter(key="collection_account", is_deleted=False).first()
    account_items = []
    if option_group and isinstance(option_group.data, dict):
        raw_items = option_group.data.get("items") or []
        if isinstance(raw_items, list):
            account_items = [item for item in raw_items if isinstance(item, dict)]
    draft = apply_draft_overrides(
        build_default_draft(
            project_data,
            customer.data if customer and isinstance(customer.data, dict) else None,
            own_company.data if own_company and isinstance(own_company.data, dict) else None,
            service_orders,
            account_items,
        ),
        payload,
    )
    missing = missing_required_fields(draft, platform)
    if missing:
        return JsonResponse({"detail": "生成合同所需信息不完整。", "missing": missing}, status=400)
    return _contract_download_response(platform, draft, payload)


@csrf_exempt
@require_http_methods(["POST"])
def generate_standalone_service_contract(request):
    _, permission_error = _require_permission(request, "project.edit")
    if permission_error:
        return permission_error
    payload, error = _read_body(request)
    if error:
        return error
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "请求数据无效。"}, status=400)
    platform = normalize_contract_platform(str(payload.get("platform") or ""))
    if not has_service_contract_template(platform):
        return JsonResponse({"detail": "当前入驻平台没有可用的合同模板。"}, status=400)
    draft = apply_draft_overrides({}, payload)
    missing = missing_required_fields(draft, platform)
    if missing:
        return JsonResponse({"detail": "生成合同所需信息不完整。", "missing": missing}, status=400)
    return _contract_download_response(platform, draft, payload)


def _contract_download_response(platform: str, draft: dict, payload: dict | None):
    output_format = normalize_contract_format(payload.get("format") if isinstance(payload, dict) else None)
    if output_format not in {"word", "pdf"}:
        return JsonResponse({"detail": "合同格式仅支持 Word 或 PDF。"}, status=400)
    try:
        content, content_type, filename = render_contract_file(platform, draft, output_format)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
