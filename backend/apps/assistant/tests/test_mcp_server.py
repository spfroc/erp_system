from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.test.client import Client

from apps.assistant.services.mcp_server import list_mcp_tools
from apps.assistant.tools import reset_registration_for_tests


@override_settings(ROOT_URLCONF="config.urls")
class McpServerTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()
        self.client = Client()

    def test_list_mcp_tools_read_only(self):
        with patch.dict("os.environ", {"ASSISTANT_MCP_EXCLUDE_TOOLS": "navigation.find,devops.get_status"}, clear=False):
            names = {item["name"] for item in list_mcp_tools()}
        self.assertIn("notice.search", names)
        self.assertIn("erp.product.search", names)
        self.assertIn("erp.platform_account.search", names)
        self.assertIn("erp.platform_account.create", names)
        self.assertIn("erp.platform_account.update", names)
        self.assertNotIn("erp.invoice.delete", names)
        self.assertNotIn("devops.run_safe_job", names)
        self.assertNotIn("navigation.find", names)
        self.assertNotIn("devops.get_status", names)

    def test_mcp_disabled(self):
        with patch.dict("os.environ", {"ASSISTANT_MCP_ENABLED": "false", "ASSISTANT_MCP_TOKEN": "secret"}, clear=False):
            response = self.client.post(
                "/api/mcp/",
                data='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer secret",
            )
        self.assertEqual(response.status_code, 503)

    def test_mcp_unauthorized(self):
        with patch.dict(
            "os.environ",
            {"ASSISTANT_MCP_ENABLED": "true", "ASSISTANT_MCP_TOKEN": "secret-token"},
            clear=False,
        ):
            response = self.client.post(
                "/api/mcp/",
                data='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 401)

    def test_initialize_and_tools_list(self):
        with patch.dict(
            "os.environ",
            {"ASSISTANT_MCP_ENABLED": "true", "ASSISTANT_MCP_TOKEN": "secret-token"},
            clear=False,
        ):
            init = self.client.post(
                "/api/mcp/",
                data=(
                    '{"jsonrpc":"2.0","id":1,"method":"initialize",'
                    '"params":{"protocolVersion":"2025-06-18","capabilities":{},'
                    '"clientInfo":{"name":"test","version":"1"}}}'
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer secret-token",
                HTTP_ACCEPT="application/json, text/event-stream",
            )
            self.assertEqual(init.status_code, 200)
            body = init.json()
            self.assertEqual(body["result"]["serverInfo"]["name"], "yzc-erp-assistant")
            self.assertTrue(init.headers.get("Mcp-Session-Id"))

            listed = self.client.post(
                "/api/mcp/",
                data='{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer secret-token",
                HTTP_ACCEPT="application/json, text/event-stream",
            )
        self.assertEqual(listed.status_code, 200)
        tools = listed.json()["result"]["tools"]
        names = {item["name"] for item in tools}
        self.assertIn("notice.search", names)
        self.assertNotIn("erp.invoice.delete", names)

    def test_initialized_notification_accepted(self):
        with patch.dict(
            "os.environ",
            {"ASSISTANT_MCP_ENABLED": "true", "ASSISTANT_MCP_TOKEN": "secret-token"},
            clear=False,
        ):
            response = self.client.post(
                "/api/mcp/",
                data='{"jsonrpc":"2.0","method":"notifications/initialized"}',
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer secret-token",
            )
        self.assertEqual(response.status_code, 202)

    @patch("apps.assistant.services.mcp_server.execute_tool")
    def test_tools_call(self, execute_tool):
        execute_tool.return_value = {
            "tool_name": "notice.search",
            "status": "completed",
            "content": "找到 1 条公告。",
            "summary": "找到 1 条公告。",
            "data": {"items": [{"id": 1}], "total": 1},
        }
        with patch.dict(
            "os.environ",
            {"ASSISTANT_MCP_ENABLED": "true", "ASSISTANT_MCP_TOKEN": "secret-token"},
            clear=False,
        ):
            response = self.client.post(
                "/api/mcp/",
                data=(
                    '{"jsonrpc":"2.0","id":3,"method":"tools/call",'
                    '"params":{"name":"notice.search","arguments":{"search":"打印机"}}}'
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer secret-token",
            )
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertFalse(result["isError"])
        self.assertIn("找到 1 条公告", result["content"][0]["text"])
        execute_tool.assert_called_once()
