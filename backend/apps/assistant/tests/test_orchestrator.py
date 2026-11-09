from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.assistant.services.orchestrator import handle_chat
from apps.assistant.tools import reset_registration_for_tests


class OrchestratorTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()

    def _user(self):
        return {"id": "u1", "permissions": ["assistant.use", "notice.view", "dashboard.view", "salesOrder.view"]}

    @patch("apps.assistant.services.orchestrator.get_user_settings", return_value={})
    @patch("apps.assistant.services.orchestrator.resolve_intent")
    @patch("apps.assistant.services.orchestrator.execute_tool")
    @patch("apps.assistant.services.orchestrator.update_context", return_value={})
    @patch("apps.assistant.services.orchestrator.append_message")
    @patch("apps.assistant.services.orchestrator.create_conversation")
    def test_llm_chat_notice_search(self, create_conv, append_msg, update_ctx, execute_tool, resolve, _settings):
        conversation = MagicMock(id=10, context_json={})
        create_conv.return_value = conversation
        append_msg.side_effect = [
            MagicMock(id=1),
            MagicMock(id=2),
        ]
        resolve.return_value = {
            "intent": "notice.search",
            "tool_name": "notice.search",
            "params": {"relative_period": "last_30_days"},
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "llm",
            "mode": "llm_assisted",
        }
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
        self.assertEqual(result["mode"], "llm_assisted")
        self.assertEqual(result["intent"], "notice.search")
        self.assertEqual(result["blocks"][0]["type"], "notice_list")
        execute_tool.assert_called_once()
        self.assertEqual(execute_tool.call_args.kwargs["tool_name"], "notice.search")

    @patch("apps.assistant.services.orchestrator.get_user_settings", return_value={})
    @patch("apps.assistant.services.orchestrator.resolve_intent")
    @patch("apps.assistant.services.orchestrator.update_context", return_value={})
    @patch("apps.assistant.services.orchestrator.append_message")
    @patch("apps.assistant.services.orchestrator.create_conversation")
    def test_clarification_when_unrecognized(self, create_conv, append_msg, update_ctx, resolve, _settings):
        conversation = MagicMock(id=11, context_json={})
        create_conv.return_value = conversation
        append_msg.side_effect = [MagicMock(id=1), MagicMock(id=2)]
        resolve.return_value = {
            "intent": "clarification",
            "tool_name": None,
            "params": {},
            "confidence": 0.1,
            "needs_clarification": True,
            "reason": "unrecognized",
            "clarification": "请说明要查询的业务。",
            "mode": "llm_assisted",
        }

        result = handle_chat(user_data=self._user(), message="今天天气怎么样")
        self.assertEqual(result["intent"], "clarification")
        self.assertEqual(result["blocks"][0]["type"], "clarification")
        update_ctx.assert_called()

    @patch("apps.assistant.services.orchestrator.get_user_settings", return_value={})
    @patch("apps.assistant.services.orchestrator.resolve_intent")
    @patch("apps.assistant.services.orchestrator.update_context", return_value={})
    @patch("apps.assistant.services.orchestrator.append_message")
    @patch("apps.assistant.services.orchestrator.create_conversation")
    def test_missing_mode_unrecognized_not_rule_only(self, create_conv, append_msg, update_ctx, resolve, _settings):
        conversation = MagicMock(id=12, context_json={})
        create_conv.return_value = conversation
        append_msg.side_effect = [MagicMock(id=1), MagicMock(id=2)]
        resolve.return_value = {
            "intent": "clarification",
            "tool_name": None,
            "params": {},
            "confidence": 0.2,
            "needs_clarification": True,
            "reason": "defer_analytics_to_llm",
            "clarification": "我还不能确定要执行的操作。你可以试试：查询采购公告。",
            # 故意缺 mode，模拟旧路由/异常返回
        }

        result = handle_chat(user_data=self._user(), message="使用柱状图表帮我统计下近7天采购公告类型")
        self.assertEqual(result["intent"], "clarification")
        self.assertEqual(result["mode"], "degraded")
        self.assertNotEqual(result["mode"], "rule_only")
