from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .models import (
    OptionGroupRecord,
    OrganizationRecord,
    ProjectRecord,
    PurchaseOrderRecord,
    SalesOrderRecord,
    ServiceOrderRecord,
    TransactionRecord,
    UserRecord,
)

UNASSIGNED_NAME = "未归属"
KIND_ALIASES = {
    "service": "服务",
    "product": "商品",
    "purchase": "采购",
    "服务": "服务",
    "商品": "商品",
    "采购": "采购",
}
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _payload(record) -> dict:
    data = dict(record.data) if isinstance(record.data, dict) else {}
    data.setdefault("id", record.id)
    return data


def _money(value) -> float:
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def _date_part(value: str) -> str:
    match = DATE_PREFIX.match((value or "").strip())
    return match.group(1) if match else ""


def _occurred_raw(payload: dict, record: TransactionRecord) -> str:
    return str(payload.get("occurredAt") or payload.get("date") or record.date or payload.get("createdAt") or "")


def _org_name(orgs: dict[str, str], org_id: str | None) -> str:
    if not org_id:
        return ""
    return (orgs.get(org_id) or "").strip()


def _find_collection_account(account: str, items: list[dict], orgs: dict[str, str]) -> dict | None:
    if not account:
        return None
    by_id = next((item for item in items if item.get("id") == account), None)
    if by_id:
        return by_id
    by_number = [
        item
        for item in items
        if item.get("accountNumber")
        and (account == item.get("accountNumber") or str(item.get("accountNumber")) in account)
    ]
    if len(by_number) <= 1:
        return by_number[0] if by_number else None
    for item in by_number:
        company = _org_name(orgs, item.get("ownCompanyOrgId") or "")
        if company and company in account:
            return item
    return by_number[0]


def _account_fields(account: str, items: list[dict], orgs: dict[str, str]) -> tuple[str, str, str, str]:
    if not account:
        return "未录入", "", "", ""
    option = _find_collection_account(account, items, orgs)
    if not option:
        return account, "", account, ""
    company_id = str(option.get("ownCompanyOrgId") or "")
    company = _org_name(orgs, company_id) or "未设置主体"
    bank = str(option.get("bankName") or "未设置银行")
    number = str(option.get("accountNumber") or account)
    return "\n".join([company, bank, number]), bank, number, company_id


def _business_kind(payload: dict, project: ProjectRecord | None) -> str:
    if payload.get("purchaseOrderId"):
        return "采购"
    if (project and project.type == "服务项目") or payload.get("serviceOrderId"):
        return "服务"
    if (project and project.type == "商品项目") or payload.get("salesOrderId"):
        return "商品"
    return UNASSIGNED_NAME


def _salesperson(payload: dict, service: dict | None, project: ProjectRecord | None, users: dict[str, str]) -> tuple[str, str]:
    if service:
        user_id = str(service.get("salesUserId") or "")
        name = (users.get(user_id) or service.get("salesName") or "").strip()
        if name:
            return name, user_id or f"name:{name}"
    project_data = _payload(project) if project else {}
    if project and project.type == "服务项目":
        user_id = str(project_data.get("serviceSalesUserId") or "")
        name = (users.get(user_id) or project_data.get("serviceSalesName") or "").strip()
        if name:
            return name, user_id or f"name:{name}"
    if project and project.type == "商品项目":
        name = str(project_data.get("owner") or "").strip()
        if name:
            return name, f"name:{name}"
    return UNASSIGNED_NAME, ""


def _records_by_id(model, ids: set[str]) -> dict:
    if not ids:
        return {}
    return {record.id: record for record in model.objects.filter(is_deleted=False, id__in=ids)}


def _collection_account_items() -> list[dict]:
    group = OptionGroupRecord.objects.filter(is_deleted=False, key="collection_account").first()
    if not group or not isinstance(group.data, dict):
        return []
    items = group.data.get("items") or []
    return [item for item in items if isinstance(item, dict)]


def _live_business_ids() -> dict[str, set[str]]:
    return {
        "projects": set(ProjectRecord.objects.filter(is_deleted=False).values_list("id", flat=True)),
        "salesOrders": set(SalesOrderRecord.objects.filter(is_deleted=False).values_list("id", flat=True)),
        "serviceOrders": set(ServiceOrderRecord.objects.filter(is_deleted=False).values_list("id", flat=True)),
        "purchaseOrders": set(PurchaseOrderRecord.objects.filter(is_deleted=False).values_list("id", flat=True)),
    }


def transaction_has_live_link(record: TransactionRecord, live: dict[str, set[str]] | None = None) -> bool:
    live = live or _live_business_ids()
    payload = _payload(record)
    project_id = str(record.project_id or payload.get("projectId") or "")
    sales_id = str(payload.get("salesOrderId") or "")
    service_id = str(payload.get("serviceOrderId") or "")
    purchase_id = str(payload.get("purchaseOrderId") or "")
    if not (project_id or sales_id or service_id or purchase_id):
        return True
    return bool(
        (project_id and project_id in live["projects"])
        or (sales_id and sales_id in live["salesOrders"])
        or (service_id and service_id in live["serviceOrders"])
        or (purchase_id and purchase_id in live["purchaseOrders"])
    )


def orphaned_transaction_ids() -> set[str]:
    live = _live_business_ids()
    return {
        record.id
        for record in TransactionRecord.objects.filter(is_deleted=False).only("id", "project_id", "data")
        if not transaction_has_live_link(record, live)
    }


def build_finance_statement_rows(filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    kind_filter = KIND_ALIASES.get((filters.get("businessKind") or "").strip(), "")
    customer_org_id = (filters.get("customerOrgId") or "").strip()
    own_company_org_id = (filters.get("ownCompanyOrgId") or "").strip()
    salesperson = (filters.get("salesperson") or "").strip()
    collection_account_id = (filters.get("collectionAccountId") or "").strip()
    date_from = _date_part(str(filters.get("dateFrom") or ""))
    date_to = _date_part(str(filters.get("dateTo") or ""))

    transactions = list(TransactionRecord.objects.filter(is_deleted=False).exclude(status="作废"))
    payloads = [(record, _payload(record)) for record in transactions]
    payloads = [(record, payload) for record, payload in payloads if str(payload.get("status") or record.status) != "作废"]

    sales_ids = {str(payload.get("salesOrderId") or "") for _, payload in payloads if payload.get("salesOrderId")}
    service_ids = {str(payload.get("serviceOrderId") or "") for _, payload in payloads if payload.get("serviceOrderId")}
    purchase_ids = {str(payload.get("purchaseOrderId") or "") for _, payload in payloads if payload.get("purchaseOrderId")}
    sales_map = _records_by_id(SalesOrderRecord, sales_ids)
    service_map = _records_by_id(ServiceOrderRecord, service_ids)
    purchase_map = _records_by_id(PurchaseOrderRecord, purchase_ids)

    project_ids = {
        str(record.project_id or payload.get("projectId") or "")
        for record, payload in payloads
        if record.project_id or payload.get("projectId")
    }
    for record in (*sales_map.values(), *service_map.values(), *purchase_map.values()):
        if record.project_id:
            project_ids.add(record.project_id)
    project_map = _records_by_id(ProjectRecord, {item for item in project_ids if item})

    orgs = {
        record.id: record.name
        for record in OrganizationRecord.objects.filter(is_deleted=False)
    }
    users = {
        record.id: record.name
        for record in UserRecord.objects.filter(is_deleted=False)
    }
    account_items = _collection_account_items()

    rows: list[dict] = []
    for record, payload in payloads:
        sales = sales_map.get(str(payload.get("salesOrderId") or ""))
        service = service_map.get(str(payload.get("serviceOrderId") or ""))
        purchase = purchase_map.get(str(payload.get("purchaseOrderId") or ""))
        project_id = str(
            record.project_id
            or payload.get("projectId")
            or (sales.project_id if sales else "")
            or (service.project_id if service else "")
            or (purchase.project_id if purchase else "")
            or ""
        )
        project = project_map.get(project_id)
        if not sales and not service and not purchase and not project:
            referenced = bool(
                record.project_id
                or payload.get("projectId")
                or payload.get("salesOrderId")
                or payload.get("serviceOrderId")
                or payload.get("purchaseOrderId")
            )
            if referenced:
                continue
        sales_data = _payload(sales) if sales else {}
        service_data = _payload(service) if service else {}
        purchase_data = _payload(purchase) if purchase else {}
        project_data = _payload(project) if project else {}

        kind = _business_kind(payload, project)
        customer_id = str(
            (sales.customer_org_id if sales else "")
            or (service.customer_org_id if service else "")
            or payload.get("counterpartyOrgId")
            or (project.customer_org_id if project else "")
            or ""
        )
        customer_name = _org_name(orgs, customer_id) or UNASSIGNED_NAME
        raw_account = str(payload.get("account") or "")
        matched_account = _find_collection_account(raw_account, account_items, orgs)
        account_text, bank_name, account_number, account_company_id = _account_fields(
            raw_account,
            account_items,
            orgs,
        )
        company_id = str(
            sales_data.get("ownCompanyOrgId")
            or purchase_data.get("ownCompanyOrgId")
            or (project.own_company_org_id if project else "")
            or project_data.get("ownCompanyOrgId")
            or account_company_id
            or ""
        )
        company_name = _org_name(orgs, company_id) or UNASSIGNED_NAME
        salesperson_name, salesperson_id = _salesperson(payload, service_data or None, project, users)
        occurred_at = _occurred_raw(payload, record)
        occurred_date = _date_part(occurred_at)
        service_customer_kind = ""
        if kind == "服务":
            raw_kind = str(project_data.get("serviceCustomerKind") or "").strip()
            if raw_kind in {"首次服务", "续费客户"}:
                service_customer_kind = raw_kind

        if kind_filter and kind != kind_filter:
            continue
        if customer_org_id and customer_id != customer_org_id:
            continue
        if own_company_org_id and company_id != own_company_org_id:
            continue
        if salesperson:
            if salesperson_id != salesperson and salesperson_name != salesperson:
                continue
        if collection_account_id:
            option = next((item for item in account_items if item.get("id") == collection_account_id), None)
            option_number = str((option or {}).get("accountNumber") or "")
            matched_id = str((matched_account or {}).get("id") or "")
            if matched_id != collection_account_id and raw_account != collection_account_id:
                if not option_number or (
                    raw_account != option_number and option_number not in raw_account
                ):
                    continue
        if date_from and (not occurred_date or occurred_date < date_from):
            continue
        if date_to and (not occurred_date or occurred_date > date_to):
            continue

        rows.append(
            {
                "id": record.id,
                "businessKind": kind,
                "customerOrgId": customer_id,
                "customerName": customer_name,
                "ownCompanyOrgId": company_id,
                "companyName": company_name,
                "accountText": account_text,
                "bankName": bank_name,
                "accountNumber": account_number,
                "salesperson": salesperson_name,
                "salespersonId": salesperson_id,
                "amount": _money(payload.get("amount", record.amount)),
                "occurredAt": occurred_at,
                "txType": record.type or payload.get("type") or "",
                "serviceCustomerKind": service_customer_kind,
                "_sortAt": occurred_at,
            }
        )

    rows.sort(key=lambda item: (item.get("_sortAt") or "", item.get("id") or ""), reverse=True)
    for item in rows:
        item.pop("_sortAt", None)
    return rows
