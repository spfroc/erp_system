# Deploy

Development stack:

```bash
docker compose -f deploy/docker-compose.dev.yml up --build
```

Services:

- `frontend` - Vite development server on host port `18082`.
- `backend` - Django development server on host port `18080` (container `8000`).
- `ocr-service` - FastAPI development server on host port `18081` (container `8100`).
- `mysql` - MySQL 8.0.21 on host port `13306` (container `3306`).
- `redis` - Redis on host port `16379` (container `6379`).
- `minio` - Object storage API on host `19000`, console on `19001`.
- `notice-crawler` - 公告/供应商抓取。启动时执行一轮，之后每 3 小时（`CRAWL_INTERVAL_SECONDS=10800`）再执行。开发环境数据库由 compose 覆盖为内部 `mysql`；账号写在 `notice_crawler/.env`（`SD_ACCOUNT` / `SD_PASSWORD`、京东 `JD_CONTRACT_NUM` 泉易采、`JD_QHC_CONTRACT_NUM` 青慧采）。生产环境读取 `.env.prod` 的 `MYSQL_*` 和 `CRAWL_*`，不读取带本机地址的 `notice_crawler/.env`。

## Huawei Cloud RDS MySQL

Production uses the same Django MySQL backend as development. Configure the backend with:

```env
MYSQL_DATABASE=yicai_erp
MYSQL_USER=<rds-user>
MYSQL_PASSWORD=<rds-password>
MYSQL_HOST=<rds-private-endpoint>
MYSQL_PORT=3306
MYSQL_CONN_MAX_AGE=60
MYSQL_SSL_CA=/run/secrets/rds-ca.pem
```

Create the RDS database with the `utf8mb4` character set. Mount Huawei Cloud's CA certificate into the backend container when certificate verification is enabled. Do not place production credentials or certificates in the repository.
