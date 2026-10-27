"""结果公告规则打标。只读采集表，写入标签表，不参与抓取事务。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from .notice_dict import DEFAULT_NATURES, DEFAULT_ORG_TYPES, KIND_NATURE, KIND_ORG_TYPE, list_dict_names
from .notice_models import NoticeGoods, NoticeParsed, NoticeRaw
from .notice_region_atlas import enrich_region
from .notice_tag_models import NoticeBuyerProfile, NoticeProductTag, NoticeResultTag, NoticeTagRule

RESULT_KINDS = ("成交公告", "成交结果公告", "结果公告")
JD_SITES = ("jd-qing-huicai", "jd-quan-yicai")
DEAL_KIND_GOODS = "商品"
DEAL_KIND_SERVICE = "服务"
DEAL_KIND_ENGINEERING = "工程"
DEAL_KIND_UNKNOWN = "未识别"
# 正式成交类型三种；「未识别」仅作未归类兜底
DEAL_KINDS = (DEAL_KIND_GOODS, DEAL_KIND_SERVICE, DEAL_KIND_ENGINEERING, DEAL_KIND_UNKNOWN)
# 兼容旧值
_LEGACY_DEAL_KINDS = {"混合": DEAL_KIND_UNKNOWN}
# 兼容旧 import；运行时优先读字典表
ORG_TYPES = DEFAULT_ORG_TYPES
NATURES = DEFAULT_NATURES
# 旧标签兼容
_ORG_TYPE_ALIASES = {"医院": "医疗卫生"}

# 含「服务/工程」但偏其它含义的词，识别前先剔除
_SERVICE_FALSE_POSITIVES = ("服务器", "服务台", "服务车", "服务热线", "服务区")
_ENGINEERING_FALSE_POSITIVES = ("工程师", "工程院", "工程学院", "工程大学", "工程系")
_SERVICE_KEYWORDS = (
    "运维",
    "维保",
    "咨询",
    "租赁",
    "培训",
    "维护",
    "检修",
    "监理",
    "测评",
    "保洁",
    "安保",
    "劳务",
    "技术支持",
    "售后服务",
    "信息化服务",
    "系统集成服务",
    "服务项目",
    "服务采购",
    "服务类",
    "检测服务",
    "设计服务",
    "外包服务",
    "托管服务",
)
_ENGINEERING_KEYWORDS = (
    "工程类",
    "工程项目",
    "建设工程",
    "施工",
    "土建",
    "装修",
    "装饰装修",
    "改造工程",
    "维修改造",
    "修缮",
    "加固",
    "市政工程",
    "园林绿化",
    "安装工程",
    "基建",
    "新建工程",
    "扩建工程",
    "工程采购",
)
_GOODS_KEYWORDS = (
    "设备",
    "耗材",
    "物资",
    "器材",
    "商品",
    "硬件",
    "家具",
    "电脑",
    "打印机",
    "服务器",
    "空调",
    "车辆",
    "仪器",
    "货物",
    "货物类",
    "商品类",
    "物资类",
    "办公用品",
    "耗材类",
    "采购设备",
)

# 更具体的在前：研究院含「学院」字样，须排在「学院→大学」之前
_ORG_KEYWORDS = (
    ("幼儿园", "幼儿园"),
    ("幼教", "幼儿园"),
    ("中心校", "小学"),
    ("小学", "小学"),
    ("初级中学", "中学"),
    ("中学", "中学"),
    ("初中", "中学"),
    ("高中", "中学"),
    ("联合校", "教育"),
    ("职业技术学院", "大专"),
    ("职业学院", "大专"),
    ("专科学校", "大专"),
    ("大专", "大专"),
    ("大学", "大学"),
    ("农业科学研究院", "科研"),
    ("农科院", "科研"),
    ("科学研究院", "科研"),
    ("研究院", "科研"),
    ("研究所", "科研"),
    ("科研所", "科研"),
    ("科学院", "科研"),
    ("研究中心", "科研"),
    ("学院", "大学"),
    ("看守所", "公安系统"),
    ("拘留所", "公安系统"),
    ("戒毒所", "公安系统"),
    ("派出所", "公安系统"),
    ("交警", "公安系统"),
    ("交通警察", "公安系统"),
    ("巡逻警察", "公安系统"),
    ("公安分局", "公安系统"),
    ("公安局", "公安系统"),
    ("人民警察", "公安系统"),
    ("警察训练", "公安系统"),
    ("消防救援", "公安系统"),
    ("消防支队", "公安系统"),
    ("消防大队", "公安系统"),
    ("消防队", "公安系统"),
    ("高级人民法院", "司法"),
    ("中级人民法院", "司法"),
    ("人民法院", "司法"),
    ("基层法院", "司法"),
    ("法院", "司法"),
    ("检察院", "司法"),
    ("法律援助", "司法"),
    ("司法局", "司法"),
    ("司法所", "司法"),
    ("国家税务总局", "财税"),
    ("税务总局", "财税"),
    ("税务局", "财税"),
    ("财政局", "财税"),
    ("公共资源交易中心", "公共资源"),
    ("政府采购中心", "公共资源"),
    ("博物馆", "文化"),
    ("图书馆", "文化"),
    ("文化馆", "文化"),
    ("美术馆", "文化"),
    ("纪念馆", "文化"),
    ("艺术馆", "文化"),
    ("剧院", "文化"),
    ("文物", "文化"),
    ("档案馆", "文化"),
    ("档案局", "文化"),
    ("妇幼保健", "医疗卫生"),
    ("计划生育服务", "医疗卫生"),
    ("血站", "医疗卫生"),
    ("疾病预防控制", "医疗卫生"),
    ("疾控中心", "医疗卫生"),
    ("医院", "医疗卫生"),
    ("卫生院", "医疗卫生"),
    ("交通建设", "交通"),
    ("交通运输", "交通"),
    ("公路事业", "交通"),
    ("城乡建设", "住建"),
    ("城市建设", "住建"),
    ("住房和城乡建设", "住建"),
    ("住房公积金", "住建"),
    ("房产管理", "住建"),
    ("住建局", "住建"),
    ("农业农村", "农业"),
    ("农业局", "农业"),
    ("国有林场", "农业"),
    ("林场", "农业"),
    ("殡葬", "民政"),
    ("民政局", "民政"),
    ("社区卫生服务", "医疗卫生"),
    ("卫生服务中心", "医疗卫生"),
    ("应急救援", "应急"),
    ("应急管理局", "应急"),
    ("应急管理", "应急"),
    ("妇女联合会", "群团"),
    ("妇联", "群团"),
    ("残疾人联合会", "群团"),
    ("残联", "群团"),
    ("社会科学界联合会", "群团"),
    ("社科联", "群团"),
    ("国际贸易促进委员会", "群团"),
    ("贸促会", "群团"),
    ("招生考试", "教育"),
    ("学校", "教育"),
    ("教体局", "教育"),
    ("教育局", "教育"),
    ("行政审批", "机关"),
    ("自然资源", "机关"),
    ("工业和信息化", "机关"),
    ("外事办公室", "机关"),
    ("外事办", "机关"),
    ("机关事务", "机关"),
    ("风景名胜区", "机关"),
    ("管理委员会", "机关"),
)
_CULTURE_TOKENS = ("博物馆", "图书馆", "文化馆", "美术馆", "纪念馆", "艺术馆", "剧院", "文物", "档案馆")
_HEALTH_TOKENS = ("血站", "医院", "卫生院", "疾控", "疾病预防控制", "妇幼保健", "计划生育服务", "社区卫生", "卫生服务中心")
_RESEARCH_TOKENS = ("研究院", "研究所", "科研所", "农科院", "科学院", "研究中心")
_JUDICIAL_TOKENS = ("法院", "人民法院", "检察院", "司法局", "司法所", "法律援助")
_TAX_TOKENS = ("税务局", "税务总局", "财政局")
_PUBLIC_RESOURCE_TOKENS = ("公共资源交易中心", "政府采购中心")
_POLICE_TOKENS = ("公安", "派出所", "交警", "警察", "消防", "看守所", "拘留所", "戒毒所")
_GOV_ORG_TYPES = {"公安系统", "司法", "财税", "机关"}
_INSTITUTION_ORG_TYPES = {
    "幼儿园",
    "小学",
    "中学",
    "大专",
    "大学",
    "医疗卫生",
    "文化",
    "科研",
    "公共资源",
    "交通",
    "住建",
    "农业",
    "民政",
    "应急",
}
# 省级馆所等简称（无「市」时补省/市）
_KNOWN_BUYERS = {
    "山东博物馆": ("山东省", "济南市", ""),
    "山东省博物馆": ("山东省", "济南市", ""),
}
_CENTRAL = (
    "国家电网", "中国石油", "中国石化", "中国海油", "中国移动", "中国电信", "中国联通",
    "中国建筑", "中国中铁", "中国铁建", "中国交建", "中国中车", "国家能源", "中国华能",
    "中国大唐", "中国华电", "国家电投", "中国核", "中国兵器", "中国电子", "中粮", "中国五矿",
    "中国宝武", "中国邮政", "中国烟草",
)
_SCHOOL_TOKENS = ("幼儿园", "幼教", "小学", "中学", "初中", "高中", "大学", "学院", "大专", "学校", "中心校", "联合校")
_BUYER_SUFFIX_NOISE = re.compile(r"(本级|机关)+$")


def _buyer_core(name: str) -> str:
    """去掉「本级/机关」后缀，便于按局/厅判断性质。"""
    return _BUYER_SUFFIX_NOISE.sub("", (name or "").strip())


# 排除「省级/省部级」等非行政区「省」
_REGION_PROVINCE = re.compile(r"([\u4e00-\u9fff]{2,8}(?:省(?!级)|自治区))")
_REGION_CITY_SHORT = re.compile(r"([\u4e00-\u9fff]{2,3}市)")
_KNOWN_ZONES = (
    "经济技术开发区",
    "高新技术产业开发区",
    "高新技术开发区",
    "工业园区",
    "高新区",
    "开发区",
)


def parse_region(*texts: str) -> dict[str, str]:
    from .notice_region_atlas import find_known_city

    blob = " ".join(text for text in texts if text)
    province = ""
    city = ""
    district = ""
    matched = _REGION_PROVINCE.search(blob)
    if matched:
        province = matched.group(1)
    elif blob.startswith(("北京", "上海", "天津", "重庆")):
        province = blob[:2] + "市"
    # 先按已知地级市定位，避免「国家税务总局东营市」整段被当成市名
    known = find_known_city(blob)
    if known:
        city, _start, end = known
        rest = blob[end:]
    else:
        city_match = _REGION_CITY_SHORT.search(blob)
        if city_match:
            city = city_match.group(1)
            rest = blob[city_match.end() :]
        else:
            rest = blob
    for zone in _KNOWN_ZONES:
        if zone in rest:
            district = zone
            break
    if not district:
        district_match = re.search(r"([\u4e00-\u9fff]{1,6}(?:区|县))", rest)
        if district_match:
            district = district_match.group(1)
            if district in {"区", "县"} or "度假" in district or "局" in district:
                district = ""
    return enrich_region(province, city, district, blob)


def _rule_value(rules: list[dict], kind: str, text: str) -> str:
    hits = [rule for rule in rules if rule.get("kind") == kind and rule.get("pattern") and rule["pattern"] in text]
    if not hits:
        return ""
    hits.sort(key=lambda rule: len(rule["pattern"]), reverse=True)
    return str(hits[0].get("value") or "")


def classify_buyer(name: str, region_text: str = "", rules: list[dict] | None = None) -> dict[str, Any]:
    buyer = (name or "").strip()
    core = _buyer_core(buyer)
    rules = rules or []
    org_type = _rule_value(rules, "buyer_org_type", buyer)
    if not org_type:
        for keyword, label in _ORG_KEYWORDS:
            if keyword in buyer:
                org_type = label
                break
    if not org_type and "教育" in buyer and any(token in buyer for token in ("局", "委员会", "中心", "院")):
        org_type = "教育"
    # 其余厅/局/办公室默认归「机关」，避免大量落「其他」
    if not org_type and core and "公司" not in buyer:
        if core.endswith(("厅", "局", "办公室")) or any(token in buyer for token in ("人民政府", "办公室本级")):
            org_type = "机关"
    org_type = _ORG_TYPE_ALIASES.get(org_type, org_type)
    allowed_org = set(list_dict_names(KIND_ORG_TYPE, enabled_only=False))
    if org_type not in allowed_org:
        org_type = "其他" if buyer and "其他" in allowed_org else ("" if not buyer else org_type)
        if org_type and org_type not in allowed_org:
            org_type = "其他" if "其他" in allowed_org else ""

    nature = _rule_value(rules, "buyer_nature", buyer)
    if not nature:
        if any(token in buyer for token in _CENTRAL):
            nature = "央企"
        elif "国有" in buyer or "国营" in buyer:
            nature = "国企"
        elif org_type in _INSTITUTION_ORG_TYPES or (
            any(token in buyer for token in _SCHOOL_TOKENS) and "局" not in buyer
        ) or any(token in buyer for token in _CULTURE_TOKENS + _HEALTH_TOKENS + _RESEARCH_TOKENS + _PUBLIC_RESOURCE_TOKENS):
            # 幼儿园名里常带「街道」，不能因此判成政府；馆所/血站/科研/交易中心按事业单位
            nature = "事业单位"
        elif org_type == "司法" and "法律援助" in buyer:
            nature = "事业单位"
        elif org_type in _GOV_ORG_TYPES or org_type == "群团" or any(
            token in buyer for token in _POLICE_TOKENS + _JUDICIAL_TOKENS + _TAX_TOKENS
        ):
            # 机关事务服务中心等多为事业单位，不宜因类型=机关一律判政府
            if (
                org_type == "机关"
                and "服务中心" in buyer
                and not core.endswith(("局", "厅", "办公室"))
                and "委员会" not in buyer
            ):
                nature = "事业单位"
            else:
                nature = "政府"
        elif org_type == "教育" and any(token in buyer for token in ("教育局", "教体局", "教育和体育局", "招生考试")):
            nature = "政府" if "局" in buyer else "事业单位"
        elif any(token in buyer for token in ("人民政府", "委员会", "管理局", "办事处", "街道办")) or (
            core.endswith(("局", "厅", "办公室")) and "公司" not in buyer and "医院" not in buyer
        ):
            nature = "政府"
        elif any(token in buyer for token in ("公司", "集团")):
            nature = "国企" if "国" in buyer else "其他"
        elif "中心" in buyer or buyer.endswith("院"):
            nature = "事业单位"
        else:
            nature = "其他" if buyer else ""
    allowed_nature = set(list_dict_names(KIND_NATURE, enabled_only=False))
    if nature not in allowed_nature:
        nature = "其他" if buyer and "其他" in allowed_nature else ("" if not buyer else nature)
        if nature and nature not in allowed_nature:
            nature = "其他" if "其他" in allowed_nature else ""

    region = parse_region(region_text, buyer)
    known_buyer = _KNOWN_BUYERS.get(buyer)
    if known_buyer:
        kp, kc, kd = known_buyer
        region["province"] = region["province"] or kp
        region["city"] = region["city"] or kc
        region["district"] = region["district"] or kd
    if _rule_value(rules, "buyer_province", buyer):
        region["province"] = _rule_value(rules, "buyer_province", buyer)
    if _rule_value(rules, "buyer_city", buyer):
        region["city"] = _rule_value(rules, "buyer_city", buyer)
    if _rule_value(rules, "buyer_district", buyer):
        region["district"] = _rule_value(rules, "buyer_district", buyer)
    region = enrich_region(region["province"], region["city"], region["district"], region_text, buyer)
    filled = sum(1 for value in (org_type, nature, region["province"], region["city"]) if value)
    return {
        "buyerName": buyer,
        "orgType": org_type,
        "nature": nature,
        **region,
        "confidence": Decimal("0.90") if filled >= 3 else Decimal("0.60") if filled else Decimal("0.20"),
    }


def is_result_notice(site_id: str | None, notice_type: str | None, notice_kind: str | None) -> bool:
    kind = (notice_kind or "").strip()
    if kind in RESULT_KINDS or "成交" in kind:
        return True
    if site_id in JD_SITES and str(notice_type or "") == "2":
        return True
    if site_id == "sd-ggzyjyzx" and str(notice_type or "") == "1":
        return True
    return False


def _scrub_tokens(text: str, tokens: tuple[str, ...]) -> str:
    scrubbed = text or ""
    for token in tokens:
        scrubbed = scrubbed.replace(token, "")
    return scrubbed


def _normalize_deal_kind(value: str) -> str:
    text = (value or "").strip()
    text = _LEGACY_DEAL_KINDS.get(text, text)
    return text if text in DEAL_KINDS else DEAL_KIND_UNKNOWN


def _row_has_goods(category: str, name: str, rules: list[dict] | None = None) -> bool:
    """明细行是否含商品（货物）；凡有商品的公告一律归商品。"""
    rules = rules or []
    category = (category or "").strip()
    name = (name or "").strip()
    for key in (category, name):
        hit = _rule_value(rules, "deal_kind", key) if key else ""
        if hit and _normalize_deal_kind(hit) == DEAL_KIND_GOODS:
            return True
        if hit and _normalize_deal_kind(hit) in (DEAL_KIND_SERVICE, DEAL_KIND_ENGINEERING):
            return False
    blob = f"{category} {name}".strip()
    if not blob:
        return False
    if any(token in blob for token in ("货物类", "商品类", "物资类", "货物采购", "货物")):
        return True
    if any(token in blob for token in _GOODS_KEYWORDS):
        return True
    # 明确服务/工程类明细不算商品
    if any(token in blob for token in ("服务类", "工程类", "服务采购", "工程采购")):
        return False
    eng = _scrub_tokens(blob, _ENGINEERING_FALSE_POSITIVES)
    svc = _scrub_tokens(blob, _SERVICE_FALSE_POSITIVES)
    if ("工程" in eng or any(token in eng for token in _ENGINEERING_KEYWORDS)) and not any(
        token in blob for token in _GOODS_KEYWORDS
    ):
        return False
    if (any(token in svc for token in _SERVICE_KEYWORDS) or "服务" in svc) and not any(
        token in blob for token in _GOODS_KEYWORDS
    ):
        return False
    # 其余有品名/分类的明细视为商品（凡有商品 → 商品公告）
    return True


def _title_service_or_engineering(title: str) -> str | None:
    """无商品时，仅按公告名称区分服务 / 工程。"""
    raw = (title or "").strip()
    if not raw:
        return None
    if any(token in raw for token in ("工程类", "工程项目", "建设工程", "工程采购")):
        return DEAL_KIND_ENGINEERING
    if any(token in raw for token in ("服务类", "服务采购", "服务项目", "服务外包")):
        return DEAL_KIND_SERVICE
    eng_text = _scrub_tokens(raw, _ENGINEERING_FALSE_POSITIVES)
    svc_text = _scrub_tokens(raw, _SERVICE_FALSE_POSITIVES)
    has_engineering = "工程" in eng_text or any(token in eng_text for token in _ENGINEERING_KEYWORDS)
    has_service = any(token in svc_text for token in _SERVICE_KEYWORDS) or ("服务" in svc_text)
    if has_engineering and not has_service:
        return DEAL_KIND_ENGINEERING
    if has_service and not has_engineering:
        return DEAL_KIND_SERVICE
    if has_engineering and has_service:
        # 如「工程监理服务」偏服务；带施工/建设/装修等偏工程
        if any(token in eng_text for token in ("施工", "建设", "装修", "修缮", "土建", "改造", "基建", "安装工程")):
            return DEAL_KIND_ENGINEERING
        return DEAL_KIND_SERVICE
    return None


def classify_deal_kind(
    *,
    title: str = "",
    product_rows: list[dict] | None = None,
    rules: list[dict] | None = None,
) -> dict[str, Any]:
    """识别结果公告成交类型：商品 / 服务 / 工程（未识别为兜底）。

    规则：凡明细中有商品 → 商品；否则结合公告名称识别服务或工程。
    """
    rules = rules or []
    title = (title or "").strip()
    rule_hit = _normalize_deal_kind(_rule_value(rules, "deal_kind", title) or "")
    if _rule_value(rules, "deal_kind", title) and rule_hit in (
        DEAL_KIND_GOODS,
        DEAL_KIND_SERVICE,
        DEAL_KIND_ENGINEERING,
    ):
        return {"dealKind": rule_hit, "confidence": Decimal("0.95")}

    has_goods = False
    for row in product_rows or []:
        category = str(row.get("category") or "").strip()
        name = str(row.get("product_name") or row.get("productName") or "").strip()
        if _row_has_goods(category, name, rules):
            has_goods = True
            break
    if has_goods:
        return {"dealKind": DEAL_KIND_GOODS, "confidence": Decimal("0.90")}

    title_kind = _title_service_or_engineering(title)
    if title_kind in (DEAL_KIND_SERVICE, DEAL_KIND_ENGINEERING):
        return {"dealKind": title_kind, "confidence": Decimal("0.70")}
    return {"dealKind": DEAL_KIND_UNKNOWN, "confidence": Decimal("0.20")}


def _product_rows_for_notice(notice_raw_id: int) -> list[dict]:
    tagged = {
        item.goods_id: item
        for item in NoticeProductTag.objects.filter(notice_raw_id=notice_raw_id)
    }
    rows = []
    for item in NoticeGoods.objects.filter(notice_raw_id=notice_raw_id).order_by("line_no", "id"):
        tag = tagged.get(item.id)
        rows.append(
            {
                "category": (tag.category if tag and tag.category else "") or (item.category or ""),
                "product_name": (tag.product_name if tag and tag.product_name else "") or (item.product_name or ""),
            }
        )
    if rows:
        return rows
    return [
        {"category": item.category, "product_name": item.product_name}
        for item in NoticeProductTag.objects.filter(notice_raw_id=notice_raw_id).order_by("id")
    ]


def _parse_ymd(value: str) -> date | None:
    text = (value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def period_bounds(
    period: str,
    now: datetime | None = None,
    *,
    start_date: str = "",
    end_date: str = "",
) -> tuple[datetime, datetime]:
    """返回 [start, end) 半开区间；自定义时 end_date 按当天 inclusive 处理。"""
    current = timezone.localtime(now or timezone.now())
    start_of_day = current.replace(hour=0, minute=0, second=0, microsecond=0)
    period = (period or "").strip() or "this_month"
    custom_start = _parse_ymd(start_date)
    custom_end = _parse_ymd(end_date)
    if period == "custom" or (custom_start and custom_end):
        if custom_start and custom_end:
            if custom_end < custom_start:
                custom_start, custom_end = custom_end, custom_start
            end_day = custom_end + timedelta(days=1)
            start = start_of_day.replace(
                year=custom_start.year, month=custom_start.month, day=custom_start.day
            )
            end = start_of_day.replace(year=end_day.year, month=end_day.month, day=end_day.day)
            return start, end
        period = "this_month"
    if period == "today":
        return start_of_day, start_of_day + timedelta(days=1)
    if period == "this_week":
        start = start_of_day - timedelta(days=start_of_day.weekday())
        return start, start + timedelta(days=7)
    month_start = start_of_day.replace(day=1)
    if period == "last_month":
        previous = month_start - timedelta(days=1)
        return previous.replace(day=1), month_start
    if period == "this_year":
        year_start = start_of_day.replace(month=1, day=1)
        return year_start, year_start.replace(year=year_start.year + 1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    return month_start, next_month


STAT_PERIODS = frozenset({"today", "this_week", "this_month", "last_month", "this_year", "custom"})


def normalize_stats_period(period: str, start_date: str = "", end_date: str = "") -> str:
    period = (period or "").strip() or "this_month"
    if period == "custom" or (_parse_ymd(start_date) and _parse_ymd(end_date)):
        if _parse_ymd(start_date) and _parse_ymd(end_date):
            return "custom"
        return "this_month"
    if period not in STAT_PERIODS:
        return "this_month"
    return period


def _inclusive_day_bounds(start_date: str = "", end_date: str = "") -> tuple[datetime, datetime] | None:
    """把 YYYY-MM-DD 起止转成本地时区 [start, end) ；只填一端时另一端放宽。"""
    start_day = _parse_ymd(start_date)
    end_day = _parse_ymd(end_date)
    if not start_day and not end_day:
        return None
    current = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    if start_day and end_day and end_day < start_day:
        start_day, end_day = end_day, start_day
    if start_day:
        start = current.replace(year=start_day.year, month=start_day.month, day=start_day.day)
    else:
        start = current.replace(year=1970, month=1, day=1)
    if end_day:
        end = current.replace(year=end_day.year, month=end_day.month, day=end_day.day) + timedelta(days=1)
    else:
        end = current + timedelta(days=36600)
    return start, end


def _name_key(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").strip())[:256]


def _load_rules() -> list[dict]:
    return list(NoticeTagRule.objects.values("kind", "pattern", "value"))


def _upsert_rule(kind: str, pattern: str, value: str) -> None:
    pattern = (pattern or "").strip()
    value = (value or "").strip()
    if not pattern or not value:
        return
    NoticeTagRule.objects.update_or_create(
        kind=kind,
        pattern=pattern[:256],
        defaults={"value": value[:128], "source": "manual"},
    )


def _apply_deal_kind(tag: NoticeResultTag, *, title: str, rules: list[dict]) -> str:
    _tag_products(tag.notice_raw_id, rules)
    deal = classify_deal_kind(
        title=title,
        product_rows=_product_rows_for_notice(tag.notice_raw_id),
        rules=rules,
    )
    tag.deal_kind = deal["dealKind"]
    if tag.source != "manual":
        tag.confidence = max(tag.confidence or Decimal("0"), deal["confidence"])
    tag.save(update_fields=["deal_kind", "confidence", "updated_at"])
    return deal["dealKind"]


def tag_result_notices(*, limit: int = 200, rebuild: bool = False) -> dict[str, int]:
    rules = _load_rules()
    # 优先补写/纠正成交类型：空值、旧「混合」、或非三种正式类型
    pending_ids = list(
        NoticeResultTag.objects.filter(
            Q(deal_kind="")
            | Q(deal_kind__isnull=True)
            | Q(deal_kind="混合")
            | ~Q(deal_kind__in=(DEAL_KIND_GOODS, DEAL_KIND_SERVICE, DEAL_KIND_ENGINEERING, DEAL_KIND_UNKNOWN))
        )
        .exclude(locked=True)
        .order_by("-notice_raw_id")
        .values_list("notice_raw_id", flat=True)[:limit]
    )
    if pending_ids:
        parsed_rows = list(NoticeParsed.objects.filter(notice_raw_id__in=pending_ids))
        parsed_map = {row.notice_raw_id: row for row in parsed_rows}
        tagged = 0
        skipped = 0
        for notice_raw_id in pending_ids:
            if tagged >= limit:
                break
            existing = NoticeResultTag.objects.filter(notice_raw_id=notice_raw_id).select_related("buyer_profile").first()
            if not existing or existing.locked:
                skipped += 1
                continue
            parsed = parsed_map.get(notice_raw_id)
            raw = NoticeRaw.objects.filter(id=notice_raw_id).only("id", "title").first()
            title = ((parsed.notice_title if parsed else "") or (raw.title if raw else "") or "").strip()
            with transaction.atomic():
                _apply_deal_kind(existing, title=title, rules=rules)
            tagged += 1
        return {"tagged": tagged, "skipped": skipped}

    # 全类型公告打标：优先未打标；rebuild 时覆盖未锁定记录
    tagged_ids = NoticeResultTag.objects.values("notice_raw_id")
    pending_qs = NoticeParsed.objects.order_by("-notice_raw_id")
    if not rebuild:
        pending_qs = pending_qs.exclude(notice_raw_id__in=tagged_ids)
    parsed_rows = list(pending_qs[: max(limit * 3, limit)])
    tagged = 0
    skipped = 0
    for parsed in parsed_rows:
        if tagged >= limit:
            break
        raw = NoticeRaw.objects.filter(id=parsed.notice_raw_id).only("id", "site_id", "notice_type", "title", "region_name").first()
        if not raw:
            skipped += 1
            continue
        existing = NoticeResultTag.objects.filter(notice_raw_id=raw.id).select_related("buyer_profile").first()
        if existing and existing.locked:
            skipped += 1
            continue
        if existing and existing.deal_kind and (existing.buyer_profile_id or not (parsed.buyer_name or "").strip()) and not rebuild:
            skipped += 1
            continue
        buyer_name = (parsed.buyer_name or "").strip()
        title = (parsed.notice_title or raw.title or "").strip()
        region_text = parsed.region_name or raw.region_name or ""
        with transaction.atomic():
            _tag_products(raw.id, rules)
            deal = classify_deal_kind(title=title, product_rows=_product_rows_for_notice(raw.id), rules=rules)
            profile = existing.buyer_profile if existing and existing.buyer_profile_id else None
            confidence = deal["confidence"]
            if buyer_name:
                classified = classify_buyer(buyer_name, region_text, rules)
                confidence = max(classified["confidence"], deal["confidence"])
                profile, _created = NoticeBuyerProfile.objects.get_or_create(
                    name_key=_name_key(buyer_name),
                    defaults={"buyer_name": buyer_name, "source": "rule"},
                )
                if not profile.locked:
                    profile.buyer_name = buyer_name
                    profile.org_type = classified["orgType"]
                    profile.nature = classified["nature"]
                    profile.province = classified["province"]
                    profile.city = classified["city"]
                    profile.district = classified["district"]
                    profile.source = "rule"
                    profile.confidence = classified["confidence"]
                    profile.save()
            elif region_text and not profile:
                # 无采购人时仍落地区线索到标签置信度，不强制建空档案
                classified = classify_buyer("", region_text, rules)
                confidence = max(classified["confidence"], deal["confidence"])
            NoticeResultTag.objects.update_or_create(
                notice_raw_id=raw.id,
                defaults={
                    "buyer_profile": profile,
                    "deal_kind": deal["dealKind"],
                    "source": "rule",
                    "confidence": confidence,
                    "locked": False,
                },
            )
        tagged += 1
    return {"tagged": tagged, "skipped": skipped}


def _retag_notice_record(
    *,
    raw: NoticeRaw,
    parsed: NoticeParsed | None,
    rules: list[dict],
    force_profile: bool = False,
) -> NoticeResultTag:
    """对单条公告重新跑规则识别（采购人/地区/成交类型/商品），写回标签表。"""
    existing = NoticeResultTag.objects.filter(notice_raw_id=raw.id).select_related("buyer_profile").first()
    buyer_name = ((parsed.buyer_name if parsed else "") or "").strip()
    title = ((parsed.notice_title if parsed else "") or raw.title or "").strip()
    region_text = ((parsed.region_name if parsed else "") or raw.region_name or "")
    with transaction.atomic():
        _tag_products(raw.id, rules, force=force_profile)
        deal = classify_deal_kind(title=title, product_rows=_product_rows_for_notice(raw.id), rules=rules)
        profile = existing.buyer_profile if existing and existing.buyer_profile_id else None
        confidence = deal["confidence"]
        if buyer_name:
            classified = classify_buyer(buyer_name, region_text, rules)
            confidence = max(classified["confidence"], deal["confidence"])
            profile, _created = NoticeBuyerProfile.objects.get_or_create(
                name_key=_name_key(buyer_name),
                defaults={"buyer_name": buyer_name, "source": "rule"},
            )
            if force_profile or not profile.locked:
                profile.buyer_name = buyer_name
                profile.org_type = classified["orgType"]
                profile.nature = classified["nature"]
                profile.province = classified["province"]
                profile.city = classified["city"]
                profile.district = classified["district"]
                profile.source = "rule"
                profile.confidence = classified["confidence"]
                if force_profile:
                    profile.locked = False
                profile.save()
        elif region_text and not profile:
            classified = classify_buyer("", region_text, rules)
            confidence = max(classified["confidence"], deal["confidence"])
        NoticeResultTag.objects.update_or_create(
            notice_raw_id=raw.id,
            defaults={
                "buyer_profile": profile,
                "deal_kind": deal["dealKind"],
                "source": "rule",
                "confidence": confidence,
                "locked": False,
            },
        )
    return NoticeResultTag.objects.select_related("buyer_profile").get(notice_raw_id=raw.id)


def retag_notice(notice_raw_id: int, *, force: bool = False) -> dict:
    """指定公告重新识别。已锁定时需 force=True。"""
    existing = NoticeResultTag.objects.filter(notice_raw_id=notice_raw_id).select_related("buyer_profile").first()
    if existing and existing.locked and not force:
        return {
            "ok": False,
            "locked": True,
            "detail": "标签已锁定。确认后可强制重新识别并解除锁定。",
        }
    raw = NoticeRaw.objects.filter(id=notice_raw_id).only("id", "site_id", "notice_type", "title", "region_name").first()
    if not raw:
        return {"ok": False, "detail": "公告不存在。"}
    parsed = NoticeParsed.objects.filter(notice_raw_id=notice_raw_id).first()
    rules = _load_rules()
    tag = _retag_notice_record(raw=raw, parsed=parsed, rules=rules, force_profile=force)
    return {"ok": True, "noticeRawId": tag.notice_raw_id, "dealKind": tag.deal_kind or ""}


def _tag_products(notice_raw_id: int, rules: list[dict], *, force: bool = False) -> None:
    goods = NoticeGoods.objects.filter(notice_raw_id=notice_raw_id).order_by("line_no", "id")
    for item in goods:
        name = (item.product_name or "").strip()
        existing = NoticeProductTag.objects.filter(notice_raw_id=notice_raw_id, goods_id=item.id).first()
        if existing and existing.locked and not force:
            continue
        category = _rule_value(rules, "product_category", name) or (item.category or "")
        brand = _rule_value(rules, "product_brand", name) or (item.brand or "")
        NoticeProductTag.objects.update_or_create(
            notice_raw_id=notice_raw_id,
            goods_id=item.id,
            defaults={
                "category": category[:128],
                "product_name": name[:512],
                "brand": brand[:128],
                "source": "rule",
                "confidence": Decimal("0.70") if brand or category else Decimal("0.40"),
                "locked": False,
            },
        )


def correct_notice_tag(notice_raw_id: int, payload: dict) -> NoticeResultTag | None:
    tag = NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id=notice_raw_id).first()
    parsed = NoticeParsed.objects.filter(notice_raw_id=notice_raw_id).first()
    if not tag or not tag.buyer_profile or not parsed:
        return None
    profile = tag.buyer_profile
    profile.org_type = str(payload.get("orgType") or profile.org_type or "")[:32]
    profile.nature = str(payload.get("nature") or profile.nature or "")[:32]
    profile.province = str(payload.get("province") or "")[:32]
    profile.city = str(payload.get("city") or "")[:64]
    profile.district = str(payload.get("district") or "")[:64]
    profile.source = "manual"
    profile.locked = True
    profile.confidence = Decimal("1.00")
    profile.save()
    deal_kind = _normalize_deal_kind(str(payload.get("dealKind") or tag.deal_kind or ""))
    if deal_kind not in (DEAL_KIND_GOODS, DEAL_KIND_SERVICE, DEAL_KIND_ENGINEERING, DEAL_KIND_UNKNOWN):
        deal_kind = DEAL_KIND_UNKNOWN
    tag.deal_kind = deal_kind
    tag.source = "manual"
    tag.locked = True
    tag.confidence = Decimal("1.00")
    tag.save(update_fields=["deal_kind", "source", "locked", "confidence", "updated_at"])
    buyer = profile.buyer_name
    _upsert_rule("buyer_org_type", buyer, profile.org_type)
    _upsert_rule("buyer_nature", buyer, profile.nature)
    _upsert_rule("buyer_province", buyer, profile.province)
    _upsert_rule("buyer_city", buyer, profile.city)
    _upsert_rule("buyer_district", buyer, profile.district)
    title = (parsed.notice_title or "").strip()
    if title and deal_kind in DEAL_KINDS:
        _upsert_rule("deal_kind", title, deal_kind)
    for row in payload.get("products") or []:
        goods_id = row.get("goodsId")
        if goods_id in (None, ""):
            continue
        product_name = str(row.get("productName") or "")[:512]
        category = str(row.get("category") or "")[:128]
        brand = str(row.get("brand") or "")[:128]
        NoticeProductTag.objects.update_or_create(
            notice_raw_id=notice_raw_id,
            goods_id=int(goods_id),
            defaults={
                "product_name": product_name,
                "category": category,
                "brand": brand,
                "source": "manual",
                "confidence": Decimal("1.00"),
                "locked": True,
            },
        )
        _upsert_rule("product_category", product_name, category)
        _upsert_rule("product_brand", product_name, brand)
    return tag


def batch_correct_notice_tags(notice_ids: list[int], payload: dict) -> dict[str, int]:
    """批量修正类型 / 性质 / 成交；仅更新 payload 中给出的字段，并锁定。"""
    ids: list[int] = []
    for value in notice_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    # 去重并限量，避免一次过大
    ids = list(dict.fromkeys(ids))[:200]
    if not ids:
        return {"updated": 0, "skipped": 0}

    patch_org = "orgType" in payload and str(payload.get("orgType") or "").strip() != ""
    patch_nature = "nature" in payload and str(payload.get("nature") or "").strip() != ""
    patch_deal = "dealKind" in payload and str(payload.get("dealKind") or "").strip() != ""
    if not (patch_org or patch_nature or patch_deal):
        return {"updated": 0, "skipped": len(ids)}

    org_type = str(payload.get("orgType") or "").strip()[:32] if patch_org else ""
    nature = str(payload.get("nature") or "").strip()[:32] if patch_nature else ""
    deal_kind = _normalize_deal_kind(str(payload.get("dealKind") or "")) if patch_deal else ""

    tags = {
        tag.notice_raw_id: tag
        for tag in NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id__in=ids)
    }
    parsed_map = {
        row.notice_raw_id: row
        for row in NoticeParsed.objects.filter(notice_raw_id__in=ids).only("notice_raw_id", "notice_title")
    }
    updated = 0
    skipped = 0
    for notice_id in ids:
        tag = tags.get(notice_id)
        if not tag or not tag.buyer_profile:
            skipped += 1
            continue
        profile = tag.buyer_profile
        if patch_org:
            profile.org_type = org_type
        if patch_nature:
            profile.nature = nature
        profile.source = "manual"
        profile.locked = True
        profile.confidence = Decimal("1.00")
        profile.save()
        if patch_deal:
            tag.deal_kind = deal_kind
        tag.source = "manual"
        tag.locked = True
        tag.confidence = Decimal("1.00")
        tag.save(update_fields=["deal_kind", "source", "locked", "confidence", "updated_at"])
        buyer = profile.buyer_name
        if patch_org:
            _upsert_rule("buyer_org_type", buyer, profile.org_type)
        if patch_nature:
            _upsert_rule("buyer_nature", buyer, profile.nature)
        if patch_deal:
            title = ((parsed_map.get(notice_id).notice_title if parsed_map.get(notice_id) else "") or "").strip()
            if title and tag.deal_kind in DEAL_KINDS:
                _upsert_rule("deal_kind", title, tag.deal_kind)
        updated += 1
    return {"updated": updated, "skipped": skipped}


def _stats_parsed_queryset(*, notice_kinds: list[str] | None = None):
    """统计底表：默认全部公告；可按公告类型多选过滤。"""
    qs = NoticeParsed.objects.all()
    kinds = [kind for kind in (notice_kinds or []) if kind and kind != "全部"]
    if not kinds:
        return qs
    from .notice_views import _raw_ids_for_kinds

    kind_q = _raw_ids_for_kinds(kinds, "")
    if kind_q == Q():
        return qs
    return qs.filter(notice_raw_id__in=NoticeRaw.objects.filter(kind_q).values("id"))


def build_result_stats(
    *,
    period: str,
    province: str = "",
    buyer: str = "",
    deal_kind: str = "",
    site_ids: list[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    publish_date_from: str = "",
    publish_date_to: str = "",
    start_date_from: str = "",
    start_date_to: str = "",
    end_date_from: str = "",
    end_date_to: str = "",
    notice_kinds: list[str] | None = None,
) -> dict:
    # 发布日期起止优先于周期预设
    publish_from = (publish_date_from or start_date or "").strip()
    publish_to = (publish_date_to or end_date or "").strip()
    if publish_from or publish_to:
        period = "custom"
        if publish_from and publish_to:
            start_date, end_date = publish_from, publish_to
        elif publish_from:
            start_date = end_date = publish_from
        else:
            start_date = end_date = publish_to
    period = normalize_stats_period(period, start_date, end_date)
    start, end = period_bounds(period, start_date=start_date, end_date=end_date)
    parsed_qs = _stats_parsed_queryset(notice_kinds=notice_kinds).filter(publish_time__gte=start, publish_time__lt=end)
    start_bounds = _inclusive_day_bounds(start_date_from, start_date_to)
    if start_bounds:
        parsed_qs = parsed_qs.filter(start_time__gte=start_bounds[0], start_time__lt=start_bounds[1])
    end_bounds = _inclusive_day_bounds(end_date_from, end_date_to)
    if end_bounds:
        parsed_qs = parsed_qs.filter(end_time__gte=end_bounds[0], end_time__lt=end_bounds[1])
    if site_ids is not None:
        if not site_ids:
            return {
                "period": period,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "startDate": start.date().isoformat(),
                "endDate": (end.date() - timedelta(days=1)).isoformat(),
                "noticeCount": 0,
                "dealAmount": "0.00",
                "buyerCount": 0,
                "goodsCount": 0,
                "byDealKind": [{"dealKind": kind, "count": 0, "amount": "0.00"} for kind in DEAL_KINDS],
                "byNoticeKind": [],
                "byProvince": [],
                "byRegion": [],
                "byBuyer": [],
                "noticeKinds": list(notice_kinds or []),
            }
        parsed_qs = parsed_qs.filter(notice_raw_id__in=NoticeRaw.objects.filter(site_id__in=site_ids).values("id"))
    rows = list(
        parsed_qs.values(
            "notice_raw_id",
            "buyer_name",
            "region_name",
            "deal_amount",
            "budget_amount",
            "notice_title",
            "notice_kind",
            "publish_time",
        )
    )
    raw_ids = [row["notice_raw_id"] for row in rows]
    tags = {
        tag.notice_raw_id: tag
        for tag in NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id__in=raw_ids)
    }
    province = province.strip()
    buyer = buyer.strip()
    deal_kind = deal_kind.strip()
    if deal_kind and deal_kind not in DEAL_KINDS:
        deal_kind = ""
    kept = []
    for row in rows:
        tag = tags.get(row["notice_raw_id"])
        profile = tag.buyer_profile if tag and tag.buyer_profile_id else None
        row_deal_kind = ((tag.deal_kind if tag else "") or "").strip() or DEAL_KIND_UNKNOWN
        row_province = (profile.province if profile else "") or ""
        row_city = (profile.city if profile else "") or ""
        row_district = (profile.district if profile else "") or ""
        row_buyer = (profile.buyer_name if profile else "") or (row.get("buyer_name") or "")
        row_region = row.get("region_name") or ""
        if province and province not in row_province and province not in row_region and province not in row_city and province not in row_district:
            continue
        if buyer and buyer not in row_buyer:
            continue
        if deal_kind and row_deal_kind != deal_kind:
            continue
        if profile and (row_province or row_city or row_district):
            province_label = row_province or "未分区"
            # 无市：归「省级」（仅到省、未落到具体市）
            city_label = row_city or "省级"
            region_label = "".join(part for part in (row_province, row_city, row_district) if part)
        else:
            # 无标签时尽量从地区文案抽出省；否则归「未分区」
            guessed = parse_region(row_region)
            province_label = guessed.get("province") or "未分区"
            city_label = guessed.get("city") or "省级"
            region_label = row_region or "未分区"
        notice_kind_label = ((row.get("notice_kind") or "").strip()) or "未分类"
        kept.append((row, profile, row_buyer, region_label, province_label, city_label, row_deal_kind, notice_kind_label))
    amount = Decimal("0")
    buyers = set()
    by_region: dict[str, dict] = {}
    by_province: dict[str, dict] = {}
    by_buyer: dict[str, dict] = {}
    by_deal_kind: dict[str, dict] = {
        kind: {"dealKind": kind, "count": 0, "amount": Decimal("0")} for kind in DEAL_KINDS
    }
    by_notice_kind: dict[str, dict] = {}
    for row, profile, row_buyer, region_label, province_label, city_label, row_deal_kind, notice_kind_label in kept:
        deal = row.get("deal_amount") or Decimal("0")
        amount += deal
        if row_buyer:
            buyers.add(row_buyer)
        region_bucket = by_region.setdefault(region_label, {"region": region_label, "count": 0, "amount": Decimal("0")})
        region_bucket["count"] += 1
        region_bucket["amount"] += deal
        province_bucket = by_province.setdefault(
            province_label,
            {"province": province_label, "count": 0, "amount": Decimal("0"), "cities": {}},
        )
        province_bucket["count"] += 1
        province_bucket["amount"] += deal
        city_bucket = province_bucket["cities"].setdefault(
            city_label,
            {"city": city_label, "count": 0, "amount": Decimal("0")},
        )
        city_bucket["count"] += 1
        city_bucket["amount"] += deal
        kind_bucket = by_deal_kind.setdefault(
            row_deal_kind,
            {"dealKind": row_deal_kind, "count": 0, "amount": Decimal("0")},
        )
        kind_bucket["count"] += 1
        kind_bucket["amount"] += deal
        notice_kind_bucket = by_notice_kind.setdefault(
            notice_kind_label,
            {"noticeKind": notice_kind_label, "count": 0, "amount": Decimal("0")},
        )
        notice_kind_bucket["count"] += 1
        notice_kind_bucket["amount"] += deal
        if row_buyer:
            buyer_bucket = by_buyer.setdefault(row_buyer, {"buyerName": row_buyer, "orgType": profile.org_type if profile else "", "nature": profile.nature if profile else "", "count": 0, "amount": Decimal("0")})
            buyer_bucket["count"] += 1
            buyer_bucket["amount"] += deal
    goods_count = NoticeProductTag.objects.filter(notice_raw_id__in=[row["notice_raw_id"] for row, *_rest in kept]).count()
    if goods_count == 0 and kept:
        goods_count = NoticeGoods.objects.filter(notice_raw_id__in=[row["notice_raw_id"] for row, *_rest in kept]).count()

    def money(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"

    province_rows = []
    for item in sorted(by_province.values(), key=lambda entry: entry["count"], reverse=True):
        cities = [
            {"city": city["city"], "count": city["count"], "amount": money(city["amount"])}
            for city in sorted(item["cities"].values(), key=lambda entry: entry["count"], reverse=True)
        ]
        province_rows.append(
            {
                "province": item["province"],
                "count": item["count"],
                "amount": money(item["amount"]),
                "cities": cities,
            }
        )

    deal_kind_order = {kind: index for index, kind in enumerate(DEAL_KINDS)}
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "startDate": start.date().isoformat(),
        "endDate": (end.date() - timedelta(days=1)).isoformat(),
        "noticeCount": len(kept),
        "dealAmount": money(amount),
        "buyerCount": len(buyers),
        "goodsCount": goods_count,
        "noticeKinds": [kind for kind in (notice_kinds or []) if kind],
        "byDealKind": [
            {"dealKind": item["dealKind"], "count": item["count"], "amount": money(item["amount"])}
            for item in sorted(
                by_deal_kind.values(),
                key=lambda entry: (deal_kind_order.get(entry["dealKind"], 99), -entry["count"]),
            )
            if item["count"] > 0 or item["dealKind"] in DEAL_KINDS
        ],
        "byNoticeKind": [
            {"noticeKind": item["noticeKind"], "count": item["count"], "amount": money(item["amount"])}
            for item in sorted(by_notice_kind.values(), key=lambda entry: entry["count"], reverse=True)
        ],
        "byProvince": province_rows,
        "byRegion": [
            {"region": item["region"], "count": item["count"], "amount": money(item["amount"])}
            for item in sorted(by_region.values(), key=lambda item: item["amount"], reverse=True)[:30]
        ],
        "byBuyer": [
            {**item, "amount": money(item["amount"])}
            for item in sorted(by_buyer.values(), key=lambda item: item["amount"], reverse=True)[:30]
        ],
    }


def safe_stats(**kwargs) -> dict:
    try:
        return build_result_stats(**kwargs)
    except DatabaseError:
        return {
            "period": kwargs.get("period") or "this_month",
            "noticeCount": 0,
            "dealAmount": "0.00",
            "buyerCount": 0,
            "goodsCount": 0,
            "noticeKinds": list(kwargs.get("notice_kinds") or []),
            "byDealKind": [{"dealKind": kind, "count": 0, "amount": "0.00"} for kind in DEAL_KINDS],
            "byNoticeKind": [],
            "byProvince": [],
            "byRegion": [],
            "byBuyer": [],
            "detail": "公告表尚未创建",
        }
