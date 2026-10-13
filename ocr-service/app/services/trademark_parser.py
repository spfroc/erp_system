from __future__ import annotations

import io
import re
from typing import Any

from app.services.business_license_parser import _pdf_pages
from app.services.invoice_parser import normalize_date, prepare_invoice_text, squeeze_invoice_text


FIELD_LABELS = {
    "registration_no": ("商标注册号", "注册号"),
    "registrant": ("注册人",),
    "registrant_address": ("注册人地址", "地址"),
    "international_class": ("国际分类", "国际分类号", "类别"),
    "approved_goods": ("核定使用商品/服务项目", "核定使用商品", "核定使用服务项目", "商品/服务项目"),
    "registration_date": ("注册日期", "有效期自", "有效期起"),
    "valid_until": ("有效期至", "截止日期"),
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip("：:。*;＊")


def _normalize_lines(lines: list[str]) -> list[str]:
    cleaned = [_clean(line) for line in lines if _clean(line)]
    phrases = (
        "商标注册证",
        "商标注册号",
        "注册人地址",
        "注册人",
        "注册号",
        "注册日期",
        "国际分类号",
        "国际分类",
        "核定使用商品/服务项目",
        "核定使用商品",
        "有效期至",
        "有效期起",
        "有效期自",
    )
    merged: list[str] = []
    index = 0
    while index < len(cleaned):
        matched = False
        for phrase in phrases:
            chars = list(phrase)
            if index + len(chars) > len(cleaned):
                continue
            if cleaned[index:index + len(chars)] == chars:
                merged.append(phrase)
                index += len(chars)
                matched = True
                break
            # Allow "注册人地址山东省..." glued to the last glyph.
            if len(chars) >= 2 and cleaned[index:index + len(chars) - 1] == chars[:-1]:
                last = cleaned[index + len(chars) - 1]
                if last.startswith(chars[-1]):
                    merged.append(phrase)
                    remainder = last[len(chars[-1]):]
                    if remainder:
                        merged.append(remainder)
                    index += len(chars)
                    matched = True
                    break
        if matched:
            continue
        merged.append(cleaned[index])
        index += 1
    return merged


# Shorter labels that are prefixes of longer ones must not steal the longer match.
_LABEL_PREFIX_BLOCKERS: dict[str, tuple[str, ...]] = {
    "注册人": ("注册人地址",),
    "注册号": ("商标注册号",),
    "地址": ("注册人地址",),
    "国际分类": ("国际分类号",),
}


def _is_blocked_label_match(line: str, label: str, position: int) -> bool:
    tail = line[position:]
    for longer in _LABEL_PREFIX_BLOCKERS.get(label, ()):
        if tail.startswith(longer):
            return True
    # "注册人" immediately followed by "地址" is the address label leftover.
    if label == "注册人" and re.match(r"^注册人\s*地址", tail):
        return True
    return False


def _value_after_label(lines: list[str], labels: tuple[str, ...], *, collect_lines: int = 1) -> str:
    stop_words = {label for group in FIELD_LABELS.values() for label in group} | {
        "商标注册证",
        "第号",
        "国家知识产权局",
        "局长",
        "发证",
    }
    # Longer labels first so "注册人地址" wins over "注册人" / "地址".
    ordered_labels = sorted(labels, key=len, reverse=True)
    for index, raw_line in enumerate(lines):
        line = _clean(raw_line)
        for label in ordered_labels:
            position = line.find(label)
            if position < 0:
                continue
            if _is_blocked_label_match(line, label, position):
                continue
            value = line[position + len(label):].lstrip("：:")
            prefix = line[:position].strip("：:。；;，,")
            # Certificate OCR often emits "临沂市...厂注册人" (value then label).
            if not value and prefix and position + len(label) == len(line):
                if prefix not in stop_words and prefix not in {"地址", "人地址"}:
                    if not any(prefix.startswith(candidate) for candidate in stop_words if len(candidate) >= 2):
                        return prefix
            chunks: list[str] = []
            if value and value not in stop_words and not any(
                value.startswith(candidate) for candidate in stop_words if len(candidate) >= 2
            ):
                chunks.append(value)
            for offset in range(1, max(collect_lines, 1) + 8):
                if index + offset >= len(lines):
                    break
                if len(chunks) >= collect_lines and collect_lines == 1:
                    break
                next_value = _clean(lines[index + offset])
                if not next_value:
                    continue
                if next_value in stop_words:
                    if chunks:
                        break
                    continue
                if any(candidate in next_value for candidate in stop_words if len(candidate) >= 2):
                    # Allow "第21类：碗..." style continuation for approved goods.
                    if label.startswith("核定") and ("第" in next_value or "类" in next_value or "；" in next_value or ";" in next_value):
                        chunks.append(next_value)
                        if collect_lines == 1:
                            break
                        continue
                    if chunks:
                        break
                    continue
                # Skip bare "地址" leftover from a mis-split 注册人地址 label.
                if next_value in {"地址", "人地址"}:
                    continue
                # Skip bare class numbers when looking for registrant names.
                if label == "注册人" and re.fullmatch(r"\d{1,2}", next_value):
                    continue
                chunks.append(next_value)
                if collect_lines == 1:
                    break
                if len(chunks) >= collect_lines:
                    break
            if chunks:
                return "".join(chunks) if label.startswith("核定") else chunks[0]
    return ""


def _extract_registration_no(text: str, lines: list[str]) -> str:
    barcode = re.search(r"TMZC(\d{5,12})", text.upper())
    if barcode:
        return barcode.group(1)
    labeled = _value_after_label(lines, FIELD_LABELS["registration_no"])
    labeled_digits = re.search(r"(\d{5,12})", labeled)
    if labeled_digits:
        return labeled_digits.group(1)
    # Prefer standalone numbers that look like registration IDs.
    for line in lines:
        match = re.fullmatch(r"(\d{5,12})", _clean(line))
        if match:
            return match.group(1)
    match = re.search(r"(?<!\d)(\d{7,10})(?!\d)", text)
    return match.group(1) if match else ""


def _extract_international_class(text: str, lines: list[str]) -> str:
    found = [str(int(item)) for item in re.findall(r"第\s*(\d{1,2})\s*类", text)]
    if not found:
        range_match = re.search(r"国际分类[号]?[：:]?\s*([0-9和、,，;；/\s]{1,40})", text)
        if range_match:
            found = [str(int(item)) for item in re.findall(r"\d{1,2}", range_match.group(1))]
    if not found:
        labeled = _value_after_label(lines, ("国际分类号", "国际分类"))
        found = [str(int(item)) for item in re.findall(r"\d{1,2}", labeled)]
    # Nice-class numbers are 1-45.
    unique: list[str] = []
    for item in found:
        value = int(item)
        if 1 <= value <= 45 and item not in unique:
            unique.append(item)
    return "、".join(unique)


def _extract_date(lines: list[str], labels: tuple[str, ...], full_text: str) -> str:
    labeled = _value_after_label(lines, labels)
    normalized = normalize_date(labeled)
    if normalized:
        return normalized
    # Fallback: find Chinese dates near the label keyword in full text.
    for label in labels:
        pattern = rf"{re.escape(label)}[：:\s]*(\d{{4}}年\d{{1,2}}月\d{{1,2}}日)"
        match = re.search(pattern, full_text)
        if match:
            return normalize_date(match.group(1))
    return ""


def _looks_like_goods_continuation(text: str) -> bool:
    value = text or ""
    if not value:
        return False
    if re.match(r"第\d{1,2}类", value):
        return True
    field_markers = (
        "注册人",
        "注册日期",
        "有效期",
        "商标注册",
        "国际分类",
        "核定使用",
        "国家知识产权",
        "局长",
        "发证",
    )
    if any(marker in value for marker in field_markers):
        return False
    if "截止" in value:
        return True
    if "；" in value or "、" in value or ";" in value or "，" in value:
        return True
    # Wrapped mid-word continuations are usually short commodity fragments.
    return 1 <= len(value) <= 40


def _is_class_marker_only(text: str) -> bool:
    return bool(
        re.fullmatch(
            r"[（(]?国际分类[号]?[：:]?[0-9和、,，;；/\s]{1,40}[)）]?",
            text or "",
        )
    )


def _collect_class_goods_blocks(search_text: str) -> str:
    """Join every「第N类：…（截止）」block; multi-class certificates list several."""
    blocks = re.findall(
        r"第\s*\d{1,2}\s*类[：:][^第]{1,800}?(?:（截止）|\(截止\)|截止)",
        search_text or "",
    )
    if not blocks:
        return ""
    merged = []
    seen: set[str] = set()
    for block in blocks:
        value = re.sub(r"\s+", "", block).strip("：:。*;＊")
        value = _trim_field_noise(value)
        if len(value) < 4 or value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return "".join(merged)[:1200]


def _stitch_front_back_goods(search_text: str) -> str:
    """Merge front-page goods truncated at 见背面/见附页 with the back-page continuation.

    New-style certificates print 核定使用商品 on the back (or 附页). OCR of a
    multi-page PDF already concatenates pages into search_text, but the front
    block stops at「见背面」and the back block resumes mid-phrase after the
    registrant / seal area, ending at「（截止）」.
    """
    text = re.sub(r"\s+", "", search_text or "")
    if not re.search(r"见背面|见附页", text):
        return ""
    front_match = re.search(
        r"(第\s*\d{1,2}\s*类[：:].{5,1500}?)"
        r"[（(<【\[]?见(?:背面|附页)(?:，共\d+页)?[）)>】\]]?",
        text,
    )
    if not front_match:
        return ""
    front = _trim_field_noise(front_match.group(1).rstrip("（(<【["))
    rest = text[front_match.end() :]
    cutoff = re.search(r"（截止）|\(截止\)", rest)
    if not cutoff:
        return ""
    segment = rest[: cutoff.end()]
    # Drop the front-side identity block that sits between the two goods halves.
    segment = re.sub(
        r"^.*?(?:发证机关|商标局|局长签发|国家知识产权局|局长)",
        "",
        segment,
        count=1,
    )
    segment = re.sub(r"^(?:号|第)+", "", segment)
    segment = re.sub(r"（国际分类：[^）]*）", "", segment)
    segment = re.sub(r"核定使用商品/服务项目|核定使用商品", "", segment)
    segment = re.sub(r"\*+[A-Z0-9]+\*+", "", segment)
    segment = re.sub(r"(?:发证机关|商标局号?|商标局)", "", segment)
    segment = re.sub(r"(?<![第类])\d{7,9}(?![年月日])", "", segment)
    segment = _trim_field_noise(segment)
    if len(segment) < 4 or ("；" not in segment and "、" not in segment and "截止" not in segment):
        return ""
    return _trim_field_noise(front + segment)[:1200]


def _extract_approved_goods(lines: list[str], search_text: str) -> str:
    stop_labels = {
        "注册人",
        "注册人地址",
        "注册日期",
        "有效期至",
        "有效期起",
        "有效期自",
        "商标注册号",
        "商标注册证",
        "国家知识产权局",
        "局长",
        "发证",
    }

    stitched = _stitch_front_back_goods(search_text)
    if stitched and "截止" in stitched and "见背面" not in stitched and "见附页" not in stitched:
        return stitched

    # Prefer collecting from OCR line boxes so wrapped / multi-class goods join.
    start_index = -1
    for index, raw_line in enumerate(lines):
        cleaned = _clean(raw_line)
        if re.match(r"第\d{1,2}类", cleaned):
            start_index = index
            break
    if start_index < 0:
        for index, raw_line in enumerate(lines):
            cleaned = _clean(raw_line)
            if any(label in cleaned for label in FIELD_LABELS["approved_goods"]):
                start_index = index
                break

    if start_index >= 0:
        chunks: list[str] = []
        for offset in range(0, 40):
            if start_index + offset >= len(lines):
                break
            piece = _clean(lines[start_index + offset])
            if not piece:
                continue
            if any(label in piece for label in FIELD_LABELS["approved_goods"]) and not re.match(r"第\d{1,2}类", piece):
                remainder = piece
                for label in sorted(FIELD_LABELS["approved_goods"], key=len, reverse=True):
                    if label in remainder:
                        remainder = remainder.split(label, 1)[-1].lstrip("：:")
                        break
                if remainder and not _is_class_marker_only(remainder):
                    if re.match(r"第\d{1,2}类", remainder) or _looks_like_goods_continuation(remainder):
                        chunks.append(remainder)
                continue
            if piece in stop_labels:
                break
            if any(piece.startswith(label) for label in stop_labels):
                break
            if _is_class_marker_only(piece) or piece in {"国际分类", "国际分类号"}:
                continue
            # Keep going across multiple「第N类…（截止）」sections.
            if re.match(r"第\d{1,2}类", piece) or _looks_like_goods_continuation(piece):
                chunks.append(piece)
                continue
            if chunks:
                break
        value = _trim_field_noise("".join(chunks))
        # Prefer full multi-class extraction from continuous text when richer.
        from_blocks = _collect_class_goods_blocks(search_text)
        if from_blocks and len(from_blocks) > len(value):
            value = from_blocks
        if stitched and len(stitched) > len(value):
            value = stitched
        if len(value) >= 4 and ("类" in value or "；" in value or "截止" in value):
            return value[:1200]

    if stitched:
        return stitched

    from_blocks = _collect_class_goods_blocks(search_text)
    if from_blocks:
        return from_blocks

    block = re.search(
        r"第\s*\d{1,2}\s*类[：:].{2,800}?(?=注册人|注册日期|有效期至|国家知识产权局|局长|$)",
        search_text,
    )
    if block:
        value = re.sub(r"\s+", "", block.group(0)).strip("：:。*;＊")
        value = _trim_field_noise(value)
        if len(value) >= 4 and "类" in value:
            return value[:1200]

    value = _value_after_label(lines, FIELD_LABELS["approved_goods"], collect_lines=20)
    value = _trim_field_noise(value)
    if _is_class_marker_only(value or ""):
        value = ""
    if not value:
        return ""
    return value[:1200]


def _extract_trademark_ocr_lines(image_bytes: bytes) -> tuple[list[str], list[float], int]:
    """Full-page OCR for trademark certificates.

    Business-license OCR masks the lower-left region (经营范围). On trademark
    certificates that same area holds wrapped 核定使用商品 lines, so we must
    scan the whole page without that mask.
    """
    import numpy as np
    from PIL import Image, ImageOps

    from app.services.business_license_parser import _ocr_engine, _payload_lines

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        max_side = max(image.size)
        if max_side > 2200:
            scale = 2200 / max_side
            image = image.resize((int(image.width * scale), int(image.height * scale)))

        angles = [0]
        if image.height > image.width * 1.12:
            angles = [0, 90, 270]
        elif image.width >= image.height:
            angles = [0, 180]

        best_lines: list[str] = []
        best_scores: list[float] = []
        best_angle = 0
        best_rank = -1.0
        anchors = ("商标注册证", "注册人", "核定使用", "有效期至", "TMZC", "国际分类")
        for angle in angles:
            candidate = image if angle == 0 else image.rotate(angle, expand=True)
            lines, scores = _payload_lines(_ocr_engine()(np.asarray(candidate)))
            joined = "".join(lines)
            rank = sum(2.0 for anchor in anchors if anchor in joined)
            if "第" in joined and "类" in joined:
                rank += 1.5
            if scores:
                rank += sum(scores) / len(scores)
            rank += min(len(lines), 80) * 0.02
            if rank > best_rank:
                best_rank = rank
                best_lines = lines
                best_scores = scores
                best_angle = angle
        return best_lines, best_scores, best_angle


def _value_before_label(text: str, labels: tuple[str, ...]) -> str:
    for label in sorted(labels, key=len, reverse=True):
        for match in re.finditer(
            rf"([\u3400-\u9fffA-Za-z0-9（）()·\-、，,]{{2,120}}){re.escape(label)}",
            text,
        ):
            end = match.end()
            if label == "注册人" and text[end:].startswith("地址"):
                continue
            if _is_blocked_label_match(text, label, match.start() + len(match.group(1))):
                continue
            value = match.group(1)
            # Prefer the segment after the previous label-like keyword.
            for stopper in ("商标注册证", "商标注册号", "第号", "国际分类", "核定使用"):
                pos = value.rfind(stopper)
                if pos >= 0:
                    value = value[pos + len(stopper):]
            value = value.strip("：:。；;，,")
            if value and value not in labels and value not in {"地址", "人地址"}:
                return value
    return ""


def _trim_field_noise(value: str) -> str:
    text = value or ""
    for stopper in (
        "注册人地址",
        "注册人",
        "注册日期",
        "有效期至",
        "有效期起",
        "有效期自",
        "国际分类",
        "国际分类号",
        "核定使用",
        "商标注册号",
        "局长",
        "发证",
        "国家知识产权局",
    ):
        pos = text.find(stopper)
        if pos > 0:
            text = text[:pos]
    return text.strip("：:。；;，,")


def _guess_mark_from_registrant(registrant: str) -> str:
    """Company names often embed the mark, e.g. 青岛众拾天成石油化工有限公司 → 众拾天成."""
    text = _clean(registrant)
    if not text:
        return ""

    # Peel geo prefixes carefully; optional-suffix wildcards would eat the brand too.
    for _ in range(6):
        matched = re.match(
            r"^(?:北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门)(?:省|市|自治区|特别行政区)?",
            text,
        )
        if matched:
            text = text[matched.end():]
            continue
        matched = re.match(r"^[\u3400-\u9fff]{2,3}(?:省|市|区|县|自治州|地区|盟)", text)
        if matched:
            text = text[matched.end():]
            continue
        matched = re.match(
            r"^(?:青岛|济南|烟台|潍坊|淄博|临沂|威海|日照|德州|聊城|滨州|菏泽|枣庄|东营|泰安|莱西|即墨|胶州|平度)",
            text,
        )
        if matched and len(text) - matched.end() >= 2:
            text = text[matched.end():]
            continue
        break

    text = re.sub(
        r"(?:有限责任公司|股份有限公司|集团有限公司|有限公司|集团公司|集团|厂|店|中心|事务所|研究院)$",
        "",
        text,
    )
    text = re.sub(
        r"(?:石油化工|化工|塑料制品|科技发展|科技|实业|商贸|贸易|电子|电器|食品|服装|服饰|建材|机械|生物|医药|制药|农业|文化传媒|文化|咨询|服务|工程|制造|制品|能源|环保|新材料|材料|物流|运输|投资|控股)$",
        "",
        text,
    )
    text = text.strip("·.—-_ ")
    if 2 <= len(text) <= 8 and re.fullmatch(r"[\u3400-\u9fff·]+", text):
        return text
    return ""


def _extract_trademark_name(lines: list[str], search_text: str, registrant: str = "") -> str:
    """Extract mark/logo text (商标名称). Certificates rarely label it; fall back to heuristics."""
    labeled = _trim_field_noise(_value_after_label(lines, ("商标名称", "商标图样名称")))
    if labeled and labeled not in {"名称", "图样"} and not re.fullmatch(r"\d{1,12}", labeled):
        return labeled[:80]

    skip_exact = {
        "商标注册证",
        "商标注册号",
        "注册号",
        "注册人",
        "注册人地址",
        "国际分类",
        "国际分类号",
        "核定使用商品/服务项目",
        "核定使用商品",
        "注册日期",
        "有效期至",
        "有效期起",
        "有效期自",
        "国家知识产权局",
        "局长",
        "发证",
        "第号",
    }
    skip_substrings = (
        "注册",
        "核定",
        "国际分类",
        "有效期",
        "知识产权",
        "截止",
        "TMZC",
        "局长",
        "第号",
        "有限公司",
        "股份公司",
    )

    # Mark/logo sits in the upper block before registrant / goods text.
    cutoff = len(lines)
    for index, raw in enumerate(lines):
        compact = _clean(raw)
        if compact.startswith("注册人") or compact.startswith("核定") or "核定使用" in compact:
            cutoff = index
            break
    scan_lines = lines[:cutoff]

    chinese_candidates: list[str] = []
    latin_candidates: list[str] = []
    for raw in scan_lines:
        text = (raw or "").strip()
        if not text:
            continue
        compact = _clean(text)
        if not compact or compact in skip_exact:
            continue
        if any(token in compact for token in skip_substrings):
            continue
        if re.fullmatch(r"\*?.{0,4}\d{5,12}.{0,12}\*?", compact):
            continue
        if re.fullmatch(r"第?\d{1,2}类.*", compact):
            continue
        if re.search(r"\d{4}年\d{1,2}月", compact):
            continue
        if len(compact) > 28:
            continue
        # Pure / mostly Chinese short mark text.
        if re.fullmatch(r"[\u3400-\u9fff·]{2,12}", compact):
            chinese_candidates.append(compact)
            continue
        # Latin / mixed brand like Luqiya / ZHONGSHITIANCHENG
        latin_compact = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9\-&.]{1,36}", latin_compact):
            latin_candidates.append(latin_compact)
            continue
        mixed = re.fullmatch(
            r"([\u3400-\u9fff·]{2,12})\s*([A-Za-z][A-Za-z0-9\-&.]{1,36})",
            text,
        ) or re.fullmatch(
            r"([\u3400-\u9fff·]{2,12})([A-Za-z][A-Za-z0-9\-&.]{1,36})",
            compact,
        )
        if mixed:
            return f"{mixed.group(1)} {mixed.group(2)}"[:80]

    if chinese_candidates and latin_candidates:
        return f"{chinese_candidates[0]} {latin_candidates[0]}"[:80]
    if chinese_candidates:
        return chinese_candidates[0][:80]
    if latin_candidates:
        return latin_candidates[0][:80]

    for match in re.finditer(r"([\u3400-\u9fff]{2,8})\s*([A-Za-z][A-Za-z0-9\-&.]{1,36})", search_text):
        chinese, latin = match.group(1), match.group(2)
        if any(token in chinese for token in ("注册", "分类", "核定", "有效", "国家", "地址", "商品", "青岛", "山东")):
            continue
        return f"{chinese} {latin}"[:80]

    # Logo OCR often fails on stylized marks; recover brand embedded in registrant.
    guessed = _guess_mark_from_registrant(registrant)
    if guessed:
        return guessed
    return ""


def parse_trademark_certificate_text(lines: list[str]) -> dict[str, Any]:
    normalized_lines = _normalize_lines(lines)
    full_text = "".join(normalized_lines)
    squeezed = prepare_invoice_text("\n".join(lines))
    search_text = squeezed or full_text

    registration_date = _extract_date(normalized_lines, FIELD_LABELS["registration_date"], search_text)
    valid_until = _extract_date(normalized_lines, FIELD_LABELS["valid_until"], search_text)
    if not registration_date or not valid_until:
        dates = re.findall(r"\d{4}年\d{1,2}月\d{1,2}日", search_text)
        if len(dates) >= 2:
            # Certificate layout often puts 有效期至 left of 注册日期 visually; order in text may vary.
            sorted_dates = sorted(normalize_date(item) for item in dates if normalize_date(item))
            if len(sorted_dates) >= 2:
                registration_date = registration_date or sorted_dates[0]
                valid_until = valid_until or sorted_dates[-1]
            else:
                registration_date = registration_date or normalize_date(dates[0])
                valid_until = valid_until or normalize_date(dates[1])
        elif len(dates) == 1 and not registration_date:
            registration_date = normalize_date(dates[0])

    registrant = _trim_field_noise(_value_after_label(normalized_lines, ("注册人",)))
    if not registrant or registrant in {"地址", "注册人地址", "人地址"}:
        registrant = _trim_field_noise(_value_before_label(search_text, ("注册人",)))

    registrant_address = _trim_field_noise(
        _value_after_label(normalized_lines, ("注册人地址",))
    )
    if not registrant_address:
        registrant_address = _trim_field_noise(
            _value_before_label(search_text, ("注册人地址",))
        )
    if not registrant_address:
        address_match = re.search(
            r"((?:北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门)[\u3400-\u9fffA-Za-z0-9\-号室园镇路街巷村区县市省]{6,80})",
            search_text,
        )
        if address_match:
            registrant_address = _trim_field_noise(address_match.group(1))

    trademark_name = _extract_trademark_name(lines, search_text, registrant)
    # Only drop when the "mark" is literally the whole registrant / address.
    if trademark_name and registrant:
        tn = trademark_name.replace(" ", "")
        rn = registrant.replace(" ", "")
        if tn == rn or (len(tn) >= 10 and tn == rn[: len(tn)] and re.search(r"(公司|厂|店|中心)$", rn)):
            trademark_name = ""
    if trademark_name and registrant_address:
        tn = trademark_name.replace(" ", "")
        if tn == registrant_address.replace(" ", "") or len(tn) > 20 and tn in registrant_address.replace(" ", ""):
            trademark_name = ""
    if not trademark_name:
        trademark_name = _guess_mark_from_registrant(registrant)

    fields = {
        "registration_no": _extract_registration_no(search_text, normalized_lines),
        "trademark_name": trademark_name,
        "registrant": registrant,
        "registrant_address": registrant_address,
        "international_class": _extract_international_class(search_text, normalized_lines),
        "approved_goods": _extract_approved_goods(normalized_lines, search_text),
        "registration_date": registration_date,
        "valid_until": valid_until,
        "raw_text": "\n".join(lines),
    }
    # Avoid treating address label leftovers as registrant.
    if fields["registrant"] in {"地址", "注册人地址", "人地址"}:
        fields["registrant"] = ""
    if fields["registrant"] and re.fullmatch(r"\d{1,4}", fields["registrant"]):
        fields["registrant"] = ""
    if fields["registrant_address"] in {"注册人", "地址"}:
        fields["registrant_address"] = ""
    if fields["registrant"] and fields["registrant_address"] and fields["registrant_address"] in fields["registrant"]:
        fields["registrant"] = _trim_field_noise(fields["registrant"].replace(fields["registrant_address"], ""))
    # If registrant still empty, take the company-like line after 注册号 block.
    if not fields["registrant"]:
        for index, raw_line in enumerate(normalized_lines):
            cleaned = _clean(raw_line)
            if cleaned != "注册人" and not cleaned.endswith("注册人"):
                continue
            if cleaned.endswith("注册人") and len(cleaned) > len("注册人"):
                candidate = _trim_field_noise(cleaned[: -len("注册人")])
                if candidate and candidate not in {"地址", "注册人地址"} and not re.fullmatch(r"\d{1,4}", candidate):
                    fields["registrant"] = candidate
                    break
            for offset in range(1, 5):
                if index + offset >= len(normalized_lines):
                    break
                candidate = _trim_field_noise(normalized_lines[index + offset])
                if not candidate or candidate in {"地址", "注册人地址", "人地址"}:
                    continue
                if candidate.startswith("注册") or candidate.startswith("国际") or candidate.startswith("核定"):
                    continue
                if re.fullmatch(r"\d{1,4}", candidate):
                    continue
                if re.search(r"(公司|厂|店|中心|事务所|研究院|大学|学院|工作室|合伙)", candidate) or len(candidate) >= 6:
                    fields["registrant"] = candidate
                    break
            break

    core_fields = (
        "registration_no",
        "registrant",
        "registrant_address",
        "international_class",
        "registration_date",
        "valid_until",
    )
    fields["confidence"] = round(sum(bool(fields[field]) for field in core_fields) / len(core_fields), 2)
    return fields


def _pdf_text_lines(content: bytes) -> list[str]:
    try:
        import pdfplumber
    except Exception:
        return []
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as document:
        for page in document.pages[:2]:
            text = page.extract_text() or ""
            if not text.strip():
                continue
            # Trademark PDFs often insert spaces between glyphs.
            squeezed = squeeze_invoice_text(text)
            for line in (squeezed or text).splitlines():
                cleaned = line.strip()
                if cleaned:
                    lines.append(cleaned)
    return lines


def parse_trademark_certificate(content: bytes, filename: str, content_type: str | None = None) -> dict[str, Any]:
    is_pdf = (content_type or "").lower() == "application/pdf" or filename.lower().endswith(".pdf")
    lines: list[str] = []
    scores: list[float] = []

    try:
        if is_pdf:
            lines = _pdf_text_lines(content)
            data = parse_trademark_certificate_text(lines) if lines else None
            if data and data.get("registration_no") and data.get("registrant"):
                return {
                    "status": "recognized",
                    "message": "商标注册证识别完成，请核对后保存。",
                    "data": data,
                }
            images = _pdf_pages(content)
        else:
            images = [content]

        for image in images:
            page_lines, page_scores, _rotation = _extract_trademark_ocr_lines(image)
            lines.extend(page_lines)
            scores.extend(page_scores)
    except Exception as error:
        return {
            "status": "ocr_error",
            "message": f"商标注册证 OCR 处理失败：{error}",
            "data": None,
        }

    if not lines:
        return {
            "status": "not_recognized",
            "message": "未从文件中识别到文字，请上传清晰、完整的商标注册证。",
            "data": None,
        }

    data = parse_trademark_certificate_text(lines)
    data["ocr_confidence"] = round(sum(scores) / len(scores), 3) if scores else None
    if not data["registration_no"] and not data["registrant"]:
        return {
            "status": "not_recognized",
            "message": "已识别文字，但未找到商标注册号或注册人，请确认文件是清晰完整的商标注册证。",
            "data": data,
        }
    return {
        "status": "recognized",
        "message": "商标注册证 OCR 识别完成，请核对后保存。",
        "data": data,
    }
