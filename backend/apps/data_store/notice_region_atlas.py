"""行政区划补全：只有市/区县时默认补省、市。数据以山东为主。"""

from __future__ import annotations

import re

# 地级市简称 -> 省（不含“市”后缀）
CITY_TO_PROVINCE: dict[str, str] = {
    # 山东
    "济南": "山东省",
    "青岛": "山东省",
    "淄博": "山东省",
    "枣庄": "山东省",
    "东营": "山东省",
    "烟台": "山东省",
    "潍坊": "山东省",
    "济宁": "山东省",
    "泰安": "山东省",
    "威海": "山东省",
    "日照": "山东省",
    "临沂": "山东省",
    "德州": "山东省",
    "聊城": "山东省",
    "滨州": "山东省",
    "菏泽": "山东省",
    "莱芜": "山东省",
    # 常见外省（公告里偶发）
    "北京": "北京市",
    "上海": "上海市",
    "天津": "天津市",
    "重庆": "重庆市",
}

# 区/县全称 -> (省, 市)
DISTRICT_TO_CITY: dict[str, tuple[str, str]] = {
    # 济南
    "历下区": ("山东省", "济南市"),
    "槐荫区": ("山东省", "济南市"),
    "天桥区": ("山东省", "济南市"),
    "历城区": ("山东省", "济南市"),
    "长清区": ("山东省", "济南市"),
    "章丘区": ("山东省", "济南市"),
    "济阳区": ("山东省", "济南市"),
    "莱芜区": ("山东省", "济南市"),
    "钢城区": ("山东省", "济南市"),
    "平阴县": ("山东省", "济南市"),
    "商河县": ("山东省", "济南市"),
    # 青岛
    "市南区": ("山东省", "青岛市"),
    "市北区": ("山东省", "青岛市"),
    "黄岛区": ("山东省", "青岛市"),
    "崂山区": ("山东省", "青岛市"),
    "李沧区": ("山东省", "青岛市"),
    "城阳区": ("山东省", "青岛市"),
    "即墨区": ("山东省", "青岛市"),
    "胶州市": ("山东省", "青岛市"),
    "平度市": ("山东省", "青岛市"),
    "莱西市": ("山东省", "青岛市"),
    "四方区": ("山东省", "青岛市"),  # 历史区名，仍常见于单位名
    # 淄博
    "淄川区": ("山东省", "淄博市"),
    "张店区": ("山东省", "淄博市"),
    "博山区": ("山东省", "淄博市"),
    "临淄区": ("山东省", "淄博市"),
    "周村区": ("山东省", "淄博市"),
    "桓台县": ("山东省", "淄博市"),
    "高青县": ("山东省", "淄博市"),
    "沂源县": ("山东省", "淄博市"),
    # 枣庄
    "薛城区": ("山东省", "枣庄市"),
    "峄城区": ("山东省", "枣庄市"),
    "台儿庄区": ("山东省", "枣庄市"),
    "山亭区": ("山东省", "枣庄市"),
    "滕州市": ("山东省", "枣庄市"),
    # 东营
    "东营区": ("山东省", "东营市"),
    "河口区": ("山东省", "东营市"),
    "垦利区": ("山东省", "东营市"),
    "利津县": ("山东省", "东营市"),
    "广饶县": ("山东省", "东营市"),
    # 烟台
    "芝罘区": ("山东省", "烟台市"),
    "福山区": ("山东省", "烟台市"),
    "牟平区": ("山东省", "烟台市"),
    "莱山区": ("山东省", "烟台市"),
    "蓬莱区": ("山东省", "烟台市"),
    "龙口市": ("山东省", "烟台市"),
    "莱阳市": ("山东省", "烟台市"),
    "莱州市": ("山东省", "烟台市"),
    "招远市": ("山东省", "烟台市"),
    "栖霞市": ("山东省", "烟台市"),
    "海阳市": ("山东省", "烟台市"),
    # 潍坊
    "潍城区": ("山东省", "潍坊市"),
    "寒亭区": ("山东省", "潍坊市"),
    "坊子区": ("山东省", "潍坊市"),
    "奎文区": ("山东省", "潍坊市"),
    "临朐县": ("山东省", "潍坊市"),
    "昌乐县": ("山东省", "潍坊市"),
    "青州市": ("山东省", "潍坊市"),
    "诸城市": ("山东省", "潍坊市"),
    "寿光市": ("山东省", "潍坊市"),
    "安丘市": ("山东省", "潍坊市"),
    "高密市": ("山东省", "潍坊市"),
    "昌邑市": ("山东省", "潍坊市"),
    # 济宁
    "任城区": ("山东省", "济宁市"),
    "兖州区": ("山东省", "济宁市"),
    "微山县": ("山东省", "济宁市"),
    "鱼台县": ("山东省", "济宁市"),
    "金乡县": ("山东省", "济宁市"),
    "嘉祥县": ("山东省", "济宁市"),
    "汶上县": ("山东省", "济宁市"),
    "泗水县": ("山东省", "济宁市"),
    "梁山县": ("山东省", "济宁市"),
    "曲阜市": ("山东省", "济宁市"),
    "邹城市": ("山东省", "济宁市"),
    # 泰安
    "泰山区": ("山东省", "泰安市"),
    "岱岳区": ("山东省", "泰安市"),
    "宁阳县": ("山东省", "泰安市"),
    "东平县": ("山东省", "泰安市"),
    "新泰市": ("山东省", "泰安市"),
    "肥城市": ("山东省", "泰安市"),
    # 威海
    "环翠区": ("山东省", "威海市"),
    "文登区": ("山东省", "威海市"),
    "荣成市": ("山东省", "威海市"),
    "乳山市": ("山东省", "威海市"),
    # 日照
    "东港区": ("山东省", "日照市"),
    "岚山区": ("山东省", "日照市"),
    "五莲县": ("山东省", "日照市"),
    "莒县": ("山东省", "日照市"),
    # 临沂
    "兰山区": ("山东省", "临沂市"),
    "罗庄区": ("山东省", "临沂市"),
    "河东区": ("山东省", "临沂市"),
    "沂南县": ("山东省", "临沂市"),
    "郯城县": ("山东省", "临沂市"),
    "沂水县": ("山东省", "临沂市"),
    "兰陵县": ("山东省", "临沂市"),
    "费县": ("山东省", "临沂市"),
    "平邑县": ("山东省", "临沂市"),
    "莒南县": ("山东省", "临沂市"),
    "蒙阴县": ("山东省", "临沂市"),
    "临沭县": ("山东省", "临沂市"),
    # 德州
    "德城区": ("山东省", "德州市"),
    "陵城区": ("山东省", "德州市"),
    "宁津县": ("山东省", "德州市"),
    "庆云县": ("山东省", "德州市"),
    "临邑县": ("山东省", "德州市"),
    "齐河县": ("山东省", "德州市"),
    "平原县": ("山东省", "德州市"),
    "夏津县": ("山东省", "德州市"),
    "武城县": ("山东省", "德州市"),
    "乐陵市": ("山东省", "德州市"),
    "禹城市": ("山东省", "德州市"),
    # 聊城
    "东昌府区": ("山东省", "聊城市"),
    "茌平区": ("山东省", "聊城市"),
    "阳谷县": ("山东省", "聊城市"),
    "莘县": ("山东省", "聊城市"),
    "东阿县": ("山东省", "聊城市"),
    "冠县": ("山东省", "聊城市"),
    "高唐县": ("山东省", "聊城市"),
    "临清市": ("山东省", "聊城市"),
    # 滨州
    "滨城区": ("山东省", "滨州市"),
    "沾化区": ("山东省", "滨州市"),
    "惠民县": ("山东省", "滨州市"),
    "阳信县": ("山东省", "滨州市"),
    "无棣县": ("山东省", "滨州市"),
    "博兴县": ("山东省", "滨州市"),
    "邹平市": ("山东省", "滨州市"),
    # 菏泽
    "牡丹区": ("山东省", "菏泽市"),
    "定陶区": ("山东省", "菏泽市"),
    "曹县": ("山东省", "菏泽市"),
    "单县": ("山东省", "菏泽市"),
    "成武县": ("山东省", "菏泽市"),
    "巨野县": ("山东省", "菏泽市"),
    "郓城县": ("山东省", "菏泽市"),
    "鄄城县": ("山东省", "菏泽市"),
    "东明县": ("山东省", "菏泽市"),
}


_CITY_NOISE = ("税务", "公安", "警察", "消防", "医院", "学校", "总局", "支队", "大队", "中队", "派出所", "交警")


def find_known_city(text: str) -> tuple[str, int, int] | None:
    """在文本中定位已知地级市，返回 (市名, start, end)。"""
    text = text or ""
    best: tuple[str, int, int] | None = None
    for key in sorted(CITY_TO_PROVINCE, key=len, reverse=True):
        for candidate in (f"{key}市", key):
            idx = text.find(candidate)
            if idx < 0:
                continue
            end = idx + len(candidate)
            city = normalize_city_name(candidate)
            if best is None or len(candidate) > len(best[0]) or (len(candidate) == len(best[0]) and idx < best[1]):
                best = (city, idx, end)
    return best


def sanitize_city_label(city: str, blob: str = "") -> str:
    city = (city or "").strip()
    if not city:
        return ""
    if any(token in city for token in _CITY_NOISE):
        known = find_known_city(city) or find_known_city(blob)
        return known[0] if known else ""
    return normalize_city_name(city)


def sanitize_district_label(district: str, blob: str = "") -> str:
    district = (district or "").strip()
    if not district:
        return ""
    for zone in (
        "经济技术开发区",
        "高新技术产业开发区",
        "高新技术开发区",
        "工业园区",
        "高新区",
        "开发区",
    ):
        if zone in district or zone in (blob or ""):
            # 仅当区划字段本身是开发区类，或 blob 里紧跟已知市名后出现
            if district == zone or district.endswith(zone):
                return zone
    # 「省级旅游度假区」不是行政区
    if "度假区" in district or district.startswith("省级"):
        return ""
    # 去掉机关名前缀，只保留末尾区/县
    cleaned = re.sub(
        r"^.*?(警察|支队|大队|中队|公安|消防|税务|学校|医院|中心|教育局|分局)",
        "",
        district,
    )
    match = re.search(r"([\u4e00-\u9fff]{1,8}(?:区|县))$", cleaned or district)
    if match:
        value = match.group(1)
        # 不要把「文登区天福社区」整段当成区名
        if "社区" in value or "街道" in value or "度假" in value:
            zone = re.search(r"([\u4e00-\u9fff]{1,6}(?:区|县))", value)
            value = zone.group(1) if zone else ""
        if value and value not in {"区", "县"} and not any(token in value for token in _CITY_NOISE):
            if any(token in value for token in ("局", "委", "部", "办", "育", "省级")):
                return ""
            return value
    if any(token in district for token in _CITY_NOISE):
        return ""
    if "社区" in district or district.endswith("街道") or "度假区" in district:
        zone = re.search(r"([\u4e00-\u9fff]{1,6}(?:区|县))", district)
        if zone and "度假" not in zone.group(1) and "局" not in zone.group(1):
            return zone.group(1)
        return ""
    return district


def _city_key(name: str) -> str:
    name = (name or "").strip()
    for suffix in ("市", "地区", "州", "盟"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def normalize_city_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if name in {"北京市", "上海市", "天津市", "重庆市"}:
        return name
    key = _city_key(name)
    if key in CITY_TO_PROVINCE:
        province = CITY_TO_PROVINCE[key]
        if province.endswith("市"):
            return province
        return f"{key}市"
    return name if name.endswith(("市", "州", "盟")) else name


# 「山东博物馆」这类只有省简称、无「省」字
_PROVINCE_SHORT = (
    ("内蒙古", "内蒙古自治区"),
    ("广西", "广西壮族自治区"),
    ("西藏", "西藏自治区"),
    ("宁夏", "宁夏回族自治区"),
    ("新疆", "新疆维吾尔自治区"),
    ("黑龙江", "黑龙江省"),
    ("山东", "山东省"),
    ("河南", "河南省"),
    ("河北", "河北省"),
    ("山西", "山西省"),
    ("江苏", "江苏省"),
    ("浙江", "浙江省"),
    ("安徽", "安徽省"),
    ("福建", "福建省"),
    ("江西", "江西省"),
    ("湖南", "湖南省"),
    ("湖北", "湖北省"),
    ("广东", "广东省"),
    ("海南", "海南省"),
    ("四川", "四川省"),
    ("贵州", "贵州省"),
    ("云南", "云南省"),
    ("陕西", "陕西省"),
    ("甘肃", "甘肃省"),
    ("青海", "青海省"),
    ("辽宁", "辽宁省"),
    ("吉林", "吉林省"),
)
_KNOWN_PROVINCES = {full for _short, full in _PROVINCE_SHORT} | {"北京市", "上海市", "天津市", "重庆市"}


def normalize_province_name(name: str) -> str:
    """只保留真实省名；『济宁北湖省』这类由『省级』误切的一律清空。"""
    name = (name or "").strip()
    if not name:
        return ""
    if name in _KNOWN_PROVINCES:
        return name
    for short, full in _PROVINCE_SHORT:
        if name in {short, f"{short}省", full}:
            return full
    if name in {"北京", "上海", "天津", "重庆"}:
        return f"{name}市"
    return ""


def enrich_region(province: str, city: str, district: str, *texts: str) -> dict[str, str]:
    """缺省时按市/区县补全省、市；青岛这类无“市”字也会识别。"""
    province = normalize_province_name(province)
    city = (city or "").strip()
    district = (district or "").strip()
    blob = "".join(text for text in texts if text)

    # 省字段里不应出现机关名
    if province and any(token in province for token in _CITY_NOISE):
        province = ""

    if not province:
        for short, full in _PROVINCE_SHORT:
            # 要求「山东省」完整出现，或文首简称；避免「省级」误命中
            if full in blob or blob.startswith(short) or re.search(rf"{re.escape(short)}省(?!级)", blob):
                province = full
                break

    city = sanitize_city_label(city, blob)
    if not city:
        known = find_known_city(blob)
        if known:
            city = known[0]

    district = sanitize_district_label(district, blob)

    if district and district in DISTRICT_TO_CITY:
        mapped_province, mapped_city = DISTRICT_TO_CITY[district]
        if not province:
            province = mapped_province
        if not city:
            city = mapped_city

    if not district:
        for zone in (
            "经济技术开发区",
            "高新技术产业开发区",
            "高新技术开发区",
            "工业园区",
            "高新区",
            "开发区",
        ):
            if zone in blob:
                district = zone
                break
    if not district:
        for key in sorted(DISTRICT_TO_CITY, key=len, reverse=True):
            if key in blob:
                district = key
                mapped_province, mapped_city = DISTRICT_TO_CITY[key]
                if not province:
                    province = mapped_province
                if not city:
                    city = mapped_city
                break

    # 县级市（胶州/滕州等）提升为「地级市 + 区县」
    if city in DISTRICT_TO_CITY:
        mapped_province, mapped_city = DISTRICT_TO_CITY[city]
        if not province:
            province = mapped_province
        if not district:
            district = city
        city = mapped_city

    if city and not province:
        key = _city_key(city)
        province = CITY_TO_PROVINCE.get(key) or CITY_TO_PROVINCE.get(city) or ""

    if province in {"北京", "上海", "天津", "重庆"}:
        province = f"{province}市"
        if not city:
            city = province

    return {"province": province, "city": city, "district": district}
