from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.assistant.services.orchestrator import handle_chat


class OrchestratorTests(SimpleTestCase):
    def _user(self):
        return {"id": "u1", "permissions": ["assistant.use", "notice.view", "dashboard.view", "salesOrder.view"]}

    @patch("apps.assistant.services.orchestrator.execute_tool")
    @patch("apps.assistant.services.orchestrator.update_context", return_value={})
    @patch("apps.assistant.services.orchestrator.append_message")
    @patch("apps.assistant.services.orchestrator.create_conversation")
    def test_rule_chat_notice_search(self, create_conv, append_msg, update_ctx, execute_tool):
        conversation = MagicMock(id=10, context_json={})
        create_conv.return_value = conversation
        append_msg.side_effect = [
            MagicMock(id=1),
            MagicMock(id=2),
        ]
        execute_tool.return_value = {
            "execution_id": 99,
            "block_type": "notice_list",
            "content": "找到 2 条公告。",
            "summary": "找到 2 条公告。",
            "data": {"items": [{"id": 101}, {"id": 102}], "total": 2, "page": 1},
        }

        result = handle_chat(
            user_data=self._user(),
            message="查找最近一个月济南市办公设备采购公告",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["mode"], "rule_only")
        self.assertEqual(result["intent"], "notice.search")
        self.assertEqual(result["blocks"][0]["type"], "notice_list")
        execute_tool.assert_called_once()
        self.assertEqual(execute_tool.call_args.kwargs["tool_name"], "notice.search")

    @patch("apps.assistant.services.orchestrator.update_context", return_value={})
    @patch("apps.assistant.services.orchestrator.append_message")
    @patch("apps.assistant.services.orchestrator.create_conversation")
    def test_clarification_when_unrecognized(self, create_conv, append_msg, update_ctx):
        conversation = MagicMock(id=11, context_json={})
        create_conv.return_value = conversation
        append_msg.side_effect = [MagicMock(id=1), MagicMock(id=2)]

        result = handle_chat(user_data=self._user(), message="今天天气怎么样")
        self.assertEqual(result["intent"], "clarification")
        self.assertEqual(result["blocks"][0]["type"], "clarification")
        update_ctx.assert_called()
