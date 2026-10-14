import os
import uuid

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from apps.data_store.models import RoleRecord, UserRecord


class Command(BaseCommand):
    help = "Create or update the production administrator from environment variables."

    def handle(self, *args, **options):
        name = os.getenv("INITIAL_ADMIN_NAME", "").strip()
        phone = os.getenv("INITIAL_ADMIN_PHONE", "").strip()
        password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        if not name or not phone or not password:
            raise CommandError("INITIAL_ADMIN_NAME, INITIAL_ADMIN_PHONE and INITIAL_ADMIN_PASSWORD are required.")

        role, _ = RoleRecord.objects.update_or_create(
            id="role-production-admin",
            defaults={
                "name": "生产管理员",
                "data": {
                    "id": "role-production-admin",
                    "name": "生产管理员",
                    "description": "生产环境全局管理员。",
                    "permissions": [
                        "dashboard.view", "project.view", "project.create", "project.edit",
                        "entity.view", "entity.create", "product.view", "product.manage",
                        "purchase.manage", "serviceOrder.view", "serviceOrder.manage",
                        "salesOrder.view", "salesOrder.manage", "purchaseOrder.view", "purchaseOrder.manage",
                        "finance.view", "finance.manage", "invoice.manage",
                        "onboarding.manage", "platformAccount.view", "platformAccount.manage",
                        "trademarkCertificate.view", "trademarkCertificate.manage",
                        "notice.view", "notice.manage",
                        "lead.manage", "sensitive.view", "profit.view", "user.manage",
                    ],
                },
                "is_deleted": False,
            },
        )
        user = UserRecord.objects.filter(phone=phone).first()
        user_id = user.id if user else f"user-{uuid.uuid4().hex[:12]}"
        data = dict(user.data) if user else {}
        data.update({
            "id": user_id,
            "name": name,
            "phone": phone,
            "password": make_password(password),
            "roleIds": sorted(set(data.get("roleIds", [])) | {role.id}),
            "status": "启用",
        })
        UserRecord.objects.update_or_create(
            id=user_id,
            defaults={"name": name, "phone": phone, "status": "启用", "data": data, "is_deleted": False},
        )
        disabled = 0
        for legacy_user in UserRecord.objects.exclude(id=user_id):
            legacy_data = dict(legacy_user.data)
            if legacy_data.get("password") != "123456":
                continue
            legacy_data["status"] = "停用"
            legacy_user.data = legacy_data
            legacy_user.status = "停用"
            legacy_user.save(update_fields=["data", "status", "updated_at"])
            disabled += 1
        self.stdout.write(self.style.SUCCESS(f"Production administrator ready: {phone[-4:].rjust(len(phone), '*')}"))
        self.stdout.write(self.style.SUCCESS(f"Disabled {disabled} development users with default passwords."))
