"""客户 Portal 企业视图 API：按登录账号 customerOrgId 过滤，禁止走员工 /api/collections/*。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from urllib.parse import quote

from django.contrib.auth.hashers import make_password
from django.db.models import CharField, Q, Value
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    CustomerAccountRecord,
    InvoiceRecord,
    ManagedFile,
    ProjectItemRecord,
    ProjectRecord,
    PurchaseOrderRecord,
    SalesOrderRecord,
    ServiceOrderRecord,
)
from .portal import (
    account_defaults,
    normalize_portal_permissions,
    public_account,
    require_portal,
)


def portal_format_datetime(value, *, seconds: bool = False) -> str:
    """将 UTC/带偏移 ISO 转为 Asia/Shanghai 墙钟；无时区信息则视为已是东八区墙钟。

    Portal 前端曾把 ``2026-09-09T05:35:00.000Z`` 直接截成 ``05:35``（UTC 墙钟），
    这里统一输出东八区，避免把 UTC 当本地显示。
    """
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        # 纯日期：不改
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return text
        normalized = text.replace("Z", "+00:00").replace("z", "+00:00")
        if "T" not in normalized and " " in normalized[:20]:
            # "2026-09-09 05:35:00+00:00" / "2026-09-09 05:35:00"
            head, _, tail = normalized.partition(" ")
            if tail[:1].isdigit():
                normalized = f"{head}T{tail}"
        dt = parse_datetime(normalized)
        if dt is None:
            pretty = text.replace("T", " ")
            return pretty[:19] if seconds else pretty[:16]
    if timezone.is_naive(dt):
        local = dt
    else:
        local = timezone.localtime(dt, timezone.get_default_timezone())
    return local.strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")


def _apply_portal_datetimes(data: dict, keys: tuple[str, ...], *, seconds: bool = False) -> dict:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            data[key] = portal_format_datetime(data[key], seconds=seconds)
    return data


def _read_json(request) -> tuple[dict | None, JsonResponse | None]:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None, JsonResponse({"detail": "请求体无效。"}, status=400)
    if not isinstance(payload, dict):
        return None, JsonResponse({"detail": "请求体无效。"}, status=400)
    return payload, None


def _portal_org_id(record: CustomerAccountRecord) -> str:
    return str(record.customer_org_id or (record.data or {}).get("customerOrgId") or "").strip()


def _require_org(record: CustomerAccountRecord):
    org_id = _portal_org_id(record)
    if not org_id:
        return "", JsonResponse(
            {"detail": "当前账号未绑定客户企业，请联系管理员补绑后再查看企业数据。"},
            status=403,
        )
    return org_id, None


def _page_params(request) -> tuple[int, int]:
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


def _paged(items: list, request) -> JsonResponse:
    page, page_size = _page_params(request)
    total = len(items)
    start = (page - 1) * page_size
    return JsonResponse(
        {
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


def _project_name_map(project_ids: set[str]) -> dict[str, str]:
    if not project_ids:
        return {}
    return {
        row.id: (row.name or "")
        for row in ProjectRecord.objects.filter(is_deleted=False, id__in=project_ids).only("id", "name")
    }


def _order_line_items(order_id: str, project_id: str, kind: str) -> list[dict]:
    """销售订单取 project_items；服务订单用项目服务商品名作一行摘要。"""
    if kind == "销售订单":
        qs = ProjectItemRecord.objects.filter(is_deleted=False, sales_order_id=order_id).order_by("id")
        rows = []
        for item in qs:
            payload = item.data if isinstance(item.data, dict) else {}
            rows.append(
                {
                    "productName": payload.get("productName") or "",
                    "quantity": float(item.quantity or 0),
                    "actualPrice": float(payload.get("actualPrice") or 0),
                    "amount": float(payload.get("actualPrice") or 0) * float(item.quantity or 0),
                }
            )
        return rows
    # 服务订单：项目上的服务名称
    if not project_id:
        return []
    project = ProjectRecord.objects.filter(id=project_id, is_deleted=False).first()
    if not project:
        return []
    payload = project.data if isinstance(project.data, dict) else {}
    name = payload.get("serviceProductName") or project.name or ""
    if not name:
        return []
    return [{"productName": name, "quantity": 1, "actualPrice": None, "amount": None}]


def _order_public(record, kind: str, *, detail: bool = False, project_names: dict[str, str] | None = None) -> dict:
    data = dict(record.data or {})
    data["id"] = record.id
    data["kind"] = kind
    data["orderNo"] = record.order_no or data.get("orderNo") or ""
    project_id = record.project_id or data.get("projectId") or ""
    data["projectId"] = project_id
    if project_names is not None:
        data["projectName"] = project_names.get(project_id) or data.get("projectName") or ""
    elif project_id:
        project = ProjectRecord.objects.filter(id=project_id, is_deleted=False).only("name").first()
        data["projectName"] = (project.name if project else "") or data.get("projectName") or ""
    else:
        data["projectName"] = data.get("projectName") or ""
    data["customerOrgId"] = record.customer_org_id or data.get("customerOrgId") or ""
    data["amount"] = float(record.amount or 0)
    data["status"] = record.status or data.get("status") or ""
    if hasattr(record, "receivable_amount"):
        data["receivableAmount"] = float(record.receivable_amount or 0)
    if hasattr(record, "received_amount"):
        data["receivedAmount"] = float(record.received_amount or 0)
    data.pop("password", None)
    if not data.get("createdAt") and getattr(record, "created_at", None):
        data["createdAt"] = record.created_at
    if detail:
        data["items"] = _order_line_items(record.id, project_id, kind)
    return _apply_portal_datetimes(
        data,
        ("createdAt", "updatedAt", "paidAt", "orderTime", "occurredAt"),
        seconds=False,
    )


def _invoice_public(record: InvoiceRecord) -> dict:
    data = dict(record.data or {})
    data["id"] = record.id
    data["invoiceNo"] = record.invoice_no or data.get("invoiceNo") or ""
    data["invoiceDate"] = record.invoice_date or data.get("invoiceDate") or ""
    data["type"] = record.type or data.get("type") or ""
    data["amount"] = float(record.amount or 0)
    data["status"] = record.status or data.get("status") or ""
    data["buyerOrgId"] = data.get("buyerOrgId") or ""
    data["sellerOrgId"] = data.get("sellerOrgId") or ""
    data["counterpartyOrgId"] = data.get("counterpartyOrgId") or ""
    data["buyerName"] = data.get("buyerName") or ""
    data["sellerName"] = data.get("sellerName") or ""
    data["fileId"] = data.get("fileId") or ""
    data["fileName"] = data.get("fileName") or ""
    # invoiceDate 通常为 YYYY-MM-DD；其余时间戳统一东八区
    data["invoiceDate"] = portal_format_datetime(data.get("invoiceDate") or "") or data["invoiceDate"]
    return _apply_portal_datetimes(data, ("createdAt", "updatedAt", "issuedAt"), seconds=False)


def _invoice_for_customer_org(org_id: str):
    """客户门户发票过滤。

    约定：客户作为买方。
    - 优先 data.buyerOrgId == customerOrgId（现行录入主路径）
    - 兼容存量销项：仅写了 counterpartyOrgId（销项时 counterparty=买方）且 buyerOrgId 为空
    """
    return (
        InvoiceRecord.objects.filter(is_deleted=False)
        .filter(
            # 主路径：买方企业 ID
            Q(data__buyerOrgId=org_id)
            # 兼容存量销项：counterpartyOrgId 即买方（与后台销项录入约定一致）
            | (Q(type="销项") & Q(data__counterpartyOrgId=org_id))
        )
        .order_by("-invoice_date", "-id")
    )


def _contract_sort_key(payload: dict) -> str:
    return str(
        payload.get("contractUpdatedAt")
        or payload.get("updatedAt")
        or payload.get("createdAt")
        or ""
    )


def _has_contract_file(payload: dict) -> bool:
    return bool(payload.get("contractFileId"))


def _portal_contract_rows_for_org(org_id: str, search: str = "") -> list[dict]:
    """仅查本企业相关合同，避免全库构建后再切片。"""
    projects_qs = ProjectRecord.objects.filter(is_deleted=False, customer_org_id=org_id).filter(
        Q(type="服务项目") | (~Q(data__contractFileId=None) & ~Q(data__contractFileId=""))
    )
    org_project_ids = ProjectRecord.objects.filter(is_deleted=False, customer_org_id=org_id).values_list("id", flat=True)
    purchase_qs = (
        PurchaseOrderRecord.objects.filter(is_deleted=False, project_id__in=org_project_ids)
        .exclude(Q(data__contractFileId=None) | Q(data__contractFileId=""))
    )

    keywords = [part for part in (search or "").lower().split() if part]
    for keyword in keywords:
        projects_qs = projects_qs.filter(
            Q(name__icontains=keyword)
            | Q(project_no__icontains=keyword)
            | Q(data__sourcePlatform__icontains=keyword)
            | Q(data__serviceProductName__icontains=keyword)
            | Q(data__platformOrderNo__icontains=keyword)
            | Q(data__contractFileName__icontains=keyword)
            | Q(data__contractStatus__icontains=keyword)
            | Q(status__icontains=keyword)
        )
        purchase_qs = purchase_qs.filter(
            Q(order_no__icontains=keyword)
            | Q(data__contractFileName__icontains=keyword)
            | Q(data__contractStatus__icontains=keyword)
            | Q(status__icontains=keyword)
            | Q(project_id__in=projects_qs.values_list("id", flat=True))
        )

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


def _find_portal_contract(org_id: str, contract_id: str) -> dict | None:
    contract_id = str(contract_id or "").strip()
    if contract_id.startswith("project:"):
        source_id = contract_id.split(":", 1)[1]
        record = ProjectRecord.objects.filter(id=source_id, is_deleted=False, customer_org_id=org_id).first()
        if not record:
            return None
        payload = record.data if isinstance(record.data, dict) else {}
        return {
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
            "updatedAt": _contract_sort_key(payload),
        }
    if contract_id.startswith("purchaseOrder:"):
        source_id = contract_id.split(":", 1)[1]
        record = PurchaseOrderRecord.objects.filter(id=source_id, is_deleted=False).first()
        if not record:
            return None
        project = ProjectRecord.objects.filter(id=record.project_id, is_deleted=False).first()
        if not project or str(project.customer_org_id or "") != org_id:
            return None
        payload = record.data if isinstance(record.data, dict) else {}
        if not _has_contract_file(payload):
            return None
        return {
            "id": f"purchaseOrder:{record.id}",
            "kind": "采购合同",
            "source": "purchaseOrder",
            "sourceId": record.id,
            "projectId": record.project_id,
            "projectName": project.name,
            "projectNo": project.project_no,
            "projectType": project.type,
            "customerOrgId": project.customer_org_id,
            "counterpartyOrgId": record.supplier_org_id,
            "ownCompanyOrgId": payload.get("ownCompanyOrgId") or project.own_company_org_id or "",
            "orderNo": record.order_no,
            "contractStatus": payload.get("contractStatus") or "待签",
            "contractFileId": payload.get("contractFileId") or "",
            "contractFileName": payload.get("contractFileName") or "",
            "createdAt": payload.get("createdAt") or "",
            "updatedAt": _contract_sort_key(payload),
        }
    return None


def _file_response(request, file_id: str):
    from django.core.exceptions import SuspiciousFileOperation

    from .views import _missing_document_response, _open_managed_file

    record = ManagedFile.objects.filter(id=file_id).first()
    if not record:
        return _missing_document_response(request)
    try:
        file_handle = _open_managed_file(record)
    except (FileNotFoundError, SuspiciousFileOperation, OSError):
        return _missing_document_response(request, record.document_type)
    response = FileResponse(file_handle, content_type=record.content_type or "application/octet-stream")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(record.original_name)}"
    response["X-Original-Filename"] = record.original_name
    return response


@require_http_methods(["GET"])
def portal_orders(request):
    record, error = require_portal(request, "portal.order.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    search = (request.GET.get("search") or "").strip()
    sales = SalesOrderRecord.objects.filter(is_deleted=False, customer_org_id=org_id)
    services = ServiceOrderRecord.objects.filter(is_deleted=False, customer_org_id=org_id)
    if search:
        sales = sales.filter(Q(order_no__icontains=search) | Q(status__icontains=search) | Q(data__platform__icontains=search))
        services = services.filter(Q(order_no__icontains=search) | Q(status__icontains=search) | Q(data__platform__icontains=search))

    page, page_size = _page_params(request)
    sales_keys = sales.annotate(_kind=Value("销售订单", output_field=CharField())).values_list("id", "created_at", "_kind")
    service_keys = services.annotate(_kind=Value("服务订单", output_field=CharField())).values_list("id", "created_at", "_kind")
    # union 在部分后端对 count 不友好；本企业订单量通常可控，合并轻量键后再切片。
    def _sort_created(value):
        if value is None:
            return datetime.min
        if timezone.is_aware(value):
            return timezone.make_naive(value, timezone.utc)
        return value

    merged = sorted(
        list(sales_keys) + list(service_keys),
        key=lambda row: (_sort_created(row[1]), row[0] or ""),
        reverse=True,
    )
    total = len(merged)
    start = (page - 1) * page_size
    page_keys = merged[start : start + page_size]

    sales_ids = [row[0] for row in page_keys if row[2] == "销售订单"]
    service_ids = [row[0] for row in page_keys if row[2] == "服务订单"]
    sales_map = {
        item.id: item
        for item in SalesOrderRecord.objects.filter(id__in=sales_ids, is_deleted=False)
    }
    service_map = {
        item.id: item
        for item in ServiceOrderRecord.objects.filter(id__in=service_ids, is_deleted=False)
    }
    project_ids = {
        *(item.project_id for item in sales_map.values() if item.project_id),
        *(item.project_id for item in service_map.values() if item.project_id),
    }
    project_names = _project_name_map(project_ids)
    items = []
    for order_id, _created, kind in page_keys:
        if kind == "销售订单":
            order = sales_map.get(order_id)
            if order:
                items.append(_order_public(order, "销售订单", project_names=project_names))
        else:
            order = service_map.get(order_id)
            if order:
                items.append(_order_public(order, "服务订单", project_names=project_names))
    return JsonResponse({"items": items, "total": total, "page": page, "page_size": page_size})


@require_http_methods(["GET"])
def portal_order_detail(request, order_id: str):
    record, error = require_portal(request, "portal.order.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    sales = SalesOrderRecord.objects.filter(id=order_id, is_deleted=False, customer_org_id=org_id).first()
    if sales:
        return JsonResponse({"data": _order_public(sales, "销售订单", detail=True)})
    service = ServiceOrderRecord.objects.filter(id=order_id, is_deleted=False, customer_org_id=org_id).first()
    if service:
        return JsonResponse({"data": _order_public(service, "服务订单", detail=True)})
    return JsonResponse({"detail": "订单不存在或无权查看。"}, status=404)


@require_http_methods(["GET"])
def portal_invoices(request):
    record, error = require_portal(request, "portal.invoice.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    search = (request.GET.get("search") or "").strip()
    qs = _invoice_for_customer_org(org_id)
    if search:
        qs = qs.filter(
            Q(invoice_no__icontains=search)
            | Q(status__icontains=search)
            | Q(data__buyerName__icontains=search)
            | Q(data__sellerName__icontains=search)
        )
    page, page_size = _page_params(request)
    total = qs.count()
    start = (page - 1) * page_size
    items = [_invoice_public(item) for item in qs[start : start + page_size]]
    return JsonResponse({"items": items, "total": total, "page": page, "page_size": page_size})


@require_http_methods(["GET"])
def portal_invoice_detail(request, invoice_id: str):
    record, error = require_portal(request, "portal.invoice.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    invoice = _invoice_for_customer_org(org_id).filter(id=invoice_id).first()
    if not invoice:
        return JsonResponse({"detail": "发票不存在或无权查看。"}, status=404)
    return JsonResponse({"data": _invoice_public(invoice)})


@require_http_methods(["GET"])
def portal_invoice_file(request, invoice_id: str):
    record, error = require_portal(request, "portal.invoice.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    invoice = _invoice_for_customer_org(org_id).filter(id=invoice_id).first()
    if not invoice:
        return JsonResponse({"detail": "发票不存在或无权查看。"}, status=404)
    file_id = str((invoice.data or {}).get("fileId") or "").strip()
    if not file_id:
        return JsonResponse({"detail": "该发票没有附件。"}, status=404)
    return _file_response(request, file_id)


@require_http_methods(["GET"])
def portal_contracts(request):
    record, error = require_portal(request, "portal.contract.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    search = (request.GET.get("search") or "").strip()
    rows = [
        _apply_portal_datetimes(
            dict(row),
            ("createdAt", "updatedAt", "contractUpdatedAt", "signedAt"),
            seconds=False,
        )
        for row in _portal_contract_rows_for_org(org_id, search)
    ]
    return _paged(rows, request)


@require_http_methods(["GET"])
def portal_contract_detail(request, contract_id: str):
    record, error = require_portal(request, "portal.contract.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    row = _find_portal_contract(org_id, contract_id)
    if not row:
        return JsonResponse({"detail": "合同不存在或无权查看。"}, status=404)
    data = _apply_portal_datetimes(
        dict(row),
        ("createdAt", "updatedAt", "contractUpdatedAt", "signedAt"),
        seconds=False,
    )
    return JsonResponse({"data": data})


@require_http_methods(["GET"])
def portal_contract_file(request, contract_id: str):
    record, error = require_portal(request, "portal.contract.view")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    row = _find_portal_contract(org_id, contract_id)
    if not row:
        return JsonResponse({"detail": "合同不存在或无权查看。"}, status=404)
    file_id = str(row.get("contractFileId") or "").strip()
    if not file_id:
        return JsonResponse({"detail": "该合同没有附件。"}, status=404)
    return _file_response(request, file_id)


def _account_belongs_to_org(account: CustomerAccountRecord, org_id: str) -> bool:
    return _portal_org_id(account) == org_id


@csrf_exempt
@require_http_methods(["GET", "POST"])
def portal_accounts(request):
    if request.method == "GET":
        record, error = require_portal(request, "portal.account.view")
        if error:
            return error
        org_id, org_error = _require_org(record)
        if org_error:
            return org_error
        search = (request.GET.get("search") or "").strip()
        qs = CustomerAccountRecord.objects.filter(is_deleted=False, customer_org_id=org_id)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(phone__icontains=search) | Q(customer_name__icontains=search))
        page, page_size = _page_params(request)
        total = qs.count()
        start = (page - 1) * page_size
        items = [public_account(item) for item in qs.order_by("-created_at", "-id")[start : start + page_size]]
        return JsonResponse({"items": items, "total": total, "page": page, "page_size": page_size})

    record, error = require_portal(request, "portal.account.manage")
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    payload, read_error = _read_json(request)
    if read_error:
        return read_error
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    password = str(payload.get("password") or "")
    if not name or not phone:
        return JsonResponse({"detail": "请填写账号名称和手机号。"}, status=400)
    if not password:
        return JsonResponse({"detail": "请设置登录密码。"}, status=400)
    if CustomerAccountRecord.objects.filter(is_deleted=False, phone=phone).exists():
        return JsonResponse({"detail": "该手机号已有客户账号。"}, status=400)
    account_payload = {
        "id": str(payload.get("id") or f"portal-user-{uuid.uuid4().hex[:12]}"),
        "name": name,
        "phone": phone,
        "password": make_password(password),
        "customerOrgId": org_id,
        "customerName": str(record.customer_name or (record.data or {}).get("customerName") or "").strip(),
        "status": (str(payload.get("status") or "启用").strip() or "启用"),
        "permissions": normalize_portal_permissions(payload.get("permissions") or ["portal.notice.view"]),
        "subscription": {"enabled": False, "keywords": ""},
        "createdAt": timezone.now().isoformat(),
    }
    if "allowedSiteIds" in payload:
        account_payload["allowedSiteIds"] = payload.get("allowedSiteIds")
    defaults = account_defaults(account_payload)
    created = CustomerAccountRecord.objects.create(
        id=account_payload["id"],
        **defaults,
        is_deleted=False,
        deleted_at=None,
        deleted_by="",
        created_at=timezone.now(),
    )
    return JsonResponse({"data": public_account(created)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def portal_account_detail(request, account_id: str):
    record, error = require_portal(request)
    if error:
        return error
    org_id, org_error = _require_org(record)
    if org_error:
        return org_error
    target = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not target or not _account_belongs_to_org(target, org_id):
        return JsonResponse({"detail": "账号不存在或无权操作（禁止跨企业）。"}, status=404)

    if request.method == "GET":
        _, view_error = require_portal(request, "portal.account.view")
        if view_error:
            return view_error
        return JsonResponse({"data": public_account(target)})

    _, manage_error = require_portal(request, "portal.account.manage")
    if manage_error:
        return manage_error

    if request.method == "DELETE":
        if target.id == record.id:
            return JsonResponse({"detail": "不能删除当前登录账号。"}, status=400)
        target.is_deleted = True
        target.deleted_at = timezone.now()
        target.deleted_by = record.name or record.id
        target.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
        return JsonResponse({"data": None})

    payload, read_error = _read_json(request)
    if read_error:
        return read_error
    data = dict(target.data or {})
    if "name" in payload:
        data["name"] = str(payload.get("name") or "").strip()
    if "phone" in payload:
        phone = str(payload.get("phone") or "").strip()
        if not phone:
            return JsonResponse({"detail": "手机号不能为空。"}, status=400)
        if CustomerAccountRecord.objects.filter(is_deleted=False, phone=phone).exclude(id=target.id).exists():
            return JsonResponse({"detail": "该手机号已有客户账号。"}, status=400)
        data["phone"] = phone
    if payload.get("password"):
        data["password"] = make_password(str(payload.get("password")))
    if "status" in payload:
        data["status"] = str(payload.get("status") or "启用").strip() or "启用"
    if "permissions" in payload:
        data["permissions"] = normalize_portal_permissions(payload.get("permissions"))
    if "allowedSiteIds" in payload:
        raw = payload.get("allowedSiteIds")
        if raw is None:
            data.pop("allowedSiteIds", None)
        else:
            data["allowedSiteIds"] = raw
    # 强制锁定本企业，禁止改绑跨企业。
    data["customerOrgId"] = org_id
    data["customerName"] = str(record.customer_name or (record.data or {}).get("customerName") or data.get("customerName") or "").strip()
    data["id"] = target.id
    defaults = account_defaults(data)
    for field, value in defaults.items():
        setattr(target, field, value)
    target.save()
    return JsonResponse({"data": public_account(target)})
