# How to Run the Cancer Biomarker Identifier

This guide walks through running the Cancer Biomarker Identifier (CBI) on your own machine, from zero to a working browser session. Pick one of the two paths:

- **Path A — Docker Compose (recommended).** One command brings up the stack in [`docker-compose.yml`](docker-compose.yml): PostgreSQL, Redis, a one-shot **migrate** job, the backend API, **Celery worker**, **Celery beat** (scheduling), **Flower** (Celery UI on port 5555), and the **frontend** on port 80 (the frontend image serves the built React app). Best for demos, grading, and first-time users.
- **Path B — Manual / developer setup.** Run the backend and frontend directly on your host (plus a small Compose stack for Postgres + Redis). Best when you want hot-reload and to step through code.

If you just want to see the app working, follow **Path A**.

---

## 0. Prerequisites

Install these once before either path:

| Tool | Minimum version | Check with |
|------|------------------|------------|
| Docker Desktop / Docker Engine | 20.10+ | `docker --version` |
| Docker Compose plugin | v2+ | `docker compose version` |
| Git | any recent | `git --version` |

For **Path B** (manual) you additionally need:

| Tool | Minimum version | Check with |
|------|------------------|------------|
| Python | 3.11 (3.9+ works, 3.11 tested) | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

**Hardware:** 8 GB RAM minimum, 16 GB recommended. 20 GB free disk for images and caches.

**Platforms:** Windows 10/11, macOS 12+, Ubuntu 22.04+. Commands below use Bash syntax; on Windows use PowerShell equivalents (or run from **Git Bash**). A PowerShell starter script, [`START_SERVICES.ps1`](START_SERVICES.ps1), is included for Windows users.

---

## Path A — Run with Docker Compose (recommended)

### Step 1. Get the code

```bash
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier
```

### Step 2. Create a local environment file

The repository ships with `env.template` (full reference) and `production.env.example` (deployment-oriented). For a quick local run you can copy the production example and relax a couple of settings:

```bash
cp production.env.example .env
```

Open `.env` in an editor and make sure at minimum:

```env
BIOMARKER_ENV=development
DEBUG=True
SECRET_KEY=change-me-to-a-long-random-string
ALLOWED_ORIGINS=http://localhost:3000,http://localhost
```

Never commit a real secret. `.env` is already in `.gitignore`.

### Step 3. Build and start the stack

```bash
docker compose up -d --build
```

On the first run this pulls the Postgres, Redis, and Nginx images and builds the backend and frontend images. Allow 5–15 minutes depending on your connection.

### Step 4. Wait for services to become healthy

```bash
docker compose ps
```

You should see `healthy` for `postgres` and `redis`, and `running` for `migrate` → `backend` → `celery-worker` → `frontend`/`nginx`. The `migrate` service runs Alembic migrations once and then exits — that is expected.

### Step 5. Open the app

| URL | What it is |
|-----|------------|
| <http://localhost> | React frontend (served by Nginx) |
| <http://localhost:8000/docs> | FastAPI Swagger UI |
| <http://localhost:8000/redoc> | ReDoc API reference |
| <http://localhost:8000/api/v1/system/health> | Detailed system health (JSON) |
| <http://localhost:8000/api/status> | Short application status and useful path pointers |
| <http://localhost:5555> | Flower (Celery monitor), when the `flower` service is up |

### Step 6. Create your first account

1. Click **Register** on the login page.
2. Create a user (email, password, display name).
3. Log in. You land on the **Dashboard**.

### Step 7. Run a biomarker analysis end to end

1. Go to **Data Upload**.
2. Upload an expression matrix (`.csv` / `.tsv` — genes as rows, samples as columns) and a labels file (sample ID → phenotype).
   - For a quick demo, generate synthetic data: `python backend/scripts/setup_real_data.py --generate-sample` (from the repo root; see notes in [`docs/QUICK_START_GUIDE.md`](docs/QUICK_START_GUIDE.md)).
   - For real public data, see [`data_collection/README.md`](data_collection/README.md). Run `python -m data_collection.preflight` first — it tells you which sources are ready and which still need API tokens (OncoKB, COSMIC, optional `NCBI_API_KEY`).
3. Pick normalization (e.g. log2), a statistical test (Welch t-test), and one or more ML models (Random Forest is a good default).
4. Click **Start Analysis**. The **Pipeline Monitoring** page streams progress over WebSockets.
5. When it finishes, open **Results** for the run to view ranked biomarkers, volcano / bar charts, and tables.
6. Click **Reports** → **Generate** to produce an HTML or PDF report.

### Step 8. Stop the stack

```bash
# Stop, keep volumes (fast restart next time)
docker compose down

# Or wipe volumes too (fresh DB/Redis on next start)
docker compose down -v
```

---

## Path B — Manual / developer setup

Use this when you want hot-reload on the backend and frontend.

### Step 1. Start just Postgres + Redis in Docker

```bash
docker compose up -d postgres redis
```

### Step 2. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env                # edit if needed; SECRET_KEY etc.

# Apply DB schema
alembic upgrade head

# Start the API with hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Leave that terminal running. The API is now at `http://localhost:8000`.

### Step 3. Celery worker (analysis runs)

Open a **second terminal**:

```bash
cd backend
source .venv/bin/activate          # same venv as step 2
celery -A app.services.celery_service:celery_app worker --loglevel=info
```

Background jobs (biomarker pipeline, report generation) run here.

### Step 4. Frontend (React)

Open a **third terminal**:

```bash
cd frontend
npm ci                              # reproducible install; use `npm install` if no lockfile
npm start
```

This opens <http://localhost:3000> automatically. The dev server proxies `/api` calls to the backend at `:8000`.

### Step 5. (Optional) Shortcuts via the `Makefile`

From the repo root:

```bash
make install-backend       # pip install -r backend/requirements.txt
make install-frontend      # npm ci in frontend/
make backend               # uvicorn backend, hot reload
make frontend              # npm start
make test                  # pytest + frontend Jest (watch off)
make lint                  # Black, flake8, ESLint
```

---

## Running the tests

```bash
# Backend — full suite with coverage (80% gate)
cd backend
pytest --cov=app --cov-report=html --cov-fail-under=80
# Open htmlcov/index.html to inspect coverage

# Backend — unit tests only (fast)
pytest tests/unit/ -v

# Backend — integration tests (needs Postgres + Redis running)
pytest tests/integration/ -v

# End-to-end (requires a live server; set flag)
E2E_REQUIRE_LIVE_SERVER=1 pytest -m e2e

# Frontend
cd frontend
npm test -- --watchAll=false --coverage
```

More detail lives in [`TESTING_GUIDE.md`](TESTING_GUIDE.md) and [`docs/CONTRIBUTOR_TESTING_GUIDE.md`](docs/CONTRIBUTOR_TESTING_GUIDE.md).

---

## Windows quick-start (PowerShell)

1. Ensure Docker Desktop is running.
2. From the repo root, build and start the stack:

   ```powershell
   docker compose up -d --build
   ```

3. (Optional) Run `.\START_SERVICES.ps1` to print `docker compose ps`, probe `http://localhost:8000/health` and `/api/status`, check the UI on port 80, and verify R/DESeq2 inside the `backend` container. The script also runs `docker compose up -d` again, which is harmless if services are already up.

---

## Common problems and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker compose up` hangs on `migrate` | DB not healthy yet | `docker compose logs postgres` — wait for `database system is ready to accept connections`, then retry |
| Backend container restarts in a loop | Default `SECRET_KEY` with `BIOMARKER_ENV=production` | Set a real `SECRET_KEY` in `.env`, or set `BIOMARKER_ENV=development` for local runs |
| `403 Forbidden` on `/api/...` from the frontend | Origin not allow-listed | Add the frontend URL to `ALLOWED_ORIGINS` in `.env`, e.g. `http://localhost:3000,http://localhost` |
| `429 Too Many Requests` during tests | SlowAPI rate limits | Set `BIOMARKER_DISABLE_RATE_LIMIT=1` in the environment |
| Celery worker keeps crashing on startup | Redis not reachable | Confirm `redis` container is `healthy`; check `REDIS_URL` matches the Compose service name (`redis://redis:6379/0`) |
| `DESeq2` / `edgeR` unavailable | rpy2 + R not installed | These are optional. See [`R_INSTALLATION_NOTES.md`](R_INSTALLATION_NOTES.md); leave `ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2=False` to skip |
| Frontend shows blank page in production build | Wrong `REACT_APP_API_URL` | Rebuild the frontend image after editing it, or set it to `http://localhost:8000/api` for local |
| Port 80, 3000, 8000, 5433, or 6379 already in use | Another service is listening | Edit the `ports:` mapping in `docker-compose.yml` (e.g. `"8001:8000"`) |

For deeper troubleshooting and production topics (Kubernetes, AWS Lambda / SAM, TLS, multi-region) see [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md).

---

## Where to go next

- [`README.md`](README.md) — feature overview and configuration reference.
- [`docs/QUICK_START_GUIDE.md`](docs/QUICK_START_GUIDE.md) — scenario-based walkthrough of a first analysis.
- [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) — REST endpoints and payloads.
- [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md) — product themes and what is implemented in this repo.
