from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.services.intent_router import resolve_intent
from apps.assistant.services.llm_adapter import LlmUnavailable
from apps.assistant.tools import reset_registration_for_tests


class IntentRouterTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()

    def test_rule_priority_skips_llm(self):
        with patch("apps.assistant.services.intent_router.chat_completion_json") as chat:
            routed = resolve_intent("查找最近一个月济南市办公设备采购公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertEqual(routed["mode"], "rule_only")
        chat.assert_not_called()

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": True})
    @patch("apps.assistant.services.intent_router.llm_config")
    @patch("apps.assistant.services.intent_router.chat_completion_json")
    def test_llm_assists_when_rule_unclear(self, chat, cfg, probe):
        cfg.return_value = {
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
        }
        chat.return_value = {
            "ok": True,
            "data": {
                "tool_name": "erp.product.search",
                "params": {"keyword": "交换机"},
                "confidence": 0.7,
                "clarification": None,
                "reason": "llm",
            },
            "duration_ms": 12,
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "total_tokens": 100,
                "source": "exact",
            },
        }
        routed = resolve_intent(
            "帮我找一下那个网络设备型号资料",
            system_prompt_addon="回答尽量简洁",
        )
        self.assertEqual(routed["tool_name"], "erp.product.search")
        self.assertEqual(routed["mode"], "llm_assisted")
        self.assertEqual(routed["params"]["keyword"], "交换机")
        self.assertEqual(routed["llm_usage"]["total_tokens"], 100)
        self.assertEqual(routed["llm_usage"]["source"], "exact")
        system_prompt = chat.call_args.kwargs["system_prompt"]
        self.assertIn("ERP意图解析器", system_prompt)
        self.assertIn("用户个人偏好", system_prompt)
        self.assertIn("回答尽量简洁", system_prompt)

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": True})
    @patch("apps.assistant.services.intent_router.llm_config")
    @patch("apps.assistant.services.intent_router.chat_completion_json")
    def test_analytics_goes_through_llm(self, chat, cfg, probe):
        cfg.return_value = {
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
            "intent_timeout": 20,
        }
        chat.return_value = {
            "ok": True,
            "data": {
                "tool_name": "notice.stats",
                "params": {"relative_period": "last_7_days"},
                "confidence": 0.9,
                "clarification": None,
                "reason": "llm",
            },
            "duration_ms": 20,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "source": "exact"},
        }
        routed = resolve_intent("使用柱状图表帮我统计下近7天公告数据的类型和数量")
        self.assertEqual(routed["mode"], "llm_assisted")
        self.assertEqual(routed["tool_name"], "notice.stats")
        self.assertEqual(routed["params"].get("relative_period"), "last_7_days")
        chat.assert_called_once()

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": True})
    @patch("apps.assistant.services.intent_router.llm_config")
    @patch("apps.assistant.services.intent_router.chat_completion_json")
    def test_order_amount_stats_goes_through_llm(self, chat, cfg, probe):
        """含『销售订单』的金额统计不得走规则列表快路径。"""
        cfg.return_value = {
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
            "intent_timeout": 20,
        }
        chat.return_value = {
            "ok": True,
            "data": {
                "tool_name": "erp.sales.overview",
                "params": {"relative_period": "this_month"},
                "confidence": 0.9,
                "clarification": None,
                "reason": "llm",
            },
            "duration_ms": 20,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "source": "exact"},
        }
        routed = resolve_intent("帮我统计商品销售订单/采购订单的总金额，还有已经开完发票的总金额")
        self.assertEqual(routed["mode"], "llm_assisted")
        self.assertEqual(routed["tool_name"], "erp.sales.overview")
        chat.assert_called_once()

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": False})
    @patch("apps.assistant.services.intent_router.llm_config")
    def test_degrade_when_offline(self, cfg, probe):
        cfg.return_value = {
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
        }
        routed = resolve_intent("随便聊聊")
        self.assertTrue(routed["needs_clarification"])
        self.assertEqual(routed["mode"], "degraded")
        self.assertNotIn("我还不能确定要执行的操作", routed.get("clarification") or "")

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": True})
    @patch("apps.assistant.services.intent_router.llm_config")
    def test_degrade_analytics_when_llm_disabled(self, cfg, probe):
        cfg.return_value = {
            "enabled": False,
            "fallback_enabled": True,
            "base_url": "",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "",
        }
        routed = resolve_intent("使用柱状图表帮我统计下近7天采购公告类型")
        self.assertEqual(routed["mode"], "degraded")
        self.assertTrue(routed["needs_clarification"])
        self.assertNotIn("我还不能确定要执行的操作", routed.get("clarification") or "")
        self.assertIn("模型", routed.get("clarification") or "")

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": True})
    @patch("apps.assistant.services.intent_router.llm_config")
    @patch("apps.assistant.services.intent_router.chat_completion_json")
    def test_reject_unknown_tool_from_llm(self, chat, cfg, probe):
        cfg.return_value = {
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
        }
        chat.return_value = {
            "ok": True,
            "data": {"tool_name": "hack.shell", "params": {}, "confidence": 0.9},
            "duration_ms": 3,
        }
        routed = resolve_intent("执行神秘指令")
        self.assertIsNone(routed["tool_name"])
        self.assertTrue(routed["needs_clarification"])

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": True})
    @patch("apps.assistant.services.intent_router.llm_config")
    @patch(
        "apps.assistant.services.intent_router.chat_completion_json",
        side_effect=LlmUnavailable("llm_error", "timeout"),
    )
    def test_fallback_on_llm_error(self, chat, cfg, probe):
        cfg.return_value = {
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
        }
        routed = resolve_intent("模糊业务")
        self.assertEqual(routed["mode"], "degraded")
        self.assertTrue(routed["needs_clarification"])
