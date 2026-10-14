#!/usr/bin/env bash
set -euo pipefail
echo "=== nginx center ==="
grep -RIn --include='*.conf' -E 'center|8899|sms' /home/spf/projects/docker/nginx /etc/nginx 2>/dev/null | head -40 || true
echo "=== docker compose center ==="
find /home/spf/projects/docker /home/spf/projects/center -maxdepth 3 \( -name 'docker-compose*.yml' -o -name 'compose*.yml' \) 2>/dev/null
echo "=== admin proxy note ==="
grep -RIn --include='*.php' -E 'center/note|sms/marketing|8899' /home/spf/projects/admin 2>/dev/null | head -40 || true
echo "=== listening php/nginx ==="
ss -lntp 2>/dev/null | head -40 || netstat -lntp 2>/dev/null | head -40
echo "=== center public ==="
ls /home/spf/projects/center/public | head
echo "=== try common urls ==="
for u in \
  'http://127.0.0.1/api/sms/type/options' \
  'http://127.0.0.1:80/api/sms/type/options' \
  'http://center.local/api/sms/type/options' \
  'http://127.0.0.1:8080/api/sms/type/options'
 do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 2 "$u" || true)
  echo "$code $u"
done
