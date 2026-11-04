"""Ensure seed catalog roles exist. Does not modify user.roleIds or overwrite existing roles."""

from django.core.management.base import BaseCommand

from apps.data_store.models import RoleRecord

DEFAULT_ROLES = [
    {
        "id": "role-admin",
        "name": "老板/管理员",
        "description": "查看全局、管理用户权限、查看利润、处理异常。",
        "permissions": [
            "dashboard.view", "project.view", "project.create", "project.edit",
            "entity.view", "entity.create", "product.view", "product.manage",
            "purchase.manage", "serviceOrder.view", "serviceOrder.manage",
            "salesOrder.view", "salesOrder.manage", "purchaseOrder.view", "purchaseOrder.manage",
            "finance.view", "finance.manage", "invoice.manage",
            "onboarding.manage", "platformAccount.view", "platformAccount.manage",
            "trademarkCertificate.view", "trademarkCertificate.manage",
            "notice.view", "notice.manage",
            "notice.stats.view", "notice.tag.view", "notice.tag.manage",
            "notice.orgType.view", "notice.orgType.manage",
            "notice.nature.view", "notice.nature.manage",
            "site.view", "site.manage",
            "library.view", "library.manage",
            "mallCustomer.view", "mallCustomer.manage",
            "sms.view", "sms.manage",
            "customerAccount.view", "customerAccount.manage",
            "portal.notice.view", "portal.notice.subscribe", "portal.stats.view",
            "portal.order.view", "portal.invoice.view", "portal.contract.view",
            "portal.account.view", "portal.account.manage",
            "menu.view", "menu.manage",
            "lead.manage", "sensitive.view", "profit.view",
            "dev.ops.view", "dev.ops.manage",
            "assistant.view", "assistant.use", "assistant.manage",
            "user.manage",
        ],
    },
    {
        "id": "role-sales",
        "name": "业务负责人",
        "description": "维护客户、项目、报价、合同和收款跟进。",
        "permissions": [
            "dashboard.view", "project.view", "project.create", "project.edit",
            "entity.view", "entity.create", "product.view", "lead.manage",
            "library.view", "library.manage", "mallCustomer.view", "mallCustomer.manage",
            "sms.view", "sms.manage", "notice.view", "notice.manage",
            "notice.stats.view", "notice.tag.view", "notice.tag.manage",
            "notice.orgType.view", "notice.orgType.manage",
            "notice.nature.view", "notice.nature.manage",
            "trademarkCertificate.view", "trademarkCertificate.manage",
            "serviceOrder.view", "serviceOrder.manage",
            "salesOrder.view", "salesOrder.manage", "purchaseOrder.view",
        ],
    },
    {
        "id": "role-purchase",
        "name": "采购/履约",
        "description": "维护供应商、采购、发货、安装和核销。",
        "permissions": [
            "dashboard.view", "project.view", "entity.view", "product.view",
            "purchase.manage", "notice.view", "notice.stats.view",
            "notice.tag.view", "notice.orgType.view", "notice.nature.view",
            "serviceOrder.view", "salesOrder.view",
            "purchaseOrder.view", "purchaseOrder.manage",
        ],
    },
    {
        "id": "role-finance",
        "name": "财务",
        "description": "维护发票、流水、垫付和财务状态。",
        "permissions": [
            "dashboard.view", "project.view", "entity.view",
            "finance.view", "finance.manage", "invoice.manage", "profit.view",
            "notice.view", "notice.stats.view", "notice.tag.view",
            "notice.orgType.view", "notice.nature.view",
            "serviceOrder.view", "serviceOrder.manage",
            "salesOrder.view", "salesOrder.manage", "purchaseOrder.view",
        ],
    },
    {
        "id": "role-platform",
        "name": "平台运营",
        "description": "维护平台入驻、账号资料、备案、CA 和续费。",
        "permissions": [
            "dashboard.view", "project.view", "entity.view", "entity.create",
            "onboarding.manage", "platformAccount.view", "platformAccount.manage",
            "trademarkCertificate.view", "trademarkCertificate.manage",
            "notice.view", "notice.stats.view", "notice.tag.view",
            "notice.orgType.view", "notice.nature.view", "sensitive.view",
            "serviceOrder.view", "serviceOrder.manage",
            "salesOrder.view", "purchaseOrder.view",
        ],
    },
    {
        "id": "role-developer",
        "name": "开发运维",
        "description": "仅管理定时任务与脚本，不自动授给业务角色。",
        "permissions": [
            "dashboard.view", "dev.ops.view", "dev.ops.manage",
            "assistant.view", "assistant.use", "assistant.manage",
            "mcpLog.view",
        ],
    },
]


class Command(BaseCommand):
    help = "Create missing default roles from seed catalog without changing users or existing roles."

    def handle(self, *args, **options):
        created, restored, skipped_id, skipped_name = [], [], [], []
        for role in DEFAULT_ROLES:
            existing = RoleRecord.objects.filter(id=role["id"]).first()
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.deleted_by = ""
                    existing.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
                    restored.append(f"{role['id']}({role['name']})")
                else:
                    skipped_id.append(f"{role['id']}({existing.name})")
                continue
            name_hit = (
                RoleRecord.objects.filter(is_deleted=False, name=role["name"])
                .exclude(id=role["id"])
                .first()
            )
            if name_hit:
                skipped_name.append(f"{role['name']} -> keep {name_hit.id}")
                continue
            RoleRecord.objects.create(
                id=role["id"],
                name=role["name"],
                data={
                    "id": role["id"],
                    "name": role["name"],
                    "description": role["description"],
                    "permissions": role["permissions"],
                },
                is_deleted=False,
            )
            created.append(f"{role['id']}({role['name']})")

        self.stdout.write(self.style.SUCCESS(f"CREATED: {created or ['none']}"))
        self.stdout.write(self.style.SUCCESS(f"RESTORED: {restored or ['none']}"))
        self.stdout.write(f"SKIP_EXISTING_ID: {skipped_id or ['none']}")
        self.stdout.write(f"SKIP_SAME_NAME: {skipped_name or ['none']}")
        self.stdout.write("ACTIVE_ROLES:")
        for record in RoleRecord.objects.filter(is_deleted=False).order_by("name"):
            self.stdout.write(f"  {record.name}\t{record.id}")
