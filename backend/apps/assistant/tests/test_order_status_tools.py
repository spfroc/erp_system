from django.test import TestCase

from apps.assistant.services.rule_router import route_intent
from apps.assistant.services.tool_executor import ToolExecutionError, execute_tool
from apps.assistant.tools import reset_registration_for_tests
from apps.data_store.models import RoleRecord, SalesOrderRecord, UserRecord


class OrderStatusToolsTests(TestCase):
    def setUp(self):
        reset_registration_for_tests()
        RoleRecord.objects.create(
            id="role-order-status",
            name="订单状态测试",
            data={
                "id": "role-order-status",
                "name": "订单状态测试",
                "permissions": [
                    "assistant.use",
                    "salesOrder.view",
                    "salesOrder.manage",
                ],
            },
        )
        self.user = UserRecord.objects.create(
            id="user-order-status",
            name="订单测试员",
            phone="18600000888",
            status="启用",
            data={
                "id": "user-order-status",
                "name": "订单测试员",
                "phone": "18600000888",
                "status": "启用",
                "roleIds": ["role-order-status"],
                "password": "x",
            },
        )
        self.user_data = dict(self.user.data)
        self.order = SalesOrderRecord.objects.create(
            id="so-status-1",
            project_id="proj-1",
            order_no="SO-STATUS-001",
            customer_org_id="org-1",
            amount=100,
            receivable_amount=100,
            received_amount=0,
            status="待付款",
            data={
                "id": "so-status-1",
                "projectId": "proj-1",
                "orderNo": "SO-STATUS-001",
                "customerOrgId": "org-1",
                "amount": "100",
                "status": "待付款",
            },
        )

    def test_rule_router_extracts_order_status_update(self):
        routed = route_intent("把销售订单 SO-STATUS-001 状态改为已付款")
        self.assertEqual(routed["tool_name"], "erp.sales_order.update_status")
        self.assertEqual(routed["params"]["order_no"], "SO-STATUS-001")
        self.assertEqual(routed["params"]["status"], "已付款")

    def test_update_requires_permission(self):
        user = {
            "id": "u-no-perm",
            "permissions": ["assistant.use"],
        }
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool(
                tool_name="erp.sales_order.update_status",
                params={"order_no": "SO-STATUS-001", "status": "已付款"},
                user_data=user,
                confirmed=False,
            )
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_update_status_with_confirmation(self):
        preview = execute_tool(
            tool_name="erp.order.update_status",
            params={"order_no": "SO-STATUS-001", "status": "已付款"},
            user_data=self.user_data,
            confirmed=False,
        )
        self.assertEqual(preview["status"], "awaiting_confirmation")
        self.assertIn("SO-STATUS-001", preview["content"])

        result = execute_tool(
            tool_name="erp.order.update_status",
            params={"order_no": "SO-STATUS-001", "status": "已付款"},
            user_data=self.user_data,
            confirmed=True,
        )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["data"]["updated"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "已付款")
        self.assertEqual((self.order.data or {}).get("status"), "已付款")

    def test_invalid_transition(self):
        self.order.status = "已付款"
        data = dict(self.order.data or {})
        data["status"] = "已付款"
        self.order.data = data
        self.order.save()
        result = execute_tool(
            tool_name="erp.sales_order.update_status",
            params={"order_no": "SO-STATUS-001", "status": "待付款"},
            user_data=self.user_data,
            confirmed=True,
        )
        self.assertEqual(result["block_type"], "clarification")
        self.assertIn("不能改为", result["content"])
