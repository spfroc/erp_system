#!/usr/bin/env python3
"""将根目录 customers.sql（Navicat dump）转换写入 mall_customer。

用法（在 notice_crawler 目录）:
  python scripts/import_customers_sql.py ../../customers.sql
  python scripts/import_customers_sql.py ../../customers.sql --limit 100 --dry-run
  python cli.py import-customers --sql ../customers.sql
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import (  # noqa: E402
    MallCustomer,
    _ensure_mall_customer_columns,
    get_session,
    init_db,
)
from sqlalchemy import select  # noqa: E402

# customers 表字段顺序（与 dump CREATE TABLE 一致）
CUSTOMER_COLS = [
    "id",
    "name",
    "platform_customer_id",
    "type",
    "address",
    "province",
    "city",
    "license",
    "license_code",
    "business_scope",
    "enter_time",
    "legal_person",
    "mobile",
    "email",
    "sell_id",
    "signed",
    "remark",
    "created_at",
    "updated_at",
    "agent_shop_product_number",
    "online_shop_product_number",
    "manufacturer_shop_product_number",
    "tag",
    "origin",
    "entering_origin",
    "new_mobile",
]

INSERT_RE = re.compile(r"^INSERT INTO\s+`?customers`?\s+VALUES\s*\(", re.I)


def parse_mysql_values(body: str) -> list:
    """解析 INSERT VALUES 括号内内容，返回 Python 值列表。"""
    values: list = []
    i = 0
    n = len(body)
    while i < n:
        while i < n and body[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if body[i] == ")":
            break
        if body.startswith("NULL", i) and (i + 4 >= n or body[i + 4] in ",)"):
            values.append(None)
            i += 4
            continue
        if body[i] in ("'", '"'):
            quote = body[i]
            i += 1
            chunks: list[str] = []
            while i < n:
                ch = body[i]
                if ch == "\\" and i + 1 < n:
                    nxt = body[i + 1]
                    esc = {
                        "0": "\0",
                        "n": "\n",
                        "r": "\r",
                        "t": "\t",
                        "b": "\b",
                        "Z": "\x1a",
                        "'": "'",
                        '"': '"',
                        "\\": "\\",
                    }
                    chunks.append(esc.get(nxt, nxt))
                    i += 2
                    continue
                if ch == quote:
                    # MySQL '' 转义
                    if i + 1 < n and body[i + 1] == quote:
                        chunks.append(quote)
                        i += 2
                        continue
                    i += 1
                    break
                chunks.append(ch)
                i += 1
            values.append("".join(chunks))
            continue
        # 数字
        j = i
        while j < n and body[j] not in ",)":
            j += 1
        raw = body[i:j].strip()
        i = j
        if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            values.append(int(raw))
        else:
            try:
                values.append(float(raw) if "." in raw else int(raw))
            except ValueError:
                values.append(raw)
    return values


def extract_values_body(line: str) -> str | None:
    m = INSERT_RE.match(line)
    if not m:
        return None
    start = m.end() - 1  # '('
    # 找匹配的结尾 ');'（行尾通常只有一行一个 VALUES）
    end = line.rfind(")")
    if end <= start:
        return None
    return line[start + 1 : end]


def _str(value, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_len is not None:
        return text[:max_len]
    return text


def _int(value, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dt(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def row_to_payload(cols: dict) -> dict | None:
    name = _str(cols.get("name"), 256)
    if not name:
        return None
    return {
        "name": name,
        "platform_customer_id": _str(cols.get("platform_customer_id"), 64) or "0",
        "type": _str(cols.get("type"), 128) or "",
        "address": _str(cols.get("address")),
        "province": _str(cols.get("province"), 64) or "",
        "city": _str(cols.get("city"), 64) or "",
        "license": _str(cols.get("license"), 256) or "",
        "license_code": _str(cols.get("license_code"), 128) or "",
        "business_scope": _str(cols.get("business_scope")) or "",
        "enter_time": _str(cols.get("enter_time"), 64) or "",
        "legal_person": _str(cols.get("legal_person"), 128) or "",
        "mobile": _str(cols.get("mobile"), 512) or "",
        "new_mobile": _str(cols.get("new_mobile"), 512),
        "email": _str(cols.get("email"), 256) or "",
        "origin": _str(cols.get("origin"), 64) or "4",
        "signed": _str(cols.get("signed"), 32) or "0",
        "tag": _str(cols.get("tag"), 191),
        "sell_id": _int(cols.get("sell_id"), 0) or 0,
        "remark": _str(cols.get("remark")),
        "agent_shop_product_number": _int(cols.get("agent_shop_product_number")),
        "online_shop_product_number": _int(cols.get("online_shop_product_number")),
        "manufacturer_shop_product_number": _int(cols.get("manufacturer_shop_product_number")),
        "entering_origin": _int(cols.get("entering_origin"), 0) or 0,
        "legacy_customer_id": _int(cols.get("id")),
        "crawled_at": _dt(cols.get("created_at")),
        "updated_at": _dt(cols.get("updated_at")),
    }


def iter_customer_rows(sql_path: Path):
    with sql_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            body = extract_values_body(line)
            if body is None:
                continue
            values = parse_mysql_values(body)
            if len(values) < len(CUSTOMER_COLS):
                # 允许尾部缺列
                values = values + [None] * (len(CUSTOMER_COLS) - len(values))
            elif len(values) > len(CUSTOMER_COLS):
                values = values[: len(CUSTOMER_COLS)]
            cols = dict(zip(CUSTOMER_COLS, values))
            payload = row_to_payload(cols)
            if payload:
                yield line_no, payload


def import_customers(
    sql_path: Path,
    *,
    batch: int = 500,
    limit: int | None = None,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """返回 (读入, 写入/更新, 跳过)。"""
    init_db()
    _ensure_mall_customer_columns()

    read_n = 0
    write_n = 0
    skip_n = 0
    session = get_session()
    try:
        buffer: list[dict] = []

        def flush():
            nonlocal write_n, skip_n, buffer
            if not buffer:
                return
            # 同批 / dump 内同名多行：保留最后一条（通常 legacy id 更大）
            deduped: dict[str, dict] = {}
            for payload in buffer:
                name = payload["name"]
                if name in deduped:
                    skip_n += 1
                deduped[name] = payload
            rows = list(deduped.values())
            buffer = []
            if dry_run:
                write_n += len(rows)
                return
            names = [row["name"] for row in rows]
            existing = {
                row.name: row
                for row in session.execute(select(MallCustomer).where(MallCustomer.name.in_(names))).scalars()
            }
            for payload in rows:
                name = payload["name"]
                row = existing.get(name)
                if row is None:
                    row = MallCustomer(name=name)
                    session.add(row)
                    existing[name] = row  # 避免同批再 INSERT
                for key, value in payload.items():
                    if key == "name":
                        continue
                    if value is not None:
                        setattr(row, key, value)
                write_n += 1
            session.commit()

        for _line_no, payload in iter_customer_rows(sql_path):
            read_n += 1
            buffer.append(payload)
            if len(buffer) >= batch:
                flush()
                if read_n % 10000 == 0:
                    print(f"… {read_n} rows", flush=True)
            if limit and read_n >= limit:
                break
        flush()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return read_n, write_n, skip_n


def main() -> None:
    parser = argparse.ArgumentParser(description="Import customers.sql into mall_customer")
    parser.add_argument("sql", type=Path, help="path to customers.sql")
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = args.sql.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"file not found: {path}")
    read_n, write_n, skip_n = import_customers(
        path, batch=args.batch, limit=args.limit, dry_run=args.dry_run
    )
    mode = "dry-run" if args.dry_run else "imported"
    print(f"{mode}: read={read_n} upserted={write_n} skipped={skip_n}")


if __name__ == "__main__":
    main()
