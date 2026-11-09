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


if __name__ == "__main__":
    unittest.main()
