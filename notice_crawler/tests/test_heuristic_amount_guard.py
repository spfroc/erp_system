import unittest

from pipeline.extractors.heuristic import HeuristicExtractor, _sane_amount


class HeuristicAmountGuardTests(unittest.TestCase):
    def setUp(self):
        self.ext = HeuristicExtractor()

    def test_sane_amount_rejects_account_like(self):
        self.assertIsNone(_sane_amount(9999999999999999.99))
        self.assertIsNone(_sane_amount(631389397))
        self.assertIsNone(_sane_amount(91370117))
        self.assertIsNone(_sane_amount(817973001421007859))
        self.assertEqual(_sane_amount(1705596.12), 1705596.12)
        self.assertEqual(_sane_amount(1182.0), 1182.0)
        # 整数但不足 8 位，保留常见成交价
        self.assertEqual(_sane_amount(9999999.0), 9999999.0)

    def test_void_notice_does_not_take_bank_account(self):
        text = """
一、项目编号：SDGP370000000202602009737
二、项目名称：空天信息大学工程采购项目
三、采购结果
废标理由：供应商不足三家，本项目废标。
五、评审专家（单一来源采购人员）名单：
徐新艳
六、代理服务收费标准及金额：
收款单位：华德诚工程项目管理有限公司；账号：817973001421007859；行号：313451009690
代理服务费金额：0元。
1.采购人信息
名称：
空天信息大学(筹)
地址：
山东省济南市章丘区大学路1686号
"""
        out = self.ext.extract(text, title="空天信息大学工程采购项目结果公告（采购包1）")
        self.assertIsNone(out.get("deal_amount"))
        self.assertEqual(out.get("buyer_name"), "空天信息大学(筹)")

    def test_bank_account_not_used_as_deal_amount(self):
        text = """
二、成交结果
成交供应商：山东时代暖阳教育装备有限公司
代理服务费：名称：金招（山东）项目管理有限公司，银行账户：631389397
代理服务费金额：1182元。
1.采购人信息
名称：山东商业职业技术大学
"""
        out = self.ext.extract(text, title="UPS电池更换结果公告")
        self.assertNotEqual(out.get("deal_amount"), 631389397)
        if out.get("deal_amount") is not None:
            self.assertLess(out["deal_amount"], 10_000_000)

    def test_gpfa_product_category_is_name_and_name_is_spec(self):
        text = """
四、成交标的
产品名称
技术规格
数量
单价（元）
金额（元）
复印纸
晨光/M&G, 红晨光多功能复印纸70gA4-8包APYVQ957, APYVQ957;
17
￥176.00
￥2992.00
合计
￥2992.00
五、公告期限
"""
        out = self.ext.extract(text, title="平度市同和街道白埠小学复印纸直接选定结果公告")
        goods = out.get("goods") or []
        self.assertEqual(len(goods), 1)
        self.assertEqual(goods[0]["category"], "复印纸")
        self.assertIn("红晨光多功能复印纸", goods[0]["name"])
        self.assertEqual(goods[0]["brand"], "晨光")
        self.assertEqual(goods[0]["quantity"], 17)

    def test_missing_start_time_uses_publish_time(self):
        from datetime import datetime
        from types import SimpleNamespace

        from pipeline.parse_llm import enrich_from_raw

        published = datetime(2026, 11, 12, 14, 9, 12)
        raw = SimpleNamespace(
            detail_json=None,
            list_json=None,
            title="复印纸直接选定结果公告",
            district_name=None,
            region_guid=None,
            region_name="青岛市",
            publish_time=published,
            site_id="sd-gpfa-frame",
            content_text="五、公告期限\n发布日期:\n2026年11月12日",
            content_html=None,
            notice_type="1",
            notice_key="908599293131292672",
            auction_type="17",
        )
        parsed = enrich_from_raw({"goods": [{"name": "规格", "category": "复印纸"}]}, raw)
        self.assertEqual(parsed["start_time"], published)
        kept = enrich_from_raw(
            {"goods": [{"name": "规格", "category": "复印纸"}], "start_time": "2026-11-01 09:00:00"},
            raw,
        )
        self.assertEqual(kept["start_time"], "2026-11-01 09:00:00")


if __name__ == "__main__":
    unittest.main()
