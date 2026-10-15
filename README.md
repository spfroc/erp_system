# Yicai ERP

Formal development workspace for the Yicai supply-chain management system.

## Projects

- `frontend/` - React + TypeScript client.
- `backend/` - Django REST business API.
- `ocr-service/` - FastAPI service for OCR workloads.
- `deploy/` - Local and production deployment assets.
- `scripts/` - Repeatable import and maintenance scripts.

## Development Order

1. Backend domain models and API contracts.
2. Frontend module split from the prototype.
3. Excel import scripts for initial data.
4. OCR service integration through backend APIs.
5. Docker-based development environment.

## Data Initialization

Legacy Excel workbooks can be normalized into JSON before database import:

```bash
python scripts/import_init_data.py \
  --input-dir "当前使用的表格数据" \
  --output "tmp/import/initial_data.json" \
  --summary
```

The generated JSON is intentionally not committed because it contains business data.

## Development Environment

From the repository root:

```bash
docker compose -f deploy/docker-compose.dev.yml up --build
```

Default services (host ports avoid common conflicts like 3306/6379/8000):

- Frontend: http://localhost:18082
- Backend health: http://localhost:18080/api/health/
- OCR health: http://localhost:18081/api/health
- MinIO console: http://localhost:19001
- MySQL: `localhost:13306`
- Redis: `localhost:16379`

Frontend dev API targets are configured in `frontend/.env.development` (`VITE_BACKEND_PORT=18080`, `VITE_OCR_PORT=18081`).

The development database is MySQL 8.0.21 with `utf8mb4`, matching the production Huawei Cloud RDS instance.

On the `comp` development machine, use:

- Frontend: http://comp:18082
- Backend health: http://comp:18080/api/health/
- OCR health: http://comp:18081/api/health
