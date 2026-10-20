#!/bin/sh
# 启动时先抓一轮，之后每 INTERVAL_SECONDS（默认 3 小时）再抓。
set -u

cd /app
INTERVAL="${CRAWL_INTERVAL_SECONDS:-10800}"
STOP_DUP="${CRAWL_STOP_DUP:-5}"
PAGE_SIZE="${CRAWL_PAGE_SIZE:-20}"
LOOKBACK_DAYS="${CRAWL_LOOKBACK_DAYS:-2}"
ATT_LIMIT="${CRAWL_ATT_LIMIT:-100}"

python cli.py init-db || echo "init-db failed"

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
    || echo "download-att quan failed"
  python cli.py download-att --site jd-qing-huicai --limit "$ATT_LIMIT" \
    || echo "download-att qhc failed"

  python cli.py crawl-supplier --stop-dup "$STOP_DUP" --page-size 50 \
    || echo "crawl-supplier failed"

  echo "=== $(date -Is) sleep ${INTERVAL}s ==="
  sleep "$INTERVAL"
done
