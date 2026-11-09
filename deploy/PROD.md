# 生产部署说明（huawei_52）

给同事接手用。开发环境见仓库根目录 `README.md` 与 `deploy/README.md`。

## 环境与机器

| 环境 | 机器 / 用途 | 说明 |
|------|-------------|------|
| 开发 | `one` / 本机 | `deploy/docker-compose.dev.yml` |
| 生产 | `huawei_52` | 代码目录：`/var/www/projects/yzc-erp` |

### 生产域名

| 域名 | 指向 | 说明 |
|------|------|------|
| https://assist.qlyc.co | `yzc-erp-frontend-prod` | 管理后台；nginx 反代 `/api/` → backend |
| https://portal.qlyc.co 等 | `yzc-erp-official-web-prod` | 客户门户 / 官网（挂载 `official-web/`） |

入口为 Traefik，使用外部网络 `prod.host`。

### 密钥与配置（勿提交仓库）

- `/var/www/projects/yzc-erp/.env.prod` — Django / MySQL / Redis / 微信等
- `/var/www/projects/yzc-erp/.env.official` — 官网 Node
- 微信配置样例：`deploy/.env.wechat.mp.example`（本地 `.local` 勿提交）

数据库为华为云 RDS MySQL，连接信息在 `.env.prod` 的 `MYSQL_*`。

## 标准生产部署（推荐）

在 `huawei_52` 上：

```bash
cd /var/www/projects/yzc-erp

# 1. 同步代码到服务器（git pull / scp / rsync，按团队习惯）

# 2. 构建并滚动更新（按需指定服务）
docker compose -f deploy/docker-compose.prod.yml build backend frontend
docker compose -f deploy/docker-compose.prod.yml up -d backend frontend

# Celery 使用 backend 镜像（yzc-erp-backend:latest），backend 重建后通常一并重启
docker compose -f deploy/docker-compose.prod.yml up -d celery-worker celery-beat celery-crawler-worker

# 3. 数据库迁移
docker exec -e PYTHONPATH=/app -w /app yzc-erp-backend-prod python manage.py migrate --noinput
```

### 官网 / 门户

`official-web/` 为宿主机目录挂载。只改 html/静态时同步文件即可；改了 `server.mjs` 等再重启：

```bash
docker restart yzc-erp-official-web-prod
```

### 仅部署爬虫

```bash
docker compose -f deploy/docker-compose.prod.crawler.yml up -d --build
```

全量生产栈需已有外部网络：`docker network create prod.host`（一般由 Traefik 环境创建）。

## 热修（应急）

未重建镜像时可用 `docker cp`，但**容器重建后会丢**，正式发布仍以 compose build 为准。

### Backend

1. 把改动的 `.py` 同步到服务器  
2. `docker cp ... yzc-erp-backend-prod:/app/...`  
3. **必须** `docker restart yzc-erp-backend-prod`（gunicorn 不热更新）  
4. 有迁移再执行 `migrate`  
5. 改了异步/定时逻辑时，同步重启 `celery-worker` / `celery-beat`

### Frontend

1. 在 `frontend/` 执行 `npm run build`  
2. 拷贝产物进容器：

```bash
docker cp frontend/dist/. yzc-erp-frontend-prod:/usr/share/nginx/html/
```

3. **立刻修正权限**（否则会出现白页，nginx `Permission denied`）：

```bash
docker exec yzc-erp-frontend-prod sh -c '
  find /usr/share/nginx/html -type d -exec chmod 755 {} \;
  find /usr/share/nginx/html -type f -exec chmod 644 {} \;
'
```

## 主要容器

| 容器 | 作用 |
|------|------|
| `yzc-erp-frontend-prod` | 管理后台静态站 + `/api` 反代 |
| `yzc-erp-backend-prod` | Django / Gunicorn |
| `yzc-erp-official-web-prod` | 官网 + 门户 |
| `yzc-erp-celery-worker-prod` | 异步任务 |
| `yzc-erp-celery-beat-prod` | 定时任务（含公告日汇总推送等） |
| `yzc-erp-celery-crawler-prod` | 爬虫队列 |
| `yzc-erp-notice-crawler-prod` | 公告抓取常驻 |
| `yzc-erp-ocr-prod` | OCR |

Compose 定义见 `deploy/docker-compose.prod.yml`。

## 注意点

1. 生产改后端必须 `restart`，只 `docker cp` 不够。  
2. 前端热更后必须 `chmod`，否则白页。  
3. 迁移出现多个 leaf 时先检查 `apps/data_store/migrations`，需要 merge，不要硬拷冲突的 `004x`。  
4. 微信：`WECHAT_MP_*` 在 `.env.prod`；「网页授权域名」与「JS 接口安全域名」不是一回事；OAuth 回调为 `/api/wechat/mp/oauth/callback/`。  
5. 正式上线优先：**同步代码 → compose build/up → migrate → 验证域名**；`docker cp` 仅应急。

## 开发环境（对照）

仓库根目录：

```bash
docker compose -f deploy/docker-compose.dev.yml up --build
```

- 前端：http://localhost:18082  
- 后端健康检查：http://localhost:18080/api/health/  
