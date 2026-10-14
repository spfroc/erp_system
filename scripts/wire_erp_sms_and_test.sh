#!/usr/bin/env bash
set -euo pipefail
cd /home/spf/projects/erp_system/deploy

# Carbon 新版本不认 PRC，center 列表序列化会炸；改成 Asia/Shanghai
sed -i "s/timezone('PRC')/timezone('Asia\/Shanghai')/g" \
  /home/spf/projects/center/app/Traits/DateFormate.php

cd /home/spf/projects/erp_system/deploy
docker compose -f docker-compose.one.yml -p yzc-erp up -d --force-recreate backend
sleep 8

echo "==== env in backend ===="
docker exec yzc-erp-backend-1 printenv | grep CENTER_SMS || true

echo "==== reachability from backend ===="
docker exec yzc-erp-backend-1 python - <<'PY'
import os, urllib.request
base=os.environ.get('CENTER_SMS_BASE_URL','')
print('CENTER_SMS_BASE_URL=', base)
url=base.rstrip('/')+'/type/options'
try:
  with urllib.request.urlopen(url, timeout=5) as r:
    print('ok', r.status, r.read()[:200])
except Exception as e:
  print('fail', e)
PY

echo "==== ERP send via django shell ===="
docker exec yzc-erp-backend-1 python manage.py shell -c "
from apps.data_store.library_sms import send_sms_via_center, center_sms_config
print('cfg', center_sms_config())
content = '【壹知产】青岛吉祥万家商贸有限公司的刘经理,咨询:青慧采关于青慧采入驻代办/代运营.联系电话:13964271978'
result, err = send_sms_via_center(mobile='18698853145', content=content, prefix='壹知产')
print('err=', err)
print('result=', result)
"

echo "==== center page (after tz fix) ===="
curl -sS 'http://127.0.0.1:8899/api/sms/page?page_size=2' | head -c 1500; echo
