#!/usr/bin/env python3
"""将 notice_* 中误用 UTC 墙钟保存的时间纠正为 Asia/Shanghai。

用法（在 notice_crawler 目录）:
  .venv/bin/python scripts/fix_timezone.py --dry-run
  .venv/bin/python scripts/fix_timezone.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from db import NoticeParsed, NoticeRaw, get_session, init_db
from utils import parse_dt


def _json_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _dig_ms(*candidates):
    for v in candidates:
        if v in (None, ""):
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            continue
        if num > 1e9:
            return num
    return None


def _jd_times_from_raw(raw: NoticeRaw) -> dict:
    detail = _json_dict(raw.detail_json)
    list_item = _json_dict(raw.list_json)
    nested = _json_dict(detail.get("detail"))
    base = _json_dict(nested.get("auctionNoticeBaseInfo"))
    publish = parse_dt(
        _dig_ms(
            list_item.get("createTime"),
            detail.get("createTime"),
            detail.get("publishTime"),
            list_item.get("publishTime"),
        )
        or detail.get("createTime")
        or detail.get("publishTime")
        or list_item.get("publishTime")
    )
    start = parse_dt(
        _dig_ms(base.get("startTime"), detail.get("startTime"), list_item.get("startTime"))
        or base.get("startTime")
        or detail.get("startTime")
    )
    end = parse_dt(
        _dig_ms(base.get("endTime"), detail.get("endTime"), list_item.get("endTime"))
        or base.get("endTime")
        or detail.get("endTime")
    )
    return {"publish_time": publish, "start_time": start, "end_time": end}


def _looks_utc_wall(value: datetime | None, shanghai: datetime | None) -> bool:
    """当前值≈同一绝对时刻的 UTC 墙钟。"""
    if value is None or shanghai is None:
        return False
    return abs((value - (shanghai - timedelta(hours=8))).total_seconds()) <= 2


def _ops_looks_utc(value: datetime | None, publish: datetime | None) -> bool:
    """采集/更新时间是否像 UTC 墙钟。

    仅在「相对上海发布时间明显偏早」时判定，避免误伤凌晨合法抓取。
    """
    if value is None or publish is None:
        return False
    # 上海墙钟下采集应不早于发布太多；早于发布超过 1 小时 → 多半是 UTC 墙钟
    return value < publish - timedelta(hours=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix notice timezone wall clocks to Asia/Shanghai")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db()
    session = get_session()
    raw_changed = 0
    parsed_changed = 0
    publish_fixed = 0
    ops_fixed = 0
    try:
        rows = session.execute(select(NoticeRaw)).scalars().all()
        for raw in rows:
            changed = False
            if (raw.site_id or "").startswith("jd"):
                times = _jd_times_from_raw(raw)
                if times["publish_time"] and raw.publish_time != times["publish_time"]:
                    if raw.publish_time is None or _looks_utc_wall(raw.publish_time, times["publish_time"]):
                        raw.publish_time = times["publish_time"]
                        publish_fixed += 1
                        changed = True

            for field in ("crawled_at", "detail_at", "updated_at"):
                old = getattr(raw, field)
                if old is None:
                    continue
                if _ops_looks_utc(old, raw.publish_time):
                    setattr(raw, field, old + timedelta(hours=8))
                    ops_fixed += 1
                    changed = True

            if changed:
                raw_changed += 1

        parsed_rows = session.execute(select(NoticeParsed)).scalars().all()
        raw_by_id = {r.id: r for r in rows}
        for row in parsed_rows:
            changed = False
            raw = raw_by_id.get(row.notice_raw_id)
            if raw and (raw.site_id or "").startswith("jd"):
                times = _jd_times_from_raw(raw)
                for field in ("publish_time", "start_time", "end_time"):
                    correct = times.get(field)
                    old = getattr(row, field)
                    if correct and old != correct and (old is None or _looks_utc_wall(old, correct)):
                        setattr(row, field, correct)
                        changed = True
            for field in ("parsed_at", "updated_at"):
                old = getattr(row, field)
                if old is None:
                    continue
                if _ops_looks_utc(old, row.publish_time or (raw.publish_time if raw else None)):
                    setattr(row, field, old + timedelta(hours=8))
                    changed = True
            if changed:
                parsed_changed += 1

        print(
            f"{'[dry-run] ' if args.dry_run else ''}"
            f"raw_rows={raw_changed} parsed_rows={parsed_changed} "
            f"jd_publish_fixed={publish_fixed} ops_shifted={ops_fixed}"
        )
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
            print("committed")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
