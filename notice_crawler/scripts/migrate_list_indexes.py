#!/usr/bin/env python3
"""为公告列表/筛选补加速索引（已存在则跳过）。

用法（在 notice_crawler 目录）:
  .venv/bin/python scripts/migrate_list_indexes.py --dry-run
  .venv/bin/python scripts/migrate_list_indexes.py

或:
  .venv/bin/python cli.py migrate-list-indexes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import ensure_list_indexes, ping  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="补齐公告列表查询索引")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要新建的索引，不执行")
    args = parser.parse_args()

    if not ping():
        print("数据库连接失败，请检查 .env 中 NOTICE_DB_URL", file=sys.stderr)
        return 1

    created = ensure_list_indexes(dry_run=args.dry_run)
    if not created:
        print("索引已齐全，无需变更")
        return 0
    prefix = "将新建" if args.dry_run else "已新建"
    print(f"{prefix} {len(created)} 个索引:")
    for name in created:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
