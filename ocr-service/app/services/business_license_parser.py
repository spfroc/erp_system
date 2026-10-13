from __future__ import annotations

import io
import re
from functools import lru_cache
from typing import Any


FIELD_LABELS = {
    "unified_credit_code": ("统一社会信用代码", "社会信用代码", "注册号"),
    "name": ("名称", "企业名称"),
    "entity_type": ("类型", "公司类型", "主体类型"),
    "legal_person": ("法定代表人", "负责人", "经营者", "执行事务合伙人"),
    "registered_capital": ("注册资本", "注册资金"),
    "founded_date": ("成立日期", "注册日期"),
    "address": ("住所", "营业场所", "经营场所", "注册地址"),
    "business_scope": ("经营范围", "业务范围"),
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip("：:。")


def _merge_split_labels(lines: list[str]) -> list[str]:
    """Join labels that OCR commonly splits into separate text boxes."""
    pairs = {"名": "称", "类": "型", "住": "所"}
    cleaned = [_clean(line) for line in lines if _clean(line)]
    merged: list[str] = []
    index = 0
    while index < len(cleaned):
        line = cleaned[index]
        suffix = pairs.get(line)
        if suffix and index + 1 < len(cleaned) and cleaned[index + 1].startswith(suffix):
            merged.append(line + cleaned[index + 1])
            index += 2
            continue
        if line.startswith("称") and len(line) > 1:
            line = "名称" + line[1:]
        elif line.startswith("型") and len(line) > 1:
            line = "类型" + line[1:]
        elif line.startswith("所") and len(line) > 1:
            line = "住所" + line[1:]
        merged.append(line)
        index += 1
    return merged


def _value_after_label(lines: list[str], labels: tuple[str, ...]) -> str:
    for index, raw_line in enumerate(lines):
        line = _clean(raw_line)
        for label in labels:
            position = line.find(label)
            if position < 0:
                continue
            value = line[position + len(label):].lstrip("：:")
            if value:
                return value
            if index + 1 < len(lines):
                next_value = _clean(lines[index + 1])
                if next_value and not any(candidate in next_value for group in FIELD_LABELS.values() for candidate in group):
                    return next_value
    return ""


def _address_value(lines: list[str]) -> str:
    labels = FIELD_LABELS["address"]
    base = _value_after_label(lines, labels)
    if not base:
        return ""

    label_index = next(
        (
            index
            for index, line in enumerate(lines)
            if any(label in _clean(line) for label in labels)
        ),
        -1,
    )
    if label_index < 0:
        return base

    continuations: list[str] = []
    stop_words = {label for field_labels in FIELD_LABELS.values() for label in field_labels}
    for raw_line in lines[label_index + 1:label_index + 12]:
        line = _clean(raw_line)
        if not line or line == base or any(label in line for label in stop_words):
            continue
        if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", line):
            continue
        is_address_suffix = bool(
            re.fullmatch(r"\d{3}|\d{1,4}(?:-\d{1,4})?(?:号|室|层|楼|单元)", line)
            or re.fullmatch(r"[\u3400-\u9fff]{1,8}(?:村|社区|小区)", line)
            or (line.startswith("号") and len(line) <= 30)
            or (len(line) <= 20 and re.search(r"(?:号|室|层|楼|单元)$", line))
        )
        if is_address_suffix and line not in continuations:
            continuations.append(line)
    return base + "".join(continuations)


def parse_business_license_text(lines: list[str]) -> dict[str, Any]:
    normalized_lines = _merge_split_labels(lines)
    full_text = "\n".join(normalized_lines)
    credit_match = re.search(r"(?<![0-9A-Z])[0-9A-Z]{18}(?![0-9A-Z])", full_text.upper())
    fields = {
        field: _value_after_label(normalized_lines, labels)
        for field, labels in FIELD_LABELS.items()
    }
    if credit_match:
        fields["unified_credit_code"] = credit_match.group(0)
    fields["address"] = _address_value(normalized_lines)
    fields["raw_text"] = "\n".join(lines)
    fields["confidence"] = round(
        sum(bool(fields[field]) for field in FIELD_LABELS) / len(FIELD_LABELS),
        2,
    )
    return fields


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    # Bound ONNX Runtime to the production host's four CPU cores. The default
    # creates a large thread pool for each model and causes severe contention.
    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)


def _payload_lines(result) -> tuple[list[str], list[float]]:
    payload = result[0] if isinstance(result, tuple) else result
    if hasattr(payload, "txts"):
        return list(payload.txts or []), [float(score) for score in (payload.scores or [])]
    texts: list[str] = []
    scores: list[float] = []
    for item in payload or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            texts.append(str(item[1]))
            scores.append(float(item[2]))
    return texts, scores


def _orientation_score(lines: list[str], scores: list[float]) -> float:
    data = parse_business_license_text(lines)
    weights = {
        "unified_credit_code": 4,
        "name": 4,
        "entity_type": 1,
        "legal_person": 2,
        "registered_capital": 1,
        "founded_date": 1,
        "address": 2,
        "business_scope": 1,
    }
    legal_person = data.get("legal_person", "")
    valid_legal_person = bool(re.fullmatch(r"[\u3400-\u9fff·]{2,8}", legal_person))
    field_score = sum(
        weight
        for field, weight in weights.items()
        if data.get(field) and (field != "legal_person" or valid_legal_person)
    )
    if legal_person and not valid_legal_person:
        field_score -= 3
    field_score += min(len(data.get("address", "")), 40) * 0.05
    confidence_score = (sum(scores) / len(scores)) if scores else 0
    return field_score * 10 + min(len(lines), 50) * 0.05 + confidence_score


def _extract_ocr_lines(image_bytes: bytes) -> tuple[list[str], list[float], int]:
    import numpy as np
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        max_side = max(image.size)
        if max_side > 2000:
            scale = 2000 / max_side
            image = image.resize((int(image.width * scale), int(image.height * scale)))
        # A Chinese business licence is landscape. The image aspect ratio narrows
        # the possible upright rotations to two without sacrificing orientation
        # support (including sideways phone photos).
        base_angle = 90 if image.height > image.width * 1.15 else 0
        # Detect page orientation on one small copy. The line classifier reads
        # upside-down text, so the title/code box position tells us whether the
        # whole page needs another 180-degree turn without a second OCR pass.
        orientation_image = image.copy()
        orientation_image.thumbnail((500, 500))
        preview = orientation_image if base_angle == 0 else orientation_image.rotate(base_angle, expand=True)
        band_height = max(1, int(preview.height * 0.32))
        preview_bands = Image.new("RGB", (preview.width, band_height * 2), "white")
        preview_bands.paste(preview.crop((0, 0, preview.width, band_height)), (0, 0))
        preview_bands.paste(
            preview.crop((0, preview.height - band_height, preview.width, preview.height)),
            (0, band_height),
        )
        preview = preview_bands
        preview_result = _ocr_engine()(np.asarray(preview))
        payload = preview_result[0] if isinstance(preview_result, tuple) else preview_result
        anchor_centers: list[float] = []
        footer_centers: list[float] = []
        for item in payload or []:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            box, text = item[0], str(item[1])
            try:
                center_y = sum(float(point[1]) for point in box) / len(box)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if any(anchor in text for anchor in ("营业执照", "统一社会", "信用代码")):
                anchor_centers.append(center_y)
            if any(anchor in text for anchor in ("国家市场监督", "登记机关")):
                footer_centers.append(center_y)
        is_upside_down = (
            bool(anchor_centers) and sum(anchor_centers) / len(anchor_centers) > preview.height * 0.55
        ) or (
            not anchor_centers
            and bool(footer_centers)
            and sum(footer_centers) / len(footer_centers) < preview.height * 0.45
        )
        angle = (base_angle + (180 if is_upside_down else 0)) % 360
        candidate = image if angle == 0 else image.rotate(angle, expand=True)
        # Core license fields are in the upper information area. Excluding the
        # dense business-scope/footer region greatly reduces OCR inference time.
        field_region = candidate.crop((0, 0, candidate.width, int(candidate.height * 0.92)))
        # Dense business-scope text is never used for form filling and dominates
        # recognition time. Mask its usual lower-left block while preserving the
        # multi-line address and registration fields on the right.
        from PIL import ImageDraw

        mask_width_ratio = 0.58 if base_angle == 90 else 0.25
        ImageDraw.Draw(field_region).rectangle(
            (0, int(field_region.height * 0.62), int(field_region.width * mask_width_ratio), field_region.height),
            fill="white",
        )
        lines, scores = _payload_lines(_ocr_engine()(np.asarray(field_region)))
        parsed = parse_business_license_text(lines)
        required_fields = ("unified_credit_code", "name", "legal_person", "address")
        if not all(parsed.get(field) for field in required_fields):
            candidate = image if angle == 0 else image.rotate(angle, expand=True)
            full_lines, full_scores = _payload_lines(_ocr_engine()(np.asarray(candidate)))
            if _orientation_score(full_lines, full_scores) > _orientation_score(lines, scores):
                lines, scores = full_lines, full_scores
        return lines, scores, angle


def _pdf_pages(content: bytes) -> list[bytes]:
    import fitz

    pages: list[bytes] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for page_number in range(min(2, len(document))):
            page = document[page_number]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
            pages.append(pixmap.tobytes("png"))
    return pages


def parse_business_license(content: bytes, filename: str, content_type: str | None = None) -> dict[str, Any]:
    is_pdf = (content_type or "").lower() == "application/pdf" or filename.lower().endswith(".pdf")
    try:
        images = _pdf_pages(content) if is_pdf else [content]
        lines: list[str] = []
        scores: list[float] = []
        rotations: list[int] = []
        for image in images:
            page_lines, page_scores, rotation = _extract_ocr_lines(image)
            lines.extend(page_lines)
            scores.extend(page_scores)
            rotations.append(rotation)
    except Exception as error:
        return {
            "status": "ocr_error",
            "message": f"营业执照 OCR 处理失败：{error}",
            "data": None,
        }

    if not lines:
        return {"status": "not_recognized", "message": "未从文件中识别到文字，请上传清晰、完整的营业执照。", "data": None}

    data = parse_business_license_text(lines)
    data["ocr_confidence"] = round(sum(scores) / len(scores), 3) if scores else None
    data["rotations"] = rotations
    if not data["unified_credit_code"] and not data["name"]:
        return {
            "status": "not_recognized",
            "message": "已识别文字，但未找到企业名称或统一社会信用代码，请确认文件是清晰完整的营业执照。",
            "data": data,
        }
    return {
        "status": "recognized",
        "message": "营业执照 OCR 识别完成，请核对后保存。",
        "data": data,
    }
