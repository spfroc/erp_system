from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.assistant.permissions import ASSISTANT_USE, expand_assistant_permissions, user_has_permission
from apps.assistant.services.tool_executor import ToolExecutionError, execute_tool
from apps.assistant.services.tool_registry import get_tool, list_tools
from apps.assistant.tools import reset_registration_for_tests


REQUIRED_TOOLS = [
    "notice.search",
    "notice.get_detail",
    "notice.stats",
    "goods.search",
    "buyer.search",
    "buyer.get_profile",
    "deal.search",
    "deal.stats",
    "deal.suppliers",
    "erp.product.search",
    "erp.sales_order.search",
    "erp.purchase_order.search",
    "erp.service_order.search",
    "erp.transaction.stats",
    "erp.sales.overview",
    "erp.customer.expiry",
    "erp.project.status",
    "erp.invoice.delete",
    "navigation.find",
    "devops.get_status",
    "devops.run_safe_job",
]


class ToolRegistryTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()

    def test_required_tools_registered(self):
        names = {tool.name for tool in list_tools()}
        for name in REQUIRED_TOOLS:
            self.assertIn(name, names)
            tool = get_tool(name)
            self.assertIsNotNone(tool)
            self.assertTrue(tool.permission)
            self.assertIsNotNone(tool.handler)

    def test_assistant_permission_implies(self):
        expanded = expand_assistant_permissions(["assistant.manage"])
        self.assertIn(ASSISTANT_USE, expanded)
        self.assertIn("assistant.view", expanded)


class ToolExecutorPermissionTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()

    def _user(self, *permissions: str) -> dict:
        return {
            "id": "user-test",
            "status": "启用",
            "permissions": list(permissions),
        }

    def test_user_has_permission_direct_list(self):
        user = self._user("assistant.use", "notice.view")
        self.assertTrue(user_has_permission(user, "assistant.use"))
        self.assertTrue(user_has_permission(user, "assistant.view"))
        self.assertTrue(user_has_permission(user, "notice.view"))
        self.assertFalse(user_has_permission(user, "product.view"))

    def test_missing_assistant_use_forbidden(self):
        user = self._user("notice.view")
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool(tool_name="notice.search", params={"search": "打印机"}, user_data=user)
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_missing_business_permission_forbidden(self):
        user = self._user("assistant.use")
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool(tool_name="notice.search", params={"search": "打印机"}, user_data=user)
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_unknown_tool(self):
        user = self._user("assistant.use")
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool(tool_name="hack.shell", params={}, user_data=user)
        self.assertEqual(ctx.exception.code, "unknown_tool")

    @patch("apps.assistant.services.tool_executor.AssistantToolExecution.objects.create")
    def test_navigation_tool_runs_with_permissions(self, create_mock):
        record = MagicMock()
        record.id = 99
        create_mock.return_value = record
        user = self._user("assistant.use", "dashboard.view", "salesOrder.view")
        result = execute_tool(
            tool_name="navigation.find",
            params={"keyword": "销售订单"},
            user_data=user,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["block_type"], "navigation")
        self.assertGreaterEqual(result["data"]["total"], 1)
        create_mock.assert_called_once()
        self.assertEqual(record.status, "completed")
        record.save.assert_called()

    @patch("apps.assistant.services.tool_executor.AssistantToolExecution.objects.create")
    def test_navigation_matches_manage_suffix(self, create_mock):
        record = MagicMock()
        record.id = 100
        create_mock.return_value = record
        user = self._user("assistant.use", "dashboard.view", "salesOrder.view")
        result = execute_tool(
            tool_name="navigation.find",
            params={"keyword": "销售订单管理"},
            user_data=user,
        )
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["data"]["total"], 1)
        self.assertTrue(result["data"].get("auto_open"))
        self.assertEqual(result["data"]["items"][0]["viewId"], "salesOrders")
