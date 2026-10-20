#!/bin/sh
# 启动时先抓一轮，之后每 INTERVAL_SECONDS（默认 3 小时）再抓。
set -u

cd /app

if [ -z "${NOTICE_DB_URL:-}" ]; then
  if [ -z "${MYSQL_HOST:-}" ] || [ -z "${MYSQL_USER:-}" ] || [ -z "${MYSQL_DATABASE:-}" ]; then
    echo "NOTICE_DB_URL or MYSQL_HOST/MYSQL_USER/MYSQL_DATABASE is required" >&2
    exit 1
  fi
  NOTICE_DB_URL="$(python - <<'PY'
import os
from urllib.parse import quote_plus

user = quote_plus(os.environ["MYSQL_USER"])
password = quote_plus(os.environ.get("MYSQL_PASSWORD", ""))
host = os.environ["MYSQL_HOST"]
port = os.environ.get("MYSQL_PORT", "3306")
database = os.environ["MYSQL_DATABASE"]
print(f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")
PY
)"
  export NOTICE_DB_URL
fi

INTERVAL="${CRAWL_INTERVAL_SECONDS:-10800}"
STOP_DUP="${CRAWL_STOP_DUP:-5}"
PAGE_SIZE="${CRAWL_PAGE_SIZE:-20}"
LOOKBACK_DAYS="${CRAWL_LOOKBACK_DAYS:-2}"
ATT_LIMIT="${CRAWL_ATT_LIMIT:-100}"

python cli.py init-db
python cli.py ping >/dev/null

while true; do
  START=$(date -d "${LOOKBACK_DAYS} days ago" +%F)
  END=$(date +%F)
  echo "=== $(date -Is) crawl ${START}..${END} ==="

  python cli.py crawl \
    --site all \
    --start-date "$START" \
    --end-date "$END" \
    --stop-dup "$STOP_DUP" \
    --page-size "$PAGE_SIZE" \
    || echo "crawl failed"

  python cli.py download-att --site jd-quan-yicai --limit "$ATT_LIMIT" \
    || echo "download-att failed"

  python cli.py crawl-supplier --stop-dup "$STOP_DUP" --page-size 50 \
    || echo "crawl-supplier failed"

  echo "=== $(date -Is) sleep ${INTERVAL}s ==="
  sleep "$INTERVAL"
done
