# Scripts

Repeatable data import and maintenance scripts belong here.

## Legacy Excel Import

Generate normalized initialization JSON from the current Excel workbooks:

```bash
python scripts/import_init_data.py \
  --input-dir "当前使用的表格数据" \
  --output "tmp/import/initial_data.json" \
  --summary
```

The generated JSON keeps source rows for audit and can be loaded into PostgreSQL
with the Django seed command:

```bash
cd backend
python manage.py migrate
python manage.py seed_database --file ../tmp/import/initial_data.json --force
```

## Database Seed

Seed empty database with base admin/user/options:

```bash
cd backend
python manage.py migrate
python manage.py seed_database
```

Migrate an existing legacy `app_state.default` JSON snapshot into normalized
business tables:

```bash
cd backend
python manage.py migrate
python manage.py seed_database --from-app-state --force
```

The frontend now treats PostgreSQL as the authoritative data store through
`/api/app-data/`. Browser IndexedDB is only read once for migration when it
contains more records than the server, then it is cleared.
