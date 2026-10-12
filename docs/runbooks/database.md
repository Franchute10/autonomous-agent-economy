# Database runbook

## Configure a local/test database

Set a PostgreSQL DSN without committing it:

```powershell
$env:AEOS_DATABASE_URL = "postgresql+psycopg://<user>:<password>@<host>:5432/<database>"
```

`DATABASE_URL` is accepted as a compatibility fallback. Run the initial schema migration:

```powershell
\.venv\Scripts\alembic.exe upgrade head
```

To inspect generated SQL without connecting:

```powershell
\.venv\Scripts\alembic.exe upgrade head --sql
```

For a disposable empty test database, verify downgrade and clean re-upgrade:

```powershell
\.venv\Scripts\alembic.exe downgrade base
\.venv\Scripts\alembic.exe upgrade head
```

## Validation

```powershell
$env:PYTHONPATH = "src"
\.venv\Scripts\python.exe -m pytest
\.venv\Scripts\python.exe -m mypy src tests
\.venv\Scripts\ruff.exe check .
\.venv\Scripts\ruff.exe format --check .
git diff --check
```

PostgreSQL-specific integration validation requires the configured DSN and must not silently fall back to SQLite. Keep skipped integration tests visible in the test output.
