# Database metadata and migrations

## Primary `Base`

Application tables use a single declarative base: `app.core.database.Base`.

`init_db()` and Alembic both target `Base.metadata` for this base.

## Legacy secondary bases

`app.models.clinical` and `app.models.monitoring` define their own `declarative_base()` instances. Those models are **not** included in `init_db()` unless refactored to subclass `app.core.database.Base`.

## Migrations

- **Development:** `create_all` on startup (`init_db`) is acceptable.
- **Production:** use Alembic — from `backend/`:

  ```bash
  # PowerShell example (SQLite dev file)
  $env:DATABASE_URL="sqlite:///./dev.db"
  python -m alembic upgrade head
  ```

  Configure `DATABASE_URL` in the environment before running.

## Alembic layout

- `alembic.ini` — entrypoint
- `alembic/env.py` — imports `Base` from `app.core.database`
- `alembic/versions/` — revision scripts
