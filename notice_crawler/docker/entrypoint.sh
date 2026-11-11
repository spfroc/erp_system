#!/bin/sh
# 各平台独立循环并行抓取，互不阻塞：
# - sd-mall / sd-gpfa / jd / sd-ccgp / crawl-supplier / jd-att 各自调度
# - 同平台 flock：上轮未结束则跳过本轮，避免堆积
# - 公告站点：本地 0–6 点每 3h，其余时段每 1h（可用环境变量覆盖）
# - 京东附件仍按 CRAWL_ATT_INTERVAL_SECONDS（默认 30min）
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

# 兼容旧变量：未单独配置时，夜间沿用 CRAWL_INTERVAL_SECONDS（默认 3h）
DAY_INTERVAL="${CRAWL_DAY_INTERVAL_SECONDS:-3600}"
NIGHT_INTERVAL="${CRAWL_NIGHT_INTERVAL_SECONDS:-${CRAWL_INTERVAL_SECONDS:-10800}}"
NIGHT_START_HOUR="${CRAWL_NIGHT_START_HOUR:-0}"
NIGHT_END_HOUR="${CRAWL_NIGHT_END_HOUR:-6}"
# 供应商全量同步仍用固定间隔（默认跟夜间 3h，避免白天每小时全扫）
SUPPLIER_INTERVAL="${CRAWL_SUPPLIER_INTERVAL_SECONDS:-${NIGHT_INTERVAL}}"
ATT_INTERVAL="${CRAWL_ATT_INTERVAL_SECONDS:-1800}"
STOP_DUP="${CRAWL_STOP_DUP:-5}"
PAGE_SIZE="${CRAWL_PAGE_SIZE:-20}"
GPFA_PAGE_SIZE="${CRAWL_GPFA_PAGE_SIZE:-50}"
GPFA_MAX_ITEMS="${CRAWL_GPFA_MAX_ITEMS:-100}"
LOOKBACK_DAYS="${CRAWL_LOOKBACK_DAYS:-2}"
ATT_LIMIT="${CRAWL_ATT_LIMIT:-100}"
ATT_LOCK="${CRAWL_ATT_LOCK:-/app/data/jd-att.lock}"
CCGP_TIMEOUT="${CRAWL_CCGP_TIMEOUT_SECONDS:-1200}"
DATA_DIR="${CRAWL_DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

# 按本地墙钟选择站点抓取间隔：默认 0点(含)–6点(不含) 用夜间间隔，其余用白天间隔
crawl_interval_seconds() {
  hour=$(date +%H)
  hour=$((10#$hour))
  start_h=$((10#$NIGHT_START_HOUR))
  end_h=$((10#$NIGHT_END_HOUR))
  if [ "$hour" -ge "$start_h" ] && [ "$hour" -lt "$end_h" ]; then
    echo "$NIGHT_INTERVAL"
  else
    echo "$DAY_INTERVAL"
  fi
}

# /app/models 常为只读挂载；模型可放在可写的 data volume
if [ -z "${LOCAL_MODEL_PATH:-}" ] || [ ! -f "${LOCAL_MODEL_PATH}" ]; then
  for candidate in \
    /app/data/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    /app/data/models/qwen2.5-3b-instruct-q4_k_m.gguf \
    /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    /app/models/qwen2.5-3b-instruct-q4_k_m.gguf
  do
    if [ -f "$candidate" ]; then
      export LOCAL_MODEL_PATH="$candidate"
      break
    fi
  done
fi
if [ -n "${LOCAL_MODEL_PATH:-}" ]; then
  echo "=== $(date -Is) LOCAL_MODEL_PATH=${LOCAL_MODEL_PATH} ==="
fi

echo "=== $(date -Is) init-db ==="
python cli.py init-db

echo "=== $(date -Is) migrate-list-indexes ==="
python cli.py migrate-list-indexes

python cli.py ping >/dev/null

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

# 非阻塞抢锁：上轮未结束则跳过（子进程持锁，退出即释放）
with_flock() {
  lock_file="$1"
  label="$2"
  shift 2
  if ! command -v flock >/dev/null 2>&1; then
    echo "=== $(date -Is) flock missing, run ${label} without lock ===" >&2
    "$@"
    return $?
  fi
  mkdir -p "$(dirname "$lock_file")"
  # dash 仅支持 FD 0-9，故用 9
  (
    flock -n 9 || {
      echo "=== $(date -Is) ${label} still running, skip this slot ==="
      exit 0
    }
    "$@"
  ) 9>"$lock_file"
}

crawl_notice_site() {
  site="$1"
  start="$2"
  end="$3"
  echo "=== $(date -Is) crawl ${site} ${start}..${end} ==="
  python cli.py crawl \
    --site "$site" \
    --start-date "$start" \
    --end-date "$end" \
    --stop-dup "$STOP_DUP" \
    --page-size "$PAGE_SIZE" \
    || echo "crawl ${site} failed"
}

crawl_gpfa_once() {
  # 框架协议列表无日期参数；每类固定抓取 GPFA_MAX_ITEMS 条并解析
  echo "=== $(date -Is) crawl sd-gpfa max-items=${GPFA_MAX_ITEMS} page-size=${GPFA_PAGE_SIZE} ==="
  python cli.py crawl \
    --site sd-gpfa \
    --stop-dup "$STOP_DUP" \
    --page-size "$GPFA_PAGE_SIZE" \
    --max-items "$GPFA_MAX_ITEMS" \
    || echo "crawl sd-gpfa failed"
}

crawl_ccgp_once() {
  start="$1"
  end="$2"
  # 省采验证码重试极慢：限时；并去掉代理直连
  unset NOTICE_HTTP_PROXY HTTPS_PROXY HTTP_PROXY ALL_PROXY \
    https_proxy http_proxy all_proxy
  echo "=== $(date -Is) crawl sd-ccgp ${start}..${end} (timeout=${CCGP_TIMEOUT}s) ==="
  if command -v timeout >/dev/null 2>&1; then
    timeout "$CCGP_TIMEOUT" python cli.py crawl \
      --site sd-ccgp \
      --start-date "$start" \
      --end-date "$end" \
      --stop-dup "$STOP_DUP" \
      --page-size "$PAGE_SIZE" \
      || echo "crawl sd-ccgp failed/timeout"
  else
    python cli.py crawl \
      --site sd-ccgp \
      --start-date "$start" \
      --end-date "$end" \
      --stop-dup "$STOP_DUP" \
      --page-size "$PAGE_SIZE" \
      || echo "crawl sd-ccgp failed"
  fi
}

crawl_supplier_once() {
  echo "=== $(date -Is) crawl-supplier (full, no stop-dup) ==="
  python cli.py crawl-supplier --page-size 50 \
    || echo "crawl-supplier failed"
}

run_jd_att() {
  echo "=== $(date -Is) att download+parse (limit=${ATT_LIMIT}) ==="
  python cli.py download-att --site jd-quan-yicai --limit "$ATT_LIMIT" \
    || echo "download-att quan failed"
  python cli.py download-att --site jd-qing-huicai --limit "$ATT_LIMIT" \
    || echo "download-att qhc failed"
  python cli.py download-att --site sd-ggzyjyzx --limit "$ATT_LIMIT" \
    || echo "download-att mall failed"
  python cli.py parse-att --site jd-quan-yicai --limit "$ATT_LIMIT" \
    || echo "parse-att quan failed"
  python cli.py parse-att --site jd-qing-huicai --limit "$ATT_LIMIT" \
    || echo "parse-att qhc failed"
  python cli.py parse-att --site sd-ggzyjyzx --limit "$ATT_LIMIT" \
    || echo "parse-att mall failed"
}

# ---- 独立调度循环 ----

notice_loop() {
  site="$1"
  lock="${DATA_DIR}/crawl-${site}.lock"
  echo "=== $(date -Is) ${site} loop start (day=${DAY_INTERVAL}s night=${NIGHT_INTERVAL}s ${NIGHT_START_HOUR}-${NIGHT_END_HOUR}) ==="
  while true; do
    cycle_start=$(date +%s)
    start=$(date -d "${LOOKBACK_DAYS} days ago" +%F)
    end=$(date +%F)
    with_flock "$lock" "crawl-${site}" crawl_notice_site "$site" "$start" "$end"
    interval="$(crawl_interval_seconds)"
    sleep_until_next_slot "$cycle_start" "$interval" "crawl-${site}"
  done
}

ccgp_loop() {
  lock="${DATA_DIR}/crawl-sd-ccgp.lock"
  echo "=== $(date -Is) sd-ccgp loop start (day=${DAY_INTERVAL}s night=${NIGHT_INTERVAL}s ${NIGHT_START_HOUR}-${NIGHT_END_HOUR}, timeout=${CCGP_TIMEOUT}s) ==="
  while true; do
    cycle_start=$(date +%s)
    start=$(date -d "${LOOKBACK_DAYS} days ago" +%F)
    end=$(date +%F)
    with_flock "$lock" "crawl-sd-ccgp" crawl_ccgp_once "$start" "$end"
    interval="$(crawl_interval_seconds)"
    sleep_until_next_slot "$cycle_start" "$interval" "crawl-sd-ccgp"
  done
}

gpfa_loop() {
  lock="${DATA_DIR}/crawl-sd-gpfa.lock"
  echo "=== $(date -Is) sd-gpfa loop start (day=${DAY_INTERVAL}s night=${NIGHT_INTERVAL}s ${NIGHT_START_HOUR}-${NIGHT_END_HOUR}, max-items=${GPFA_MAX_ITEMS}) ==="
  while true; do
    cycle_start=$(date +%s)
    with_flock "$lock" "crawl-sd-gpfa" crawl_gpfa_once
    interval="$(crawl_interval_seconds)"
    sleep_until_next_slot "$cycle_start" "$interval" "crawl-sd-gpfa"
  done
}

supplier_loop() {
  lock="${DATA_DIR}/crawl-supplier.lock"
  echo "=== $(date -Is) crawl-supplier loop start (interval=${SUPPLIER_INTERVAL}s) ==="
  while true; do
    cycle_start=$(date +%s)
    with_flock "$lock" "crawl-supplier" crawl_supplier_once
    sleep_until_next_slot "$cycle_start" "$SUPPLIER_INTERVAL" "crawl-supplier"
  done
}

att_loop() {
  echo "=== $(date -Is) jd-att loop start (interval=${ATT_INTERVAL}s) ==="
  while true; do
    cycle_start=$(date +%s)
    with_flock "$ATT_LOCK" "jd-att" run_jd_att
    sleep_until_next_slot "$cycle_start" "$ATT_INTERVAL" "jd-att"
  done
}

LOOP_PIDS=""
start_loop() {
  "$@" &
  pid=$!
  LOOP_PIDS="${LOOP_PIDS} ${pid}"
  echo "=== $(date -Is) started $* pid=${pid} ==="
}

kill_loops() {
  for pid in $LOOP_PIDS; do
    kill "$pid" 2>/dev/null || true
  done
}

trap 'kill_loops' EXIT INT TERM

echo "=== $(date -Is) start independent crawl loops ==="
echo "=== $(date -Is) site schedule: ${NIGHT_START_HOUR}:00-${NIGHT_END_HOUR}:00 -> ${NIGHT_INTERVAL}s, else -> ${DAY_INTERVAL}s ==="
start_loop notice_loop sd-mall
start_loop gpfa_loop
start_loop notice_loop jd
start_loop ccgp_loop
start_loop supplier_loop
start_loop att_loop

# 主进程挂起，等待任一子循环退出（异常时重启容器会拉起）
wait
