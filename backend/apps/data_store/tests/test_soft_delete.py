from django.test import TestCase

from apps.data_store.models import AppState, OrganizationRecord, ProductRecord, ProjectItemRecord, ProjectRecord
from apps.data_store.views import (
    DEFAULT_KEY,
    ProtectedOrganizationError,
    _soft_delete_queryset,
    load_app_data,
    save_app_data,
)


class SoftDeleteTests(TestCase):
    product = {
        "id": "product-1",
        "code": "P-001",
        "name": "Test product",
        "kind": "goods",
        "category": "test",
    }

    def test_snapshot_omission_logically_deletes_record(self):
        save_app_data({"products": [self.product]})

        save_app_data({"products": []})

        record = ProductRecord.objects.get(id=self.product["id"])
        self.assertTrue(record.is_deleted)
        self.assertIsNotNone(record.deleted_at)
        self.assertEqual(record.deleted_by, "system")
        self.assertTrue(record.data["isDeleted"])
        self.assertEqual(AppState.objects.get(key=DEFAULT_KEY).data["products"], [])

    def test_resaving_logically_deleted_record_restores_it(self):
        save_app_data({"products": [self.product]})
        save_app_data({"products": []})

        save_app_data({"products": [self.product]})

        record = ProductRecord.objects.get(id=self.product["id"])
        self.assertFalse(record.is_deleted)
        self.assertIsNone(record.deleted_at)
        self.assertEqual(record.deleted_by, "")

    def test_soft_delete_helper_never_removes_database_row(self):
        save_app_data({"products": [self.product]})

        deleted_count = _soft_delete_queryset(ProductRecord.objects.all(), "tester")

        self.assertEqual(deleted_count, 1)
        record = ProductRecord.objects.get(id=self.product["id"])
        self.assertTrue(record.is_deleted)
        self.assertEqual(record.deleted_by, "tester")

    def test_snapshot_cannot_delete_organization_referenced_by_project(self):
        organization = {
            "id": "organization-1",
            "name": "Referenced organization",
            "entityType": "company",
            "roles": ["customer"],
            "status": "active",
            "createdAt": "2026-07-21",
        }
        project = {
            "id": "project-1",
            "projectNo": "P-001",
            "name": "Protected project",
            "type": "service",
            "customerOrgId": organization["id"],
            "status": "active",
        }
        save_app_data({"organizations": [organization], "projects": [project]})

        with self.assertRaises(ProtectedOrganizationError):
            save_app_data({"organizations": [], "projects": []})

        self.assertFalse(OrganizationRecord.objects.get(id=organization["id"]).is_deleted)
        self.assertFalse(ProjectRecord.objects.get(id=project["id"]).is_deleted)

    def test_partial_service_order_snapshot_does_not_delete_omitted_orders(self):
        from apps.data_store.models import ServiceOrderRecord

        first = {
            "id": "svc-keep",
            "orderNo": "SV-001",
            "projectId": "pj-1",
            "serviceId": "prd-1",
            "customerOrgId": "org-1",
            "amount": 1000,
            "status": "待付款",
            "createdAt": "2026-08-13T08:00:00",
            "updatedAt": "2026-08-13T08:00:00",
        }
        second = {
            "id": "svc-new",
            "orderNo": "SV-002",
            "projectId": "pj-2",
            "serviceId": "prd-1",
            "customerOrgId": "org-1",
            "amount": 2000,
            "status": "待付款",
            "createdAt": "2026-08-13T08:35:00",
            "updatedAt": "2026-08-13T08:35:00",
        }
        save_app_data({"serviceOrders": [first, second]})
        save_app_data({"serviceOrders": [first]}, partial=True)

        self.assertFalse(ServiceOrderRecord.objects.get(id="svc-keep").is_deleted)
        self.assertFalse(ServiceOrderRecord.objects.get(id="svc-new").is_deleted)

    def test_partial_project_snapshot_does_not_delete_omitted_projects(self):
        first = {
            "id": "pj-keep",
            "projectNo": "XM-001",
            "name": "已有项目",
            "type": "服务项目",
            "customerOrgId": "org-1",
            "status": "入驻中",
            "createdAt": "2026-08-20T01:00:00",
            "updatedAt": "2026-08-20T01:00:00",
        }
        second = {
            "id": "pj-new",
            "projectNo": "XM-002",
            "name": "刚创建的项目",
            "type": "服务项目",
            "customerOrgId": "org-1",
            "status": "入驻中",
            "createdAt": "2026-08-20T01:59:00",
            "updatedAt": "2026-08-20T01:59:00",
        }
        item = {
            "id": "pi-new",
            "projectId": "pj-new",
            "productId": "prd-1",
            "productName": "服务",
            "quantity": 1,
            "actualPrice": 1500,
        }
        save_app_data({"projects": [first, second], "projectItems": [item]})
        save_app_data({"projects": [first], "projectItems": []}, partial=True)

        self.assertFalse(ProjectRecord.objects.get(id="pj-keep").is_deleted)
        self.assertFalse(ProjectRecord.objects.get(id="pj-new").is_deleted)
        self.assertFalse(ProjectItemRecord.objects.get(id="pi-new").is_deleted)

    def test_full_project_snapshot_omission_still_deletes(self):
        project = {
            "id": "pj-full-delete",
            "projectNo": "XM-DEL",
            "name": "待删除项目",
            "type": "商品项目",
            "customerOrgId": "org-1",
            "status": "初始化",
        }
        save_app_data({"projects": [project]})
        save_app_data({"projects": []})

        record = ProjectRecord.objects.get(id="pj-full-delete")
        self.assertTrue(record.is_deleted)

    def test_partial_website_lead_snapshot_does_not_delete_omitted_leads(self):
        from apps.data_store.models import WebsiteLeadRecord

        first = {
            "id": "lead-keep",
            "companyName": "甲公司",
            "phone": "13800000001",
            "contactName": "张三",
            "platform": "泉E采",
            "status": "未跟进",
            "createdAt": "2026-08-20T01:00:00",
            "memos": [{"id": "lmemo-1", "content": "已电话联系", "createdBy": "张三", "createdAt": "2026-08-20T01:10:00"}],
        }
        second = {
            "id": "lead-other",
            "companyName": "乙公司",
            "phone": "13800000002",
            "contactName": "李四",
            "platform": "齐鲁云采",
            "status": "未跟进",
            "createdAt": "2026-08-21T01:00:00",
            "memos": [],
        }
        save_app_data({"websiteLeads": [first, second]})
        save_app_data({"websiteLeads": [{**first, "status": "已跟进"}]}, partial=True)

        kept = WebsiteLeadRecord.objects.get(id="lead-keep")
        other = WebsiteLeadRecord.objects.get(id="lead-other")
        self.assertFalse(kept.is_deleted)
        self.assertFalse(other.is_deleted)
        self.assertEqual(kept.status, "已跟进")
        self.assertEqual(other.company_name, "乙公司")
        self.assertEqual(other.phone, "13800000002")

    def test_partial_product_snapshot_does_not_delete_omitted_products(self):
        other = {
            "id": "product-2",
            "code": "P-002",
            "name": "Other product",
            "kind": "goods",
            "category": "test",
        }
        save_app_data({"products": [self.product, other]})
        save_app_data({"products": [{**self.product, "name": "Updated product"}]}, partial=True)

        kept = ProductRecord.objects.get(id=self.product["id"])
        omitted = ProductRecord.objects.get(id="product-2")
        self.assertFalse(kept.is_deleted)
        self.assertFalse(omitted.is_deleted)
        self.assertEqual(kept.name, "Updated product")
        self.assertEqual(omitted.name, "Other product")

    def test_partial_delete_ids_soft_deletes_specified_records(self):
        other = {
            "id": "product-2",
            "code": "P-002",
            "name": "Other product",
            "kind": "goods",
            "category": "test",
        }
        save_app_data({"products": [self.product, other]})
        save_app_data({"products": []}, partial=True, delete_ids={"products": [self.product["id"]]})

        deleted = ProductRecord.objects.get(id=self.product["id"])
        kept = ProductRecord.objects.get(id="product-2")
        self.assertTrue(deleted.is_deleted)
        self.assertEqual(deleted.deleted_by, "system")
        self.assertFalse(kept.is_deleted)

    def test_load_app_data_uses_tables_instead_of_stale_snapshot(self):
        save_app_data({"products": [self.product]})
        state = AppState.objects.get(key=DEFAULT_KEY)
        stale = dict(state.data)
        stale["products"] = [
            {**self.product, "name": "快照旧名"},
            {"id": "product-ghost", "code": "GHOST", "name": "快照幽灵商品", "kind": "goods", "category": "test"},
        ]
        state.data = stale
        state.save(update_fields=["data"])

        save_app_data({"products": [{**self.product, "name": "表内新名"}]}, partial=True)
        loaded = load_app_data() or {}
        names = {item["id"]: item.get("name") for item in loaded.get("products", [])}
        self.assertEqual(names.get(self.product["id"]), "表内新名")
        self.assertNotIn("product-ghost", names)


    def test_load_app_data_limits_operation_logs(self):
        from apps.data_store.views import APP_DATA_OPERATION_LOG_LIMIT, load_app_data, save_app_data

        logs = [
            {
                "id": f"log-{index}",
                "action": "测试",
                "targetType": "系统",
                "targetName": f"t-{index}",
                "operator": "tester",
                "detail": "",
                "createdAt": f"2026-09-{(index % 28) + 1:02d}T10:00:00",
            }
            for index in range(APP_DATA_OPERATION_LOG_LIMIT + 40)
        ]
        save_app_data({"operationLogs": logs}, partial=True)
        loaded = load_app_data() or {}
        self.assertEqual(len(loaded.get("operationLogs") or []), APP_DATA_OPERATION_LOG_LIMIT)
