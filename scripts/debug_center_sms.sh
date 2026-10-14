#!/usr/bin/env bash
set -euo pipefail
cd /home/spf/projects/center

echo "==== listeners 8899 ===="
ss -lntp | grep 8899 || true
ps aux | grep -E 'artisan serve|8899' | grep -v grep || true

echo "==== kill all serve ===="
pkill -9 -f 'artisan serve' 2>/dev/null || true
fuser -k 8899/tcp 2>/dev/null || true
sleep 1
ss -lntp | grep 8899 || echo '8899 free'

echo "==== config ===="
ls -la bootstrap/cache/ || true
php -r '
require "vendor/autoload.php";
$app = require "bootstrap/app.php";
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();
echo "host=".config("database.connections.mysql.host").PHP_EOL;
echo "port=".config("database.connections.mysql.port").PHP_EOL;
echo "db=".config("database.connections.mysql.database").PHP_EOL;
try {
  DB::select("select 1 as ok");
  echo "query_ok\n";
} catch (Throwable $e) {
  echo "query_fail ".$e->getMessage().PHP_EOL;
}
'

echo "==== start serve ===="
nohup php artisan serve --host=0.0.0.0 --port=8899 >/tmp/center-sms-8899.log 2>&1 &
echo "pid=$!"
sleep 2
curl -sS -o /tmp/sms_type.json -w 'http=%{http_code}\n' http://127.0.0.1:8899/api/sms/type/options
# Extract exception from HTML comment
python3 - <<'PY'
import re
t=open('/tmp/sms_type.json','r',errors='replace').read()
m=re.search(r'<!--\s*(.*?)\s*#', t, re.S)
print((m.group(1) if m else t)[:500])
PY

echo "==== log tail ===="
tail -30 /tmp/center-sms-8899.log

# Also try connecting via 127.0.0.1:3306 from host
echo "==== tcp 3306 ===="
python3 - <<'PY'
import socket
for host in ['127.0.0.1','localhost']:
  s=socket.socket(); s.settimeout(2)
  try:
    s.connect((host,3306)); print(host, 'ok')
  except Exception as e:
    print(host, e)
  finally:
    s.close()
PY
