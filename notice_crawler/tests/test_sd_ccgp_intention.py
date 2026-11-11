from pipeline.extractors.sd_ccgp_intention import extract_ccgp_intention, looks_like_intention


SAMPLE_TABLE = """
青岛市即墨区融媒体中心2026年11月政府采购意向
为便于供应商及时了解政府采购信息，现将
青岛市即墨区融媒体中心2026年11月政府采购意向
公开如下：
序号
采购项目名称
采购需求概况
预算金额
（万元）
拟面向中小企业预留
预计采购时间
（填写到月）
备注
1
车辆维修保养
按照车辆要求
3.008000
是
2026年11月
本次公开的采购意向是本单位政府采购工作的初步安排，具体采购项目情况以相关采购公告和采购文件为准。
青岛市即墨区融媒体中心
2026年11月10日
"""

SAMPLE_PUBLICITY = """
一、项目名称：
2026年度软器械租赁服务
二、采购单位：
莱西市人民医院
八、总预算：
90万元
七、项目概况：
手术辅料租赁服务
"""


def test_looks_like_intention_by_type():
    assert looks_like_intention(notice_type="2500")
    assert looks_like_intention(list_item={"colCode": "2504"})


def test_extract_intention_table():
    parsed = extract_ccgp_intention(
        SAMPLE_TABLE,
        title="青岛市即墨区融媒体中心2026年11月政府采购意向",
        list_item={"userName": "青岛市即墨区融媒体中心", "areaName": "即墨区"},
    )
    assert parsed["notice_kind"] == "意向公开"
    assert parsed["project_code"] is None
    assert parsed["project_name"] == "车辆维修保养"
    assert parsed["buyer_name"] == "青岛市即墨区融媒体中心"
    assert parsed["budget_amount"] == 30080.0
    assert len(parsed["goods"]) == 1
    assert parsed["goods"][0]["name"] == "车辆维修保养"
    assert parsed["start_time"].startswith("2026-11-01")
    assert parsed["end_time"].startswith("2026-11-30")


def test_extract_demand_publicity():
    parsed = extract_ccgp_intention(
        SAMPLE_PUBLICITY,
        title="【莱西市】莱西市人民医院2026年度软器械租赁服务采购需求公示",
    )
    assert parsed["project_name"] == "2026年度软器械租赁服务"
    assert parsed["buyer_name"] == "莱西市人民医院"
    assert parsed["budget_amount"] == 900000.0
    assert len(parsed["goods"]) == 1
