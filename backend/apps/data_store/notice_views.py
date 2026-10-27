from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import ProgrammingError
from django.db.models import Exists, OuterRef, Q, TextField
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_models import NoticeGoods, NoticeParsed, NoticeRaw
from .notice_tag_models import NoticeResultTag
from .views import _require_permission

# 列表查询只取展示所需列，避免拖出 MEDIUMTEXT / 大 JSON
_LIST_RAW_ONLY = (
    "id",
    "site_id",
    "notice_key",
    "auction_type",
    "notice_type",
    "title",
    "region_name",
    "publish_time",
    "source_url",
    "crawl_status",
    "parse_status",
    "crawled_at",
)
_LIST_PARSED_ONLY = (
    "notice_raw_id",
    "site_id",
    "project_code",
    "project_name",
    "notice_title",
    "buyer_name",
    "buyer_contact_name",
    "buyer_phone",
    "buyer_address",
    "buyer_contact",
    "region_name",
    "budget_amount",
    "deal_amount",
    "deal_supplier",
    "notice_kind",
    "procurement_mode",
    "publish_time",
    "start_time",
    "end_time",
)
_OPTIONS_TTL_SEC = 60.0
_options_cache: dict[str, tuple[float, Any]] = {}


def _cached_options(key: str, builder):
    now = time.monotonic()
    hit = _options_cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = builder()
    _options_cache[key] = (now + _OPTIONS_TTL_SEC, value)
    return value


SITE_LABELS = {
    "sd-ggzyjyzx": "山东网上商城",
    "jd-quan-yicai": "京东泉易采",
    "jd-qing-huicai": "京东青慧采",
}

# 与抓取端一致：青慧采=青岛，泉E采=济南
SITE_FIXED_REGIONS = {
    "jd-qing-huicai": "青岛",
    "jd-quan-yicai": "济南",
}
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


def _normalize_region_name(site_id: str | None, region_name: str | None) -> str | None:
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


def _resolve_region(raw: NoticeRaw, parsed: NoticeParsed | None) -> str | None:
    raw_region = (parsed.region_name if parsed and parsed.region_name else None) or raw.region_name
    return _normalize_region_name(raw.site_id, raw_region)

# 与京东公告页 tab 一致：竞价公告 / 询比公告 / 成交 / 终止 / 失败 / 废标
JD_NOTICE_TYPE_LABELS = {
    "1": "竞价公告",
    "2": "成交公告",
    "3": "终止公告",
    "4": "失败公告",
    "5": "询比公告",
    "6": "废标公告",
}
JD_SITE_IDS = frozenset({"jd-quan-yicai", "jd-qing-huicai"})

# 结果类公告一般不算「进行中」
CLOSED_NOTICE_KINDS = (
    "成交公告",
    "成交结果公告",
    "成交结果",
    "终止公告",
    "终止",
    "废标公告",
    "废标",
    "失败公告",
    "结果公告",
)
CLOSED_KIND_KEYWORDS = ("成交结果", "结果公告", "终止", "废标", "失败公告", "成交公告")
# 「进行中」不包含直接采购 / 直购
DIRECT_PURCHASE_KEYWORDS = ("直接采购", "直购")

# 列表接口按分类抓取时已写入 notice_raw.notice_type，未解析也能显示
NOTICE_TYPE_LABELS = {
    "jd-quan-yicai": JD_NOTICE_TYPE_LABELS,
    "jd-qing-huicai": JD_NOTICE_TYPE_LABELS,
    "sd-ggzyjyzx": {
        "0": "采购公告",
        "1": "成交公告",
        "5": "终止公告",
        "10": "终止公告",
        "13": "公示公告",
    },
    "sd-gpfa-frame": {
        "0": "采购公告",
        "1": "成交公告",
        "10": "终止公告",
    },
}


def _parse_dt(value: Any):
    """解析字符串 / 秒或毫秒时间戳为 aware datetime。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        num = float(value)
        # 13 位毫秒 / 10 位秒
        if num > 1e12:
            num = num / 1000.0
        try:
            return datetime.fromtimestamp(num, tz=timezone.get_current_timezone())
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip().replace("T", " ")
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            naive = datetime.strptime(s[:n], fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def _json_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _field_deferred(obj, name: str) -> bool:
    try:
        return name in obj.get_deferred_fields()
    except Exception:  # noqa: BLE001
        return False


def _safe_json_dict(obj, name: str) -> dict:
    if _field_deferred(obj, name):
        return {}
    return _json_dict(getattr(obj, name, None))


def _notice_wall_clock(now=None) -> str:
    """公告库时间为上海墙钟 naive；筛选用同口径字符串，避免 ORM 时区偏移。"""
    now = now or timezone.now()
    if timezone.is_aware(now):
        local = timezone.localtime(now, timezone.get_default_timezone())
    else:
        local = now
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _dig(data: dict, *paths: str):
    """按 a.b.c 路径取值，跳过空值。"""
    for path in paths:
        cur: Any = data
        ok = True
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                ok = False
                break
            cur = cur[part]
        if ok and cur not in (None, "", []):
            return cur
    return None


def _from_notice_db(value):
    """notice_* 表由爬虫写入上海墙钟 naive DATETIME。

    Django USE_TZ=True 读 MySQL 时会把 naive 误标成 UTC，这里还原为 Asia/Shanghai。
    """
    if value is None:
        return None
    if timezone.is_aware(value):
        wall = timezone.make_naive(value, dt_timezone.utc)
    else:
        wall = value
    return timezone.make_aware(wall, timezone.get_default_timezone())


_TIME_TOKEN = r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"
_TIME_RANGE_RE = re.compile(
    rf"(?:报价|竞价|报名|采购|询比)?\s*(?:时间|起止时间|时段)\s*[:：]?\s*{_TIME_TOKEN}\s*"
    rf"(?:至|到|—|–|-|~|～)\s*{_TIME_TOKEN}",
    re.I,
)
_START_TIME_TEXT_RE = re.compile(
    rf"(?:竞价|报价|报名|采购|询比)?\s*(?:开始时间|起始时间|开标时间)\s*[:：]\s*{_TIME_TOKEN}",
    re.I,
)
_PLAIN_START_TIME_RE = re.compile(rf"开始时间\s*[:：]\s*{_TIME_TOKEN}", re.I)
_END_TIME_TEXT_RE = re.compile(
    rf"(?:竞价|报价|报名|采购|询比)?\s*(?:截止时间|结束时间|终止时间|闭标时间)\s*[:：]\s*{_TIME_TOKEN}",
    re.I,
)
_PLAIN_END_TIME_RE = re.compile(rf"(?:结束时间|截止时间)\s*[:：]\s*{_TIME_TOKEN}", re.I)


def _normalize_time_token(raw: str) -> str:
    text = (raw or "").strip()
    return (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("/", "-")
        .replace("  ", " ")
        .strip()
    )


def _extract_time_window_from_text(*blobs: str):
    """与 crawler utils.extract_time_window 对齐，供列表展示兜底。"""
    text = "\n".join(b for b in blobs if b)
    if not text.strip():
        return None, None
    start = end = None
    m = _TIME_RANGE_RE.search(text)
    if m:
        start = _parse_dt(_normalize_time_token(m.group(1)))
        end = _parse_dt(_normalize_time_token(m.group(2)))
    if start is None:
        for pattern in (_START_TIME_TEXT_RE, _PLAIN_START_TIME_RE):
            m = pattern.search(text)
            if m:
                start = _parse_dt(_normalize_time_token(m.group(1)))
                if start:
                    break
    if end is None:
        for pattern in (_END_TIME_TEXT_RE, _PLAIN_END_TIME_RE):
            m = pattern.search(text)
            if m:
                end = _parse_dt(_normalize_time_token(m.group(1)))
                if end:
                    break
    return start, end


_FW_DIGIT_TRANS = str.maketrans("０１２３４５６７８９－—　", "0123456789-- ")
_CONTACT_PHONE_FALLBACK_RE = re.compile(
    r"(?:项目|采购人|采购单位)?(?:联系方式|联系电话|联系号码|电话|手机号?)"
    r"\s*[:：]?\s*(?:\n|\r|\s)*"
    r"((?:\+?86[-\s]*)?1[3-9](?:[\s-]?\d){9}|0\d{2,3}[-\s]?\d{7,8})",
    re.I,
)
_CONTACT_NAME_FALLBACK_RE = re.compile(
    r"(?:项目|采购人|采购单位)?联系人\s*[:：]\s*([^\n\r，,；;。、<>{}]{1,20})"
)
_SECTION_CONTACT_HEADER_RE = re.compile(
    r"^[（(]?[一二三四五六七八九十百千零\d]+[、.．)）].{0,12}联系方式\s*$"
    r"|^\s*项目联系方式\s*$"
)


def _normalize_phone_display(raw: str | None) -> str | None:
    if not raw:
        return None
    text = str(raw).translate(_FW_DIGIT_TRANS).replace(" ", "").replace("　", "")
    text = re.sub(r"^\+?86", "", text)
    m = re.search(r"(1[3-9]\d{9})", text)
    if m:
        return m.group(1)
    m = re.search(r"(0\d{2,3}-?\d{7,8})", text)
    if m:
        return m.group(1)
    return None


def _clean_fallback_contact_name(raw: str | None) -> str | None:
    if not raw:
        return None
    name = re.sub(r"(?:联系方式|联系电话|电话|手机).*$", "", str(raw)).strip(" ：:,，")
    if not name or re.fullmatch(r"[\d\-\s]+", name):
        return None
    if "、" in name or name in {"联系", "方式", "电话", "手机", "四", "三", "二", "一"}:
        return None
    if re.match(r"^[一二三四五六七八九十\d]+", name):
        return None
    return name


def _extract_contact_from_text(*blobs: str) -> tuple[str | None, str | None]:
    text = "\n".join(b for b in blobs if b).translate(_FW_DIGIT_TRANS)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    if not text.strip():
        return None, None
    # 去掉供应商联系段，减少误命中
    safe = re.sub(r".{0,30}供应商联系.{0,80}", " ", text)
    name = None
    phone = None
    m = _CONTACT_NAME_FALLBACK_RE.search(safe)
    if m:
        name = _clean_fallback_contact_name(m.group(1))
    m = _CONTACT_PHONE_FALLBACK_RE.search(safe)
    if m:
        phone = _normalize_phone_display(m.group(1))
    if not name or not phone:
        lines = [ln.strip() for ln in safe.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            if _SECTION_CONTACT_HEADER_RE.match(line):
                for nxt in lines[i + 1 : i + 5]:
                    if _SECTION_CONTACT_HEADER_RE.match(nxt):
                        break
                    if not name:
                        nm = _CONTACT_NAME_FALLBACK_RE.search(nxt)
                        if nm:
                            name = _clean_fallback_contact_name(nm.group(1)) or name
                    if not phone:
                        phone = _normalize_phone_display(nxt)
                        if not phone:
                            pm = _CONTACT_PHONE_FALLBACK_RE.search(nxt)
                            if pm:
                                phone = _normalize_phone_display(pm.group(1))
                    if name and phone:
                        break
                continue
            if not phone and re.fullmatch(
                r"(?:项目|采购人)?(?:联系方式|联系电话|电话|手机)\s*[:：]?", line
            ):
                for nxt in lines[i + 1 : i + 3]:
                    phone = _normalize_phone_display(nxt)
                    if phone:
                        break
            if phone and name:
                break
    return name, phone


def _resolve_buyer_contact(raw: NoticeRaw, parsed: NoticeParsed | None) -> tuple[str | None, str | None]:
    name = (parsed.buyer_contact_name if parsed and parsed.buyer_contact_name else None) or None
    phone = _normalize_phone_display(parsed.buyer_phone if parsed else None)
    if name and phone:
        return name, phone
    detail = _json_dict(raw.detail_json)
    list_item = _json_dict(raw.list_json)
    if not name:
        name = (
            detail.get("contactName")
            or detail.get("linkMan")
            or detail.get("linkman")
            or list_item.get("contactName")
            or list_item.get("linkMan")
        )
    if not phone:
        phone = _normalize_phone_display(
            detail.get("contactPhone")
            or detail.get("linkPhone")
            or detail.get("linkTel")
            or detail.get("mobile")
            or detail.get("tel")
            or detail.get("phone")
            or list_item.get("contactPhone")
            or list_item.get("linkPhone")
            or list_item.get("mobile")
        )
    if not name or not phone:
        # 正文与 HTML 都扫一遍（联系块有时只在其一）
        t_name, t_phone = _extract_contact_from_text(
            raw.content_text or "",
            (raw.content_html or "")[:30000],
        )
        name = name or t_name
        phone = phone or t_phone
    if (not name or not phone) and parsed and (parsed.project_code or "").strip():
        # 成交/终止等：同项目编号其它公告（优先采购公告）已有联系方式时借用来展示
        siblings = list(
            NoticeParsed.objects.filter(
                site_id=raw.site_id,
                project_code=parsed.project_code,
            )
            .exclude(notice_raw_id=raw.id)
            .exclude(buyer_phone__isnull=True)
            .exclude(buyer_phone="")
            .only("buyer_contact_name", "buyer_phone", "notice_kind", "notice_raw_id")[:20]
        )
        siblings.sort(
            key=lambda s: (0 if (s.notice_kind or "") == "采购公告" else 1, -(s.notice_raw_id or 0))
        )
        if siblings:
            sib = siblings[0]
            name = name or sib.buyer_contact_name
            phone = phone or _normalize_phone_display(sib.buyer_phone)
    if name and ("、" in str(name) or re.match(r"^[一二三四五六七八九十\d]+", str(name))):
        name = None
    return (str(name).strip() if name else None), phone


def _resolve_times(raw: NoticeRaw, parsed: NoticeParsed | None) -> tuple:
    """优先 parsed，回落到 list/detail JSON（含京东嵌套毫秒时间）。

    列表查询 deferred 了大 JSON 时，只用 parsed 时间，避免 N+1。
    """
    start = _from_notice_db(parsed.start_time) if parsed and parsed.start_time else None
    end = _from_notice_db(parsed.end_time) if parsed and parsed.end_time else None
    if start and end:
        return start, end

    detail = _safe_json_dict(raw, "detail_json")
    list_item = _safe_json_dict(raw, "list_json")
    if not detail and not list_item:
        return start, end

    nested = _json_dict(detail.get("detail"))
    base = _json_dict(nested.get("auctionNoticeBaseInfo"))
    demand = _json_dict(nested.get("auctionDemandInfo"))
    start_keys = (
        "startTime",
        "beginTime",
        "quoteStartTime",
        "bidStartTime",
        "auctionStartTime",
        "offerStartTime",
        "priceStartTime",
    )
    end_keys = (
        "endTime",
        "closeTime",
        "deadline",
        "quoteEndTime",
        "bidEndTime",
        "auctionEndTime",
        "offerEndTime",
        "priceEndTime",
    )
    if not start:
        start = _parse_dt(
            _dig(detail, *start_keys)
            or _dig(list_item, *start_keys)
            or _dig(base, *start_keys)
            or _dig(demand, *start_keys)
        )
    if not end:
        end = _parse_dt(
            _dig(detail, *end_keys)
            or _dig(list_item, *end_keys)
            or _dig(base, *end_keys)
            or _dig(demand, *end_keys)
        )
    # 正文「报价时间：A至B」兜底（商城 HTML 常落在 content_text；列表 deferred 则跳过）
    if (not start or not end) and not (
        _field_deferred(raw, "content_text") and _field_deferred(raw, "content_html")
    ):
        blob = ""
        if not _field_deferred(raw, "content_text"):
            blob = (raw.content_text or "").strip()
        if len(blob) < 40 and not _field_deferred(raw, "content_html"):
            blob = ((raw.content_html or "")[:12000]).strip()
        if blob:
            t_start, t_end = _extract_time_window_from_text(blob)
            start = start or t_start
            end = end or t_end
    return start, end


def _kind_from_notice_type(site_id: str | None, notice_type: Any) -> str:
    code = str(notice_type).strip() if notice_type not in (None, "") else ""
    if not code:
        return ""
    return NOTICE_TYPE_LABELS.get(site_id or "", {}).get(code, "")


def _normalize_display_kind(site_id: str | None, kind: str) -> str:
    """把历史统一名改回各站原文（京东竞价页叫「竞价公告」不是「采购公告」）。"""
    text = (kind or "").strip()
    if not text or text.isdigit():
        return text
    if site_id in JD_SITE_IDS and text == "采购公告":
        return "竞价公告"
    return text


def _resolve_kind(raw: NoticeRaw, parsed: NoticeParsed | None) -> str:
    detail = _safe_json_dict(raw, "detail_json")
    list_item = _safe_json_dict(raw, "list_json")

    # 有站点 notice_type 映射时以其为准（与筛选、抓取分类一致）
    # 避免正文套话把采购公告误标成终止公告
    mapped = _kind_from_notice_type(raw.site_id, raw.notice_type)
    if not mapped:
        mapped = _kind_from_notice_type(
            raw.site_id,
            detail.get("noticeType")
            if detail.get("noticeType") not in (None, "")
            else list_item.get("noticeType"),
        )
    if mapped:
        return mapped

    kind = (parsed.notice_kind if parsed and parsed.notice_kind else "") or ""
    kind = _normalize_display_kind(raw.site_id, kind)
    # 解析结果有时只落了接口里的数字编码
    if kind and not kind.isdigit():
        return kind
    for key in ("noticeTypeName", "noticeKind", "typeName"):
        for src in (detail, list_item):
            v = src.get(key)
            if v and not str(v).strip().isdigit():
                return _normalize_display_kind(raw.site_id, str(v))
    title = (raw.title or "") + " " + (parsed.notice_title if parsed and parsed.notice_title else "")
    for token, label in (
        ("废标公告", "废标公告"),
        ("终止公告", "终止公告"),
        ("成交结果", "成交结果公告"),
        ("结果公告", "结果公告"),
        ("成交公告", "成交公告"),
        ("失败公告", "失败公告"),
        ("询比公告", "询比公告"),
        ("竞价公告", "竞价公告"),
        ("采购公告", "采购公告"),
    ):
        if token in title:
            return label
    return kind if kind and not kind.isdigit() else ""


def _raw_ids_for_kind(notice_kind: str, site_id: str) -> Q:
    """公告类型筛选：优先站点 notice_type；解析字段作无编码时的兜底。"""
    q = Q()
    for sid, mapping in NOTICE_TYPE_LABELS.items():
        if site_id and sid != site_id:
            continue
        codes = [code for code, label in mapping.items() if label == notice_kind]
        if codes:
            q |= Q(site_id=sid, notice_type__in=codes)

    # 解析字段兜底：排除「notice_type 已映射成其它类型」的冲突行
    parsed_qs = NoticeParsed.objects.filter(notice_kind=notice_kind)
    if site_id:
        parsed_qs = parsed_qs.filter(site_id=site_id)
    conflict = Q()
    for sid, mapping in NOTICE_TYPE_LABELS.items():
        if site_id and sid != site_id:
            continue
        other_codes = [code for code, label in mapping.items() if label != notice_kind]
        if other_codes:
            conflict |= Q(site_id=sid, notice_type__in=other_codes)
    q |= Q(id__in=parsed_qs.values("notice_raw_id")) & ~conflict

    # 京东历史曾把竞价公告写成「采购公告」
    if notice_kind == "竞价公告" and (not site_id or site_id in JD_SITE_IDS):
        legacy = NoticeParsed.objects.filter(
            site_id__in=JD_SITE_IDS if not site_id else [site_id],
            notice_kind="采购公告",
        )
        q |= Q(id__in=legacy.values("notice_raw_id")) & ~conflict

    return q if q else Q(pk__in=[])


def _parse_notice_kinds(*values: str) -> list[str]:
    kinds: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in str(value or "").replace("，", ",").split(","):
            kind = part.strip()
            if kind and kind not in seen:
                seen.add(kind)
                kinds.append(kind)
    return kinds


def _raw_ids_for_kinds(notice_kinds: list[str], site_id: str) -> Q:
    """多选公告类型：任一命中即可。空列表表示不按类型限制。"""
    kinds = [kind for kind in notice_kinds if kind and kind != "全部"]
    if not kinds:
        return Q()
    combined = Q()
    for kind in kinds:
        combined |= _raw_ids_for_kind(kind, site_id)
    return combined if combined else Q(pk__in=[])


def _notice_kind_options(site_id: str) -> list[str]:
    def build() -> list[str]:
        labels: set[str] = set()
        # 站点映射表本身就是完整枚举，优先用它，避免扫全表 distinct
        for sid, mapping in NOTICE_TYPE_LABELS.items():
            if site_id and sid != site_id:
                continue
            labels.update(mapping.values())
        kind_qs = NoticeParsed.objects.exclude(notice_kind__isnull=True).exclude(notice_kind="")
        if site_id:
            kind_qs = kind_qs.filter(site_id=site_id)
        for sid, kind in kind_qs.values_list("site_id", "notice_kind").distinct()[:200]:
            if not kind or str(kind).strip().isdigit():
                continue
            labels.add(_normalize_display_kind(sid, str(kind)))
        return sorted(labels)

    return _cached_options(f"notice_kinds:{site_id or '*'}", build)


def _is_closed_kind(kind: str, title: str = "") -> bool:
    text = f"{kind} {title}".strip()
    if not text:
        return False
    if kind in CLOSED_NOTICE_KINDS:
        return True
    return any(k in text for k in CLOSED_KIND_KEYWORDS)


def _is_direct_purchase(raw: NoticeRaw, parsed: NoticeParsed | None, kind: str, title: str) -> bool:
    """直接采购 / 直购不计入「进行中」。"""
    mode = (parsed.procurement_mode if parsed and parsed.procurement_mode else "") or ""
    text = f"{kind} {mode} {title}".strip()
    if any(k in text for k in DIRECT_PURCHASE_KEYWORDS):
        return True
    list_item = _safe_json_dict(raw, "list_json")
    detail = _safe_json_dict(raw, "detail_json")
    for src in (list_item, detail):
        for key in ("procurementMode", "projectTypeName", "noticeTypeName", "title"):
            v = src.get(key)
            if v and any(k in str(v) for k in DIRECT_PURCHASE_KEYWORDS):
                return True
    return False


def _progress_status(raw: NoticeRaw, parsed: NoticeParsed | None, now=None) -> str:
    """ongoing=进行中 / upcoming=未开始 / ended=已截止 / unknown=未知。"""
    now = now or timezone.now()
    start, end = _resolve_times(raw, parsed)
    kind = _resolve_kind(raw, parsed)
    title = (parsed.notice_title if parsed and parsed.notice_title else None) or raw.title or ""
    if _is_closed_kind(kind, title):
        return "ended"
    if end and end < now:
        return "ended"
    if start and start > now:
        return "upcoming"
    # 直接采购即使未截止也不算进行中
    if _is_direct_purchase(raw, parsed, kind, title):
        return "unknown"
    if end and end >= now and (not start or start <= now):
        return "ongoing"
    # 有截止时间且未开始时间：视为进行中（常见于商城列表只带 endTime）
    if end and end >= now and not start:
        return "ongoing"
    if not end and start and start <= now and ("采购" in kind or "竞价" in kind or "反拍" in kind):
        return "ongoing"
    return "unknown"


def _dec(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dt(value) -> str | None:
    """格式化为上海本地字符串；ORM 字段需先经 _from_notice_db。"""
    if not value:
        return None
    if timezone.is_aware(value):
        local = timezone.localtime(value, timezone.get_default_timezone())
    else:
        local = value
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _serialize_list_item(raw: NoticeRaw, parsed: NoticeParsed | None, now=None) -> dict:
    start, end = _resolve_times(raw, parsed)
    progress = _progress_status(raw, parsed, now=now)
    progress_label = {
        "ongoing": "进行中",
        "upcoming": "未开始",
        "ended": "已截止",
        "unknown": "未知",
    }.get(progress, "未知")
    kind = _resolve_kind(raw, parsed) or (parsed.notice_kind if parsed else None)
    publish = (parsed.publish_time if parsed and parsed.publish_time else None) or raw.publish_time
    return {
        "id": raw.id,
        "siteId": raw.site_id,
        "siteLabel": SITE_LABELS.get(raw.site_id or "", raw.site_id or ""),
        "noticeKey": raw.notice_key,
        "title": (parsed.notice_title if parsed and parsed.notice_title else None) or raw.title,
        "projectCode": parsed.project_code if parsed else None,
        "projectName": parsed.project_name if parsed else None,
        "buyerName": parsed.buyer_name if parsed else None,
        "dealSupplier": parsed.deal_supplier if parsed else None,
        "dealAmount": _dec(parsed.deal_amount) if parsed else None,
        "budgetAmount": _dec(parsed.budget_amount) if parsed else None,
        "noticeKind": kind,
        "procurementMode": parsed.procurement_mode if parsed else None,
        "regionName": _resolve_region(raw, parsed),
        "publishTime": _dt(_from_notice_db(publish)),
        "startTime": _dt(start),
        "endTime": _dt(end),
        "progressStatus": progress,
        "progressLabel": progress_label,
        "crawlStatus": raw.crawl_status,
        "parseStatus": raw.parse_status,
        "sourceUrl": raw.source_url,
        "crawledAt": _dt(_from_notice_db(raw.crawled_at)),
    }


# 同项目关联公告展示顺序：采购/竞价 → 结果类
_RELATED_KIND_ORDER = (
    "竞价公告",
    "询比公告",
    "采购公告",
    "成交公告",
    "成交结果公告",
    "失败公告",
    "终止公告",
    "废标公告",
    "公示公告",
)


def _related_kind_sort_key(kind: str | None) -> tuple[int, str]:
    label = (kind or "").strip()
    try:
        return (_RELATED_KIND_ORDER.index(label), label)
    except ValueError:
        return (len(_RELATED_KIND_ORDER), label)


_PROJECT_CODE_SUFFIX_RE = re.compile(r"[，,]\d+$")


def _normalize_project_code(code: str | None) -> str:
    """去掉成交公告常见的「，1」包号后缀，让同一项目能对上。"""
    text = (code or "").strip().replace("－", "-").replace("，", ",")
    text = _PROJECT_CODE_SUFFIX_RE.sub("", text)
    return text.strip(" ,，")


def _auction_no(site_id: str | None, notice_key: str | None) -> str:
    """京东公告键是「项目编号:类型」，项目编号才是同一采购的关联键。"""
    if site_id not in JD_SITE_IDS:
        return ""
    head, sep, tail = (notice_key or "").strip().partition(":")
    if sep and head and tail.isdigit():
        return head
    return ""


def _project_code_of(parsed: NoticeParsed | None) -> str:
    if not parsed:
        return ""
    return _normalize_project_code(parsed.project_code)


def _sort_related_items(items: list[dict]) -> list[dict]:
    items.sort(
        key=lambda item: (
            _related_kind_sort_key(item.get("noticeKind")),
            item.get("publishTime") or "",
            item.get("id") or 0,
        )
    )
    return items


def _related_from_raws(raws: list[NoticeRaw], *, exclude_raw_id: int | None, now=None) -> list[dict]:
    raws = [row for row in raws if exclude_raw_id is None or row.id != exclude_raw_id]
    if not raws:
        return []
    parsed_map = {
        item.notice_raw_id: item
        for item in NoticeParsed.objects.filter(notice_raw_id__in=[row.id for row in raws])
    }
    return _sort_related_items(
        [_serialize_list_item(row, parsed_map.get(row.id), now=now) for row in raws]
    )


def _load_related_notices(raw: NoticeRaw, parsed: NoticeParsed | None, now=None) -> list[dict]:
    """同一项目下的其他公告。京东按竞价单号，其余站点按规范化项目编号。"""
    auction = _auction_no(raw.site_id, raw.notice_key)
    if auction:
        siblings = list(
            NoticeRaw.objects.filter(site_id=raw.site_id, notice_key__startswith=f"{auction}:").exclude(id=raw.id)[:80]
        )
        return _related_from_raws(siblings, exclude_raw_id=None, now=now)

    code = _project_code_of(parsed)
    if not code:
        return []
    raw_ids = list(
        NoticeParsed.objects.filter(site_id=raw.site_id)
        .filter(Q(project_code=code) | Q(project_code__startswith=code + "，") | Q(project_code__startswith=code + ","))
        .exclude(notice_raw_id=raw.id)
        .values_list("notice_raw_id", flat=True)[:80]
    )
    if not raw_ids:
        return []
    return _related_from_raws(list(NoticeRaw.objects.filter(id__in=raw_ids)), exclude_raw_id=None, now=now)


def _sibling_kinds_by_project(
    *,
    project_codes: list[str],
    site_ids: list[str] | None = None,
) -> dict[tuple[str, str], list[str]]:
    """(site_id, project_code) -> 去重后的公告种类列表（含当前条）。"""
    codes = sorted({_normalize_project_code(c) for c in project_codes if _normalize_project_code(c)})
    if not codes:
        return {}
    code_query = Q()
    for code in codes:
        code_query |= Q(project_code=code) | Q(project_code__startswith=code + "，") | Q(project_code__startswith=code + ",")
    parsed_qs = NoticeParsed.objects.filter(code_query)
    if site_ids:
        parsed_qs = parsed_qs.filter(site_id__in=site_ids)
    parsed_rows = list(
        parsed_qs.values("notice_raw_id", "site_id", "project_code", "notice_kind")[:2000]
    )
    if not parsed_rows:
        return {}
    raw_ids = [row["notice_raw_id"] for row in parsed_rows]
    raw_type = {
        rid: (sid, ntype)
        for rid, sid, ntype in NoticeRaw.objects.filter(id__in=raw_ids).values_list(
            "id", "site_id", "notice_type"
        )
    }
    buckets: dict[tuple[str, str], set[str]] = {}
    for row in parsed_rows:
        code = _normalize_project_code(row.get("project_code") or "")
        if not code:
            continue
        sid = row.get("site_id") or ""
        raw_meta = raw_type.get(row["notice_raw_id"])
        notice_type = raw_meta[1] if raw_meta else None
        kind = _kind_from_notice_type(sid, notice_type) or _normalize_display_kind(
            sid, row.get("notice_kind") or ""
        )
        if not kind or str(kind).strip().isdigit():
            continue
        buckets.setdefault((sid, code), set()).add(kind)
    return {
        key: sorted(kinds, key=_related_kind_sort_key)
        for key, kinds in buckets.items()
    }


def _sibling_kinds_by_auction(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], list[str]]:
    """(site_id, auction_no) -> 该竞价单下的公告种类。"""
    unique = sorted({(site, auction) for site, auction in pairs if site and auction})
    if not unique:
        return {}
    query = Q()
    for site, auction in unique:
        query |= Q(site_id=site, notice_key__startswith=f"{auction}:")
    raw_rows = list(NoticeRaw.objects.filter(query).only("id", "site_id", "notice_key", "notice_type", "title")[:400])
    parsed_map = {
        item.notice_raw_id: item
        for item in NoticeParsed.objects.filter(notice_raw_id__in=[row.id for row in raw_rows])
    }
    buckets: dict[tuple[str, str], set[str]] = {}
    for raw in raw_rows:
        auction = _auction_no(raw.site_id, raw.notice_key)
        if not auction:
            continue
        kind = _resolve_kind(raw, parsed_map.get(raw.id))
        if not kind:
            continue
        buckets.setdefault((raw.site_id or "", auction), set()).add(kind)
    return {key: sorted(kinds, key=_related_kind_sort_key) for key, kinds in buckets.items()}


def _attach_sibling_kinds(items: list[dict]) -> list[dict]:
    auctions: list[tuple[str, str]] = []
    codes: list[str] = []
    code_sites: set[str] = set()
    for item in items:
        site = str(item.get("siteId") or "")
        auction = _auction_no(site, str(item.get("noticeKey") or ""))
        if auction:
            auctions.append((site, auction))
            continue
        code = _normalize_project_code(str(item.get("projectCode") or ""))
        if code:
            codes.append(code)
            if site:
                code_sites.add(site)
    auction_map = _sibling_kinds_by_auction(auctions)
    code_map = _sibling_kinds_by_project(project_codes=codes, site_ids=sorted(code_sites) or None)
    for item in items:
        site = str(item.get("siteId") or "")
        auction = _auction_no(site, str(item.get("noticeKey") or ""))
        if auction:
            kinds = auction_map.get((site, auction), [])
        else:
            kinds = code_map.get((site, _normalize_project_code(str(item.get("projectCode") or ""))), [])
        current = (item.get("noticeKind") or "").strip()
        others = [k for k in kinds if k != current]
        item["siblingKinds"] = others
        item["projectNoticeKinds"] = kinds
    return items


def _attach_result_tags(items: list[dict]) -> list[dict]:
    """批量挂上结果公告采购人标签，供列表首列展示。"""
    if not items:
        return items
    raw_ids = [int(item["id"]) for item in items if item.get("id") is not None]
    if not raw_ids:
        return items
    try:
        tags = {
            tag.notice_raw_id: tag
            for tag in NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id__in=raw_ids)
        }
    except Exception:
        tags = {}
    for item in items:
        tag = tags.get(int(item["id"]))
        profile = tag.buyer_profile if tag and tag.buyer_profile_id else None
        item["tagDealKind"] = ((tag.deal_kind if tag else "") or "").strip()
        if not profile:
            item["tagOrgType"] = ""
            item["tagNature"] = ""
            item["tagProvince"] = ""
            item["tagCity"] = ""
            item["tagDistrict"] = ""
            item["tagRegion"] = ""
            continue
        province = (profile.province or "").strip()
        city = (profile.city or "").strip()
        district = (profile.district or "").strip()
        item["tagOrgType"] = (profile.org_type or "").strip()
        item["tagNature"] = (profile.nature or "").strip()
        item["tagProvince"] = province
        item["tagCity"] = city
        item["tagDistrict"] = district
        item["tagRegion"] = " ".join(part for part in (province, city, district) if part)
    return items


def _serialize_detail(raw: NoticeRaw, parsed: NoticeParsed | None, goods: list[NoticeGoods]) -> dict:
    base = _serialize_list_item(raw, parsed)
    related = _load_related_notices(raw, parsed)
    sibling_kinds = sorted(
        {
            k
            for k in [base.get("noticeKind"), *[r.get("noticeKind") for r in related]]
            if k
        },
        key=_related_kind_sort_key,
    )
    contact_name, contact_phone = _resolve_buyer_contact(raw, parsed)
    contact_joined = " ".join(x for x in (contact_name, contact_phone) if x) or None
    base.update(
        {
            "buyerContactName": contact_name,
            "buyerPhone": contact_phone,
            "buyerAddress": parsed.buyer_address if parsed else None,
            "buyerContact": contact_joined or (parsed.buyer_contact if parsed else None),
            "dealSupplierPhone": parsed.deal_supplier_phone if parsed else None,
            "dealSupplierAddress": parsed.deal_supplier_address if parsed else None,
            "deliveryAddress": parsed.delivery_address if parsed else None,
            "quoteCount": parsed.quote_count if parsed else None,
            "quotes": parsed.quotes_json if parsed else [],
            "suppliers": parsed.suppliers_json if parsed else [],
            "modelName": parsed.model_name if parsed else None,
            "confidence": _dec(parsed.confidence) if parsed else None,
            "contentText": (raw.content_text or "")[:20000],
            "goods": [
                {
                    "id": g.id,
                    "lineNo": g.line_no,
                    "productName": g.product_name,
                    "category": g.category,
                    "quantity": _dec(g.quantity),
                    "unit": g.unit,
                    "brand": g.brand,
                    "model": g.product_model,
                    "unitPrice": _dec(g.unit_price),
                    "spec": g.spec,
                    "amount": _dec(g.amount),
                }
                for g in goods
            ],
            "relatedNotices": related,
            "siblingKinds": [k for k in sibling_kinds if k != base.get("noticeKind")],
            "projectNoticeKinds": sibling_kinds,
        }
    )
    return base


def _region_filter_q(region_name: str) -> Q:
    """区域筛选：固定站点映射 + 精确别名优先，长串用前缀/包含兜底。"""
    region = (region_name or "").strip()
    if not region:
        return Q()
    aliases = {region, f"{region}市"}
    q = Q(region_name__in=aliases)
    for site_id, label in SITE_FIXED_REGIONS.items():
        if label == region:
            q |= Q(site_id=site_id)
    # 历史长串：山东省济南市…；用子查询而不是先拉全量 id
    long_forms = {f"山东省{region}", f"山东省{region}市", f"{region}市"}
    parsed_match = NoticeParsed.objects.filter(
        Q(region_name__in=aliases | long_forms) | Q(region_name__startswith=f"山东省{region}")
    ).values("notice_raw_id")
    q |= Q(id__in=parsed_match) | Q(region_name__in=long_forms) | Q(
        region_name__startswith=f"山东省{region}"
    )
    return q


def _region_options(site_id: str = "") -> list[str]:
    def build() -> list[str]:
        labels: set[str] = set(SHANDONG_CITIES)
        if site_id:
            fixed = SITE_FIXED_REGIONS.get(site_id)
            if fixed:
                return [fixed]
            # 指定站点时仍返回山东地市全集，避免每次 distinct 扫表
            return sorted(labels)
        for sid, label in SITE_FIXED_REGIONS.items():
            labels.add(label)
        return sorted(labels)

    return _cached_options(f"notice_regions:{site_id or '*'}", build)


def _parse_filter_ymd(value: str) -> date | None:
    text = (value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _range_bound_strings(from_day: date | None, to_day: date | None) -> tuple[str | None, str | None]:
    """公告时间为上海墙钟 naive DATETIME；返回 [lo, hi) 字符串，缺省端为 None。"""
    if from_day and to_day and to_day < from_day:
        from_day, to_day = to_day, from_day
    lo = from_day.strftime("%Y-%m-%d 00:00:00") if from_day else None
    hi = (to_day + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00") if to_day else None
    return lo, hi


def _parsed_time_range_q(field: str, lo: str | None, hi: str | None) -> Q:
    filters: dict[str, str] = {}
    if lo:
        filters[f"{field}__gte"] = lo
    if hi:
        filters[f"{field}__lt"] = hi
    return Q(id__in=NoticeParsed.objects.filter(**filters).values("notice_raw_id"))


def _notice_day_filter_q(
    *,
    publish_from: str = "",
    publish_to: str = "",
    start_from: str = "",
    start_to: str = "",
    end_from: str = "",
    end_to: str = "",
) -> Q | None:
    """发布 / 开始 / 结束各一对起止日期（yyyy-mm-dd），闭区间按自然日筛选。"""
    q = Q()
    applied = False

    publish_lo, publish_hi = _range_bound_strings(_parse_filter_ymd(publish_from), _parse_filter_ymd(publish_to))
    if publish_lo or publish_hi:
        applied = True
        raw_filters: dict[str, str] = {}
        if publish_lo:
            raw_filters["publish_time__gte"] = publish_lo
        if publish_hi:
            raw_filters["publish_time__lt"] = publish_hi
        q &= Q(**raw_filters) | _parsed_time_range_q("publish_time", publish_lo, publish_hi)

    start_lo, start_hi = _range_bound_strings(_parse_filter_ymd(start_from), _parse_filter_ymd(start_to))
    if start_lo or start_hi:
        applied = True
        q &= _parsed_time_range_q("start_time", start_lo, start_hi)

    end_lo, end_hi = _range_bound_strings(_parse_filter_ymd(end_from), _parse_filter_ymd(end_to))
    if end_lo or end_hi:
        applied = True
        q &= _parsed_time_range_q("end_time", end_lo, end_hi)

    return q if applied else None


def _notice_field_filter_q(
    *,
    project_code: str,
    project_name: str,
    buyer_name: str,
    supplier_name: str,
    goods_name: str,
) -> Q | None:
    """按项目编号、项目名称、采购单位、供应商、商品名称叠加子查询。无筛选时返回 None。"""
    q = Q()
    applied = False
    if project_code:
        applied = True
        q &= Q(
            id__in=NoticeParsed.objects.filter(
                Q(project_code__icontains=project_code) | Q(notice_key__icontains=project_code)
            ).values("notice_raw_id")
        ) | Q(notice_key__icontains=project_code)
    if project_name:
        applied = True
        q &= Q(
            id__in=NoticeParsed.objects.filter(
                Q(project_name__icontains=project_name) | Q(notice_title__icontains=project_name)
            ).values("notice_raw_id")
        ) | Q(title__icontains=project_name)
    if buyer_name:
        applied = True
        q &= Q(
            id__in=NoticeParsed.objects.filter(buyer_name__icontains=buyer_name).values(
                "notice_raw_id"
            )
        )
    if supplier_name:
        applied = True
        # 优先 deal_supplier；JSON 文本兜底用 Exists，避免把全部命中 id 拉进 Python
        supplier_parsed = (
            NoticeParsed.objects.filter(notice_raw_id=OuterRef("pk"))
            .annotate(
                quotes_text=Cast("quotes_json", TextField()),
                suppliers_text=Cast("suppliers_json", TextField()),
            )
            .filter(
                Q(deal_supplier__icontains=supplier_name)
                | Q(quotes_text__icontains=supplier_name)
                | Q(suppliers_text__icontains=supplier_name)
            )
        )
        q &= Q(Exists(supplier_parsed))
    if goods_name:
        applied = True
        q &= Q(
            Exists(
                NoticeGoods.objects.filter(
                    notice_raw_id=OuterRef("pk"),
                    product_name__icontains=goods_name,
                )
            )
        )
    return q if applied else None


def _progress_filter_q(progress_target: str, now=None) -> Q:
    """进度筛选下推到 SQL（基于 notice_parsed 时间 + notice_type/kind），避免拉全表到内存。"""
    wall = _notice_wall_clock(now)
    closed_type_q = Q()
    for sid, mapping in NOTICE_TYPE_LABELS.items():
        codes = [
            code
            for code, label in mapping.items()
            if label in CLOSED_NOTICE_KINDS or any(k in label for k in ("成交", "终止", "废标", "失败"))
        ]
        if codes:
            closed_type_q |= Q(site_id=sid, notice_type__in=codes)

    closed_kind_ids = NoticeParsed.objects.filter(notice_kind__in=CLOSED_NOTICE_KINDS).values(
        "notice_raw_id"
    )
    closed_q = closed_type_q | Q(id__in=closed_kind_ids)

    direct_ids = NoticeParsed.objects.filter(
        Q(procurement_mode__icontains="直购") | Q(procurement_mode__icontains="直接采购")
    ).values("notice_raw_id")
    direct_q = Q(id__in=direct_ids)

    # 墙钟字符串直接比较，避免 USE_TZ 把上海时间当 UTC 偏移
    ended_by_time = NoticeParsed.objects.filter(end_time__lt=wall).values("notice_raw_id")
    upcoming_ids = NoticeParsed.objects.filter(start_time__gt=wall).values("notice_raw_id")
    ongoing_ids = (
        NoticeParsed.objects.filter(end_time__gte=wall)
        .filter(Q(start_time__isnull=True) | Q(start_time__lte=wall))
        .exclude(notice_kind__in=CLOSED_NOTICE_KINDS)
        .exclude(Q(procurement_mode__icontains="直购") | Q(procurement_mode__icontains="直接采购"))
        .values("notice_raw_id")
    )

    if progress_target == "ended":
        return closed_q | Q(id__in=ended_by_time)
    if progress_target == "upcoming":
        return Q(id__in=upcoming_ids) & ~closed_q & ~Q(id__in=ended_by_time)
    if progress_target == "ongoing":
        return Q(id__in=ongoing_ids) & ~closed_type_q & ~direct_q
    if progress_target == "unknown":
        return ~(
            (closed_q | Q(id__in=ended_by_time))
            | (Q(id__in=upcoming_ids) & ~closed_q & ~Q(id__in=ended_by_time))
            | (Q(id__in=ongoing_ids) & ~closed_type_q & ~direct_q)
        )
    return Q()


def _tables_missing_response():
    return JsonResponse(
        {
            "detail": "公告表尚未创建，请先在 notice_crawler 执行 python cli.py init-db",
            "items": [],
            "total": 0,
            "page": 1,
            "pageSize": 20,
            "noticeKinds": [],
            "regionNames": [],
        },
        status=503,
    )


def _list_raw_qs():
    return NoticeRaw.objects.only(*_LIST_RAW_ONLY).order_by("-id")


def _load_parsed_map(raw_ids: list[int]) -> dict[int, NoticeParsed]:
    if not raw_ids:
        return {}
    return {
        item.notice_raw_id: item
        for item in NoticeParsed.objects.filter(notice_raw_id__in=raw_ids).only(*_LIST_PARSED_ONLY)
    }


def query_crawled_notices(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    site_id: str = "",
    notice_kind: str = "",
    site_ids: list[str] | None = None,
) -> dict:
    """客户控制台和后台列表共用的抓取公告查询。

    site_ids:
      - None：不按站点白名单限制
      - []：无可见站点
      - [id, ...]：仅这些站点
    """
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    if site_ids is not None and not site_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    if site_ids is not None and site_id and site_id not in site_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    qs = _list_raw_qs().order_by("-publish_time", "-id")
    if site_ids is not None:
        qs = qs.filter(site_id__in=site_ids)
    if site_id:
        qs = qs.filter(site_id=site_id)
    kinds = _parse_notice_kinds(notice_kind)
    if kinds:
        qs = qs.filter(_raw_ids_for_kinds(kinds, site_id))
    keyword = (search or "").strip()
    if keyword:
        qs = qs.filter(
            Q(title__icontains=keyword)
            | Q(notice_key__icontains=keyword)
            | Q(
                id__in=NoticeParsed.objects.filter(
                    Q(project_code__icontains=keyword)
                    | Q(project_name__icontains=keyword)
                    | Q(buyer_name__icontains=keyword)
                    | Q(notice_title__icontains=keyword)
                ).values("notice_raw_id")
            )
        )
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    parsed_map = _load_parsed_map([row.id for row in rows])
    items = _attach_result_tags(
        [_serialize_list_item(row, parsed_map.get(row.id)) for row in rows]
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@csrf_exempt
@require_http_methods(["GET"])
def notice_list(request):
    _, error = _require_permission(request, "notice.view")
    if error:
        return error

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.GET.get("pageSize") or 20), 1), 100)
    except ValueError:
        page_size = 20

    site_id = (request.GET.get("siteId") or "").strip()
    parse_status = (request.GET.get("parseStatus") or "").strip()
    notice_kinds = _parse_notice_kinds(
        request.GET.get("noticeKinds") or request.GET.get("notice_kinds") or "",
        request.GET.get("noticeKind") or "",
    )
    progress = (request.GET.get("progress") or "").strip().lower()
    search = (request.GET.get("search") or "").strip()
    project_code = (request.GET.get("projectCode") or "").strip()
    project_name = (request.GET.get("projectName") or "").strip()
    buyer_name = (request.GET.get("buyerName") or "").strip()
    supplier_name = (request.GET.get("supplierName") or "").strip()
    goods_name = (request.GET.get("goodsName") or "").strip()
    region_name = (request.GET.get("regionName") or request.GET.get("region") or "").strip()
    publish_from = (request.GET.get("publishDateFrom") or request.GET.get("publish_date_from") or "").strip()
    publish_to = (request.GET.get("publishDateTo") or request.GET.get("publish_date_to") or "").strip()
    start_from = (request.GET.get("startDateFrom") or request.GET.get("start_date_from") or "").strip()
    start_to = (request.GET.get("startDateTo") or request.GET.get("start_date_to") or "").strip()
    end_from = (request.GET.get("endDateFrom") or request.GET.get("end_date_from") or "").strip()
    end_to = (request.GET.get("endDateTo") or request.GET.get("end_date_to") or "").strip()
    now = timezone.now()

    try:
        qs = _list_raw_qs()
        if site_id:
            qs = qs.filter(site_id=site_id)
        if parse_status:
            qs = qs.filter(parse_status=parse_status)
        if region_name:
            qs = qs.filter(_region_filter_q(region_name))
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(notice_key__icontains=search)
                | Q(region_name__icontains=search)
                | Q(
                    id__in=NoticeParsed.objects.filter(
                        Q(project_code__icontains=search)
                        | Q(project_name__icontains=search)
                        | Q(buyer_name__icontains=search)
                        | Q(deal_supplier__icontains=search)
                        | Q(notice_title__icontains=search)
                    ).values("notice_raw_id")
                )
            )
        if notice_kinds:
            qs = qs.filter(_raw_ids_for_kinds(notice_kinds, site_id))
        field_q = _notice_field_filter_q(
            project_code=project_code,
            project_name=project_name,
            buyer_name=buyer_name,
            supplier_name=supplier_name,
            goods_name=goods_name,
        )
        if field_q is not None:
            qs = qs.filter(field_q)
        day_q = _notice_day_filter_q(
            publish_from=publish_from,
            publish_to=publish_to,
            start_from=start_from,
            start_to=start_to,
            end_from=end_from,
            end_to=end_to,
        )
        if day_q is not None:
            qs = qs.filter(day_q)

        progress_target = None
        if progress in {"ongoing", "in_progress", "进行中"}:
            progress_target = "ongoing"
        elif progress in {"upcoming", "未开始"}:
            progress_target = "upcoming"
        elif progress in {"ended", "已截止"}:
            progress_target = "ended"
        elif progress in {"unknown", "未知"}:
            progress_target = "unknown"
        if progress_target:
            qs = qs.filter(_progress_filter_q(progress_target, now=now))

        total = qs.count()
        offset = (page - 1) * page_size
        page_rows = list(qs[offset : offset + page_size])
        parsed_map = _load_parsed_map([r.id for r in page_rows])
        items = _attach_result_tags(
            _attach_sibling_kinds(
                [_serialize_list_item(r, parsed_map.get(r.id), now=now) for r in page_rows]
            )
        )

        return JsonResponse(
            {
                "items": items,
                "total": total,
                "page": page,
                "pageSize": page_size,
                "sites": [
                    {"id": key, "label": label}
                    for key, label in SITE_LABELS.items()
                ],
                "noticeKinds": _notice_kind_options(site_id),
                "regionNames": _region_options(site_id),
            }
        )
    except ProgrammingError:
        return _tables_missing_response()


@csrf_exempt
@require_http_methods(["GET"])
def notice_detail(request, notice_id: int):
    _, error = _require_permission(request, "notice.view")
    if error:
        # 标签修正页也可查看公告详情
        _, tag_error = _require_permission(request, "notice.tag.view")
        if tag_error:
            return error
    try:
        raw = NoticeRaw.objects.filter(id=notice_id).first()
        if not raw:
            return JsonResponse({"detail": "公告不存在"}, status=404)
        parsed = NoticeParsed.objects.filter(notice_raw_id=raw.id).first()
        goods = list(
            NoticeGoods.objects.filter(notice_raw_id=raw.id).order_by("line_no", "id")
        )
        return JsonResponse(_serialize_detail(raw, parsed, goods))
    except ProgrammingError:
        return JsonResponse({"detail": "公告表尚未创建"}, status=503)
