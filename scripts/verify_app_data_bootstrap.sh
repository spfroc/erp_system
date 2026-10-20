#!/usr/bin/env bash
set -euo pipefail
cd /home/spf/projects/erp_system/deploy
docker compose -f docker-compose.one.yml -p yzc-erp up -d --force-recreate --no-deps backend frontend

echo "==== wait backend ===="
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/health/ >/dev/null 2>&1; then
    echo "backend healthy"
    break
  fi
  sleep 1
done

echo "==== app-data size ===="
curl -sS -o /tmp/app-data.json -w 'http=%{http_code} bytes=%{size_download} time=%{time_total}\n' \
  http://127.0.0.1:8000/api/app-data/

python3 <<'PY'
import json
d = json.load(open("/tmp/app-data.json"))["data"] or {}
print("libraryContacts", len(d.get("libraryContacts") or []))
print("smsRecords", len(d.get("smsRecords") or []))
print("products", len(d.get("products") or []))
print("officialSites", len(d.get("officialSites") or []))
print("keys", len(d))
PY
