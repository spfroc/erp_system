#!/usr/bin/env bash
set -euo pipefail

MOBILE="${1:-18698853145}"
CONTENT="${2:-【壹知产】青岛吉祥万家商贸有限公司的刘经理,咨询:青慧采关于青慧采入驻代办/代运营.联系电话:13964271978}"

echo "==== direct center marketing ===="
curl -sS -X POST 'http://127.0.0.1:8899/api/sms/marketing' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "mobile=${MOBILE}" \
  --data-urlencode "content=${CONTENT}" \
  --data-urlencode "source=ERP短信对接测试" \
  --data-urlencode "type=营销" \
  --data-urlencode "channel=marketing" \
  --data-urlencode "prefix=壹知产"
echo
echo
echo "==== latest page ===="
curl -sS 'http://127.0.0.1:8899/api/sms/page?page_size=3'
echo
