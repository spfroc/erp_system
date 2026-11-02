"""业务场景 A–I 的规则路由 / 降级验收（模型用替身）。"""

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.services.intent_router import resolve_intent
from apps.assistant.tools import reset_registration_for_tests


class ScenarioRoutingTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()

    def test_a_notice_search(self):
        routed = resolve_intent("查找最近一个月济南市办公设备采购公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertEqual(routed["mode"], "rule_only")

    def test_b_goods_search(self):
        routed = resolve_intent("查找惠普打印机相关采购记录")
        self.assertEqual(routed["tool_name"], "goods.search")

    def test_c_buyer_profile(self):
        routed = resolve_intent("查询这家医院过去一年采购过什么商品")
        self.assertIn(routed["tool_name"], {"buyer.get_profile", "buyer.search"})

    def test_d_erp_product(self):
        routed = resolve_intent("查找商品名称中包含交换机的商品")
        self.assertEqual(routed["tool_name"], "erp.product.search")

    def test_e_purchase_order(self):
        routed = resolve_intent("查询最近三十天未完成的采购订单")
        self.assertEqual(routed["tool_name"], "erp.purchase_order.search")

    def test_e2_customer_expiry(self):
        routed = resolve_intent("查询客户的到期时间")
        self.assertEqual(routed["tool_name"], "erp.customer.expiry")

    def test_e3_project_status(self):
        routed = resolve_intent("26922000001159238971 查询该项目的开票状态")
        self.assertEqual(routed["tool_name"], "erp.project.status")

    def test_f_navigation(self):
        routed = resolve_intent("打开销售订单管理")
        self.assertEqual(routed["tool_name"], "navigation.find")

    def test_g_devops_status(self):
        routed = resolve_intent("查看最近执行失败的采集任务")
        self.assertEqual(routed["tool_name"], "devops.get_status")

    def test_h_write_preview_route(self):
        routed = resolve_intent("运行安全任务 12")
        self.assertEqual(routed["tool_name"], "devops.run_safe_job")
        self.assertEqual(routed["params"]["job_id"], 12)

    @patch("apps.assistant.services.intent_router.probe_llm", return_value={"online": False})
    @patch(
        "apps.assistant.services.intent_router.llm_config",
        return_value={
            "enabled": True,
            "fallback_enabled": True,
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "tiny",
            "timeout": 5,
            "max_output_tokens": 128,
            "api_key": "local",
        },
    )
    def test_i_model_offline_still_rules(self, cfg, probe):
        routed = resolve_intent("查找最近一个月济南市办公设备采购公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertEqual(routed["mode"], "rule_only")
        unclear = resolve_intent("随便聊聊天气")
        self.assertEqual(unclear["mode"], "degraded")
        self.assertTrue(unclear["needs_clarification"])
