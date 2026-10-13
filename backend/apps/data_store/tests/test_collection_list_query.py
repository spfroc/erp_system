from decimal import Decimal

from django.test import Client, TestCase

from apps.data_store.models import InvoiceRecord, OrganizationRecord, PlatformAccountRecord, ProductRecord, RoleRecord, UserRecord
from apps.data_store.views import save_app_data


class CollectionListQueryTests(TestCase):
    def setUp(self):
        self.client = Client()
        admin = {
            "id": "user-admin",
            "name": "管理员",
            "phone": "13800000000",
            "password": "123456",
            "status": "启用",
            "roleIds": ["role-admin"],
        }
        role = {
            "id": "role-admin",
            "name": "管理员",
            "permissions": [
                "onboarding.manage",
                "product.view",
                "product.manage",
            "project.view",
            "sensitive.view",
            "user.manage",
            "invoice.manage",
            "salesOrder.view",
            ],
        }
        save_app_data(
            {
                "users": [admin],
                "roles": [role],
                "organizations": [
                    {
                        "id": "org-a",
                        "name": "济南客户甲",
                        "entityType": "企业",
                        "roles": ["平台入驻商"],
                        "status": "正常",
                        "createdAt": "2026-08-01T10:00:00",
                    },
                    {
                        "id": "org-b",
                        "name": "青岛客户乙",
                        "entityType": "企业",
                        "roles": ["平台入驻商"],
                        "status": "正常",
                        "createdAt": "2026-08-02T10:00:00",
                    },
                    {
                        "id": "org-supplier",
                        "name": "潍坊供应商丙",
                        "entityType": "企业",
                        "roles": ["上游供应商"],
                        "status": "正常",
                        "createdAt": "2026-08-02T11:00:00",
                    },
                    {
                        "id": "org-own",
                        "name": "壹采自有主体",
                        "entityType": "企业",
                        "roles": ["自有主体"],
                        "status": "正常",
                        "createdAt": "2026-08-02T12:00:00",
                    },
                ],
                "platformAccounts": [
                    {
                        "id": "pa-1",
                        "customerOrgId": "org-a",
                        "platform": "泉E采",
                        "accountName": "acc-a",
                        "accountPasswordMasked": "secret-a",
                        "currentStatus": "已付款待办理",
                        "createdAt": "2026-08-03T10:00:00",
                    },
                    {
                        "id": "pa-2",
                        "customerOrgId": "org-b",
                        "platform": "政采云",
                        "accountName": "acc-b",
                        "accountPasswordMasked": "secret-b",
                        "currentStatus": "已付款待办理",
                        "createdAt": "2026-08-04T10:00:00",
                    },
                ],
                "products": [
                    {
                        "id": "prod-1",
                        "code": "G-001",
                        "name": "美的空调",
                        "kind": "实体商品",
                        "category": "空调",
                        "createdAt": "2026-08-01T10:00:00",
                    },
                    {
                        "id": "prod-2",
                        "code": "S-001",
                        "name": "泉E采入驻服务",
                        "kind": "虚拟服务",
                        "category": "平台服务",
                        "createdAt": "2026-08-02T10:00:00",
                    },
                ],
                "projects": [
                    {
                        "id": "proj-service",
                        "projectNo": "FW-001",
                        "name": "泉E采服务项目",
                        "type": "服务项目",
                        "customerOrgId": "org-a",
                        "ownCompanyOrgId": "org-own",
                        "owner": "管理员",
                        "status": "进行中",
                        "contractStatus": "待签",
                        "paymentStatus": "待付款",
                        "purchaseStatus": "无需采购",
                        "invoiceStatus": "未开票",
                        "totalAmount": 1000,
                        "totalCost": 0,
                        "updatedAt": "2026-08-05T10:00:00",
                        "createdAt": "2026-08-05T10:00:00",
                    },
                    {
                        "id": "proj-goods-uploaded",
                        "projectNo": "SP-001",
                        "name": "空调采购项目",
                        "type": "商品项目",
                        "customerOrgId": "org-b",
                        "ownCompanyOrgId": "org-own",
                        "owner": "管理员",
                        "status": "进行中",
                        "contractStatus": "已签",
                        "contractFileId": "file-proj-1",
                        "contractFileName": "销售合同-空调.pdf",
                        "paymentStatus": "待付款",
                        "purchaseStatus": "已下单",
                        "invoiceStatus": "未开票",
                        "totalAmount": 5000,
                        "totalCost": 4000,
                        "sourcePlatform": "青慧采",
                        "updatedAt": "2026-08-06T10:00:00",
                        "createdAt": "2026-08-06T10:00:00",
                    },
                    {
                        "id": "proj-goods-plain",
                        "projectNo": "SP-002",
                        "name": "无合同商品项目",
                        "type": "商品项目",
                        "customerOrgId": "org-a",
                        "ownCompanyOrgId": "org-own",
                        "owner": "管理员",
                        "status": "进行中",
                        "contractStatus": "待签",
                        "paymentStatus": "待付款",
                        "purchaseStatus": "待采购",
                        "invoiceStatus": "未开票",
                        "totalAmount": 2000,
                        "totalCost": 0,
                        "sourcePlatform": "泉E采",
                        "updatedAt": "2026-08-04T10:00:00",
                        "createdAt": "2026-08-04T10:00:00",
                    },
                ],
                "salesOrders": [
                    {
                        "id": "so-qing",
                        "projectId": "proj-goods-uploaded",
                        "orderNo": "SO-QING-01",
                        "platform": "青慧采",
                        "customerOrgId": "org-b",
                        "purchaserCompany": "青慧采采购单位",
                        "purchaserName": "王采购",
                        "purchaserPhone": "13900001111",
                        "amount": 500,
                        "receivableAmount": 500,
                        "receivedAmount": 0,
                        "status": "待付款",
                        "createdAt": "2026-08-08T10:00:00",
                    },
                    {
                        "id": "so-quan-direct",
                        "projectId": "proj-goods-uploaded",
                        "orderNo": "SO-QUAN-01",
                        "platform": "泉E采",
                        "customerOrgId": "org-b",
                        "amount": 800,
                        "receivableAmount": 800,
                        "receivedAmount": 800,
                        "status": "已付款",
                        "createdAt": "2026-08-08T11:00:00",
                    },
                    {
                        "id": "so-inherit",
                        "projectId": "proj-goods-uploaded",
                        "orderNo": "SO-INHERIT-01",
                        "customerOrgId": "org-b",
                        "amount": 300,
                        "receivableAmount": 300,
                        "receivedAmount": 0,
                        "status": "待付款",
                        "createdAt": "2026-08-08T12:00:00",
                    },
                    {
                        "id": "so-quan-proj",
                        "projectId": "proj-goods-plain",
                        "orderNo": "SO-QUAN-02",
                        "customerOrgId": "org-a",
                        "amount": 200,
                        "receivableAmount": 200,
                        "receivedAmount": 50,
                        "status": "部分付款",
                        "createdAt": "2026-08-08T13:00:00",
                    },
                ],
                "purchaseOrders": [
                    {
                        "id": "po-with-contract",
                        "projectId": "proj-goods-uploaded",
                        "orderNo": "PO-1001",
                        "supplierOrgId": "org-supplier",
                        "ownCompanyOrgId": "org-own",
                        "amount": 4000,
                        "status": "已下单",
                        "contractStatus": "已签",
                        "contractFileId": "file-po-1",
                        "contractFileName": "采购合同-潍坊.pdf",
                        "createdAt": "2026-08-07T10:00:00",
                        "updatedAt": "2026-08-07T12:00:00",
                    },
                    {
                        "id": "po-without-contract",
                        "projectId": "proj-goods-plain",
                        "orderNo": "PO-1002",
                        "supplierOrgId": "org-supplier",
                        "ownCompanyOrgId": "org-own",
                        "amount": 1500,
                        "status": "待下单",
                        "contractStatus": "待签",
                        "createdAt": "2026-08-07T09:00:00",
                        "updatedAt": "2026-08-07T09:00:00",
                    },
                ],
                "invoices": [
                    {
                        "id": "inv-1",
                        "invoiceNo": "239012345678",
                        "invoiceDate": "2026-08-08",
                        "type": "销项",
                        "amount": 1800,
                        "status": "待确认",
                        "buyerName": "济南客户甲",
                        "sellerName": "壹采自有主体",
                        "buyerTaxNo": "91370100AAAA111",
                        "sellerTaxNo": "91370000BBBB222",
                        "projectId": "proj-service",
                        "projectIds": ["proj-service"],
                        "createdAt": "2026-08-08T10:00:00",
                    },
                    {
                        "id": "inv-2",
                        "invoiceNo": "339000000001",
                        "invoiceDate": "2026-08-09",
                        "type": "进项",
                        "amount": 4000,
                        "status": "已确认",
                        "buyerName": "壹采自有主体",
                        "sellerName": "潍坊供应商丙",
                        "projectId": "proj-goods-uploaded",
                        "projectIds": ["proj-goods-uploaded"],
                        "purchaseOrderIds": ["po-with-contract"],
                        "createdAt": "2026-08-09T10:00:00",
                    },
                ],
            }
        )
        self.assertTrue(UserRecord.objects.filter(id="user-admin").exists())
        self.assertTrue(OrganizationRecord.objects.filter(id="org-a").exists())
        self.assertTrue(PlatformAccountRecord.objects.filter(id="pa-1").exists())
        self.assertTrue(ProductRecord.objects.filter(id="prod-1").exists())
        login = self.client.post(
            "/api/auth/login/",
            data={"identifier": "13800000000", "password": "123456"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_platform_accounts_search_by_customer_name_and_platform_filter(self):
        response = self.client.get(
            "/api/collections/platformAccounts/",
            {"page": 1, "page_size": 10, "search": "济南", "platform": "泉E采"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 10)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["id"], "pa-1")
        # onboarding.manage 可查看敏感字段；脱敏由无权限用户触发
        self.assertEqual(payload["items"][0]["accountName"], "acc-a")
        self.assertEqual(payload["items"][0]["createdAt"], "2026-08-03T10:00:00")

    def test_platform_accounts_hydrate_timestamps_from_db_columns(self):
        from datetime import datetime, timezone as dt_timezone

        record = PlatformAccountRecord.objects.get(id="pa-1")
        data = dict(record.data)
        data.pop("createdAt", None)
        data.pop("updatedAt", None)
        record.data = data
        record.created_at = datetime(2026, 7, 1, 8, 30, tzinfo=dt_timezone.utc)
        record.save(update_fields=["data", "created_at", "updated_at"])

        response = self.client.get(
            "/api/collections/platformAccounts/",
            {"page": 1, "page_size": 10, "search": "济南", "platform": "泉E采"},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertTrue(item["createdAt"])
        self.assertTrue(item["updatedAt"])
        self.assertIn("2026-07-01", item["createdAt"])

    def test_platform_accounts_created_at_falls_back_to_updated_at(self):
        record = PlatformAccountRecord.objects.get(id="pa-1")
        data = dict(record.data)
        data.pop("createdAt", None)
        data["updatedAt"] = "2026-08-10T12:00:00"
        record.data = data
        record.created_at = None
        record.save(update_fields=["data", "created_at", "updated_at"])

        response = self.client.get(
            "/api/collections/platformAccounts/",
            {"page": 1, "page_size": 10, "search": "济南", "platform": "泉E采"},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["createdAt"], "2026-08-10T12:00:00")
        record.refresh_from_db()
        self.assertEqual(record.data.get("createdAt"), "2026-08-10T12:00:00")

    def test_platform_accounts_ordered_by_created_at_desc(self):
        response = self.client.get(
            "/api/collections/platformAccounts/",
            {"page": 1, "page_size": 10},
        )
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["items"]]
        self.assertEqual(ids, ["pa-2", "pa-1"])

    def test_products_kind_and_name_search(self):
        response = self.client.get(
            "/api/collections/products/",
            {"page": 1, "page_size": 10, "kind": "虚拟服务", "search": "入驻"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], "prod-2")

    def test_unpaged_collection_still_returns_data_array(self):
        response = self.client.get("/api/collections/products/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertEqual(len(payload["data"]), 2)

    def test_contracts_list_includes_project_and_purchase_contracts(self):
        response = self.client.get("/api/collections/contracts/", {"page": 1, "page_size": 20})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = [item["id"] for item in payload["items"]]
        kinds = {item["id"]: item["kind"] for item in payload["items"]}
        # 服务项目（待签）+ 已上传项目合同的商品项目 + 已上传采购合同
        self.assertIn("project:proj-service", ids)
        self.assertIn("project:proj-goods-uploaded", ids)
        self.assertIn("purchaseOrder:po-with-contract", ids)
        self.assertNotIn("project:proj-goods-plain", ids)
        self.assertNotIn("purchaseOrder:po-without-contract", ids)
        self.assertEqual(kinds["project:proj-service"], "项目合同")
        self.assertEqual(kinds["purchaseOrder:po-with-contract"], "采购合同")
        self.assertEqual(payload["total"], 3)

    def test_contracts_search_by_supplier_and_order_no(self):
        by_supplier = self.client.get(
            "/api/collections/contracts/",
            {"page": 1, "page_size": 10, "search": "潍坊"},
        )
        self.assertEqual(by_supplier.status_code, 200)
        supplier_payload = by_supplier.json()
        self.assertEqual(supplier_payload["total"], 1)
        self.assertEqual(supplier_payload["items"][0]["id"], "purchaseOrder:po-with-contract")
        self.assertEqual(supplier_payload["items"][0]["orderNo"], "PO-1001")

        by_order = self.client.get(
            "/api/collections/contracts/",
            {"page": 1, "page_size": 10, "search": "PO-1001"},
        )
        self.assertEqual(by_order.status_code, 200)
        self.assertEqual(by_order.json()["items"][0]["id"], "purchaseOrder:po-with-contract")

        by_file = self.client.get(
            "/api/collections/contracts/",
            {"page": 1, "page_size": 10, "search": "销售合同"},
        )
        self.assertEqual(by_file.status_code, 200)
        self.assertEqual(by_file.json()["total"], 1)
        self.assertEqual(by_file.json()["items"][0]["id"], "project:proj-goods-uploaded")

    def test_contracts_search_by_project_name(self):
        response = self.client.get(
            "/api/collections/contracts/",
            {"page": 1, "page_size": 10, "search": "泉E采服务"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], "project:proj-service")

    def test_contracts_updated_at_prefers_contract_updated_at_not_business_updated_at(self):
        from apps.data_store.models import ProjectRecord

        record = ProjectRecord.objects.get(id="proj-service")
        payload = dict(record.data or {})
        payload["updatedAt"] = "2026-09-17T12:00:00"
        payload["contractUpdatedAt"] = "2026-08-01T08:00:00"
        payload["createdAt"] = "2026-07-01T08:00:00"
        record.data = payload
        record.save(update_fields=["data"])

        response = self.client.get("/api/collections/contracts/", {"page": 1, "page_size": 20})
        self.assertEqual(response.status_code, 200)
        items = {item["id"]: item for item in response.json()["items"]}
        service_row = items["project:proj-service"]
        self.assertEqual(service_row["updatedAt"], "2026-08-01T08:00:00")
        # 业务 updatedAt 更晚也不应把该合同排到最前
        self.assertNotEqual(response.json()["items"][0]["id"], "project:proj-service")

    def test_projects_empty_or_missing_search_does_not_500(self):
        """清空搜索框后 search= / 省略 search 都应正常返回列表。"""
        for params in (
            {"paged": "1", "page": 1, "page_size": 10, "type": "服务项目"},
            {"paged": "1", "page": 1, "page_size": 10, "type": "服务项目", "search": ""},
            {"paged": "1", "page": 1, "page_size": 10, "type": "服务项目", "search": "   "},
            {"paged": "1", "page": 1, "page_size": 10, "type": "商品项目"},
            {"paged": "1", "page": 1, "page_size": 10, "type": "商品项目", "search": ""},
        ):
            with self.subTest(params=params):
                response = self.client.get("/api/collections/projects/", params)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn("items", payload)
                self.assertGreaterEqual(payload["total"], 1)
                self.assertEqual(payload["page"], 1)
                self.assertEqual(payload["page_size"], 10)

        with_keyword = self.client.get(
            "/api/collections/projects/",
            {"paged": "1", "page": 1, "page_size": 10, "type": "服务项目", "search": "泉E采"},
        )
        self.assertEqual(with_keyword.status_code, 200)
        self.assertEqual(with_keyword.json()["total"], 1)
        self.assertEqual(with_keyword.json()["items"][0]["id"], "proj-service")

        cleared = self.client.get(
            "/api/collections/projects/",
            {"paged": "1", "page": 1, "page_size": 10, "type": "服务项目"},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["total"], 1)

    def test_service_project_list_filters(self):
        save_app_data(
            {
                "organizations": [
                    {
                        "id": "org-own-2",
                        "name": "青州签约主体",
                        "entityType": "企业",
                        "roles": ["自有主体"],
                        "status": "正常",
                        "createdAt": "2026-08-02T13:00:00",
                    },
                ],
                "users": [
                    {
                        "id": "user-sales",
                        "name": "张三",
                        "phone": "13800000002",
                        "password": "123456",
                        "status": "启用",
                        "roleIds": ["role-admin"],
                    },
                ],
                "projects": [
                    {
                        "id": "proj-service-once",
                        "projectNo": "FW-002",
                        "name": "按次服务项目",
                        "type": "服务项目",
                        "customerOrgId": "org-b",
                        "ownCompanyOrgId": "org-own-2",
                        "owner": "管理员",
                        "status": "服务中",
                        "serviceType": "按次",
                        "contractStatus": "已签",
                        "paymentStatus": "待付款",
                        "purchaseStatus": "无需采购",
                        "invoiceStatus": "已开全部",
                        "serviceSalesUserId": "user-admin",
                        "serviceSalesName": "管理员",
                        "totalAmount": 2000,
                        "totalCost": 0,
                        "updatedAt": "2026-08-07T10:00:00",
                        "createdAt": "2026-08-07T10:00:00",
                    },
                    {
                        "id": "proj-service-period",
                        "projectNo": "FW-003",
                        "name": "周期服务项目",
                        "type": "服务项目",
                        "customerOrgId": "org-a",
                        "ownCompanyOrgId": "org-own",
                        "owner": "张三",
                        "status": "入驻中",
                        "serviceType": "周期",
                        "contractStatus": "无需",
                        "paymentStatus": "待付款",
                        "purchaseStatus": "无需采购",
                        "invoiceStatus": "待开",
                        "serviceSalesUserId": "user-sales",
                        "serviceSalesName": "张三",
                        "totalAmount": 3000,
                        "totalCost": 0,
                        "updatedAt": "2026-08-08T10:00:00",
                        "createdAt": "2026-08-08T10:00:00",
                    },
                ],
            },
            partial=True,
        )

        def ids_for(**params):
            response = self.client.get(
                "/api/collections/projects/",
                {"paged": "1", "page": 1, "page_size": 20, "type": "服务项目", **params},
            )
            self.assertEqual(response.status_code, 200)
            return [item["id"] for item in response.json()["items"]]

        all_ids = ids_for()
        self.assertCountEqual(all_ids, ["proj-service", "proj-service-once", "proj-service-period"])
        self.assertEqual(ids_for(ownCompanyOrgId="org-own-2"), ["proj-service-once"])
        self.assertEqual(ids_for(status="服务中"), ["proj-service-once"])
        self.assertEqual(ids_for(serviceType="按次"), ["proj-service-once"])
        self.assertCountEqual(ids_for(serviceType="周期"), ["proj-service", "proj-service-period"])
        self.assertEqual(ids_for(contractStatus="待签"), ["proj-service"])
        self.assertCountEqual(ids_for(invoiceStatus="待开"), ["proj-service", "proj-service-period"])
        self.assertEqual(ids_for(invoiceStatus="已开全部"), ["proj-service-once"])
        self.assertEqual(ids_for(serviceSalesUserId="user-sales"), ["proj-service-period"])
        self.assertCountEqual(ids_for(serviceSalesUserId="user-admin"), ["proj-service", "proj-service-once"])
        self.assertEqual(ids_for(search="按次服务"), ["proj-service-once"])

        goods = self.client.get(
            "/api/collections/projects/",
            {"paged": "1", "page": 1, "page_size": 20, "type": "商品项目", "status": "服务中"},
        )
        self.assertEqual(goods.status_code, 200)
        self.assertEqual(goods.json()["total"], 0)

    def test_products_empty_search_and_kind_filter(self):
        for params in (
            {"paged": "1", "page": 1, "page_size": 10, "kind": "实体商品"},
            {"paged": "1", "page": 1, "page_size": 10, "kind": "实体商品", "search": ""},
            {"paged": "1", "page": 1, "page_size": 10, "kind": "虚拟服务", "search": ""},
        ):
            with self.subTest(params=params):
                response = self.client.get("/api/collections/products/", params)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn("items", payload)
                self.assertEqual(payload["total"], 1)

    def test_products_list_hides_project_scoped_items(self):
        ProductRecord.objects.create(
            id="prod-project-only",
            code="PJ-XM001-1",
            name="项目专用空调",
            kind="实体商品",
            category="项目商品",
            data={
                "id": "prod-project-only",
                "code": "PJ-XM001-1",
                "name": "项目专用空调",
                "kind": "实体商品",
                "category": "项目商品",
                "source": "project",
                "sourceProjectId": "proj-goods-plain",
                "quotePrice": 1990,
                "costPrice": 0,
            },
        )
        hidden = self.client.get(
            "/api/collections/products/",
            {"paged": "1", "page": 1, "page_size": 10, "kind": "实体商品"},
        )
        self.assertEqual(hidden.status_code, 200)
        payload = hidden.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], "prod-1")

        included = self.client.get(
            "/api/collections/products/",
            {"paged": "1", "page": 1, "page_size": 10, "kind": "实体商品", "includeProject": "1"},
        )
        self.assertEqual(included.status_code, 200)
        ids = [item["id"] for item in included.json()["items"]]
        self.assertIn("prod-1", ids)
        self.assertIn("prod-project-only", ids)
        role = RoleRecord.objects.get(id="role-admin")
        data = dict(role.data)
        data["permissions"] = ["platformAccount.view"]
        role.data = data
        role.save(update_fields=["data"])

        response = self.client.get("/api/collections/platformAccounts/", {"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["total"], 1)

    def test_platform_accounts_without_permission_is_forbidden(self):
        role = RoleRecord.objects.get(id="role-admin")
        data = dict(role.data)
        data["permissions"] = ["dashboard.view"]
        role.data = data
        role.save(update_fields=["data"])

        response = self.client.get("/api/collections/platformAccounts/", {"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["permission"], "platformAccount.view")

    def test_invoices_search_by_number_buyer_and_seller(self):
        by_no = self.client.get("/api/collections/invoices/", {"page": 1, "page_size": 10, "search": "239012345678"})
        self.assertEqual(by_no.status_code, 200)
        self.assertEqual(by_no.json()["total"], 1)
        self.assertEqual(by_no.json()["items"][0]["id"], "inv-1")

        by_buyer = self.client.get("/api/collections/invoices/", {"page": 1, "page_size": 10, "search": "济南客户甲"})
        self.assertEqual(by_buyer.status_code, 200)
        self.assertEqual(by_buyer.json()["total"], 1)
        self.assertEqual(by_buyer.json()["items"][0]["id"], "inv-1")

        by_seller = self.client.get("/api/collections/invoices/", {"page": 1, "page_size": 10, "search": "潍坊供应商丙"})
        self.assertEqual(by_seller.status_code, 200)
        self.assertEqual(by_seller.json()["total"], 1)
        self.assertEqual(by_seller.json()["items"][0]["id"], "inv-2")

        by_order = self.client.get("/api/collections/invoices/", {"page": 1, "page_size": 10, "search": "PO-1001"})
        self.assertEqual(by_order.status_code, 200)
        self.assertEqual(by_order.json()["total"], 1)
        self.assertEqual(by_order.json()["items"][0]["id"], "inv-2")

        empty = self.client.get("/api/collections/invoices/", {"paged": "1", "page": 1, "page_size": 10, "search": ""})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["total"], 2)

    def test_purchase_orders_with_purchase_order_view_permission(self):
        role = RoleRecord.objects.get(id="role-admin")
        data = dict(role.data)
        data["permissions"] = ["purchaseOrder.view"]
        role.data = data
        role.save(update_fields=["data"])

        response = self.client.get("/api/collections/purchaseOrders/", {"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["total"], 1)

    def test_purchase_orders_without_permission_is_forbidden(self):
        role = RoleRecord.objects.get(id="role-admin")
        data = dict(role.data)
        data["permissions"] = ["dashboard.view"]
        role.data = data
        role.save(update_fields=["data"])

        response = self.client.get("/api/collections/purchaseOrders/", {"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["permission"], "purchaseOrder.view")

    def test_sales_orders_filter_by_platform_and_status(self):
        by_platform = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "platform": "青慧采"},
        )
        self.assertEqual(by_platform.status_code, 200)
        qing_ids = {item["id"] for item in by_platform.json()["items"]}
        self.assertEqual(qing_ids, {"so-qing", "so-inherit"})

        by_status = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "status": "待付款"},
        )
        self.assertEqual(by_status.status_code, 200)
        pending_ids = {item["id"] for item in by_status.json()["items"]}
        self.assertEqual(pending_ids, {"so-qing", "so-inherit"})

        combined = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "platform": "泉E采", "status": "已付款"},
        )
        self.assertEqual(combined.status_code, 200)
        self.assertEqual(combined.json()["total"], 1)
        self.assertEqual(combined.json()["items"][0]["id"], "so-quan-direct")

        by_purchaser = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "search": "王采购"},
        )
        self.assertEqual(by_purchaser.status_code, 200)
        self.assertEqual([item["id"] for item in by_purchaser.json()["items"]], ["so-qing"])

    def _create_invoice(self, payload: dict):
        InvoiceRecord.objects.update_or_create(
            id=payload["id"],
            defaults={
                "data": payload,
                "invoice_no": payload.get("invoiceNo", ""),
                "invoice_date": payload.get("invoiceDate", ""),
                "type": payload.get("type", ""),
                "amount": Decimal(str(payload.get("amount") or 0)),
                "status": payload.get("status", ""),
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": "",
            },
        )

    def test_sales_orders_filter_by_invoice_status(self):
        self._create_invoice({
            "id": "inv-so-full",
            "invoiceNo": "SO-FULL-1",
            "invoiceDate": "2026-08-10",
            "type": "销项",
            "amount": 500,
            "status": "已确认",
            "salesOrderIds": ["so-qing"],
        })
        self._create_invoice({
            "id": "inv-so-part",
            "invoiceNo": "SO-PART-1",
            "invoiceDate": "2026-08-10",
            "type": "销项",
            "amount": 300,
            "status": "已确认",
            "salesOrderIds": ["so-quan-direct"],
        })
        self._create_invoice({
            "id": "inv-so-void",
            "invoiceNo": "SO-VOID-1",
            "invoiceDate": "2026-08-10",
            "type": "销项",
            "amount": 300,
            "status": "作废",
            "salesOrderIds": ["so-inherit"],
        })

        unpaid = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "invoiceStatus": "未开票"},
        )
        self.assertEqual(unpaid.status_code, 200)
        self.assertEqual({item["id"] for item in unpaid.json()["items"]}, {"so-inherit", "so-quan-proj"})

        partial = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "invoiceStatus": "已开部分"},
        )
        self.assertEqual(partial.status_code, 200)
        self.assertEqual([item["id"] for item in partial.json()["items"]], ["so-quan-direct"])

        full = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "invoiceStatus": "已开全部"},
        )
        self.assertEqual(full.status_code, 200)
        self.assertEqual([item["id"] for item in full.json()["items"]], ["so-qing"])

        combined = self.client.get(
            "/api/collections/salesOrders/",
            {"page": 1, "page_size": 10, "platform": "泉E采", "invoiceStatus": "已开部分"},
        )
        self.assertEqual(combined.status_code, 200)
        self.assertEqual(combined.json()["total"], 1)
        self.assertEqual(combined.json()["items"][0]["id"], "so-quan-direct")
