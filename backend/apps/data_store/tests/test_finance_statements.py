from django.test import Client, TestCase

from apps.data_store.views import save_app_data


class FinanceStatementListTests(TestCase):
    def setUp(self):
        self.client = Client()
        save_app_data(
            {
                "users": [
                    {
                        "id": "user-admin",
                        "name": "管理员",
                        "phone": "13800000000",
                        "password": "123456",
                        "status": "启用",
                        "roleIds": ["role-admin"],
                    },
                    {
                        "id": "user-sales",
                        "name": "业务同事",
                        "phone": "13900000000",
                        "password": "123456",
                        "status": "启用",
                        "roleIds": ["role-admin"],
                    },
                ],
                "roles": [
                    {
                        "id": "role-admin",
                        "name": "管理员",
                        "permissions": ["finance.view"],
                    }
                ],
                "organizations": [
                    {
                        "id": "org-customer",
                        "name": "济南客户甲",
                        "entityType": "企业",
                        "roles": ["终端采购人"],
                        "status": "正常",
                        "createdAt": "2026-08-01T10:00:00",
                    },
                    {
                        "id": "org-service-customer",
                        "name": "青岛入驻客户",
                        "entityType": "企业",
                        "roles": ["平台入驻商"],
                        "status": "正常",
                        "createdAt": "2026-08-01T11:00:00",
                    },
                    {
                        "id": "org-own",
                        "name": "壹采自有主体",
                        "entityType": "企业",
                        "roles": ["自有主体"],
                        "status": "正常",
                        "createdAt": "2026-08-01T12:00:00",
                    },
                    {
                        "id": "org-missing-ref",
                        "name": "占位",
                        "entityType": "企业",
                        "roles": ["自有主体"],
                        "status": "正常",
                        "createdAt": "2026-08-01T13:00:00",
                    },
                ],
                "projects": [
                    {
                        "id": "pj-goods",
                        "projectNo": "SP-001",
                        "name": "空调采购项目",
                        "type": "商品项目",
                        "customerOrgId": "org-customer",
                        "ownCompanyOrgId": "org-own",
                        "owner": "王云磊",
                        "status": "进行中",
                        "updatedAt": "2026-09-01T10:00:00",
                    },
                    {
                        "id": "pj-service",
                        "projectNo": "FW-001",
                        "name": "泉E采服务项目",
                        "type": "服务项目",
                        "customerOrgId": "org-service-customer",
                        "ownCompanyOrgId": "org-own",
                        "serviceSalesUserId": "user-sales",
                        "serviceCustomerKind": "续费客户",
                        "status": "入驻中",
                        "updatedAt": "2026-09-01T10:00:00",
                    },
                ],
                "salesOrders": [
                    {
                        "id": "so-1",
                        "projectId": "pj-goods",
                        "orderNo": "SO-1",
                        "customerOrgId": "org-customer",
                        "ownCompanyOrgId": "org-own",
                        "amount": 1600,
                        "receivableAmount": 1600,
                        "receivedAmount": 1600,
                        "status": "已付款",
                        "createdAt": "2026-09-02T10:00:00",
                    }
                ],
                "serviceOrders": [
                    {
                        "id": "svc-1",
                        "projectId": "pj-service",
                        "orderNo": "SV-1",
                        "serviceId": "prd-3",
                        "customerOrgId": "org-service-customer",
                        "amount": 2000,
                        "receivableAmount": 2000,
                        "receivedAmount": 2000,
                        "status": "已付款",
                        "salesUserId": "user-sales",
                        "salesName": "业务同事",
                        "createdAt": "2026-09-02T11:00:00",
                    }
                ],
                "purchaseOrders": [
                    {
                        "id": "po-1",
                        "projectId": "pj-goods",
                        "orderNo": "PO-1",
                        "supplierOrgId": "org-customer",
                        "ownCompanyOrgId": "org-own",
                        "amount": 900,
                        "status": "已下单",
                        "createdAt": "2026-09-03T10:00:00",
                    }
                ],
                "optionGroups": [
                    {
                        "id": "optgrp-collection_account",
                        "key": "collection_account",
                        "name": "收款账号",
                        "items": [
                            {
                                "id": "acc-own",
                                "label": "公户",
                                "value": "公户",
                                "enabled": True,
                                "sortOrder": 1,
                                "ownCompanyOrgId": "org-own",
                                "bankName": "齐鲁银行",
                                "accountNumber": "62220001",
                            }
                        ],
                    }
                ],
                "transactions": [
                    {
                        "id": "tx-product",
                        "projectId": "pj-goods",
                        "salesOrderId": "so-1",
                        "type": "收款",
                        "amount": 1600,
                        "date": "2026-09-02",
                        "occurredAt": "2026-09-02T10:00:00",
                        "status": "已匹配",
                        "account": "acc-own",
                        "createdAt": "2026-09-02T10:00:00",
                    },
                    {
                        "id": "tx-service",
                        "projectId": "pj-service",
                        "serviceOrderId": "svc-1",
                        "type": "收款",
                        "amount": 2000,
                        "date": "2026-09-04",
                        "occurredAt": "2026-09-04T11:00:00",
                        "status": "已匹配",
                        "account": "acc-own",
                        "createdAt": "2026-09-04T11:00:00",
                    },
                    {
                        "id": "tx-purchase",
                        "projectId": "pj-goods",
                        "purchaseOrderId": "po-1",
                        "type": "付款",
                        "amount": 900,
                        "date": "2026-09-03",
                        "occurredAt": "2026-09-03T09:00:00",
                        "status": "已匹配",
                        "account": "acc-own",
                        "createdAt": "2026-09-03T09:00:00",
                    },
                    {
                        "id": "tx-void",
                        "projectId": "pj-goods",
                        "salesOrderId": "so-1",
                        "type": "收款",
                        "amount": 88,
                        "date": "2026-09-05",
                        "occurredAt": "2026-09-05T10:00:00",
                        "status": "作废",
                        "account": "acc-own",
                        "createdAt": "2026-09-05T10:00:00",
                    },
                ],
            }
        )
        login = self.client.post(
            "/api/auth/login/",
            data={"identifier": "13800000000", "password": "123456"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_lists_active_rows_by_occurred_time_desc(self):
        response = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "page": 1, "page_size": 20},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        ids = [item["id"] for item in payload["items"]]
        self.assertEqual(ids, ["tx-service", "tx-purchase", "tx-product"])
        self.assertEqual(payload["items"][0]["businessKind"], "服务")
        self.assertEqual(payload["items"][0]["customerName"], "青岛入驻客户")
        self.assertEqual(payload["items"][0]["serviceCustomerKind"], "续费客户")
        self.assertEqual(payload["items"][0]["companyName"], "壹采自有主体")
        self.assertEqual(payload["items"][0]["salesperson"], "业务同事")
        self.assertIn("齐鲁银行", payload["items"][0]["accountText"])
        self.assertEqual(payload["items"][1]["businessKind"], "采购")
        self.assertEqual(payload["items"][2]["businessKind"], "商品")
        self.assertEqual(payload["items"][2]["salesperson"], "王云磊")

    def test_filters_by_kind_customer_salesperson_and_date(self):
        by_kind = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "businessKind": "服务"},
        ).json()
        self.assertEqual(by_kind["total"], 1)
        self.assertEqual(by_kind["items"][0]["id"], "tx-service")

        by_customer = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "customerOrgId": "org-customer"},
        ).json()
        self.assertEqual({item["id"] for item in by_customer["items"]}, {"tx-product", "tx-purchase"})

        by_sales = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "salesperson": "user-sales"},
        ).json()
        self.assertEqual(by_sales["total"], 1)
        self.assertEqual(by_sales["items"][0]["id"], "tx-service")

        by_owner = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "salesperson": "name:王云磊"},
        ).json()
        self.assertEqual({item["id"] for item in by_owner["items"]}, {"tx-product", "tx-purchase"})

        by_date = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "dateFrom": "2026-09-03", "dateTo": "2026-09-03"},
        ).json()
        self.assertEqual(by_date["total"], 1)
        self.assertEqual(by_date["items"][0]["id"], "tx-purchase")

        by_bank = self.client.get(
            "/api/collections/financeStatements/",
            {"paged": 1, "collectionAccountId": "acc-own"},
        ).json()
        self.assertGreaterEqual(by_bank["total"], 1)
        self.assertTrue(all(item.get("bankName") == "齐鲁银行" or "62220001" in (item.get("accountNumber") or "") for item in by_bank["items"]))

    def test_skips_transactions_whose_project_and_order_were_deleted(self):
        from apps.data_store.models import TransactionRecord

        TransactionRecord.objects.update_or_create(
            id="tx-orphan",
            defaults={
                "project_id": "pj-deleted",
                "type": "收款",
                "amount": 1000,
                "date": "2026-09-02",
                "status": "已匹配",
                "data": {
                    "id": "tx-orphan",
                    "projectId": "pj-deleted",
                    "serviceOrderId": "svc-deleted",
                    "type": "收款",
                    "amount": 1000,
                    "status": "已匹配",
                    "counterpartyOrgId": "org-service-customer",
                    "occurredAt": "2026-09-02T12:00:00",
                    "createdAt": "2026-09-02T12:00:00",
                },
                "is_deleted": False,
            },
        )
        statements = self.client.get("/api/collections/financeStatements/", {"paged": 1}).json()
        self.assertEqual(statements["total"], 3)
        self.assertNotIn("tx-orphan", [item["id"] for item in statements["items"]])

        tx_list = self.client.get(
            "/api/collections/transactions/",
            {"paged": 1, "page_size": 50},
        ).json()
        self.assertNotIn("tx-orphan", [item["id"] for item in tx_list["items"]])
        response = self.client.get(
            "/api/collections/financeStatements/",
            {"businessKind": "商品", "customerOrgId": "org-customer"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("page", payload)
        ids = [item["id"] for item in payload["data"]]
        self.assertEqual(ids, ["tx-product"])
        self.assertEqual(payload["data"][0]["businessKind"], "商品")

    def test_requires_finance_view(self):
        save_app_data(
            {
                "roles": [{"id": "role-admin", "name": "管理员", "permissions": ["dashboard.view"]}],
            },
            partial=True,
        )
        response = self.client.get("/api/collections/financeStatements/", {"paged": 1})
        self.assertEqual(response.status_code, 403)
