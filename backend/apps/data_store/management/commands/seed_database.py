import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.data_store.models import AppState
from apps.data_store.nav_defaults import DEFAULT_NAV_CATEGORIES, DEFAULT_NAV_GROUPS, DEFAULT_NAV_ITEMS
from apps.data_store.views import COLLECTIONS, DEFAULT_KEY, save_app_data


APP_COLLECTIONS = [
    "users",
    "roles",
    "organizations",
    "products",
    "supplierPrices",
    "projects",
    "projectItems",
    "salesOrders",
    "purchaseOrders",
    "serviceOrders",
    "onboardingRecords",
    "platformAccounts",
    "websiteLeads",
    "projectReminders",
    "projectMemos",
    "optionGroups",
    "invoices",
    "transactions",
    "operationLogs",
    "ocrJobs",
    "trademarkCertificates",
    "notices",
    "noticeCollectionSources",
    "noticeCollectionRuns",
    "libraryContacts",
    "smsTemplates",
    "smsRecords",
    "customerAccounts",
    "navCategories",
    "navGroups",
    "navMenuItems",
]

ALL_PERMISSIONS = [
    "dashboard.view",
    "project.view",
    "project.create",
    "project.edit",
    "entity.view",
    "entity.create",
    "product.view",
    "product.manage",
    "purchase.manage",
    "serviceOrder.view",
    "serviceOrder.manage",
    "salesOrder.view",
    "salesOrder.manage",
    "purchaseOrder.view",
    "purchaseOrder.manage",
    "finance.view",
    "finance.manage",
    "invoice.manage",
    "onboarding.manage",
    "platformAccount.view",
    "platformAccount.manage",
    "trademarkCertificate.view",
    "trademarkCertificate.manage",
    "notice.view",
    "notice.manage",
    "notice.stats.view",
    "notice.tag.view",
    "notice.tag.manage",
    "notice.orgType.view",
    "notice.orgType.manage",
    "notice.nature.view",
    "notice.nature.manage",
    "site.view",
    "site.manage",
    "library.view",
    "library.manage",
    "sms.view",
    "sms.manage",
    "customerAccount.view",
    "customerAccount.manage",
    "menu.view",
    "menu.manage",
    "lead.manage",
    "sensitive.view",
    "profit.view",
    "dev.ops.view",
    "dev.ops.manage",
    "user.manage",
]

OPTION_GROUP_DEFINITIONS = [
    {"key": "platform", "name": "平台名称", "description": "采购平台、入驻平台和官网留言来源平台。", "usages": ["项目创建：来源平台", "服务项目创建：入驻平台", "平台账号：平台筛选/新增", "官网留言：平台", "导入平台账号：平台识别"], "values": ["泉E采", "青慧采", "齐鲁云采", "政采云", "公采云", "国铁", "美云销", "渠道", "直客", "其他"]},
    {"key": "project_status", "name": "项目状态", "description": "商品项目和服务项目的主流程状态。", "usages": ["项目详情：项目状态", "总览：项目数量统计"], "values": ["已付款待办理", "待签/待收款", "待采购/平台操作", "履约中", "待开票/待结算", "已完成", "异常"]},
    {"key": "sales_order_status", "name": "销售订单状态", "usages": ["项目详情：销售订单状态双击编辑", "订单列表：销售订单状态"], "values": ["待付款", "部分付款", "已付款", "退款", "取消"]},
    {"key": "purchase_order_status", "name": "采购订单状态", "usages": ["项目详情：采购订单状态双击编辑"], "values": ["草稿", "待下单", "已下单", "部分到货", "已完成", "已取消"]},
    {"key": "invoice_status", "name": "发票状态", "usages": ["发票列表：状态双击编辑", "添加发票：状态", "发票详情：状态"], "values": ["草稿", "待确认", "已确认", "作废"]},
    {"key": "reminder_work_content", "name": "跟进提醒工作内容", "usages": ["总览：创建跟进提醒", "项目详情：创建跟进提醒", "跟进提醒列表：创建跟进提醒"], "values": ["绑定账期", "产品上架", "产品审核", "服务类入池", "产品类入池", "加分类", "加品牌", "服务类上架", "开发票", "做合同"]},
    {"key": "entity_type", "name": "实体类型", "usages": ["实体管理：新增实体", "营业执照 OCR 回填"], "values": ["企业", "个体户", "政府", "事业单位", "学校", "医院", "其他"]},
    {"key": "organization_role", "name": "业务身份", "usages": ["企业/单位基础信息库：身份标签", "项目创建：企业/单位来源"], "values": ["平台入驻商", "中间销售商", "上游供应商", "使用单位", "终端采购人", "自有主体"]},
    {"key": "taxpayer_type", "name": "纳税人类型", "usages": ["企业/单位基础信息库：纳税人类型"], "values": ["一般纳税人", "小规模纳税人", "非企业单位"]},
    {"key": "website_lead_status", "name": "官网留言状态", "usages": ["官网留言：状态筛选", "官网留言：状态处理"], "values": ["未跟进", "已跟进", "已成交", "放弃"]},
    {"key": "service_project_status", "name": "服务项目状态", "usages": ["服务项目列表：服务状态", "服务项目详情：服务状态"], "values": ["入驻中", "服务中", "服务交付完成", "服务到期结束", "项目终止"]},
    {"key": "contract_status", "name": "合同签约状态", "usages": ["商品项目详情：合同签约状态", "服务项目详情：合同签约状态"], "values": ["无需", "待签", "已签"]},
    {"key": "service_type", "name": "服务类型", "usages": ["创建服务项目：服务类型", "服务项目列表：服务类型"], "values": ["周期", "按次"]},
    {"key": "service_period_unit", "name": "服务周期单位", "usages": ["创建服务项目：周期单位"], "values": ["年", "月"]},
    {"key": "service_period_year", "name": "年周期选项", "usages": ["创建服务项目：按年周期"], "values": ["1年", "2年", "3年"]},
    {"key": "service_period_month", "name": "月周期选项", "usages": ["创建服务项目：按月周期"], "values": ["1个月", "2个月", "3个月", "4个月", "5个月", "6个月"]},
    {"key": "service_gift_months", "name": "赠送月数", "usages": ["创建服务项目：赠送月数"], "values": ["0个月", "1个月", "2个月", "3个月"]},
    {"key": "service_order_status", "name": "服务订单状态", "usages": ["服务项目详情：服务订单状态"], "values": ["待付款", "部分付款", "已付款", "退款", "取消"]},
    {"key": "payment_method", "name": "收款方式", "usages": ["服务订单：收款方式", "交易流水：收款方式"], "values": ["微信", "支付宝", "银行转账", "现金", "其他"]},
    {"key": "collection_account", "name": "收款账号", "usages": ["系统设置：收款账号管理", "订单收款：收款账号"], "values": []},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_app_data() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in APP_COLLECTIONS}


def default_seed() -> dict[str, Any]:
    now = now_iso()
    admin_name = os.getenv("INITIAL_ADMIN_NAME", "管理员").strip() or "管理员"
    admin_phone = os.getenv("INITIAL_ADMIN_PHONE", "admin").strip() or "admin"
    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "123456")
    access_seed_raw = os.getenv("INITIAL_ACCESS_SEED_JSON", "").strip()
    data = empty_app_data()
    if access_seed_raw:
        access_seed = json.loads(access_seed_raw)
        roles = access_seed.get("roles")
        users = access_seed.get("users")
        if not isinstance(roles, list) or not roles or not isinstance(users, list) or not users:
            raise CommandError("INITIAL_ACCESS_SEED_JSON must contain non-empty roles and users arrays.")
        data["roles"] = roles
        data["users"] = users
    else:
        data["roles"] = [
            {
                "id": "role-production-admin",
                "name": "生产管理员",
                "description": "系统初始全局管理员角色",
                "permissions": ALL_PERMISSIONS,
            }
        ]
        data["users"] = [
            {
                "id": "user-initial-admin",
                "name": admin_name,
                "phone": admin_phone,
                "password": make_password(admin_password),
                "roleIds": ["role-production-admin"],
                "status": "启用",
                "createdAt": now,
            }
        ]
    data["optionGroups"] = [
        {
            "id": f"optgrp-{group['key']}",
            "key": group["key"],
            "name": group["name"],
            "description": group.get("description"),
            "usages": group["usages"],
            "items": [
                {
                    "id": f"opt-{group['key']}-{index}",
                    "label": value,
                    "value": value,
                    "enabled": True,
                    "sortOrder": index,
                }
                for index, value in enumerate(group["values"], start=1)
            ],
        }
        for group in OPTION_GROUP_DEFINITIONS
    ]
    data["navCategories"] = [dict(item) for item in DEFAULT_NAV_CATEGORIES]
    data["navGroups"] = [dict(item) for item in DEFAULT_NAV_GROUPS]
    data["navMenuItems"] = [dict(item) for item in DEFAULT_NAV_ITEMS]
    return data


def as_float(value: Any) -> float:
    if value in (None, ""):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def role_label(value: str) -> str:
    return {
        "customer": "客户",
        "supplier": "供应商",
        "usage_unit": "使用单位",
        "own_company": "本方主体",
    }.get(value, value or "客户")


def coerce_app_data(raw: dict[str, Any]) -> dict[str, Any]:
    if any(key in raw for key in APP_COLLECTIONS):
        data = empty_app_data()
        for key in APP_COLLECTIONS:
            value = raw.get(key, [])
            data[key] = value if isinstance(value, list) else []
        return data

    if {"channel_prices", "orders", "platform_accounts"} & set(raw.keys()):
        return convert_legacy_import(raw)

    raise CommandError("Seed JSON is neither AppData nor scripts/import_init_data.py output.")


def convert_legacy_import(raw: dict[str, Any]) -> dict[str, Any]:
    now = now_iso()
    data = default_seed()

    data["organizations"] = [
        {
            "id": item.get("id"),
            "name": item.get("name", ""),
            "entityType": "企业",
            "roles": [role_label(role) for role in item.get("roles", [])] or ["客户"],
            "phone": item.get("phone") or item.get("contact"),
            "address": item.get("address"),
            "invoiceInfo": item.get("invoice_info"),
            "bankInfo": item.get("payment_account"),
            "status": "正常",
            "createdAt": now,
            "raw": item,
        }
        for item in raw.get("organizations", [])
        if item.get("id")
    ]

    data["products"] = [
        {
            "id": item.get("id"),
            "code": item.get("id", ""),
            "name": item.get("name", ""),
            "kind": "实体商品" if item.get("kind") != "service" else "虚拟服务",
            "category": item.get("category", ""),
            "capacity": item.get("model", ""),
            "quotePrice": 0,
            "costPrice": 0,
            "raw": item,
        }
        for item in raw.get("products", [])
        if item.get("id")
    ]

    data["supplierPrices"] = [
        {
            "id": f"sp-{index + 1}",
            "productId": item.get("product_id", ""),
            "supplierOrgId": item.get("supplier_org_id", ""),
            "purchasePrice": as_float(item.get("purchase_price")),
            "effectiveDate": item.get("effective_date") or now[:10],
            "note": item.get("sale_price"),
            "raw": item,
        }
        for index, item in enumerate(raw.get("channel_prices", []))
        if item.get("product_id")
    ]

    data["projects"] = [
        {
            "id": item.get("id"),
            "projectNo": item.get("id", ""),
            "name": item.get("platform_order_no") or item.get("id", ""),
            "type": "商品项目",
            "customerOrgId": item.get("customer_org_id", ""),
            "usageUnitOrgId": item.get("usage_unit_org_id") or None,
            "sourcePlatform": item.get("platform") or None,
            "platformOrderNo": item.get("platform_order_no") or None,
            "owner": "",
            "status": item.get("status") or "待采购/平台操作",
            "contractStatus": item.get("contract_status") or "无需",
            "paymentStatus": "未收",
            "purchaseStatus": "待采购",
            "invoiceStatus": item.get("invoice_status") or "未开",
            "totalAmount": as_float(item.get("amount")),
            "totalCost": 0,
            "createdAt": now,
            "updatedAt": now,
            "raw": item,
        }
        for item in raw.get("projects", [])
        if item.get("id")
    ]

    for index, item in enumerate(raw.get("orders", []), start=1):
        order_type = item.get("order_type")
        if order_type == "sales":
            data["salesOrders"].append(
                {
                    "id": f"so-{index}",
                    "projectId": item.get("project_id", ""),
                    "orderNo": item.get("platform_order_no") or f"SO-{index}",
                    "platform": item.get("platform") or None,
                    "platformOrderNo": item.get("platform_order_no") or None,
                    "customerOrgId": "",
                    "amount": as_float(item.get("amount")),
                    "receivableAmount": as_float(item.get("amount")),
                    "receivedAmount": 0,
                    "status": "待付款",
                    "createdAt": now,
                    "updatedAt": now,
                    "raw": item,
                }
            )
        elif order_type == "purchase":
            data["purchaseOrders"].append(
                {
                    "id": item.get("id") or f"po-{index}",
                    "projectId": item.get("project_id", ""),
                    "orderNo": item.get("id") or f"PO-{index}",
                    "supplierOrgId": item.get("supplier_org_id", ""),
                    "amount": as_float(item.get("amount")),
                    "status": "待下单",
                    "createdAt": now,
                    "updatedAt": now,
                    "raw": item,
                }
            )

    data["platformAccounts"] = [
        {
            "id": item.get("id"),
            "customerOrgId": item.get("customer_org_id", ""),
            "platform": item.get("platform") or "其他",
            "accountName": item.get("account"),
            "accountPasswordMasked": item.get("password"),
            "supplierAccount": item.get("supplier_account"),
            "supplierPasswordMasked": item.get("supplier_password"),
            "cloudAccount": item.get("cloud_account"),
            "cloudPasswordMasked": item.get("cloud_password"),
            "domain": item.get("domain"),
            "icpRecordNo": item.get("icp"),
            "licenseDisplayStatus": "未处理",
            "publicSecurityStatus": "未处理",
            "backendTemplateStatus": "未录入",
            "caStatus": item.get("ca_status") or "未办理",
            "currentStatus": item.get("status") or "",
            "raw": item,
        }
        for item in raw.get("platform_accounts", [])
        if item.get("id")
    ]

    return data


def has_business_rows() -> bool:
    return any(model.objects.exists() for model in COLLECTIONS.values())


class Command(BaseCommand):
    help = "Seed PostgreSQL business tables from default data, AppState, or import JSON."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, help="Path to AppData JSON or scripts/import_init_data.py JSON output.")
        parser.add_argument("--from-app-state", action="store_true", help="Load the legacy app_state.default JSON snapshot.")
        parser.add_argument("--force", action="store_true", help="Replace existing business rows.")

    @transaction.atomic
    def handle(self, *args, **options):
        if has_business_rows() and not options["force"]:
            raise CommandError("Business tables already contain data. Re-run with --force to replace them.")

        if options["file"]:
            raw = json.loads(options["file"].read_text(encoding="utf-8-sig"))
            data = coerce_app_data(raw)
            source = str(options["file"])
        elif options["from_app_state"]:
            state = AppState.objects.filter(key=DEFAULT_KEY).first()
            if not state:
                raise CommandError("No app_state.default row exists.")
            data = coerce_app_data(state.data)
            source = "app_state.default"
        else:
            data = default_seed()
            source = "built-in default seed"

        save_app_data(data)
        counts = {key: len(data.get(key, [])) for key in APP_COLLECTIONS}
        self.stdout.write(self.style.SUCCESS(f"Seeded database from {source}."))
        self.stdout.write(json.dumps(counts, ensure_ascii=False, indent=2))
