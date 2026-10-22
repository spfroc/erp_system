from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

import pdfplumber


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def squeeze_invoice_text(text: str) -> str:
    """Chinese e-invoice PDFs often insert spaces between every glyph."""
    return re.sub(r"\s+", "", text or "")


def is_fully_doubled(text: str) -> bool:
    value = text or ""
    return len(value) >= 4 and len(value) % 2 == 0 and all(value[index] == value[index + 1] for index in range(0, len(value), 2))


def undouble_text(text: str) -> str:
    if is_fully_doubled(text):
        return text[::2]
    return text


def undouble_repeated_runs(text: str) -> str:
    """Collapse AABBCC runs used by some e-invoice text layers."""
    chars: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if (
            index + 3 < length
            and text[index] == text[index + 1]
            and text[index + 2] == text[index + 3]
        ):
            while index + 1 < length and text[index] == text[index + 1]:
                chars.append(text[index])
                index += 2
            continue
        chars.append(text[index])
        index += 1
    return "".join(chars)


def undouble_glyphs_keep_spaces(text: str) -> str:
    """Collapse doubled glyphs while preserving whitespace between fields.

    Some e-invoice text layers double every character (``套套 44 1155...``) but
    still keep spaces between unit / qty / price. Squeezing first would glue
    ``套41592.92...`` and break spaced tail parsing.
    """
    chars: list[str] = []
    index = 0
    length = len(text or "")
    while index < length:
        current = text[index]
        if current.isspace():
            chars.append(current)
            index += 1
            continue
        if index + 1 < length and text[index + 1] == current:
            chars.append(current)
            index += 2
            continue
        chars.append(current)
        index += 1
    return "".join(chars)


def invoice_text_is_doubled(squeezed: str) -> bool:
    match = re.search(r"发票号码[:：]([0-9]{16,80})", squeezed)
    if match and is_fully_doubled(match.group(1)):
        return True
    return bool(re.search(r"\d{4}年年\d{1,4}月月", squeezed))


def prepare_invoice_text(text: str) -> str:
    squeezed = squeeze_invoice_text(text)
    if invoice_text_is_doubled(squeezed):
        return undouble_repeated_runs(squeezed)
    return squeezed


def clean_party_name(value: str) -> str:
    text = compact(value)
    text = re.sub(r"(?:[购销买卖]方信息)+$", "", text)
    text = re.sub(r"方信?息?$", "", text)
    return text.strip(" ：:|-")


def normalize_date(value: str) -> str:
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", value)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return value


def money_to_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").replace("¥", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


INVOICE_ITEM_UNITS = (
    "千克",
    "公斤",
    "个",
    "盒",
    "套",
    "卷",
    "台",
    "件",
    "只",
    "条",
    "袋",
    "箱",
    "米",
    "升",
    "批",
    "项",
    "次",
    "张",
    "包",
    "桶",
    "瓶",
    "盆",
    "支",
    "组",
    "对",
    "辆",
    "吨",
    "令",
    "kg",
    "g",
)
INVOICE_ITEM_UNIT_RE = "|".join(sorted(INVOICE_ITEM_UNITS, key=len, reverse=True))
INVOICE_ITEM_TAIL_RE = re.compile(
    rf"(?P<unit>{INVOICE_ITEM_UNIT_RE})\s+"
    r"(?P<quantity>[0-9]+(?:\.[0-9]+)?)\s+"
    r"(?P<unit_price>[0-9]+(?:\.[0-9]+)?)\s+"
    r"(?P<amount>[0-9]+(?:\.[0-9]+)?)\s+"
    r"(?P<tax_rate>[0-9]+(?:\.[0-9]+)?%)\s+"
    r"(?P<tax_amount>[0-9]+(?:\.[0-9]+)?)\s*$",
)
# Compact tails after glyph-undouble + squeeze: 套41592.926371.6813%828.32
# Require decimals on unit_price/amount so quantity is not swallowed (4 vs 41592...).
INVOICE_ITEM_TAIL_COMPACT_RE = re.compile(
    rf"(?P<unit>{INVOICE_ITEM_UNIT_RE})"
    r"(?P<quantity>[0-9]+(?:\.[0-9]+)?)"
    r"(?P<unit_price>[0-9]+\.[0-9]+)"
    r"(?P<amount>[0-9]+\.[0-9]+)"
    r"(?P<tax_rate>[0-9]+(?:\.[0-9]+)?%)"
    r"(?P<tax_amount>[0-9]+(?:\.[0-9]+)?)\s*$",
)
INVOICE_ITEM_START_RE = re.compile(r"\*[^*]+\*")


_DETAIL_BLOCK_RE = re.compile(r"项目名称(.*?)(?:小\s*计|合\s*计)", re.S)
_MONEY_ONLY_RE = re.compile(r"[¥￥0-9.,\s]+")


def _invoice_detail_lines(text: str) -> list[str]:
    """明细区截止到本页小计或合计，避免多页发票停在第一页合计。"""
    match = _DETAIL_BLOCK_RE.search(text)
    if not match:
        return []
    lines: list[str] = []
    for raw_line in match.group(1).splitlines():
        line = compact(raw_line)
        if not line or line in {"的"}:
            continue
        squeezed_line = squeeze_invoice_text(line)
        if "单价" in squeezed_line and ("规格" in squeezed_line or "项目名称" in squeezed_line):
            continue
        if _MONEY_ONLY_RE.fullmatch(line):
            continue
        lines.append(line)
    return lines


def _match_invoice_item_tail(line: str) -> re.Match[str] | None:
    return INVOICE_ITEM_TAIL_RE.search(line) or INVOICE_ITEM_TAIL_COMPACT_RE.search(line)


def _merge_invoice_item_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if INVOICE_ITEM_START_RE.search(line):
            merged.append(line)
            continue
        if not merged:
            continue
        previous = merged[-1]
        tail = _match_invoice_item_tail(previous)
        if tail:
            merged[-1] = f"{previous[:tail.start()].rstrip()} {line} {previous[tail.start():].lstrip()}".strip()
        else:
            merged[-1] = f"{previous} {line}".strip()
    return merged


def _append_item_continuation(previous: str, extra: str) -> str:
    extra = compact(extra)
    if not extra:
        return previous
    tail = _match_invoice_item_tail(previous)
    if tail:
        return f"{previous[: tail.start()].rstrip()} {extra} {previous[tail.start() :].lstrip()}".strip()
    return f"{previous} {extra}".strip()


def _merged_item_lines(text: str) -> list[str]:
    """按页收集明细。下一页开头、新项目之前的文字并入上一页最后一行。"""
    pages = text.split("\f") if "\f" in text else [text]
    merged_lines: list[str] = []
    for page in pages:
        lines = _invoice_detail_lines(page)
        if not lines:
            continue
        split_at = next((index for index, line in enumerate(lines) if INVOICE_ITEM_START_RE.search(line)), None)
        if split_at is None:
            if merged_lines:
                merged_lines[-1] = _append_item_continuation(merged_lines[-1], " ".join(lines))
            continue
        if split_at and merged_lines:
            merged_lines[-1] = _append_item_continuation(merged_lines[-1], " ".join(lines[:split_at]))
        merged_lines.extend(_merge_invoice_item_lines(lines[split_at:]))
    return merged_lines


def parse_invoice_line_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in _merged_item_lines(text):
        tail = _match_invoice_item_tail(line)
        start = INVOICE_ITEM_START_RE.search(line)
        if not tail or not start:
            continue
        body = compact(line[start.end():tail.start()]).strip(" *")
        product_name, specification = _split_invoice_item_name_spec(body)
        if not product_name:
            continue
        items.append(
            {
                "product_name": product_name,
                "specification": specification,
                "unit": tail.group("unit"),
                "quantity": money_to_float(tail.group("quantity")),
                "unit_price": money_to_float(tail.group("unit_price")),
                "amount": money_to_float(tail.group("amount")),
                "tax_rate": tail.group("tax_rate"),
                "tax_amount": money_to_float(tail.group("tax_amount")),
                "raw": line,
            }
        )
    return items


def _split_invoice_item_name_spec(body: str) -> tuple[str, str]:
    """Split「商品名称 规格型号」when both appear after the *类别* tag."""
    text = compact(body).strip(" *")
    if not text:
        return "", ""
    parts = [part for part in text.split(" ") if part]
    if not parts:
        return "", ""

    # Paired wrap duplicates: "A B A B C C" -> name/spec both "A B C".
    name_parts: list[str] = []
    idx = 0
    while idx < len(parts):
        matched = False
        max_width = (len(parts) - idx) // 2
        for width in range(max_width, 0, -1):
            left = parts[idx : idx + width]
            right = parts[idx + width : idx + 2 * width]
            if left == right:
                name_parts.extend(left)
                idx += 2 * width
                matched = True
                break
        if not matched:
            name_parts.append(parts[idx])
            idx += 1

    # All tokens came from duplicated name/spec pairs (incl. wrapped lines).
    if name_parts and len(parts) == 2 * len(name_parts):
        joined = " ".join(name_parts)
        return joined, joined
    # Two distinct fields: name + specification.
    if len(name_parts) == 2:
        return name_parts[0], name_parts[1]
    if len(parts) == 2:
        return parts[0], parts[1]
    # Wrapped columns alternate name/spec when row1 name looks tied to row1 spec.
    if len(name_parts) == 4:
        a, b, c, d = name_parts
        if a and b and (a in b or b.startswith(a) or a[:2] == b[:2]):
            return f"{a} {c}", f"{b} {d}"
    # Model code sitting between Chinese name fragments.
    for i, part in enumerate(name_parts):
        if i == 0 or i == len(name_parts) - 1:
            continue
        if re.search(r"[A-Za-z]+\d|\d+[A-Za-z]", part):
            name = "".join(name_parts[:i] + name_parts[i + 1 :])
            return name, part
    return " ".join(name_parts), ""


def extract_between(text: str, left: str, right: str) -> str:
    pattern = re.escape(left) + r"(.*?)" + re.escape(right)
    match = re.search(pattern, text, re.S)
    return compact(match.group(1)) if match else ""


def _fill_missing_invoice_fields(squeezed: str, fields: dict[str, Any]) -> None:
    if not fields["invoice_no"]:
        match = re.search(r"(\d{20})(?=20\d{2}年)", squeezed) or re.search(r"(?<!\d)(\d{20})(?!\d)", squeezed)
        if match:
            fields["invoice_no"] = match.group(1)
    if not fields["invoice_date"]:
        match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", squeezed)
        if match:
            fields["invoice_date"] = normalize_date(match.group(1))
    tax_numbers = [item for item in re.findall(r"[0-9A-Z]{18}", squeezed) if re.search(r"[A-Z]", item)]
    if not fields["buyer_tax_no"] and tax_numbers:
        fields["buyer_tax_no"] = tax_numbers[0]
    if not fields["seller_tax_no"] and len(tax_numbers) >= 2:
        fields["seller_tax_no"] = tax_numbers[1]
    if not fields["buyer_name"] or not fields["seller_name"]:
        names = re.findall(r"[\u4e00-\u9fff]{2,16}(?:有限公司|股份有限公司|厂|中心|合作社)", squeezed)
        cleaned: list[str] = []
        for name in names:
            name = re.sub(r"^[年月日号码]+", "", name)
            if len(name) >= 4 and "发票" not in name and name not in cleaned:
                cleaned.append(name)
        if not fields["buyer_name"] and cleaned:
            fields["buyer_name"] = cleaned[0]
        if not fields["seller_name"] and len(cleaned) >= 2:
            fields["seller_name"] = cleaned[1]
    if fields["amount_without_tax"] is None or fields["tax_amount"] is None:
        amounts = re.findall(r"¥([0-9]+(?:\.[0-9]+)?)", squeezed)
        if len(amounts) >= 2 and fields["amount_without_tax"] is None:
            fields["amount_without_tax"] = money_to_float(amounts[0])
        if len(amounts) >= 2 and fields["tax_amount"] is None:
            fields["tax_amount"] = money_to_float(amounts[1])
    if fields["total_amount"] is None:
        match = re.search(r"[（(]小写[）)]¥([0-9]+(?:\.[0-9]+)?)", squeezed)
        if match:
            fields["total_amount"] = money_to_float(match.group(1))
        elif amounts := re.findall(r"¥([0-9]+(?:\.[0-9]+)?)", squeezed):
            fields["total_amount"] = money_to_float(amounts[-1])


def parse_invoice_text(text: str) -> dict[str, Any]:
    squeezed = prepare_invoice_text(text)

    invoice_no = ""
    invoice_date = ""
    buyer_name = ""
    buyer_tax_no = ""
    seller_name = ""
    seller_tax_no = ""

    match = re.search(r"发票号码[:：]([0-9]{8,40})", squeezed)
    if match:
        invoice_no = undouble_text(match.group(1))

    match = re.search(
        r"开票日期[:：]([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日|[0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})",
        squeezed,
    )
    if match:
        invoice_date = normalize_date(undouble_text(match.group(1)))

    buyer_seller_match = re.search(
        r"购.*?名称[:：](.*?)销名称[:：](.*?)买.*?统一社会信用代码/纳税人识别号[:：]([0-9A-Z]{15,40})信统一社会信用代码/纳税人识别号[:：]([0-9A-Z]{15,40})",
        squeezed,
    )
    if buyer_seller_match:
        buyer_name = clean_party_name(undouble_text(buyer_seller_match.group(1)))
        seller_name = clean_party_name(undouble_text(buyer_seller_match.group(2)))
        buyer_tax_no = undouble_text(buyer_seller_match.group(3))
        seller_tax_no = undouble_text(buyer_seller_match.group(4))
    else:
        buyer_match = re.search(
            r"(?:购|买)方?名称[:：]([^：]+?)(?:销|售|统一社会信用代码|项目名称)",
            squeezed,
        )
        seller_match = re.search(
            r"(?:销|售)方?名称[:：]([^：]+?)(?:购|买|统一社会信用代码|项目名称)",
            squeezed,
        )
        if buyer_match:
            buyer_name = clean_party_name(undouble_text(buyer_match.group(1)))
        if seller_match:
            seller_name = clean_party_name(undouble_text(seller_match.group(1)))
        if len(buyer_name) < 4:
            buyer_name = ""
        if len(seller_name) < 4:
            seller_name = ""
        tax_numbers = re.findall(
            r"(?:统一社会信用代码(?:/纳税人识别号)?|纳税人识别号)[:：]([0-9A-Z]{15,40})",
            squeezed,
        )
        if len(tax_numbers) >= 2:
            buyer_tax_no = undouble_text(tax_numbers[0])
            seller_tax_no = undouble_text(tax_numbers[1])
        elif len(tax_numbers) == 1 and not buyer_tax_no:
            buyer_tax_no = undouble_text(tax_numbers[0])

    total_line = extract_between(squeezed, "合计", "价税合计")
    amount_without_tax = None
    tax_amount = None
    if total_line:
        amounts = re.findall(r"¥([0-9]+(?:\.[0-9]+)?)", total_line)
        if len(amounts) >= 2:
            amount_without_tax = money_to_float(amounts[0])
            tax_amount = money_to_float(amounts[1])

    total_amount = None
    match = re.search(r"[（(]小写[）)]¥([0-9]+(?:\.[0-9]+)?)", squeezed)
    if match:
        total_amount = money_to_float(match.group(1))

    fields = {
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "buyer_name": buyer_name,
        "buyer_tax_no": buyer_tax_no,
        "seller_name": seller_name,
        "seller_tax_no": seller_tax_no,
        "amount_without_tax": amount_without_tax,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
        "line_items": parse_invoice_line_items(text) or parse_invoice_line_items(prepare_line_item_text(text)),
    }
    _fill_missing_invoice_fields(squeezed, fields)
    scalar_values = [value for key, value in fields.items() if key != "line_items"]
    matched_count = sum(1 for value in scalar_values if value not in ("", None))
    return {
        **fields,
        "confidence": round(matched_count / len(scalar_values), 2),
        "source": "pdf_text",
        "raw_text": text,
    }


def prepare_line_item_text(text: str) -> str:
    if "\f" in text:
        return "\f".join(prepare_line_item_text(part) for part in text.split("\f"))
    if not invoice_text_is_doubled(squeeze_invoice_text(text)):
        return text
    lines = []
    for line in text.splitlines():
        if not line.strip():
            lines.append("")
            continue
        # Keep field separators, then compact runs of whitespace.
        lines.append(compact(undouble_glyphs_keep_spaces(line)))
    return "\n".join(lines)


def _ocr_invoice_text(content: bytes) -> str:
    import io

    import fitz
    import numpy as np
    from PIL import Image

    from app.services.business_license_parser import _ocr_engine, _payload_lines

    page_texts: list[str] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for page_number in range(len(document)):
            page = document[page_number]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            page_lines, _scores = _payload_lines(_ocr_engine()(np.asarray(image)))
            page_texts.append("\n".join(page_lines))
    return "\f".join(page_texts)


def _invoice_missing_core(parsed: dict[str, Any] | None) -> bool:
    if not parsed:
        return True
    return not parsed.get("invoice_no") or not parsed.get("buyer_name") or parsed.get("total_amount") is None


def parse_invoice_pdf_bytes(content: bytes) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp:
        temp.write(content)
        temp_path = Path(temp.name)

    try:
        texts: list[str] = []
        page_count = 0
        image_count = 0
        with pdfplumber.open(temp_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                texts.append(page_text)
                image_count += len(page.images)
        text = "\f".join(texts).strip("\n")
        parsed = parse_invoice_text(text) if text else None
        source = "pdf_text"
        message = "发票识别完成（PDF 文本层）。"
        if _invoice_missing_core(parsed):
            try:
                ocr_text = _ocr_invoice_text(content)
            except Exception as error:
                ocr_text = ""
                if not parsed:
                    return {
                        "status": "ocr_error",
                        "message": f"发票 OCR 处理失败：{error}",
                        "page_count": page_count,
                        "image_count": image_count,
                        "data": None,
                    }
            if ocr_text.strip():
                ocr_parsed = parse_invoice_text(ocr_text)
                if not parsed or (ocr_parsed.get("confidence") or 0) > (parsed.get("confidence") or 0):
                    parsed = ocr_parsed
                    source = "image_ocr"
                    message = "发票识别完成（图片 OCR）。"
                parsed["source"] = source
        if not parsed or _invoice_missing_core(parsed):
            return {
                "status": "not_recognized",
                "message": "未从发票中识别到号码、购销方或金额，请核对 PDF 是否完整。",
                "page_count": page_count,
                "image_count": image_count,
                "data": parsed,
            }
        item_count = len(parsed.get("line_items") or [])
        if item_count:
            message = f"{message}共识别 {item_count} 个商品明细。"
        parsed["source"] = source
        return {
            "status": "recognized",
            "message": message,
            "page_count": page_count,
            "image_count": image_count,
            "data": parsed,
        }
    finally:
        temp_path.unlink(missing_ok=True)
