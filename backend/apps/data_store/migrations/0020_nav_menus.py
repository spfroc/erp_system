from django.db import migrations, models

VIEW = "menu.view"
MANAGE = "menu.manage"

# Keep seed helpers local so later nav_defaults changes (e.g. category_key) cannot break this migration.
SEED_GROUPS = [
    {"id": "nav-group-projects", "key": "projects", "label": "项目管理", "iconKey": "ClipboardList", "sortOrder": 10, "enabled": True},
    {"id": "nav-group-orders", "key": "orders", "label": "订单", "iconKey": "ShoppingCart", "sortOrder": 20, "enabled": True},
    {"id": "nav-group-customers", "key": "customers", "label": "客户管理", "iconKey": "Building2", "sortOrder": 30, "enabled": True},
    {"id": "nav-group-official", "key": "official", "label": "前端网站配置", "iconKey": "Globe", "sortOrder": 40, "enabled": True},
    {"id": "nav-group-finance", "key": "finance", "label": "财务管理", "iconKey": "WalletCards", "sortOrder": 50, "enabled": True},
    {"id": "nav-group-logs", "key": "logs", "label": "日志管理", "iconKey": "History", "sortOrder": 60, "enabled": True},
    {"id": "nav-group-system", "key": "system", "label": "系统设置", "iconKey": "Users", "sortOrder": 70, "enabled": True},
]

SEED_ITEMS = [
    {"id": "nav-item-dashboard", "viewId": "dashboard", "label": "总览", "groupKey": "", "permission": "dashboard.view", "iconKey": "Home", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-productProjects", "viewId": "productProjects", "label": "商品项目", "groupKey": "projects", "permission": "project.view", "iconKey": "ClipboardList", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-serviceProjects", "viewId": "serviceProjects", "label": "服务项目", "groupKey": "projects", "permission": "project.view", "iconKey": "ShieldCheck", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-contracts", "viewId": "contracts", "label": "合同管理", "groupKey": "projects", "permission": "project.view", "iconKey": "FileText", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-websiteLeads", "viewId": "websiteLeads", "label": "商机管理", "groupKey": "projects", "permission": "lead.manage", "iconKey": "MessageSquare", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-platformAccounts", "viewId": "platformAccounts", "label": "平台账号", "groupKey": "projects", "permission": "platformAccount.view", "iconKey": "FileScan", "sortOrder": 50, "enabled": True},
    {"id": "nav-item-reminders", "viewId": "reminders", "label": "每日任务管理", "groupKey": "projects", "permission": "dashboard.view", "iconKey": "ClipboardList", "sortOrder": 60, "enabled": True},
    {"id": "nav-item-trademarkCertificates", "viewId": "trademarkCertificates", "label": "商标管理", "groupKey": "projects", "permission": "trademarkCertificate.view", "iconKey": "Stamp", "sortOrder": 70, "enabled": True},
    {"id": "nav-item-notices", "viewId": "notices", "label": "公告管理", "groupKey": "projects", "permission": "notice.view", "iconKey": "FileText", "sortOrder": 80, "enabled": True},
    {"id": "nav-item-serviceOrders", "viewId": "serviceOrders", "label": "服务订单", "groupKey": "orders", "permission": "serviceOrder.view", "iconKey": "ShieldCheck", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-salesOrders", "viewId": "salesOrders", "label": "销售订单", "groupKey": "orders", "permission": "salesOrder.view", "iconKey": "ShoppingCart", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-purchaseOrders", "viewId": "purchaseOrders", "label": "采购订单", "groupKey": "orders", "permission": "purchaseOrder.view", "iconKey": "Truck", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-products", "viewId": "products", "label": "商品及价格体系", "groupKey": "orders", "permission": "product.view", "iconKey": "Boxes", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-entities", "viewId": "entities", "label": "客户基础信息管理", "groupKey": "customers", "permission": "entity.view", "iconKey": "Building2", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-customerAccounts", "viewId": "customerAccounts", "label": "登录账号管理", "groupKey": "customers", "permission": "customerAccount.view", "iconKey": "Users", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-libraryContacts", "viewId": "libraryContacts", "label": "政企客户资料库", "groupKey": "customers", "permission": "library.view", "iconKey": "BookUser", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-officialSites", "viewId": "officialSites", "label": "官网站点", "groupKey": "official", "permission": "site.view", "iconKey": "Globe", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-officialSeo", "viewId": "officialSeo", "label": "SEO配置", "groupKey": "official", "permission": "site.view", "iconKey": "Search", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-invoices", "viewId": "invoices", "label": "发票管理", "groupKey": "finance", "permission": "invoice.manage", "iconKey": "FileText", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-transactions", "viewId": "transactions", "label": "交易流水", "groupKey": "finance", "permission": "finance.view", "iconKey": "WalletCards", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-financeStatements", "viewId": "financeStatements", "label": "财务清单", "groupKey": "finance", "permission": "finance.view", "iconKey": "ClipboardList", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-receiptStats", "viewId": "receiptStats", "label": "收款统计", "groupKey": "finance", "permission": "finance.view", "iconKey": "BarChart3", "sortOrder": 40, "enabled": True},
    {"id": "nav-item-paymentStats", "viewId": "paymentStats", "label": "付款统计", "groupKey": "finance", "permission": "finance.view", "iconKey": "BarChart3", "sortOrder": 50, "enabled": True},
    {"id": "nav-item-sms", "viewId": "sms", "label": "短信日志", "groupKey": "logs", "permission": "sms.view", "iconKey": "MessageCircle", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-logs", "viewId": "logs", "label": "系统操作日志", "groupKey": "logs", "permission": "user.manage", "iconKey": "History", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-collectionAccounts", "viewId": "collectionAccounts", "label": "收款账号管理", "groupKey": "system", "permission": "user.manage", "iconKey": "Banknote", "sortOrder": 10, "enabled": True},
    {"id": "nav-item-optionSettings", "viewId": "optionSettings", "label": "选项管理", "groupKey": "system", "permission": "user.manage", "iconKey": "BadgeCheck", "sortOrder": 20, "enabled": True},
    {"id": "nav-item-menuSettings", "viewId": "menuSettings", "label": "菜单管理", "groupKey": "system", "permission": "menu.view", "iconKey": "LayoutList", "sortOrder": 30, "enabled": True},
    {"id": "nav-item-access", "viewId": "access", "label": "用户权限", "groupKey": "system", "permission": "user.manage", "iconKey": "Users", "sortOrder": 40, "enabled": True},
]


def _group_defaults(payload: dict) -> dict:
    data = dict(payload)
    data.setdefault("enabled", True)
    data.setdefault("sortOrder", 0)
    data.setdefault("iconKey", "")
    return {
        "data": data,
        "key": str(data.get("key") or ""),
        "label": str(data.get("label") or ""),
        "icon_key": str(data.get("iconKey") or ""),
        "sort_order": int(data.get("sortOrder") or 0),
        "enabled": bool(data.get("enabled", True)),
    }


def _item_defaults(payload: dict) -> dict:
    data = dict(payload)
    data.setdefault("enabled", True)
    data.setdefault("sortOrder", 0)
    data.setdefault("groupKey", "")
    data.setdefault("iconKey", "")
    return {
        "data": data,
        "view_id": str(data.get("viewId") or ""),
        "label": str(data.get("label") or ""),
        "group_key": str(data.get("groupKey") or ""),
        "permission": str(data.get("permission") or ""),
        "icon_key": str(data.get("iconKey") or ""),
        "sort_order": int(data.get("sortOrder") or 0),
        "enabled": bool(data.get("enabled", True)),
    }


def _grant(permissions):
    if not isinstance(permissions, list):
        return permissions, False
    if "user.manage" not in permissions:
        return permissions, False
    next_permissions = list(permissions)
    changed = False
    for key in (VIEW, MANAGE):
        if key not in next_permissions:
            next_permissions.append(key)
            changed = True
    return next_permissions, changed


def grant_and_seed(apps, schema_editor):
    RoleRecord = apps.get_model("data_store", "RoleRecord")
    AppState = apps.get_model("data_store", "AppState")
    NavGroupRecord = apps.get_model("data_store", "NavGroupRecord")
    NavMenuItemRecord = apps.get_model("data_store", "NavMenuItemRecord")

    for role in RoleRecord.objects.all():
        data = dict(role.data or {})
        permissions, changed = _grant(list(data.get("permissions") or []))
        if not changed:
            continue
        data["permissions"] = permissions
        role.data = data
        role.save(update_fields=["data"])

    for state in AppState.objects.all():
        payload = dict(state.data or {})
        roles = payload.get("roles")
        if not isinstance(roles, list):
            continue
        changed = False
        next_roles = []
        for role in roles:
            if not isinstance(role, dict):
                next_roles.append(role)
                continue
            permissions, role_changed = _grant(list(role.get("permissions") or []))
            if role_changed:
                changed = True
                next_roles.append({**role, "permissions": permissions})
            else:
                next_roles.append(role)
        if changed:
            payload["roles"] = next_roles
            state.data = payload
            state.save(update_fields=["data"])

    if not NavGroupRecord.objects.filter(is_deleted=False).exists():
        for row in SEED_GROUPS:
            defaults = _group_defaults(row)
            NavGroupRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})

    if not NavMenuItemRecord.objects.filter(is_deleted=False).exists():
        for row in SEED_ITEMS:
            defaults = _item_defaults(row)
            NavMenuItemRecord.objects.update_or_create(id=row["id"], defaults={**defaults, "is_deleted": False})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("data_store", "0019_customer_accounts")]

    operations = [
        migrations.CreateModel(
            name="NavGroupRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("key", models.CharField(db_index=True, max_length=64)),
                ("label", models.CharField(max_length=100)),
                ("icon_key", models.CharField(blank=True, max_length=64)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "nav_groups"},
        ),
        migrations.CreateModel(
            name="NavMenuItemRecord",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_by", models.CharField(blank=True, max_length=100)),
                ("view_id", models.CharField(db_index=True, max_length=64)),
                ("label", models.CharField(max_length=100)),
                ("group_key", models.CharField(blank=True, db_index=True, max_length=64)),
                ("permission", models.CharField(db_index=True, max_length=64)),
                ("icon_key", models.CharField(blank=True, max_length=64)),
                ("sort_order", models.IntegerField(db_index=True, default=0)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "nav_menu_items"},
        ),
        migrations.RunPython(grant_and_seed, noop),
    ]
