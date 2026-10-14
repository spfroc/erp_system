#!/usr/bin/env bash
set -euo pipefail
cd /home/spf/projects/center
php artisan config:clear
php artisan cache:clear || true
pkill -f 'artisan serve.*8899' 2>/dev/null || true
sleep 1
nohup php artisan serve --host=0.0.0.0 --port=8899 >/tmp/center-sms-8899.log 2>&1 &
sleep 2
echo "DB:"
grep -E '^DB_' .env
echo "==== type/options ===="
curl -sS -o /tmp/sms_type.json -w 'http=%{http_code}\n' http://127.0.0.1:8899/api/sms/type/options
head -c 800 /tmp/sms_type.json; echo
echo "==== php db test ===="
php -r '
require "vendor/autoload.php";
$app = require "bootstrap/app.php";
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();
echo "db=".DB::connection()->getDatabaseName().PHP_EOL;
echo "count=".DB::table("short_messages")->count().PHP_EOL;
'
