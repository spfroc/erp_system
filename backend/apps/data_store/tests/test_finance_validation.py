from django.test import SimpleTestCase

from apps.data_store.views import _finance_validation, _order_amount


class FinanceValidationTests(SimpleTestCase):
    def test_order_amount_prefers_receivable_over_product_price(self):
        self.assertEqual(_order_amount({"amount": 1990, "receivableAmount": 1000}), 1000)
        self.assertEqual(_order_amount({"amount": 1990}), 1990)

    def test_flags_when_transactions_match_product_price_but_not_order_amount(self):
        result = _finance_validation({
            "organizations": [
                {"id": "c1", "name": "客户甲"},
                {"id": "own1", "name": "本公司乙"},
            ],
            "salesOrders": [{
                "id": "so-1",
                "orderNo": "SO-1",
                "projectId": "pj-1",
                "customerOrgId": "c1",
                "ownCompanyOrgId": "own1",
                "amount": 1990,
                "receivableAmount": 1000,
                "receivedAmount": 1990,
                "status": "已付款",
            }],
            "serviceOrders": [],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "projectNo": "XM001",
                "name": "商品项目",
                "customerOrgId": "c1",
                "ownCompanyOrgId": "own1",
                "totalAmount": 1000,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [{
                "id": "tx-1",
                "type": "收款",
                "status": "已匹配",
                "amount": 1990,
                "salesOrderId": "so-1",
            }],
        })
        codes = [item["code"] for item in result["issues"]]
        self.assertIn("order_amount_transaction_mismatch", codes)
        mismatch = next(item for item in result["issues"] if item["code"] == "order_amount_transaction_mismatch")
        self.assertEqual(mismatch["diff"], -990.0)
        self.assertEqual(mismatch["details"]["projectName"], "商品项目")
        self.assertEqual(mismatch["details"]["buyerName"], "客户甲")
        self.assertEqual(mismatch["details"]["sellerName"], "本公司乙")
        self.assertEqual(mismatch["details"]["orderAmount"], 1000.0)
        self.assertEqual(mismatch["details"]["txTotal"], 1990.0)
        self.assertNotIn("received_transaction_mismatch", codes)

    def test_paid_order_does_not_repeat_received_and_amount_mismatch(self):
        result = _finance_validation({
            "organizations": [{"id": "c1", "name": "客户甲"}, {"id": "own1", "name": "本公司乙"}],
            "salesOrders": [],
            "serviceOrders": [{
                "id": "svc-1",
                "orderNo": "SV-1",
                "projectId": "pj-1",
                "customerOrgId": "c1",
                "amount": 2000,
                "receivableAmount": 2000,
                "receivedAmount": 2000,
                "status": "已付款",
            }],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "name": "服务项目",
                "customerOrgId": "c1",
                "ownCompanyOrgId": "own1",
                "totalAmount": 2000,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [],
        })
        order_issues = [item for item in result["issues"] if item.get("targetId") == "svc-1"]
        codes = [item["code"] for item in order_issues]
        self.assertEqual(codes.count("order_amount_transaction_mismatch"), 1)
        self.assertNotIn("received_transaction_mismatch", codes)

    def test_received_mismatch_kept_when_distinct_from_order_amount(self):
        result = _finance_validation({
            "salesOrders": [{
                "id": "so-1",
                "orderNo": "SO-1",
                "projectId": "pj-1",
                "amount": 1000,
                "receivableAmount": 1000,
                "receivedAmount": 800,
                "status": "部分付款",
            }],
            "serviceOrders": [],
            "purchaseOrders": [],
            "projects": [{"id": "pj-1", "name": "商品项目", "totalAmount": 1000, "totalCost": 0}],
            "invoices": [],
            "transactions": [{
                "type": "收款",
                "status": "已匹配",
                "amount": 500,
                "salesOrderId": "so-1",
            }],
        })
        codes = [item["code"] for item in result["issues"] if item.get("targetId") == "so-1"]
        self.assertIn("received_transaction_mismatch", codes)

    def test_service_project_matches_service_order_amount_not_missing_sales_orders(self):
        result = _finance_validation({
            "organizations": [
                {"id": "c1", "name": "青岛谟诚达"},
                {"id": "own1", "name": "济南云集"},
            ],
            "salesOrders": [],
            "serviceOrders": [{
                "id": "svc-1",
                "orderNo": "SV-1",
                "projectId": "pj-1",
                "customerOrgId": "c1",
                "amount": 1000,
                "receivableAmount": 1000,
                "receivedAmount": 1000,
                "status": "已付款",
            }],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "projectNo": "XM002",
                "name": "服务项目",
                "customerOrgId": "c1",
                "ownCompanyOrgId": "own1",
                "totalAmount": 1000,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [{
                "type": "收款",
                "status": "已匹配",
                "amount": 1000,
                "serviceOrderId": "svc-1",
            }],
        })
        codes = [item["code"] for item in result["issues"]]
        self.assertNotIn("project_amount_mismatch", codes)
        self.assertNotIn("order_amount_transaction_mismatch", codes)
        self.assertNotIn("received_transaction_mismatch", codes)

    def test_project_mismatch_includes_buyer_and_seller(self):
        result = _finance_validation({
            "organizations": [
                {"id": "c1", "name": "济南燕博"},
                {"id": "own1", "name": "济南云集"},
            ],
            "salesOrders": [],
            "serviceOrders": [{
                "id": "svc-1",
                "orderNo": "SV-1",
                "projectId": "pj-1",
                "customerOrgId": "c1",
                "amount": 800,
                "receivableAmount": 800,
                "receivedAmount": 800,
                "status": "已付款",
            }],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "projectNo": "XM003",
                "name": "燕博服务项目",
                "customerOrgId": "c1",
                "ownCompanyOrgId": "own1",
                "totalAmount": 1000,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [{
                "type": "收款",
                "status": "已匹配",
                "amount": 800,
                "serviceOrderId": "svc-1",
            }],
        })
        mismatch = next(item for item in result["issues"] if item["code"] == "project_amount_mismatch")
        self.assertEqual(mismatch["details"]["projectName"], "燕博服务项目")
        self.assertEqual(mismatch["details"]["buyerName"], "济南燕博")
        self.assertEqual(mismatch["details"]["sellerName"], "济南云集")
        self.assertEqual(mismatch["details"]["projectAmount"], 1000.0)
        self.assertEqual(mismatch["details"]["orderTotal"], 800.0)

    def test_service_project_does_not_double_count_legacy_sales_order(self):
        result = _finance_validation({
            "salesOrders": [{
                "id": "so-1",
                "orderNo": "SO-1",
                "projectId": "pj-1",
                "amount": 1000,
                "receivableAmount": 1000,
                "status": "待付款",
            }],
            "serviceOrders": [{
                "id": "svc-1",
                "orderNo": "SV-1",
                "projectId": "pj-1",
                "amount": 1000,
                "receivableAmount": 1000,
                "status": "待付款",
            }],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "type": "服务项目",
                "name": "入驻服务",
                "totalAmount": 1000,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [],
        })
        self.assertNotIn("project_amount_mismatch", [item["code"] for item in result["issues"]])

    def test_product_project_still_uses_sales_orders_for_amount_check(self):
        result = _finance_validation({
            "salesOrders": [{
                "id": "so-1",
                "projectId": "pj-1",
                "amount": 1800,
                "receivableAmount": 1800,
                "status": "待付款",
            }],
            "serviceOrders": [{
                "id": "svc-1",
                "projectId": "pj-1",
                "amount": 1800,
                "receivableAmount": 1800,
                "status": "待付款",
            }],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "type": "商品项目",
                "name": "商品项目",
                "totalAmount": 1800,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [],
        })
        self.assertNotIn("project_amount_mismatch", [item["code"] for item in result["issues"]])

    def test_multi_order_invoice_skips_warning_when_lines_are_fully_allocated(self):
        result = _finance_validation({
            "salesOrders": [
                {"id": "so-a", "orderNo": "SO-A", "projectId": "pj-1", "amount": 7000, "receivableAmount": 7000, "status": "待付款"},
                {"id": "so-b", "orderNo": "SO-B", "projectId": "pj-1", "amount": 28000, "receivableAmount": 28000, "status": "待付款"},
            ],
            "serviceOrders": [],
            "purchaseOrders": [],
            "projects": [{"id": "pj-1", "name": "空调项目", "projectNo": "XM001", "totalAmount": 35000, "totalCost": 0}],
            "invoices": [{
                "id": "inv-1",
                "invoiceNo": "26372000004336828876",
                "type": "销项",
                "amount": 35000,
                "status": "已确认",
                "salesOrderIds": ["so-a", "so-b"],
                "lineItems": [
                    {"productName": "空调", "quantity": 4, "amount": 6194.69, "taxAmount": 805.31, "salesOrderId": "so-a"},
                    {"productName": "空调", "quantity": 16, "amount": 24778.76, "taxAmount": 3221.24, "salesOrderId": "so-b"},
                ],
            }],
            "transactions": [],
        })
        self.assertNotIn("invoice_multi_order_allocation_missing", [item["code"] for item in result["issues"]])

    def test_multi_order_invoice_lists_order_amounts_when_unallocated(self):
        result = _finance_validation({
            "organizations": [{"id": "c1", "name": "买方"}, {"id": "own1", "name": "卖方"}],
            "salesOrders": [
                {"id": "so-a", "orderNo": "PO-XM-01", "projectId": "pj-1", "amount": 1750, "receivableAmount": 1750, "status": "待付款"},
                {"id": "so-b", "orderNo": "PO-XM-02", "projectId": "pj-1", "amount": 3500, "receivableAmount": 3500, "status": "待付款"},
            ],
            "serviceOrders": [],
            "purchaseOrders": [],
            "projects": [{"id": "pj-1", "name": "空调项目", "projectNo": "XM001", "customerOrgId": "c1", "ownCompanyOrgId": "own1", "totalAmount": 5250, "totalCost": 0}],
            "invoices": [{
                "id": "inv-1",
                "invoiceNo": "2637",
                "type": "销项",
                "amount": 5250,
                "status": "已确认",
                "buyerName": "买方",
                "sellerName": "卖方",
                "salesOrderIds": ["so-a", "so-b"],
                "lineItems": [
                    {"productName": "空调", "quantity": 1, "amount": 1548.67, "taxAmount": 201.33, "salesOrderId": "so-a"},
                    {"productName": "空调", "quantity": 2, "amount": 3097.35, "taxAmount": 402.65},
                ],
            }],
            "transactions": [],
        })
        warning = next(item for item in result["issues"] if item["code"] == "invoice_multi_order_allocation_missing")
        self.assertEqual(warning["details"]["invoiceAmount"], 5250.0)
        allocations = warning["details"]["orderAllocations"]
        self.assertEqual({row["orderNo"] for row in allocations}, {"PO-XM-01", "PO-XM-02"})
        so_a = next(row for row in allocations if row["orderNo"] == "PO-XM-01")
        self.assertEqual(so_a["orderAmount"], 1750.0)
        self.assertEqual(so_a["allocatedAmount"], 1750.0)
        self.assertGreater(warning["details"]["unallocatedAmount"], 0)

    def test_stale_project_cost_does_not_flag_when_purchase_orders_match(self):
        result = _finance_validation({
            "salesOrders": [{"id": "so-1", "projectId": "pj-1", "amount": 1800, "receivableAmount": 1800, "status": "待付款"}],
            "serviceOrders": [],
            "purchaseOrders": [
                {"id": "po-1", "projectId": "pj-1", "amount": 14056.83, "status": "已下单"},
                {"id": "po-2", "projectId": "pj-1", "amount": 210, "status": "已取消"},
            ],
            "projects": [{
                "id": "pj-1",
                "type": "商品项目",
                "name": "青岛国显",
                "totalAmount": 1800,
                "totalCost": 13846.83,
            }],
            "invoices": [],
            "transactions": [],
        })
        self.assertNotIn("project_cost_mismatch", [item["code"] for item in result["issues"]])

    def test_ignored_project_mismatch_is_skipped(self):
        result = _finance_validation({
            "salesOrders": [],
            "serviceOrders": [],
            "purchaseOrders": [],
            "projects": [{
                "id": "pj-1",
                "name": "已终止项目",
                "status": "项目终止",
                "totalAmount": 3000,
                "totalCost": 0,
            }],
            "invoices": [],
            "transactions": [],
            "optionGroups": [{
                "key": "finance_validation_ignores",
                "items": [{"id": "project_amount_mismatch:项目:pj-1", "value": "project_amount_mismatch:项目:pj-1"}],
            }],
        })
        self.assertNotIn("project_amount_mismatch", [item["code"] for item in result["issues"]])
