# Deploy

Development stack:

```bash
docker compose -f deploy/docker-compose.dev.yml up --build
```

Services:

- `frontend` - Vite development server on host port `18082`.
- `backend` - Django development server on port `8000`.
- `ocr-service` - FastAPI development server on port `8100`.
- `mysql` - MySQL 8.0.21 on port `3306`, matching the production RDS major/minor version.
- `redis` - Redis on port `6379`.
- `minio` - Object storage API on `9000`, console on `9001`.

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
