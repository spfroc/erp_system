#!/usr/bin/env python3
"""合并清理山东政府采购网（sd-ccgp）历史重复公告，并迁移稳定 notice_key。

去重维度：site_id + title(去空白) + publish_time + notice_type
保留策略：优先 detail_ok / 有正文 / parsed / 已打标签，其次最早 id
清理后：把保留行（及其余行）的 notice_key 迁为 tp:sha256(标题|时间|类型)

用法（容器或本机 notice_crawler 目录）:
  python scripts/dedupe_sd_ccgp.py --dry-run
  python scripts/dedupe_sd_ccgp.py
  python scripts/dedupe_sd_ccgp.py --remap-only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import bindparam, text

from clients.sd_ccgp import SdCcgpClient
from db import engine, ping

SITE = "sd-ccgp"
BATCH = 500


def _score(row: dict) -> tuple:
    return (
        1 if row["crawl_status"] == "detail_ok" else 0,
        1 if row["has_html"] else 0,
        1 if row["parse_status"] == "parsed" else 0,
        1 if row["has_result_tag"] else 0,
        1 if row["has_product_tag"] else 0,
        # 越早抓到越优先保留（稳定主键）
        -int(row["id"]),
    )


def _norm_title(title: str | None) -> str:
    return re.sub(r"\s+", "", (title or "").strip())


def fetch_dup_groups(conn):
    """按归一化标题 + 精确发布时间 + 类型找重复组。"""
    rows = conn.execute(
        text(
            """
            SELECT
              TRIM(title) AS title,
              publish_time,
              notice_type,
              COUNT(*) AS cnt
            FROM notice_raw
            WHERE site_id = :site
              AND title IS NOT NULL AND TRIM(title) <> ''
              AND publish_time IS NOT NULL
              AND notice_type IS NOT NULL AND notice_type <> ''
            GROUP BY TRIM(title), publish_time, notice_type
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC, publish_time DESC
            """
        ),
        {"site": SITE},
    ).mappings().all()
    # 再按去空白标题合并（TRIM 仍可能因中间空白不同而未合并）
    buckets: dict[tuple, dict] = {}
    for row in rows:
        key = (_norm_title(row["title"]), row["publish_time"], row["notice_type"])
        if key not in buckets:
            buckets[key] = {
                "title": row["title"],
                "publish_time": row["publish_time"],
                "notice_type": row["notice_type"],
                "cnt": int(row["cnt"]),
            }
        else:
            buckets[key]["cnt"] += int(row["cnt"])
    return [v for v in buckets.values() if v["cnt"] > 1]


def fetch_group_rows(conn, title: str, publish_time, notice_type: str):
    needle = _norm_title(title)
    rows = conn.execute(
        text(
            """
            SELECT
              r.id,
              r.notice_key,
              r.title,
              r.crawl_status,
              r.parse_status,
              r.publish_time,
              r.notice_type,
              (r.content_html IS NOT NULL AND CHAR_LENGTH(r.content_html) > 0) AS has_html,
              EXISTS(
                SELECT 1 FROM notice_result_tag t WHERE t.notice_raw_id = r.id
              ) AS has_result_tag,
              EXISTS(
                SELECT 1 FROM notice_product_tag t WHERE t.notice_raw_id = r.id
              ) AS has_product_tag
            FROM notice_raw r
            WHERE r.site_id = :site
              AND r.publish_time = :publish_time
              AND r.notice_type = :notice_type
            ORDER BY r.id
            """
        ),
        {
            "site": SITE,
            "publish_time": publish_time,
            "notice_type": notice_type,
        },
    ).mappings().all()
    return [dict(r) for r in rows if _norm_title(r["title"]) == needle]


def migrate_tags(conn, keep_id: int, drop_ids: list[int]) -> dict:
    moved_result = 0
    stmt_donor = text(
        "SELECT notice_raw_id FROM notice_result_tag "
        "WHERE notice_raw_id IN :ids ORDER BY notice_raw_id LIMIT 1"
    ).bindparams(bindparam("ids", expanding=True))
    stmt_del_result = text(
        "DELETE FROM notice_result_tag WHERE notice_raw_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    stmt_del_product = text(
        "DELETE FROM notice_product_tag WHERE notice_raw_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    stmt_move = text(
        "UPDATE notice_result_tag SET notice_raw_id = :keep WHERE notice_raw_id = :donor"
    )

    keep_has_result = conn.execute(
        text("SELECT 1 FROM notice_result_tag WHERE notice_raw_id = :id LIMIT 1"),
        {"id": keep_id},
    ).scalar()
    if not keep_has_result:
        donor = conn.execute(stmt_donor, {"ids": list(drop_ids)}).scalar()
        if donor:
            conn.execute(stmt_move, {"keep": keep_id, "donor": donor})
            moved_result = 1

    deleted_result = conn.execute(stmt_del_result, {"ids": list(drop_ids)}).rowcount or 0
    deleted_product = conn.execute(stmt_del_product, {"ids": list(drop_ids)}).rowcount or 0
    return {
        "moved_result": moved_result,
        "deleted_result": deleted_result,
        "deleted_product": deleted_product,
    }


def delete_raws(conn, ids: list[int]) -> int:
    """生产库可能没有 FK CASCADE，子表需显式删除。"""
    child_tables = (
        "notice_product_tag",
        "notice_result_tag",
        "notice_goods",
        "notice_attachment",
        "notice_parsed",
    )
    total = 0
    for i in range(0, len(ids), BATCH):
        chunk = ids[i : i + BATCH]
        for table in child_tables:
            stmt = text(f"DELETE FROM {table} WHERE notice_raw_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            )
            conn.execute(stmt, {"ids": chunk})
        stmt = text("DELETE FROM notice_raw WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        total += conn.execute(stmt, {"ids": chunk}).rowcount or 0
    return total


def count_site(conn) -> tuple[int, int]:
    raw = conn.execute(
        text("SELECT COUNT(*) FROM notice_raw WHERE site_id = :site"), {"site": SITE}
    ).scalar()
    parsed = conn.execute(
        text("SELECT COUNT(*) FROM notice_parsed WHERE site_id = :site"), {"site": SITE}
    ).scalar()
    return int(raw or 0), int(parsed or 0)


def count_remaining_dups(conn) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM (
                  SELECT TRIM(title), publish_time, notice_type
                  FROM notice_raw
                  WHERE site_id = :site
                    AND title IS NOT NULL AND TRIM(title) <> ''
                    AND publish_time IS NOT NULL
                    AND notice_type IS NOT NULL AND notice_type <> ''
                  GROUP BY TRIM(title), publish_time, notice_type
                  HAVING COUNT(*) > 1
                ) t
                """
            ),
            {"site": SITE},
        ).scalar()
        or 0
    )


def plan_cleanup(conn) -> dict:
    groups = fetch_dup_groups(conn)
    plan = {
        "dup_groups": len(groups),
        "safe_groups": 0,
        "drop_count": 0,
        "examples": [],
        "actions": [],  # (title, publish_time, notice_type, keep_id, drop_ids)
    }
    merge_examples = 0
    for g in groups:
        rows = fetch_group_rows(conn, g["title"], g["publish_time"], g["notice_type"])
        if len(rows) < 2:
            continue
        ranked = sorted(rows, key=_score, reverse=True)
        keep_id = ranked[0]["id"]
        drop_ids = [r["id"] for r in ranked[1:]]
        plan["safe_groups"] += 1
        plan["drop_count"] += len(drop_ids)
        plan["actions"].append(
            (g["title"], g["publish_time"], g["notice_type"], keep_id, drop_ids)
        )
        if merge_examples < 3:
            plan["examples"].append(
                {
                    "title": (g["title"] or "")[:40],
                    "publish_time": str(g["publish_time"]),
                    "notice_type": g["notice_type"],
                    "cnt": len(rows),
                    "action": "merge",
                    "keep_id": keep_id,
                    "drop_ids": drop_ids[:5] + (["..."] if len(drop_ids) > 5 else []),
                }
            )
            merge_examples += 1
    return plan


def remap_stable_keys(conn, *, dry_run: bool) -> dict:
    """把仍非 tp:/id: 前缀的行迁到稳定 notice_key。"""
    rows = conn.execute(
        text(
            """
            SELECT id, notice_key, title, publish_time, notice_type
            FROM notice_raw
            WHERE site_id = :site
              AND notice_key NOT LIKE 'tp:%'
              AND notice_key NOT LIKE 'id:%'
            ORDER BY id
            """
        ),
        {"site": SITE},
    ).mappings().all()
    stats = {"candidates": len(rows), "updated": 0, "skipped_clash": 0, "skipped_empty": 0}
    for row in rows:
        new_key = SdCcgpClient.stable_notice_key(
            title=row["title"],
            publish_time=row["publish_time"],
            notice_type=row["notice_type"],
        )
        if not new_key or new_key == row["notice_key"]:
            stats["skipped_empty"] += 1
            continue
        clash = conn.execute(
            text(
                """
                SELECT id FROM notice_raw
                WHERE site_id = :site AND notice_key = :key AND id <> :id
                LIMIT 1
                """
            ),
            {"site": SITE, "key": new_key, "id": row["id"]},
        ).scalar()
        if clash:
            stats["skipped_clash"] += 1
            continue
        if dry_run:
            stats["updated"] += 1
            continue
        conn.execute(
            text("UPDATE notice_raw SET notice_key = :key WHERE id = :id"),
            {"key": new_key, "id": row["id"]},
        )
        stats["updated"] += 1
    return stats


def run(*, dry_run: bool, remap_only: bool) -> int:
    if not ping():
        print("数据库连接失败，请检查 NOTICE_DB_URL / MYSQL_*", file=sys.stderr)
        return 1

    with engine.connect() as conn:
        before_raw, before_parsed = count_site(conn)
        print(f"site={SITE}")
        print(f"before raw={before_raw} parsed={before_parsed}")

        if not remap_only:
            plan = plan_cleanup(conn)
            print(
                f"dup_groups={plan['dup_groups']} safe={plan['safe_groups']} "
                f"drop={plan['drop_count']}"
            )
            for ex in plan["examples"]:
                print("example=", ex)
        else:
            plan = {"actions": []}

        if dry_run and not remap_only:
            remap_stats = remap_stable_keys(conn, dry_run=True)
            print("remap_dry=", remap_stats)
            print("dry-run: no changes")
            return 0

    tag_stats = {"moved_result": 0, "deleted_result": 0, "deleted_product": 0}
    deleted_raw = 0
    for title, publish_time, notice_type, keep_id, drop_ids in plan["actions"]:
        with engine.begin() as conn:
            rows = fetch_group_rows(conn, title, publish_time, notice_type)
            if len(rows) < 2:
                continue
            ranked = sorted(rows, key=_score, reverse=True)
            keep_id = ranked[0]["id"]
            drop_ids = [r["id"] for r in ranked[1:]]
            stats = migrate_tags(conn, keep_id, drop_ids)
            for k, v in stats.items():
                tag_stats[k] += v
            deleted_raw += delete_raws(conn, drop_ids)
            # 保留行立刻迁稳定键
            keep = ranked[0]
            new_key = SdCcgpClient.stable_notice_key(
                title=keep["title"],
                publish_time=keep["publish_time"],
                notice_type=keep["notice_type"],
            )
            clash = conn.execute(
                text(
                    """
                    SELECT id FROM notice_raw
                    WHERE site_id = :site AND notice_key = :key AND id <> :id
                    LIMIT 1
                    """
                ),
                {"site": SITE, "key": new_key, "id": keep_id},
            ).scalar()
            if not clash and new_key and new_key != keep["notice_key"]:
                conn.execute(
                    text("UPDATE notice_raw SET notice_key = :key WHERE id = :id"),
                    {"key": new_key, "id": keep_id},
                )

    with engine.begin() as conn:
        remap_stats = remap_stable_keys(conn, dry_run=False)

    with engine.connect() as conn:
        after_raw, after_parsed = count_site(conn)
        remain = count_remaining_dups(conn)

    print("tag_stats=", tag_stats)
    print("remap_stats=", remap_stats)
    print(f"after raw={after_raw} parsed={after_parsed} remaining_dup_groups={remain}")
    print(f"deleted_raw={deleted_raw} (count_delta={before_raw - after_raw})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate sd-ccgp notice_raw rows")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不删数据")
    parser.add_argument(
        "--remap-only",
        action="store_true",
        help="只迁移 notice_key，不合并删除",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run, remap_only=args.remap_only)


if __name__ == "__main__":
    raise SystemExit(main())
