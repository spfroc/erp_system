#!/bin/bash
set -euo pipefail
export MYSQL_PWD='ycsdjn1901!@#qwer'
OUT=/tmp/designated_suppliers.json
mysql -h 192.168.0.241 -P 3306 -u yizhichan yuncai --default-character-set=utf8mb4 -N -e "
SELECT JSON_ARRAYAGG(JSON_OBJECT(
  'id', id,
  'name', name,
  'account', account,
  'password', password,
  'contracts', contracts,
  'contract_number', contract_number,
  'broker', broker,
  'years_of_service', years_of_service,
  'expired_at', IFNULL(DATE_FORMAT(expired_at, '%Y-%m-%d'), CAST(NULL AS CHAR)),
  'other_account', other_account,
  'other_password', other_password,
  'domain', domain,
  'desc', \`desc\`,
  'remark', remark,
  'is_new_platform', is_new_platform,
  'created_at', IFNULL(DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s'), ''),
  'updated_at', IFNULL(DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s'), '')
))
FROM designated_suppliers;
" > "$OUT"
python3 - <<'PY'
import json
path='/tmp/designated_suppliers.json'
raw=open(path,'r',encoding='utf-8').read().strip()
data=json.loads(raw) if raw and raw!='NULL' else []
# mysql may wrap as string with NULL dates as null
open(path,'w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=2))
print('exported', len(data), 'rows to', path)
from datetime import date
today=date.today().isoformat()
alive=[r for r in data if not r.get('expired_at') or r['expired_at']>=today]
print('not_expired', len(alive))
PY
