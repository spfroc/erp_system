"""门户公告订阅：结构规范化与多维匹配。"""

from __future__ import annotations

import re
from typing import Any

# 与 notices.PORTAL_DEAL_NOTICE_KINDS 保持一致（避免循环/重依赖导入）
PORTAL_DEAL_NOTICE_KINDS = ("成交公告", "结果公告", "成交结果公告")

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
SHANDONG_CITY_SET = set(SHANDONG_CITIES)
NOTICE_CATEGORIES = ("公告", "结果")
DEFAULT_PUSH_TIMES = ("18:00",)
MAX_PUSH_TIMES = 5
MAX_PUSH_TIMES_PER_HOUR = 3
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _split_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        parts = [str(item or "").strip() for item in value]
    else:
        text = str(value or "").strip()
        parts = re.split(r"[\s,，;；|]+", text) if text else []
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        out.append(part[:64])
        if len(out) >= 20:
            break
    return out


def _string_list(value: Any, *, limit: int = 20, item_len: int = 64) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif value in (None, ""):
        raw = []
    else:
        raw = _split_keywords(value)
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()[:item_len]
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _normalize_city_name(value: str) -> str:
    text = str(value or "").strip()
    if text.endswith("市") and len(text) > 1:
        text = text[:-1]
    return text[:64]


def _normalize_regions(value: Any) -> list[dict[str, str]]:
    """仅保留山东省内地市；city 存简称（济南）。"""
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            city = _normalize_city_name(item)
            province = "山东省"
        elif isinstance(item, dict):
            city = _normalize_city_name(str(item.get("city") or ""))
            province = str(item.get("province") or "").strip()[:32] or "山东省"
        else:
            continue
        if city not in SHANDONG_CITY_SET:
            continue
        if city in seen:
            continue
        seen.add(city)
        out.append({"province": "山东省", "city": city, "district": ""})
        if len(out) >= 20:
            break
    return out


def _hhmm_to_minutes(value: str) -> int | None:
    match = _HHMM_RE.match(str(value or "").strip())
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def normalize_push_times(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif value in (None, ""):
        raw = []
    else:
        raw = [value]
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if len(text) == 4 and text[1] == ":":
            text = f"0{text}"
        if not _HHMM_RE.match(text) or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= MAX_PUSH_TIMES:
            break
    out.sort(key=lambda item: _hhmm_to_minutes(item) or 0)
    return out


def validate_push_times(value: Any) -> tuple[list[str], str | None]:
    """校验推送时刻：最多 5 个；任意连续 1 小时窗口内不超过 3 个。"""
    times = normalize_push_times(value)
    if not times:
        return list(DEFAULT_PUSH_TIMES), None
    if len(times) > MAX_PUSH_TIMES:
        return times[:MAX_PUSH_TIMES], f"推送时刻最多 {MAX_PUSH_TIMES} 个。"
    minutes = [_hhmm_to_minutes(item) for item in times]
    for index, start in enumerate(minutes):
        if start is None:
            return times, "推送时刻格式无效。"
        count = sum(1 for item in minutes[index:] if item is not None and start <= item < start + 60)
        if count > MAX_PUSH_TIMES_PER_HOUR:
            return times, f"1 小时内推送时刻最多 {MAX_PUSH_TIMES_PER_HOUR} 个。"
    return times, None


def normalize_notice_categories(value: Any) -> list[str]:
    raw = value
    if isinstance(value, str):
        raw = _split_keywords(value)
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text in NOTICE_CATEGORIES and text not in out:
            out.append(text)
    return out


def classify_notice_category(notice_kind: str = "") -> str:
    kind = str(notice_kind or "").strip()
    if not kind:
        return "公告"
    if kind in PORTAL_DEAL_NOTICE_KINDS or re.search(r"成交|结果", kind):
        return "结果"
    return "公告"


def normalize_subscription(payload: dict | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    keywords = _string_list(raw.get("keywords"))
    # 标签已下线：规范化时清空，避免旧数据继续生效
    content_tags: list[str] = []
    org_types = _string_list(raw.get("orgTypes") or raw.get("org_types"), item_len=32)
    buyers: list[str] = []
    regions = _normalize_regions(raw.get("regions") or raw.get("cities"))
    notice_categories = normalize_notice_categories(
        raw.get("noticeCategories") or raw.get("notice_categories") or raw.get("noticeTypes")
    )
    push_times, _ = validate_push_times(raw.get("pushTimes") or raw.get("push_times"))
    has_filters = bool(keywords or org_types or regions or notice_categories)
    enabled = bool(raw.get("enabled")) and has_filters
    return {
        "enabled": enabled,
        "keywords": keywords,
        "keywordsText": " ".join(keywords),
        "contentTags": content_tags,
        "regions": regions,
        "buyers": buyers,
        "orgTypes": org_types,
        "noticeCategories": notice_categories,
        "pushTimes": push_times,
    }


def subscription_has_filters(sub: dict[str, Any]) -> bool:
    return bool(
        (sub.get("keywords") or [])
        or (sub.get("regions") or [])
        or (sub.get("orgTypes") or [])
        or (sub.get("noticeCategories") or [])
    )


def subscription_summary(sub: dict[str, Any]) -> str:
    parts: list[str] = []
    if sub.get("noticeCategories"):
        parts.append("类型:" + "/".join(sub["noticeCategories"]))
    if sub.get("regions"):
        region_bits = [str(row.get("city") or "") for row in sub["regions"][:4] if row.get("city")]
        if region_bits:
            parts.append("地区:" + "/".join(region_bits))
    if sub.get("keywords"):
        parts.append("关键词:" + "/".join(sub["keywords"][:3]))
    if sub.get("orgTypes"):
        parts.append("单位:" + "/".join(sub["orgTypes"][:2]))
    if sub.get("pushTimes"):
        parts.append("推送:" + "/".join(sub["pushTimes"][:3]))
    text = "；".join(parts) if parts else "未设置条件"
    return text[:120]


def _region_match(notice_region: dict[str, str], rule: dict[str, str]) -> bool:
    """规则填到哪一级，就要求公告对应级匹配；未填的级不限制。"""
    for key in ("province", "city", "district"):
        wanted = (rule.get(key) or "").strip()
        if not wanted:
            continue
        actual = (notice_region.get(key) or "").strip()
        if not actual:
            # city 规则可用 region_name 兜底，由上层处理
            if key == "city":
                return False
            return False
        wanted_norm = _normalize_city_name(wanted) if key == "city" else wanted
        actual_norm = _normalize_city_name(actual) if key == "city" else actual
        if wanted_norm not in actual_norm and actual_norm not in wanted_norm:
            return False
    return True


def notice_matches_subscription(
    *,
    subscription: dict[str, Any],
    title: str = "",
    project_name: str = "",
    buyer_name: str = "",
    content_tag: str = "",
    org_type: str = "",
    province: str = "",
    city: str = "",
    district: str = "",
    region_name: str = "",
    notice_kind: str = "",
) -> bool:
    """公告类型为「且」过滤；关键词/地区/单位之间为「或」。"""
    del content_tag, buyer_name  # 标签与采购人条件已下线
    sub = normalize_subscription(subscription)
    if not subscription_has_filters(sub):
        return False

    categories = sub.get("noticeCategories") or []
    if categories:
        if classify_notice_category(notice_kind) not in categories:
            return False

    title_blob = f"{title or ''} {project_name or ''}"
    notice_region = {
        "province": province or "",
        "city": city or "",
        "district": district or "",
    }
    if not any(notice_region.values()) and region_name:
        notice_region = {"province": region_name, "city": region_name, "district": ""}

    other_filters = bool(sub["keywords"] or sub["orgTypes"] or sub["regions"])
    if not other_filters:
        # 仅选了公告类型时，类型命中即可
        return bool(categories)

    if sub["keywords"] and any(keyword in title_blob for keyword in sub["keywords"]):
        return True

    if sub["orgTypes"]:
        org = (org_type or "").strip()
        if org and org in sub["orgTypes"]:
            return True

    if sub["regions"]:
        if any(_region_match(notice_region, rule) for rule in sub["regions"]):
            return True
        fallback = region_name or "".join(notice_region.values())
        for rule in sub["regions"]:
            needle = str(rule.get("city") or "").strip()
            if needle and (needle in fallback or _normalize_city_name(needle) in _normalize_city_name(fallback)):
                return True

    return False
