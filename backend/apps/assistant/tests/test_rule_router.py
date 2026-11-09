from django.test import SimpleTestCase

from apps.assistant.services.rule_router import route_intent


class RuleRouterTests(SimpleTestCase):
    def test_notice_search(self):
        routed = route_intent("查找最近一个月济南市办公设备采购公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertFalse(routed["needs_clarification"])
        self.assertEqual(routed["params"].get("relative_period"), "last_30_days")

    def test_notice_search_by_project_code(self):
        routed = route_intent("查询SDGP371400000202601002301_A项目相关的公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertEqual(routed["reason"], "notice_project_code")
        self.assertEqual(routed["params"].get("project_code"), "SDGP371400000202601002301_A")
        self.assertEqual(routed["params"].get("search"), "SDGP371400000202601002301_A")

    def test_notice_yesterday_buyer(self):
        routed = route_intent("查询昨天 平度市财政局 发布的公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertEqual(routed["params"].get("relative_period"), "yesterday")
        self.assertEqual(routed["params"].get("buyer_name"), "平度市财政局")
        self.assertNotIn("昨天", routed["params"].get("search") or "")

    def test_fresh_query_does_not_keep_dirty_search(self):
        routed = route_intent(
            "查询昨天 平度市财政局 发布的公告",
            {
                "intent": "notice.search",
                "params": {
                    "search": "昨天 平度市财政局 发布的",
                    "page": 1,
                    "page_size": 20,
                },
            },
        )
        self.assertEqual(routed["reason"], "notice")
        self.assertNotIn("search", routed["params"])
        self.assertEqual(routed["params"].get("buyer_name"), "平度市财政局")

    def test_goods_search(self):
        routed = route_intent("查找惠普打印机相关采购记录")
        self.assertEqual(routed["tool_name"], "goods.search")

    def test_sales_order(self):
        routed = route_intent("查询最近三十天未完成的销售订单")
        self.assertEqual(routed["tool_name"], "erp.sales_order.search")

    def test_customer_expiry(self):
        routed = route_intent("查询客户的到期时间")
        self.assertEqual(routed["tool_name"], "erp.customer.expiry")

    def test_customer_expiry_complex_defers_to_llm(self):
        routed = route_intent("两个月内要到期的服务项目，已经续费的客户的项目不要查，只要查周期类型的")
        self.assertIsNone(routed.get("tool_name"))
        self.assertEqual(routed.get("reason"), "defer_customer_expiry_to_llm")
        self.assertTrue(routed.get("needs_clarification"))

    def test_customer_expiry_simple_keeps_params(self):
        routed = route_intent("查询两个月内要到期的服务项目")
        self.assertEqual(routed["tool_name"], "erp.customer.expiry")
        self.assertEqual(routed["params"].get("within_months"), 2)
        self.assertFalse(routed["params"].get("include_overdue"))
        self.assertFalse(routed["params"].get("customer"))
        self.assertFalse(routed["params"].get("keyword"))

    def test_platform_account_search_strips_request_noise(self):
        routed = route_intent("山东云谷的平台账号和密码发我")
        self.assertEqual(routed["tool_name"], "erp.platform_account.search")
        self.assertEqual(routed["params"].get("keyword"), "山东云谷")

    def test_deal_today_count_has_no_junk_buyer(self):
        routed = route_intent("今天发布了多少成交公告？")
        self.assertEqual(routed["tool_name"], "deal.search")
        self.assertEqual(routed["params"].get("relative_period"), "today")
        self.assertFalse(routed["params"].get("buyer_name"))
        self.assertFalse(routed["params"].get("search"))

    def test_deal_stats_this_month(self):
        routed = route_intent("本月成交金额")
        self.assertEqual(routed["tool_name"], "deal.stats")
        self.assertEqual(routed["params"].get("relative_period"), "this_month")
        self.assertFalse(routed["params"].get("buyer_name"))

    def test_deal_stats_buyer_last_month(self):
        routed = route_intent("查询 邹平市投资促进中心 上个月的成交额")
        self.assertEqual(routed["tool_name"], "deal.stats")
        self.assertEqual(routed["params"].get("relative_period"), "last_month")
        self.assertEqual(routed["params"].get("buyer_name"), "邹平市投资促进中心")
        self.assertFalse(routed["params"].get("search"))

    def test_deal_suppliers_this_month(self):
        routed = route_intent("邹平市投资促进中心本月采购了哪几家供应商？")
        self.assertEqual(routed["tool_name"], "deal.suppliers")
        self.assertEqual(routed["params"].get("relative_period"), "this_month")
        self.assertEqual(routed["params"].get("buyer_name"), "邹平市投资促进中心")
        self.assertFalse(routed["params"].get("search"))

    def test_customer_expiry_within_months(self):
        routed = route_intent("查询一个月内过期的用户")
        self.assertEqual(routed["tool_name"], "erp.customer.expiry")
        self.assertEqual(routed["params"].get("within_months"), 1)
        self.assertFalse(routed["params"].get("customer"))
        self.assertTrue(routed["params"].get("include_overdue"))

    def test_customer_expiry_six_months(self):
        routed = route_intent("查询六个月内过期的用户")
        self.assertEqual(routed["tool_name"], "erp.customer.expiry")
        self.assertEqual(routed["params"].get("within_months"), 6)
        self.assertTrue(routed["params"].get("include_overdue"))

    def test_analytics_queries_defer_to_llm(self):
        """统计/图表类不由规则硬编码，交给模型选工具。"""
        for text in (
            "本月服务项目和商品项目的流水分别是多少",
            "本月销售情况",
            "使用柱状图表帮我统计下近7天公告数据的类型和数量",
            "使用柱状图表帮我统计下近7天采购公告类型",
            "帮我统计商品销售订单/采购订单的总金额，还有已经开完发票的总金额",
        ):
            routed = route_intent(text)
            self.assertTrue(
                routed.get("needs_clarification") or not routed.get("tool_name"),
                msg=f"expected defer-to-llm for: {text} got {routed}",
            )
            if "销售订单" in text and "总金额" in text:
                self.assertEqual(routed.get("reason"), "defer_erp_amount_stats_to_llm")
                self.assertNotEqual(routed.get("tool_name"), "erp.sales_order.search")

    def test_analytics_not_captured_by_followup_refine(self):
        """已有公告会话时，『近7天…统计』不得被 followup 的『近』截走。"""
        routed = route_intent(
            "使用柱状图表帮我统计下近7天采购公告类型",
            {"intent": "notice.search", "params": {"search": "济南"}, "recent_result_ids": [1]},
        )
        self.assertEqual(routed.get("reason"), "defer_analytics_to_llm")
        self.assertTrue(routed.get("needs_clarification"))
        self.assertIsNone(routed.get("tool_name"))

    def test_customer_service_orders(self):
        routed = route_intent("查询某某公司的服务订单")
        self.assertEqual(routed["tool_name"], "erp.service_order.search")
        self.assertIn("某某公司", routed["params"].get("customer") or "")

    def test_customer_product_orders(self):
        routed = route_intent("查询某个客户购买的商品订单")
        self.assertEqual(routed["tool_name"], "erp.sales_order.search")

    def test_project_invoice_status(self):
        routed = route_intent("26922000001159238971 查询该项目的开票状态")
        self.assertEqual(routed["tool_name"], "erp.project.status")
        self.assertEqual(routed["params"].get("project_no"), "26922000001159238971")

    def test_navigation(self):
        routed = route_intent("打开销售订单管理")
        self.assertEqual(routed["tool_name"], "navigation.find")
        self.assertEqual(routed["params"].get("keyword"), "销售订单")

    def test_help(self):
        routed = route_intent("/help")
        self.assertEqual(routed["intent"], "help")
        self.assertIn("采购", routed.get("clarification") or "")

    def test_delete_invoice_routes_to_tool(self):
        routed = route_intent("删除 26372000005015205376 发票")
        self.assertEqual(routed["tool_name"], "erp.invoice.delete")
        self.assertEqual(routed["params"].get("invoice_no"), "26372000005015205376")

    def test_refuse_delete_order(self):
        routed = route_intent("删除销售订单 SO-1")
        self.assertTrue(routed["needs_clarification"])
        self.assertEqual(routed["reason"], "refuse_dangerous_write")

    def test_followup_open_first(self):
        routed = route_intent("打开第一条", {"recent_result_ids": [101, 102], "intent": "notice.search"})
        self.assertEqual(routed["tool_name"], "notice.get_detail")
        self.assertEqual(routed["params"]["notice_id"], 101)

    def test_unrecognized_needs_clarification(self):
        routed = route_intent("今天天气怎么样")
        self.assertTrue(routed["needs_clarification"])
