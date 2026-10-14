#!/usr/bin/env bash
set -euo pipefail
CENTER=/home/spf/projects/center
echo "=== routes ==="
grep -RIn --include='*.php' -E 'note|ShortMessage|short.message|marketing|sms' "$CENTER/routes" 2>/dev/null | head -50 || true
echo "=== controllers ==="
find "$CENTER/app" -iname '*Note*' -o -iname '*Message*' -o -iname '*Sms*' 2>/dev/null | head -40
echo "=== env (redacted) ==="
grep -E '^(APP_URL|APP_ENV|DB_|SMS|NOTE|CENTER)' "$CENTER/.env" 2>/dev/null | sed -E 's/(PASSWORD|SECRET|KEY|TOKEN)=.*/\1=***/' || true
echo "=== docker ==="
docker ps --format '{{.Names}}\t{{.Ports}}\t{{.Image}}' | head -40
echo "=== compose mentions ==="
grep -RIn --include='*.yml' --include='*.yaml' -E 'center' /home/spf/projects/docker /home/spf/projects/erp_system/deploy 2>/dev/null | head -30 || true
