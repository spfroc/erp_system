from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.data_store.notice_tagging import (
    classify_buyer,
    classify_deal_kind,
    is_result_notice,
    parse_region,
    period_bounds,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


class NoticeTagRuleTests(SimpleTestCase):
    def test_school_and_region_from_buyer_name(self):
        region = parse_region("山东省济南市历下区教育和体育局")
        self.assertEqual(region["province"], "山东省")
        self.assertEqual(region["city"], "济南市")
        self.assertEqual(region["district"], "历下区")
        tagged = classify_buyer("青岛市实验小学", "山东省青岛市")
        self.assertEqual(tagged["orgType"], "小学")
        self.assertEqual(tagged["nature"], "事业单位")
        self.assertEqual(tagged["city"], "青岛市")
        self.assertEqual(tagged["province"], "山东省")

    def test_fill_province_city_when_only_city_or_county(self):
        zaozhuang = classify_buyer("枣庄市图书馆（枣庄市古籍保护中心）")
        self.assertEqual(zaozhuang["province"], "山东省")
        self.assertEqual(zaozhuang["city"], "枣庄市")
        qingdao = classify_buyer("青岛四方实验小学")
        self.assertEqual(qingdao["province"], "山东省")
        self.assertEqual(qingdao["city"], "青岛市")
        yanggu = classify_buyer("阳谷县残疾人联合会")
        self.assertEqual(yanggu["province"], "山东省")
        self.assertEqual(yanggu["city"], "聊城市")
        self.assertEqual(yanggu["district"], "阳谷县")

    def test_org_subtypes_and_kindergarten_not_government(self):
        kindergarten = classify_buyer("临沂芝麻墩街道中心幼儿园")
        self.assertEqual(kindergarten["orgType"], "幼儿园")
        self.assertEqual(kindergarten["nature"], "事业单位")
        police = classify_buyer("德州市人民警察训练中心")
        self.assertEqual(police["orgType"], "公安系统")
        self.assertEqual(police["nature"], "政府")
        traffic = classify_buyer("聊城市公安局交通巡逻警察支队经济技术开发区大队")
        self.assertEqual(traffic["orgType"], "公安系统")
        self.assertEqual(traffic["province"], "山东省")
        self.assertEqual(traffic["city"], "聊城市")
        self.assertEqual(traffic["district"], "经济技术开发区")

    def test_provincial_resort_not_fake_province(self):
        police = classify_buyer("济宁北湖省级旅游度假区公安分局")
        self.assertEqual(police["orgType"], "公安系统")
        self.assertEqual(police["province"], "山东省")
        self.assertEqual(police["city"], "济宁市")
        self.assertNotIn("北湖省", police["province"])
        edu = classify_buyer("济宁市教育局北湖度假区分局")
        self.assertEqual(edu["province"], "山东省")
        self.assertEqual(edu["city"], "济宁市")

    def test_tax_bureau_region_strips_agency_name(self):
        zaozhuang = classify_buyer("国家税务总局枣庄市市中区税务局")
        self.assertEqual(zaozhuang["orgType"], "财税")
        self.assertEqual(zaozhuang["nature"], "政府")
        self.assertEqual(zaozhuang["province"], "山东省")
        self.assertEqual(zaozhuang["city"], "枣庄市")
        self.assertEqual(zaozhuang["district"], "市中区")
        self.assertNotIn("税务", zaozhuang["province"])
        self.assertNotIn("税务", zaozhuang["city"])
        dongying = classify_buyer("国家税务总局东营市东营区税务局")
        self.assertEqual(dongying["orgType"], "财税")
        self.assertEqual(dongying["province"], "山东省")
        self.assertEqual(dongying["city"], "东营市")
        self.assertEqual(dongying["district"], "东营区")

    def test_museum_culture_and_province_short(self):
        museum = classify_buyer("山东博物馆")
        self.assertEqual(museum["orgType"], "文化")
        self.assertEqual(museum["nature"], "事业单位")
        self.assertEqual(museum["province"], "山东省")
        self.assertEqual(museum["city"], "济南市")
        library = classify_buyer("枣庄市图书馆（枣庄市古籍保护中心）")
        self.assertEqual(library["orgType"], "文化")
        self.assertEqual(library["nature"], "事业单位")

    def test_health_research_court_and_trading_center(self):
        blood = classify_buyer("菏泽市中心血站")
        self.assertEqual(blood["orgType"], "医疗卫生")
        self.assertEqual(blood["nature"], "事业单位")
        hospital = classify_buyer("山东省第二荣军优抚医院")
        self.assertEqual(hospital["orgType"], "医疗卫生")
        self.assertEqual(hospital["nature"], "事业单位")
        academy = classify_buyer("淄博市农业科学研究院")
        self.assertEqual(academy["orgType"], "科研")
        self.assertEqual(academy["nature"], "事业单位")
        self.assertEqual(academy["province"], "山东省")
        self.assertEqual(academy["city"], "淄博市")
        court = classify_buyer("济南市中级人民法院")
        self.assertEqual(court["orgType"], "司法")
        self.assertEqual(court["nature"], "政府")
        trading = classify_buyer("山东省公共资源交易中心")
        self.assertEqual(trading["orgType"], "公共资源")
        self.assertEqual(trading["nature"], "事业单位")

    def test_screenshot_misses_more_org_types(self):
        cases = [
            ("沂水县杨庄镇中心校", "小学", "事业单位"),
            ("东昌府区大张联合校", "教育", "事业单位"),
            ("莘县看守所", "公安系统", "政府"),
            ("阳谷县妇幼保健计划生育服务中心", "医疗卫生", "事业单位"),
            ("聊城市文物事业服务中心", "文化", "事业单位"),
            ("淄博市司法局", "司法", "政府"),
            ("山东省法律援助中心", "司法", "事业单位"),
            ("淄博市交通建设发展中心", "交通", "事业单位"),
            ("临沂市城乡建设服务中心", "住建", "事业单位"),
            ("荣成市农业农村事务服务中心", "农业", "事业单位"),
            ("潍坊市殡葬事业服务中心", "民政", "事业单位"),
            ("枣庄市应急救援保障中心", "应急", "事业单位"),
            ("枣庄市墨子研究中心本级", "科研", "事业单位"),
            ("临沂沂河新区行政审批服务局", "机关", "政府"),
            ("泰安市岱岳区自然资源局本级", "机关", "政府"),
            ("山东省工业和信息化厅机关", "机关", "政府"),
            ("菏泽市人民政府外事办公室本级", "机关", "政府"),
            ("青岛市招生考试院", "教育", "事业单位"),
            ("青岛市城市建设档案馆", "文化", "事业单位"),
            ("中国国际贸易促进委员会荣成市委员会", "群团", "政府"),
            ("烟台市妇女联合会机关", "群团", "政府"),
            ("泰安市房产管理服务中心本级", "住建", "事业单位"),
            ("莘县国有林场管理服务中心", "农业", "国企"),
            ("威海市文登区天福社区卫生服务中心", "医疗卫生", "事业单位"),
            ("泰安市住房公积金中心", "住建", "事业单位"),
            ("国家税务总局菏泽市税务局", "财税", "政府"),
            ("潍坊市机关事务服务中心", "机关", "事业单位"),
            ("泰安市徂徕山汶河风景名胜区管理委员会本级", "机关", "政府"),
        ]
        for name, org_type, nature in cases:
            tagged = classify_buyer(name)
            self.assertEqual(tagged["orgType"], org_type, name)
            self.assertEqual(tagged["nature"], nature, name)

    def test_government_and_central_enterprise(self):
        bureau = classify_buyer("山东省济南市历下区教育和体育局")
        self.assertEqual(bureau["orgType"], "教育")
        self.assertEqual(bureau["nature"], "政府")
        company = classify_buyer("国家电网山东省电力公司")
        self.assertEqual(company["nature"], "央企")

    def test_manual_dictionary_overrides_keyword(self):
        tagged = classify_buyer(
            "青岛市实验小学",
            rules=[{"kind": "buyer_org_type", "pattern": "青岛市实验小学", "value": "教育"}],
        )
        self.assertEqual(tagged["orgType"], "教育")

    def test_result_notice_predicate(self):
        self.assertTrue(is_result_notice("jd-qing-huicai", "2", "成交公告"))
        self.assertTrue(is_result_notice("sd-ggzyjyzx", "1", ""))
        self.assertFalse(is_result_notice("jd-qing-huicai", "4", "失败公告"))

    def test_period_bounds_use_shanghai_calendar(self):
        now = datetime(2026, 10, 26, 9, 0, tzinfo=SHANGHAI)
        last_start, last_end = period_bounds("last_month", now)
        self.assertEqual(last_start.date().isoformat(), "2026-09-01")
        self.assertEqual(last_end.date().isoformat(), "2026-10-01")
        month_start, month_end = period_bounds("this_month", now)
        self.assertEqual(month_start.date().isoformat(), "2026-10-01")
        self.assertEqual(month_end.date().isoformat(), "2026-11-01")
        week_start, week_end = period_bounds("this_week", now)
        self.assertEqual(week_start.date().isoformat(), "2026-10-26")
        self.assertEqual(week_end.date().isoformat(), "2026-11-02")
        custom_start, custom_end = period_bounds(
            "custom",
            now,
            start_date="2026-10-01",
            end_date="2026-10-27",
        )
        self.assertEqual(custom_start.date().isoformat(), "2026-10-01")
        self.assertEqual(custom_end.date().isoformat(), "2026-10-28")

    def test_classify_deal_kind_from_products_and_title(self):
        # 凡有商品明细 → 商品（即使标题像服务）
        goods = classify_deal_kind(
            title="某某单位运维服务采购成交公告",
            product_rows=[{"category": "货物类", "product_name": "打印机耗材"}],
        )
        self.assertEqual(goods["dealKind"], "商品")
        # 有商品+服务明细仍归商品
        with_goods = classify_deal_kind(
            title="软硬件及运维一体化项目成交公告",
            product_rows=[
                {"category": "", "product_name": "服务器设备"},
                {"category": "", "product_name": "系统运维服务"},
            ],
        )
        self.assertEqual(with_goods["dealKind"], "商品")
        # 普通品名明细也算有商品
        plain_goods = classify_deal_kind(
            title="某单位成交公告",
            product_rows=[{"category": "", "product_name": "笔记本电脑"}],
        )
        self.assertEqual(plain_goods["dealKind"], "商品")
        # 无商品：按标题识别服务
        service = classify_deal_kind(
            title="机房运维服务采购成交公告",
            product_rows=[{"category": "服务类", "product_name": "年度运维"}],
        )
        self.assertEqual(service["dealKind"], "服务")
        # 无商品：按标题识别工程
        engineering = classify_deal_kind(
            title="教学楼维修改造工程成交公告",
            product_rows=[],
        )
        self.assertEqual(engineering["dealKind"], "工程")
        # 「服务器」有商品明细则仍是商品
        server = classify_deal_kind(
            title="服务器设备采购成交公告",
            product_rows=[{"category": "", "product_name": "机架式服务器"}],
        )
        self.assertEqual(server["dealKind"], "商品")
        # 无明细、标题也不像服务/工程
        unknown = classify_deal_kind(title="某某项目成交公告", product_rows=[])
        self.assertEqual(unknown["dealKind"], "未识别")
        ruled = classify_deal_kind(
            title="自定义标题",
            rules=[{"kind": "deal_kind", "pattern": "自定义标题", "value": "服务"}],
        )
        self.assertEqual(ruled["dealKind"], "服务")
