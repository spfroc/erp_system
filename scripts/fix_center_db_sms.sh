#!/usr/bin/env bash
set -euo pipefail

docker exec spf.mariadb mysql -uroot -psecret -e "
CREATE DATABASE IF NOT EXISTS center CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'center'@'%' IDENTIFIED BY 'center';
GRANT ALL ON center.* TO 'center'@'%';
FLUSH PRIVILEGES;
"

CENTER=/home/spf/projects/center
cd "$CENTER"

# Point center at local MariaDB (host gateway from host process = 127.0.0.1:3306)
cp -a .env .env.bak.sms.$(date +%Y%m%d%H%M%S)
sed -i 's/^DB_HOST=.*/DB_HOST=127.0.0.1/' .env
sed -i 's/^DB_PORT=.*/DB_PORT=3306/' .env
sed -i 's/^DB_DATABASE=.*/DB_DATABASE=center/' .env
sed -i 's/^DB_USERNAME=.*/DB_USERNAME=center/' .env
sed -i 's/^DB_PASSWORD=.*/DB_PASSWORD=center/' .env

grep -E '^DB_' .env

php artisan migrate --force 2>&1 | tail -40

# Kill any previous artisan serve on 8899
pkill -f 'artisan serve.*8899' 2>/dev/null || true
sleep 1

nohup php artisan serve --host=0.0.0.0 --port=8899 >/tmp/center-sms-8899.log 2>&1 &
sleep 2

echo "==== health ===="
curl -sS -o /tmp/sms_type.json -w 'http=%{http_code}\n' http://127.0.0.1:8899/api/sms/type/options || true
head -c 400 /tmp/sms_type.json; echo
ss -lntp | grep 8899 || true
