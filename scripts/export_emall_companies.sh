#!/bin/bash
set -euo pipefail
export MYSQL_PWD='ycsdjn1901!@#qwer'
OUT=/tmp/emall_companies.json

mysql -h 192.168.0.241 -P 3306 -u yizhichan yuncai --default-character-set=utf8mb4 -N -e "
SELECT JSON_ARRAYAGG(j.obj) FROM (
  SELECT JSON_OBJECT(
    'id', c.id,
    'name', c.name,
    'tel_number', c.tel_number,
    'contact_mobile', c.contact_mobile,
    'email', c.email,
    'license_code', c.license_code,
    'legal_person', c.legal_person,
    'province', c.province,
    'city', c.city,
    'address', c.address,
    'domain', c.domain,
    'icp_number', c.icp_number,
    'founded_at', IFNULL(DATE_FORMAT(c.founded_at, '%Y-%m-%d'), CAST(NULL AS CHAR)),
    'trusteeship_finish_date', IFNULL(DATE_FORMAT(c.trusteeship_finish_date, '%Y-%m-%d'), CAST(NULL AS CHAR)),
    'is_new_platform', c.is_new_platform,
    'status', c.status,
    'created_at', IFNULL(DATE_FORMAT(c.created_at, '%Y-%m-%dT%H:%i:%s'), ''),
    'updated_at', IFNULL(DATE_FORMAT(c.updated_at, '%Y-%m-%dT%H:%i:%s'), ''),
    'mall_account', pma.account,
    'mall_password', pma.password,
    'mall_account_id', pma.id
  ) AS obj
  FROM companies c
  LEFT JOIN platform_mall_accounts pma
    ON pma.company_id = c.id AND pma.deleted_at IS NULL AND pma.type = 1
  WHERE c.deleted_at IS NULL
) j;
" > "$OUT.tmp"

python3 - <<'PY'
import json
from datetime import date
raw=open('/tmp/emall_companies.json.tmp','r',encoding='utf-8').read().strip()
data=json.loads(raw) if raw and raw!='NULL' else []
today=date.today().isoformat()
alive=[r for r in data if r.get('founded_at') and r['founded_at']>=today]
alive_with_acc=[r for r in alive if (r.get('mall_account') or '').strip() not in ('','-')]
huatang=[r for r in data if '华唐' in (r.get('name') or '')]
print('companies', len(data))
print('not_expired', len(alive))
print('not_expired_with_mall_account', len(alive_with_acc))
print('huatang', huatang)
open('/tmp/emall_companies.json','w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
print('wrote /tmp/emall_companies.json')
PY
