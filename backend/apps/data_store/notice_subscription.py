"""门户公告订阅：结构规范化与多维匹配。"""

from __future__ import annotations

import re
from typing import Any


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


def _normalize_regions(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        province = str(item.get("province") or "").strip()[:32]
        city = str(item.get("city") or "").strip()[:64]
        district = str(item.get("district") or "").strip()[:64]
        if not province and not city and not district:
            continue
        key = (province, city, district)
        if key in seen:
            continue
        seen.add(key)
        out.append({"province": province, "city": city, "district": district})
        if len(out) >= 20:
            break
    return out


def normalize_subscription(payload: dict | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    # 兼容旧版 keywords 字符串
    keywords = _string_list(raw.get("keywords"))
    content_tags = _string_list(raw.get("contentTags") or raw.get("content_tags"))
    org_types = _string_list(raw.get("orgTypes") or raw.get("org_types"), item_len=32)
    buyers = _string_list(raw.get("buyers"), item_len=128)
    regions = _normalize_regions(raw.get("regions"))
    has_filters = bool(keywords or content_tags or org_types or buyers or regions)
    enabled = bool(raw.get("enabled")) and has_filters
    return {
        "enabled": enabled,
        "keywords": keywords,
        # 对外仍提供字符串，兼容旧门户表单回显
        "keywordsText": " ".join(keywords),
        "contentTags": content_tags,
        "regions": regions,
        "buyers": buyers,
        "orgTypes": org_types,
    }


def subscription_has_filters(sub: dict[str, Any]) -> bool:
    return bool(
        (sub.get("keywords") or [])
        or (sub.get("contentTags") or [])
        or (sub.get("regions") or [])
        or (sub.get("buyers") or [])
        or (sub.get("orgTypes") or [])
    )


def subscription_summary(sub: dict[str, Any]) -> str:
    parts: list[str] = []
    if sub.get("contentTags"):
        parts.append("标签:" + "/".join(sub["contentTags"][:3]))
    if sub.get("regions"):
        region_bits = []
        for row in sub["regions"][:2]:
            region_bits.append("".join(filter(None, [row.get("province"), row.get("city"), row.get("district")])))
        if region_bits:
            parts.append("地区:" + "/".join(region_bits))
    if sub.get("keywords"):
        parts.append("关键词:" + "/".join(sub["keywords"][:3]))
    if sub.get("buyers"):
        parts.append("采购人:" + "/".join(sub["buyers"][:2]))
    if sub.get("orgTypes"):
        parts.append("单位:" + "/".join(sub["orgTypes"][:2]))
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
            return False
        # 允许「山东省」对「山东」这类包含关系
        if wanted not in actual and actual not in wanted:
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
) -> bool:
    """多维度为「或」：任一已填维度命中即匹配；同一维度内多个选项仍为「或」。"""
    sub = normalize_subscription(subscription)
    if not subscription_has_filters(sub):
        return False

    title_blob = f"{title or ''} {project_name or ''}"
    notice_region = {
        "province": province or "",
        "city": city or "",
        "district": district or "",
    }
    # 无结构化地区时，把 region_name 放到 province 槽位做包含匹配
    if not any(notice_region.values()) and region_name:
        notice_region = {"province": region_name, "city": "", "district": ""}

    if sub["keywords"] and any(keyword in title_blob for keyword in sub["keywords"]):
        return True

    if sub["contentTags"]:
        tag = (content_tag or "").strip()
        if tag and tag in sub["contentTags"]:
            return True

    if sub["orgTypes"]:
        org = (org_type or "").strip()
        if org and org in sub["orgTypes"]:
            return True

    if sub["buyers"]:
        buyer = buyer_name or ""
        if any(token in buyer for token in sub["buyers"]):
            return True

    if sub["regions"]:
        if any(_region_match(notice_region, rule) for rule in sub["regions"]):
            return True
        # region_name 兜底：整串包含规则拼接
        fallback = region_name or "".join(notice_region.values())
        for rule in sub["regions"]:
            needle = "".join(filter(None, [rule.get("province"), rule.get("city"), rule.get("district")]))
            if needle and needle in fallback:
                return True

    return False
