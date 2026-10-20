from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select
from tqdm import tqdm

from clients.http_session import build_session
from config import settings
from db import NoticeAttachment, NoticeGoods, NoticeParsed, NoticeRaw, dumps, get_session
from pipeline.parse_llm import (
    enrich_from_raw,
    extract_fields,
    parsed_row_to_dict,
    save_parsed,
)
from utils import ensure_https


def _ext_from_name(name: str, url: str) -> str:
    for src in (name, urlparse(url).path):
        if "." in src:
            return src.rsplit(".", 1)[-1].lower()[:32]
    return ""


def download_pending(*, limit: int = 50, site_id: Optional[str] = None) -> int:
    session = get_session()
    done = 0
    try:
        stmt = select(NoticeAttachment).where(NoticeAttachment.download_status == "pending")
        if site_id:
            stmt = stmt.where(NoticeAttachment.site_id == site_id)
        stmt = stmt.order_by(NoticeAttachment.id.asc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        http = build_session()
        for att in tqdm(rows, desc="download-att"):
            url = ensure_https(att.file_url)
            try:
                resp = http.get(url, timeout=60)
                resp.raise_for_status()
                content = resp.content
                sha = hashlib.sha256(content).hexdigest()
                ext = _ext_from_name(att.file_name or "", url)
                folder = settings.attachment_dir / att.site_id / str(att.notice_raw_id)
                folder.mkdir(parents=True, exist_ok=True)
                safe_name = re.sub(r"[\\\\/:*?\"<>|]+", "_", att.file_name or f"{sha}.{ext or 'bin'}")
                path = folder / safe_name
                path.write_bytes(content)
                att.local_path = str(path)
                att.file_ext = ext
                att.file_size = len(content)
                att.content_sha256 = sha
                att.download_status = "done"
                att.downloaded_at = datetime.now()
                att.error_message = None
                done += 1
            except Exception as exc:  # noqa: BLE001
                att.download_status = "fail"
                att.error_message = str(exc)[:1000]
            session.commit()
    finally:
        session.close()
    return done


def extract_text_from_file(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    if ext in {"txt", "md", "csv", "json", "html", "htm"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    # 图片等交给后续 OCR；此处先跳过
    return ""


def parse_attachments(*, limit: int = 50, site_id: Optional[str] = None, use_llm: bool = True) -> int:
    session = get_session()
    ok = 0
    try:
        stmt = select(NoticeAttachment).where(
            NoticeAttachment.download_status == "done",
            NoticeAttachment.parse_status.in_(["pending", "parse_fail"]),
        )
        if site_id:
            stmt = stmt.where(NoticeAttachment.site_id == site_id)
        stmt = stmt.order_by(NoticeAttachment.id.asc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        for att in tqdm(rows, desc="parse-att"):
            if not att.local_path:
                att.parse_status = "skipped"
                session.commit()
                continue
            path = Path(att.local_path)
            if not path.exists():
                att.parse_status = "parse_fail"
                att.error_message = "local file missing"
                session.commit()
                continue
            try:
                text = extract_text_from_file(path)
                att.extracted_text = text
                if not text.strip():
                    att.parse_status = "skipped"
                    att.error_message = "no extractable text (maybe image/scan pdf)"
                elif use_llm:
                    raw = session.get(NoticeRaw, att.notice_raw_id)
                    title = (raw.title if raw else "") or att.file_name or ""
                    # 本地小上下文模型：附件正文截断，避免 Requested tokens exceed context
                    parsed = extract_fields(text[:6000], title=title)
                    if not isinstance(parsed.get("extra"), dict):
                        parsed["extra"] = {}
                    parsed["extra"]["from_attachment_id"] = att.id
                    parsed["extra"]["from_attachment"] = att.file_name
                    att.parsed_json = dumps(parsed)
                    att.parse_status = "parsed"
                    att.parsed_at = datetime.now()
                    # 同步到公告：待解析整单写入；已解析则只补空字段，避免附件覆盖正文结果
                    if raw is not None:
                        if raw.parse_status in ("pending", "parse_fail", "skipped"):
                            parsed = enrich_from_raw(parsed, raw)
                            save_parsed(session, raw, parsed)
                        else:
                            existing = session.execute(
                                select(NoticeParsed).where(
                                    NoticeParsed.notice_raw_id == raw.id
                                )
                            ).scalar_one_or_none()
                            goods_rows = list(
                                session.execute(
                                    select(NoticeGoods).where(
                                        NoticeGoods.notice_raw_id == raw.id
                                    )
                                ).scalars().all()
                            )
                            base = (
                                parsed_row_to_dict(existing, goods_rows)
                                if existing
                                else {}
                            )
                            for k, v in parsed.items():
                                if k == "extra":
                                    continue
                                if k == "goods":
                                    if not base.get("goods") and v:
                                        base["goods"] = v
                                elif base.get(k) in (None, "", []) and v not in (
                                    None,
                                    "",
                                    [],
                                ):
                                    base[k] = v
                            base = enrich_from_raw(base, raw)
                            save_parsed(session, raw, base)
                    ok += 1
                else:
                    att.parse_status = "skipped"
                session.commit()
            except Exception as exc:  # noqa: BLE001
                att.parse_status = "parse_fail"
                att.error_message = str(exc)[:1000]
                session.commit()
    finally:
        session.close()
    return ok
