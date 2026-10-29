"""默认侧栏分类 / 分组 / 菜单项（与 frontend/src/navCatalog.ts 保持一致）。"""

DEFAULT_NAV_CATEGORIES = [
    {"id": "nav-cat-overview", "key": "overview", "label": "总览", "sortOrder": 10, "enabled": True},
    {"id": "nav-cat-business", "key": "business", "label": "业务经营", "sortOrder": 20, "enabled": True},
    {"id": "nav-cat-web", "key": "web", "label": "网站与公告", "sortOrder": 30, "enabled": True},
    {"id": "nav-cat-system", "key": "system", "label": "系统运维", "sortOrder": 40, "enabled": True},
]

DEFAULT_NAV_GROUPS = [
    {"id": "nav-group-serviceProjects", "key": "serviceProjects", "label": "服务项目管理", "categoryKey": "business", "iconKey": "ShieldCheck", "sortOrder": 10, "enabled": True},
    {"id": "nav-group-productProjects", "key": "productProjects", "label": "商品项目管理", "categoryKey": "business", "iconKey": "ClipboardList", "sortOrder": 20, "enabled": True},
    {"id": "nav-group-customers", "key": "customers", "label": "客户管理", "categoryKey": "business", "iconKey": "Building2", "sortOrder": 30, "enabled": True},
    {"id": "nav-group-finance", "key": "finance", "label": "财务管理", "categoryKey": "business", "iconKey": "WalletCards", "sortOrder": 40, "enabled": True},
    {"id": "nav-group-official", "key": "official", "label": "前端网站配置", "categoryKey": "web", "iconKey": "Globe", "sortOrder": 10, "enabled": True},
    {"id": "nav-group-notices", "key": "notices", "label": "公告管理", "categoryKey": "web", "iconKey": "Bell", "sortOrder": 20, "enabled": True},
    {"id": "nav-group-logs", "key": "logs", "label": "日志管理", "categoryKey": "system", "iconKey": "History", "sortOrder": 10, "enabled": True},
    {"id": "nav-group-system", "key": "system", "label": "系统设置", "categoryKey": "system", "iconKey": "Users", "sortOrder": 20, "enabled": True},
]

# 旧分组：重组后软删，避免侧栏残留「项目管理 / 订单」。
OBSOLETE_NAV_GROUP_IDS = ["nav-group-projects", "nav-group-orders"]

DEFAULT_NAV_ITEMS = [
    {"id": "nav-item-dashboard", "viewId": "dashboard", "label": "总览", "categoryKey": "overview", "groupKey": "", "permission": "dashboard.view", "iconKey": "Home", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-websiteLeads", "viewId": "websiteLeads", "label": "商机管理", "categoryKey": "business", "groupKey": "serviceProjects", "permission": "lead.manage", "iconKey": "MessageSquare", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-serviceProjects", "viewId": "serviceProjects", "label": "服务项目", "categoryKey": "business", "groupKey": "serviceProjects", "permission": "project.view", "iconKey": "ShieldCheck", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-serviceOrders", "viewId": "serviceOrders", "label": "服务订单", "categoryKey": "business", "groupKey": "serviceProjects", "permission": "serviceOrder.view", "iconKey": "ShieldCheck", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-platformAccounts", "viewId": "platformAccounts", "label": "平台账号", "categoryKey": "business", "groupKey": "serviceProjects", "permission": "platformAccount.view", "iconKey": "FileScan", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-reminders", "viewId": "reminders", "label": "每日任务清单", "categoryKey": "business", "groupKey": "serviceProjects", "permission": "dashboard.view", "iconKey": "ClipboardList", "sortOrder": 50, "enabled": True},
    {"id": "nav-item-trademarkCertificates", "viewId": "trademarkCertificates", "label": "商标管理", "categoryKey": "business", "groupKey": "serviceProjects", "permission": "trademarkCertificate.view", "iconKey": "Stamp", "sortOrder": 60, "enabled": True},
    {"id": "nav-item-productProjects", "viewId": "productProjects", "label": "商品项目", "categoryKey": "business", "groupKey": "productProjects", "permission": "project.view", "iconKey": "ClipboardList", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-salesOrders", "viewId": "salesOrders", "label": "销售订单", "categoryKey": "business", "groupKey": "productProjects", "permission": "salesOrder.view", "iconKey": "ShoppingCart", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-purchaseOrders", "viewId": "purchaseOrders", "label": "采购订单", "categoryKey": "business", "groupKey": "productProjects", "permission": "purchaseOrder.view", "iconKey": "Truck", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-products", "viewId": "products", "label": "商品及价格体系", "categoryKey": "business", "groupKey": "productProjects", "permission": "product.view", "iconKey": "Boxes", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-entities", "viewId": "entities", "label": "客户基础信息管理", "categoryKey": "business", "groupKey": "customers", "permission": "entity.view", "iconKey": "Building2", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-customerAccounts", "viewId": "customerAccounts", "label": "登录账号管理", "categoryKey": "business", "groupKey": "customers", "permission": "customerAccount.view", "iconKey": "Users", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-libraryContacts", "viewId": "libraryContacts", "label": "政企客户资料库", "categoryKey": "business", "groupKey": "customers", "permission": "library.view", "iconKey": "BookUser", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-mallCustomers", "viewId": "mallCustomers", "label": "资料库", "categoryKey": "business", "groupKey": "customers", "permission": "mallCustomer.view", "iconKey": "LayoutList", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-contracts", "viewId": "contracts", "label": "合同管理", "categoryKey": "business", "groupKey": "finance", "permission": "project.view", "iconKey": "FileText", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-invoices", "viewId": "invoices", "label": "发票管理", "categoryKey": "business", "groupKey": "finance", "permission": "invoice.manage", "iconKey": "FileText", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-transactions", "viewId": "transactions", "label": "交易流水", "categoryKey": "business", "groupKey": "finance", "permission": "finance.view", "iconKey": "WalletCards", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-financeStatements", "viewId": "financeStatements", "label": "财务清单", "categoryKey": "business", "groupKey": "finance", "permission": "finance.view", "iconKey": "ClipboardList", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-receiptStats", "viewId": "receiptStats", "label": "收款统计", "categoryKey": "business", "groupKey": "finance", "permission": "finance.view", "iconKey": "BarChart3", "sortOrder": 50, "enabled": True},
    {"id": "nav-item-paymentStats", "viewId": "paymentStats", "label": "付款统计", "categoryKey": "business", "groupKey": "finance", "permission": "finance.view", "iconKey": "BarChart3", "sortOrder": 60, "enabled": True},
    {"id": "nav-item-notices", "viewId": "notices", "label": "公告列表", "categoryKey": "web", "groupKey": "notices", "permission": "notice.view", "iconKey": "FileText", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-noticeStats", "viewId": "noticeStats", "label": "公告统计", "categoryKey": "web", "groupKey": "notices", "permission": "notice.stats.view", "iconKey": "BarChart3", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-noticeTags", "viewId": "noticeTags", "label": "标签修正", "categoryKey": "web", "groupKey": "notices", "permission": "notice.tag.view", "iconKey": "BadgeCheck", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-noticeDict", "viewId": "noticeDict", "label": "类型与性质", "categoryKey": "web", "groupKey": "notices", "permission": "notice.orgType.view", "iconKey": "LayoutList", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-officialSites", "viewId": "officialSites", "label": "官网站点", "categoryKey": "web", "groupKey": "official", "permission": "site.view", "iconKey": "Globe", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-officialSeo", "viewId": "officialSeo", "label": "SEO配置", "categoryKey": "web", "groupKey": "official", "permission": "site.view", "iconKey": "Search", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-sms", "viewId": "sms", "label": "短信日志", "categoryKey": "system", "groupKey": "logs", "permission": "sms.view", "iconKey": "MessageCircle", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-logs", "viewId": "logs", "label": "系统操作日志", "categoryKey": "system", "groupKey": "logs", "permission": "user.manage", "iconKey": "History", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-collectionAccounts", "viewId": "collectionAccounts", "label": "收款账号管理", "categoryKey": "system", "groupKey": "system", "permission": "user.manage", "iconKey": "Banknote", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-optionSettings", "viewId": "optionSettings", "label": "选项管理", "categoryKey": "system", "groupKey": "system", "permission": "user.manage", "iconKey": "BadgeCheck", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-devOps", "viewId": "devOps", "label": "定时任务", "categoryKey": "system", "groupKey": "system", "permission": "dev.ops.view", "iconKey": "Timer", "sortOrder": 25, "enabled": True},
    {"id": "nav-item-menuSettings", "viewId": "menuSettings", "label": "菜单管理", "categoryKey": "system", "groupKey": "system", "permission": "menu.view", "iconKey": "LayoutList", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-access", "viewId": "access", "label": "用户权限", "categoryKey": "system", "groupKey": "system", "permission": "user.manage", "iconKey": "Users", "sortOrder": 40, "enabled": True},
]


def nav_category_defaults(payload: dict) -> dict:
    data = dict(payload)
    data.setdefault("enabled", True)
    data.setdefault("sortOrder", 0)
    return {
        "data": data,
        "key": str(data.get("key") or ""),
        "label": str(data.get("label") or ""),
        "sort_order": int(data.get("sortOrder") or 0),
        "enabled": bool(data.get("enabled", True)),
    }


def nav_group_defaults(payload: dict) -> dict:
    data = dict(payload)
    data.setdefault("enabled", True)
    data.setdefault("sortOrder", 0)
    data.setdefault("iconKey", "")
    data.setdefault("categoryKey", "")
    return {
        "data": data,
        "key": str(data.get("key") or ""),
        "label": str(data.get("label") or ""),
        "category_key": str(data.get("categoryKey") or ""),
        "icon_key": str(data.get("iconKey") or ""),
        "sort_order": int(data.get("sortOrder") or 0),
        "enabled": bool(data.get("enabled", True)),
    }


def nav_menu_item_defaults(payload: dict) -> dict:
    data = dict(payload)
    data.setdefault("enabled", True)
    data.setdefault("sortOrder", 0)
    data.setdefault("groupKey", "")
    data.setdefault("categoryKey", "")
    data.setdefault("iconKey", "")
    return {
        "data": data,
        "view_id": str(data.get("viewId") or ""),
        "label": str(data.get("label") or ""),
        "category_key": str(data.get("categoryKey") or ""),
        "group_key": str(data.get("groupKey") or ""),
        "permission": str(data.get("permission") or ""),
        "icon_key": str(data.get("iconKey") or ""),
        "sort_order": int(data.get("sortOrder") or 0),
        "enabled": bool(data.get("enabled", True)),
    }
