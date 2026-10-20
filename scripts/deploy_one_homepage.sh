#!/usr/bin/env bash
set -euo pipefail
cd /home/spf/projects/erp_system

git fetch codeup
git stash push -u -m "auto-before-deploy-homepage" 2>/dev/null || true
git checkout codex/formal-project-scaffold 2>/dev/null || true
git reset --hard codeup/main
git log -3 --oneline

echo "==== recreate services (no rebuild, images already local) ===="
cd deploy
# Avoid docker hub pulls; code is volume-mounted.
docker compose -f docker-compose.one.yml -p yzc-erp up -d --force-recreate --no-deps backend frontend official-web

echo "==== wait backend ===="
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/health/ >/dev/null 2>&1; then
    echo "backend healthy"
    break
  fi
  sleep 2
done

echo "==== ensure sites / smoke ===="
docker exec yzc-erp-backend-1 python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from apps.data_store.official_sites import ensure_default_official_sites, find_official_site_by_host, public_home_config
ensure_default_official_sites()
for host in ("www.qlyc.co", "www.yizhichan.co", "www.qinghuicai.cn"):
    site = find_official_site_by_host(host)
    cfg = public_home_config(site.data if site else {})
    print(host, "->", getattr(site, "key", None), "hotline=", (cfg.get("contact") or {}).get("hotline"), "platforms=", len((cfg.get("footer") or {}).get("platforms") or []))
PY

echo "==== public API ===="
curl -sS "http://127.0.0.1:8000/api/public/official-site/?host=www.qlyc.co" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('qlyc', d['site']['key'], 'homeConfig', bool(d.get('homeConfig')), 'domains', d.get('homeConfig',{}).get('domains'))"
curl -sS "http://127.0.0.1:8000/api/public/official-site/?host=www.yizhichan.co" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('yizhichan', d['site']['key'])"
curl -sS "http://127.0.0.1:8000/api/public/official-site/?host=www.qinghuicai.cn" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('qinghuicai', d['site']['key'], 'keywords', bool(d.get('homeConfig',{}).get('footer',{}).get('keywords')))"

echo "==== official-web inject smoke ===="
curl -sS -H "Host: www.qlyc.co" "http://127.0.0.1:18083/" | grep -c "__OFFICIAL_HOME_CONFIG__" || true
curl -sS -H "Host: www.qinghuicai.cn" "http://127.0.0.1:18083/" | grep -c "__OFFICIAL_HOME_CONFIG__" || true

docker ps --format '{{.Names}}\t{{.Status}}' | grep yzc-erp
echo DONE
