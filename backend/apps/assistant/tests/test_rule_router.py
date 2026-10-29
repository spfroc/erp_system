from django.test import SimpleTestCase

from apps.assistant.services.rule_router import route_intent


class RuleRouterTests(SimpleTestCase):
    def test_notice_search(self):
        routed = route_intent("查找最近一个月济南市办公设备采购公告")
        self.assertEqual(routed["tool_name"], "notice.search")
        self.assertFalse(routed["needs_clarification"])

    def test_goods_search(self):
        routed = route_intent("查找惠普打印机相关采购记录")
        self.assertEqual(routed["tool_name"], "goods.search")

    def test_sales_order(self):
        routed = route_intent("查询最近三十天未完成的销售订单")
        self.assertEqual(routed["tool_name"], "erp.sales_order.search")

    def test_navigation(self):
        routed = route_intent("打开销售订单管理")
        self.assertEqual(routed["tool_name"], "navigation.find")

    def test_followup_open_first(self):
        routed = route_intent("打开第一条", {"recent_result_ids": [101, 102], "intent": "notice.search"})
        self.assertEqual(routed["tool_name"], "notice.get_detail")
        self.assertEqual(routed["params"]["notice_id"], 101)

    def test_unrecognized_needs_clarification(self):
        routed = route_intent("今天天气怎么样")
        self.assertTrue(routed["needs_clarification"])
