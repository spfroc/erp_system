#!/bin/sh
# 启动时先抓一轮，之后：
# - 公告/供应商：按 CRAWL_INTERVAL_SECONDS（默认 3h）窗口对齐；超时跳过已错过窗口
# - 京东附件下载+解析：按 CRAWL_ATT_INTERVAL_SECONDS（默认 30min）更频调度；
#   flock 保证全局同时只跑一个附件任务（上轮未结束则跳过本轮）
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
ATT_INTERVAL="${CRAWL_ATT_INTERVAL_SECONDS:-1800}"
STOP_DUP="${CRAWL_STOP_DUP:-5}"
PAGE_SIZE="${CRAWL_PAGE_SIZE:-20}"
LOOKBACK_DAYS="${CRAWL_LOOKBACK_DAYS:-2}"
ATT_LIMIT="${CRAWL_ATT_LIMIT:-100}"
ATT_LOCK="${CRAWL_ATT_LOCK:-/app/data/jd-att.lock}"
mkdir -p "$(dirname "$ATT_LOCK")"

echo "=== $(date -Is) init-db ==="
python cli.py init-db

echo "=== $(date -Is) migrate-list-indexes ==="
python cli.py migrate-list-indexes

python cli.py ping >/dev/null

crawl_site() {
  site="$1"
  echo "=== $(date -Is) crawl ${site} ${START}..${END} ==="
  python cli.py crawl \
    --site "$site" \
    --start-date "$START" \
    --end-date "$END" \
    --stop-dup "$STOP_DUP" \
    --page-size "$PAGE_SIZE" \
    || echo "crawl ${site} failed"
}

# 从 cycle_start 对齐到下一个 interval 窗口；超时不追赶
sleep_until_next_slot() {
  cycle_start="$1"
  interval_s="$2"
  label="${3:-cycle}"
  now=$(date +%s)
  elapsed=$((now - cycle_start))
  if [ "$elapsed" -lt 0 ]; then
    elapsed=0
  fi
  if [ "$elapsed" -lt "$interval_s" ]; then
    sleep_s=$((interval_s - elapsed))
    echo "=== $(date -Is) ${label} ${elapsed}s < ${interval_s}s, sleep ${sleep_s}s ==="
  else
    over=$((elapsed % interval_s))
    if [ "$over" -eq 0 ]; then
      sleep_s=0
      echo "=== $(date -Is) ${label} overran exactly ${elapsed}s, next slot now ==="
    else
      sleep_s=$((interval_s - over))
      missed=$((elapsed / interval_s))
      echo "=== $(date -Is) ${label} overran ${elapsed}s, skip ${missed} slot(s), sleep ${sleep_s}s ==="
    fi
  fi
  if [ "$sleep_s" -gt 0 ]; then
    sleep "$sleep_s"
  fi
}

run_jd_att() {
  echo "=== $(date -Is) jd-att download+parse (limit=${ATT_LIMIT}) ==="
  python cli.py download-att --site jd-quan-yicai --limit "$ATT_LIMIT" \
    || echo "download-att quan failed"
  python cli.py download-att --site jd-qing-huicai --limit "$ATT_LIMIT" \
    || echo "download-att qhc failed"
  python cli.py parse-att --site jd-quan-yicai --limit "$ATT_LIMIT" \
    || echo "parse-att quan failed"
  python cli.py parse-att --site jd-qing-huicai --limit "$ATT_LIMIT" \
    || echo "parse-att qhc failed"
}

# 非阻塞抢锁：上轮未结束则跳过本轮（子进程持锁，退出即释放）
try_run_jd_att() {
  if ! command -v flock >/dev/null 2>&1; then
    echo "=== $(date -Is) flock missing, run jd-att without lock ===" >&2
    run_jd_att
    return 0
  fi
  # dash 仅支持 FD 0-9，故用 9
  (
    flock -n 9 || {
      echo "=== $(date -Is) jd-att still running, skip this slot ==="
      exit 0
    }
    run_jd_att
  ) 9>"$ATT_LOCK"
}

# 附件循环：更频、与公告抓取并行；flock 保证同时只一个
att_loop() {
  echo "=== $(date -Is) jd-att loop start (interval=${ATT_INTERVAL}s) ==="
  while true; do
    cycle_start=$(date +%s)
    try_run_jd_att
    sleep_until_next_slot "$cycle_start" "$ATT_INTERVAL" "jd-att"
  done
}

att_loop &
ATT_LOOP_PID=$!
trap 'kill "$ATT_LOOP_PID" 2>/dev/null || true' EXIT INT TERM

while true; do
  CYCLE_START=$(date +%s)
  START=$(date -d "${LOOKBACK_DAYS} days ago" +%F)
  END=$(date +%F)

  # 分站点执行：任一失败不阻断其余
  crawl_site sd-mall

  # 山东政府采购网走公网直连；商城 SOCKS 代理对 ccgp 易触发 blackIp
  (
    unset NOTICE_HTTP_PROXY HTTPS_PROXY HTTP_PROXY ALL_PROXY \
      https_proxy http_proxy all_proxy
    crawl_site sd-ccgp
  )

  crawl_site jd

  python cli.py crawl-supplier --stop-dup "$STOP_DUP" --page-size 50 \
    || echo "crawl-supplier failed"

  sleep_until_next_slot "$CYCLE_START" "$INTERVAL" "crawl"
done
