from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

# 公告业务时区：网站展示与入库墙钟统一用上海时间（naive DATETIME）
APP_TZ = ZoneInfo("Asia/Shanghai")


def now() -> datetime:
    """当前上海墙钟（naive），写入 MySQL DATETIME。"""
    return datetime.now(APP_TZ).replace(tzinfo=None)


def html_to_text(html: Optional[str]) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_TIME_TOKEN = r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"
_TIME_RANGE_RE = re.compile(
    rf"(?:报价|竞价|报名|采购|询比)?\s*(?:时间|起止时间|时段)\s*[:：]?\s*{_TIME_TOKEN}\s*"
    rf"(?:至|到|—|–|-|~|～)\s*{_TIME_TOKEN}",
    re.I,
)
_START_TIME_RE = re.compile(
    rf"(?:竞价|报价|报名|采购|询比)?\s*(?:开始时间|起始时间|开标时间)\s*[:：]\s*{_TIME_TOKEN}",
    re.I,
)
_END_TIME_RE = re.compile(
    rf"(?:竞价|报价|报名|采购|询比)?\s*(?:截止时间|结束时间|终止时间|闭标时间)\s*[:：]\s*{_TIME_TOKEN}",
    re.I,
)
_PLAIN_START_RE = re.compile(rf"开始时间\s*[:：]\s*{_TIME_TOKEN}", re.I)
_PLAIN_END_RE = re.compile(rf"(?:结束时间|截止时间)\s*[:：]\s*{_TIME_TOKEN}", re.I)

START_TIME_KEYS = (
    "startTime",
    "beginTime",
    "quoteStartTime",
    "bidStartTime",
    "auctionStartTime",
    "offerStartTime",
    "priceStartTime",
    "enrollStartTime",
    "signStartTime",
)
END_TIME_KEYS = (
    "endTime",
    "closeTime",
    "deadline",
    "quoteEndTime",
    "bidEndTime",
    "auctionEndTime",
    "offerEndTime",
    "priceEndTime",
    "enrollEndTime",
    "signEndTime",
)


def _normalize_time_token(raw: str) -> str:
    text = (raw or "").strip()
    text = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("/", "-")
        .replace("  ", " ")
        .strip()
    )
    return text


def extract_time_window(*blobs: Any) -> tuple[Optional[datetime], Optional[datetime]]:
    """从正文/HTML 抽报价起止时间，支持「报价时间：A至B」与独立开始/结束字段。"""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    text = "\n".join(str(b) for b in blobs if b)
    if not text.strip():
        return None, None

    m = _TIME_RANGE_RE.search(text)
    if m:
        start = parse_dt(_normalize_time_token(m.group(1))) or start
        end = parse_dt(_normalize_time_token(m.group(2))) or end

    if start is None:
        for pattern in (_START_TIME_RE, _PLAIN_START_RE):
            m = pattern.search(text)
            if m:
                start = parse_dt(_normalize_time_token(m.group(1)))
                if start:
                    break
    if end is None:
        for pattern in (_END_TIME_RE, _PLAIN_END_RE):
            m = pattern.search(text)
            if m:
                end = parse_dt(_normalize_time_token(m.group(1)))
                if end:
                    break
    return start, end


def pick_time_value(*sources: Any, keys: tuple[str, ...] = START_TIME_KEYS) -> Any:
    """从多个 dict 里按候选键取时间字段。"""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in keys:
            value = src.get(key)
            if value not in (None, ""):
                return value
    return None


def parse_dt(value: Any) -> Optional[datetime]:
    """解析为上海墙钟 naive datetime。

    - 秒/毫秒时间戳：按绝对时刻转上海本地
    - 无时区字符串（网站常用）：视为已是上海本地时间
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(APP_TZ).replace(tzinfo=None)
        return value
    if isinstance(value, (int, float)) or (isinstance(value, str) and str(value).strip().isdigit()):
        # JD createTime 常为毫秒时间戳
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=APP_TZ).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip().replace("T", " ")
    for fmt, n in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y/%m/%d %H:%M:%S", 19),
        ("%Y-%m-%d", 10),
        ("%Y/%m/%d", 10),
    ):
        try:
            return datetime.strptime(s[:n], fmt)
        except ValueError:
            continue
    return None


def ensure_https(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url.lstrip("/")


# 京东租户固定区域：青慧采=青岛，泉E采=济南
SITE_FIXED_REGIONS = {
    "jd-qing-huicai": "青岛",
    "jd-quan-yicai": "济南",
}

# 山东地市（公告主要覆盖范围），用于从「山东省青岛市市南区」等长串中取短名
SHANDONG_CITIES = (
    "济南",
    "青岛",
    "淄博",
    "枣庄",
    "东营",
    "烟台",
    "潍坊",
    "济宁",
    "泰安",
    "威海",
    "日照",
    "临沂",
    "德州",
    "聊城",
    "滨州",
    "菏泽",
)
_CITY_SUFFIX_RE = re.compile(r"(特别行政区|自治区|地区|盟|州|市)$")
_PROVINCE_PREFIX_RE = re.compile(r"^[\u4e00-\u9fff]{2,3}省")


# 项目名称里机构后缀（长的优先），用于从名称拆采购单位
_ORG_SUFFIXES = (
    "幼儿师范高等专科学校",
    "高等专科学校",
    "职业技术学院",
    "职业学院",
    "专科学校",
    "实验幼儿园",
    "附属幼儿园",
    "幼儿园",
    "附属小学",
    "实验小学",
    "附属中学",
    "实验中学",
    "教育和体育局",
    "教育体育局",
    "卫生健康局",
    "街道办事处",
    "消防救援支队",
    "救援支队",
    "人民法院",
    "人民检察院",
    "检察院",
    "公安局",
    "分局",
    "小学",
    "中学",
    "学校",
    "学院",
    "大学",
    "医院",
    "研究院",
    "研究所",
    "设计院",
    "服务中心",
    "管理中心",
    "交易中心",
    "中心",
    "委员会",
    "管理局",
    "办公室",
    "办事处",
    "博物馆",
    "图书馆",
    "文化馆",
    "纪念馆",
    "档案馆",
    "组织部",
    "宣传部",
    "财政局",
    "党校",
    "政府",
    "集团",
    "公司",
    "支队",
    "局",
    "厅",
    "部",
    "处",
    "站",
    "所",
    "院",
    "馆",
    "队",
    "园",
)
_NAME_PREFIX_RE = re.compile(r"^(?:关于|有关)")


def extract_buyer_from_project_name(project_name: str | None) -> str | None:
    """从京东类项目名称拆采购单位。

    常见形态：
    - 单位+内容+品类：济南幼儿师范……（实验园）+楼梯不锈钢栏杆升级维护+工程类
    - 单位紧贴内容：齐长城文化研究院设计服务 / 济南护理职业学院智慧教学系统
    """
    text = _NAME_PREFIX_RE.sub("", (project_name or "").strip()).strip()
    if not text:
        return None

    # 全角加号
    if "+" in text or "＋" in text:
        first = re.split(r"[+＋]", text, maxsplit=1)[0].strip()
        if len(first) >= 4:
            return first

    # 从名称开头匹配「……机构后缀」，后缀后还需有项目内容
    best: str | None = None
    best_len = 0
    for suf in _ORG_SUFFIXES:
        start = 0
        while True:
            idx = text.find(suf, start)
            if idx < 0:
                break
            end = idx + len(suf)
            # 括号补充：常春藤幼儿园（实验园）
            if end < len(text) and text[end] in "（(":
                close = "）" if text[end] == "（" else ")"
                close_at = text.find(close, end)
                if close_at > end:
                    end = close_at + 1
            if end >= len(text):
                start = idx + 1
                continue
            # 后缀起点过靠后则跳过（避免尾部「中心/公司」误伤）；允许单位占名称大部分
            if idx > max(12, int(len(text) * 0.85)):
                start = idx + 1
                continue
            candidate = text[:end].strip()
            if len(candidate) >= 4 and len(candidate) > best_len:
                best = candidate
                best_len = len(candidate)
            start = idx + 1
    return best


def extract_district_name(region_name: str | None) -> str | None:
    """从接口 regionName 抽出区县（地市之后的部分）。

    例：
    - 聊城市东昌府区 → 东昌府区
    - 临沂市沂水县 → 沂水县
    - 青岛市胶州市 → 胶州市
    - 淄博市 / 山东省 / 淄博市本级 → None
    """
    text = (region_name or "").strip()
    if not text:
        return None
    text = _PROVINCE_PREFIX_RE.sub("", text).strip() or text
    for city in SHANDONG_CITIES:
        for prefix in (f"{city}市", city):
            if text.startswith(prefix):
                rest = text[len(prefix) :].strip()
                if rest in ("本级", "市本级"):
                    return None
                return rest or None
            idx = text.find(prefix)
            if idx >= 0:
                rest = text[idx + len(prefix) :].strip()
                if rest in ("本级", "市本级"):
                    return None
                if rest:
                    return rest
    # 非标准地市前缀（如驻鲁专区）不拆区县
    return None


def normalize_region_name(site_id: str | None, region_name: str | None) -> str | None:
    """统一区域展示：站点固定值优先，其余压成地级市短名（去掉「市」等后缀）。"""
    fixed = SITE_FIXED_REGIONS.get((site_id or "").strip())
    if fixed:
        return fixed
    text = (region_name or "").strip()
    if not text:
        return None

    for city in SHANDONG_CITIES:
        if city in text:
            return city

    for sep in ("/", "\\", "-", "—", "·", ">", "|"):
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if parts:
                picked = next(
                    (
                        p
                        for p in parts
                        if p.endswith(("市", "州", "地区", "盟", "自治区", "特别行政区"))
                    ),
                    parts[0],
                )
                text = picked
            break

    text = _PROVINCE_PREFIX_RE.sub("", text).strip()
    text = _CITY_SUFFIX_RE.sub("", text).strip()
    return text or None
