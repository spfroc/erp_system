#!/usr/bin/env bash
set -euo pipefail
CENTER=/home/spf/projects/center
cd "$CENTER"

# Load DB settings from .env without printing secrets
eval "$(python3 - <<'PY'
from pathlib import Path
cfg={}
for line in Path('/home/spf/projects/center/.env').read_text().splitlines():
    line=line.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k,v=line.split('=',1)
    cfg[k.strip()]=v.strip().strip('"').strip("'")
print(f"export DB_HOST={cfg.get('DB_HOST','')!r}")
print(f"export DB_PORT={cfg.get('DB_PORT','3306')!r}")
print(f"export DB_DATABASE={cfg.get('DB_DATABASE','')!r}")
print(f"export DB_USERNAME={cfg.get('DB_USERNAME','')!r}")
print(f"export DB_PASSWORD={cfg.get('DB_PASSWORD','')!r}")
print(f"export APP_KEY={cfg.get('APP_KEY','')!r}")
PY
)"

echo "DB_HOST=$DB_HOST DB_PORT=$DB_PORT DB_DATABASE=$DB_DATABASE"

python3 - <<'PY'
import os, socket
host=os.environ['DB_HOST']; port=int(os.environ['DB_PORT'])
s=socket.socket(); s.settimeout(3)
try:
    s.connect((host, port)); print('db_tcp_ok')
except Exception as e:
    print('db_tcp_fail', e)
finally:
    s.close()
PY

# Prefer local MariaDB if configured remote port is down
if ! timeout 2 bash -c ">/dev/tcp/$DB_HOST/$DB_PORT" 2>/dev/null; then
  echo "Configured DB port unreachable; checking local MariaDB for center db..."
  docker exec spf.mariadb mysql -uroot -proot -e "SHOW DATABASES LIKE 'center';" 2>/dev/null || \
  docker exec spf.mariadb mysql -uroot -e "SHOW DATABASES LIKE 'center';" 2>/dev/null || true
fi

# Kill old center serve if any
pkill -f 'artisan (serve|octane:start).*8899' 2>/dev/null || true
mkdir -p /home/spf/projects/center/storage/logs

# Start Laravel HTTP server for SMS API (no need for full octane for ERP proxy)
nohup php artisan serve --host=0.0.0.0 --port=8899 > /home/spf/projects/center/storage/logs/serve-8899.log 2>&1 &
echo "pid=$!"
sleep 2
curl -sS -o /tmp/center_type.json -w '%{http_code}\n' http://127.0.0.1:8899/api/sms/type/options || true
head -c 300 /tmp/center_type.json; echo
tail -20 /home/spf/projects/center/storage/logs/serve-8899.log || true
