# Cancer Biomarker Identifier

A comprehensive web application for identifying and analyzing cancer biomarkers from multi-omics data using advanced machine learning and statistical methods.

## 🚀 Features

### Core Functionality
- **Multi-omics Data Integration**: Support for gene expression, clinical, and mutation data
- **Advanced Statistical Analysis**: Differential expression analysis, survival analysis, and pathway enrichment
- **Machine Learning Pipeline**: Automated feature selection and biomarker identification
- **Real-time Progress Tracking**: WebSocket-based real-time updates during analysis
- **Interactive Visualizations**: Dynamic charts and plots using Recharts
- **Clinical Annotation**: Integration with COSMIC, ClinVar, and OncoKB databases
- **Comprehensive Reporting**: HTML and PDF report generation

### Quality Assurance
- **Linting & tests**: Black, flake8, and mypy for backend; Jest and Lighthouse for frontend
- **Real data testing**: Run `python backend/scripts/setup_real_data.py --generate-sample` for local/CI tests

### Technical Features
- **Modern Web Stack**: React frontend with FastAPI backend
- **Scalable Architecture**: Microservices with Docker and Kubernetes support
- **Performance Optimization**: Redis caching and Celery background processing
- **Security**: JWT-based authentication and authorization
- **Monitoring**: Prometheus and Grafana integration
- **Testing**: Comprehensive test suite with unit, integration, and E2E tests

## 📋 Table of Contents

- [How to Run (step-by-step)](#how-to-run-step-by-step)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## 🧭 How to Run (step-by-step)

**New to the project? Start here:** [`HOW_TO_RUN.md`](HOW_TO_RUN.md) is a dedicated, numbered walkthrough that takes you from an empty machine to a running app in under 15 minutes. It covers:

- **Path A — Docker Compose** (recommended): one command brings up Postgres, Redis, migrations, the FastAPI backend, Celery worker and beat, Flower, and the frontend on port 80 (see `docker-compose.yml`).
- **Path B — Manual / developer setup**: run the backend and frontend directly on the host with hot-reload (plus a small Compose stack for Postgres and Redis).
- Windows PowerShell quick-start using [`START_SERVICES.ps1`](START_SERVICES.ps1).
- A troubleshooting table for the common first-run problems (rate limits, `SECRET_KEY`, `ALLOWED_ORIGINS`, port conflicts, optional R/rpy2, etc.).

The rest of this README is a **reference**: features, configuration variables, project layout, testing, deployment, etc. Reach for it when you already have the app running and want to go deeper.

## 🏃‍♂️ Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier

# Create a local .env (see HOW_TO_RUN.md step 2 for the minimum values)
cp production.env.example .env

# Build and start all services: Postgres, Redis, migrate (one-shot), backend,
# Celery worker, Celery beat, Flower, frontend (see docker-compose.yml)
docker compose up -d --build

# Check service health
docker compose ps

# Open the app
# Frontend:   http://localhost
# Swagger UI: http://localhost:8000/docs
# App status: http://localhost:8000/api/status
# System health (JSON): http://localhost:8000/api/v1/system/health
```

> Using Docker Compose v1? The legacy `docker-compose` command still works in place of `docker compose`.

### Manual Installation

```bash
# Start just Postgres + Redis in Docker
docker compose up -d postgres redis

# Backend setup (terminal 1)
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                # create local secrets file (never commit .env)
alembic upgrade head                # apply DB schema
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery worker (terminal 2)
cd backend
source .venv/bin/activate
celery -A app.services.celery_service:celery_app worker --loglevel=info

# Frontend (terminal 3)
cd frontend
npm ci
npm start
```

For the full narrative version of either path see [`HOW_TO_RUN.md`](HOW_TO_RUN.md).

## 🔧 Installation

### Prerequisites

- **Docker & Docker Compose (V2 plugin)**: 20.10+ (`docker compose` command)
- **Python**: 3.11+ (what CI and the backend `Dockerfile` use; 3.9+ may work on the host with care)
- **Node.js**: 18+
- **PostgreSQL**: 13+
- **Redis**: 6+

### System Requirements

- **Memory**: 8GB RAM minimum (16GB recommended)
- **Storage**: 50GB free space
- **CPU**: 4+ cores recommended

### Step-by-Step Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/jbInf-08/biomarker_identifier.git
   cd biomarker_identifier
   ```

2. **Set up environment variables**
   ```bash
   # Docker / production-oriented values (do not commit real secrets)
   cp production.env.example .env.prod
   # Edit .env.prod with your configuration

   # Local API (when running uvicorn from backend/) — optional if you rely on defaults
   cp backend/.env.example backend/.env
   # Edit backend/.env; keep .env out of version control
   ```

3. **Start the application**
   ```bash
   docker compose up -d --build
   ```

4. **Verify installation**
   ```bash
   # Check all services are running
   docker compose ps

   # Access the application
   open http://localhost                     # frontend (Nginx)
   open http://localhost:8000/docs           # FastAPI Swagger UI
   curl  http://localhost:8000/health/ready
   curl  http://localhost:8000/api/v1/system/health
   ```

For a fully annotated first-run walkthrough (including how to create an account and run your first analysis end-to-end), see [`HOW_TO_RUN.md`](HOW_TO_RUN.md).

## ⚙️ Configuration

### Environment files (secrets)

- **Local API**: Copy `backend/.env.example` to `backend/.env` and edit. Start the backend from the `backend/` directory (`uvicorn app.main:app`) so Pydantic loads that `.env` file. **Do not commit** `.env` (it is listed in `.gitignore`).
- **Production / deployment**: Use `production.env.example` as a starting point (e.g. copy to `.env.prod` on the server). Adjust URLs, passwords, and keys for your environment.
- **Root `env.template`**: Large reference list of possible operational variables. The FastAPI app only reads variables defined on `app.core.config.Settings` in `backend/app/core/config.py`, plus **`BIOMARKER_DISABLE_RATE_LIMIT`** (read directly by the SlowAPI middleware). Keys that exist only in `env.template` are ignored unless you wire them elsewhere (Compose, Kubernetes, etc.).

### Environment variables (backend `Settings`)

`ALLOWED_ORIGINS` accepts a **comma-separated** string in `.env` (for example `http://localhost:3000,http://localhost:8000`) or a **JSON array** (for example `["http://localhost:3000","http://localhost:8000"]`). With `BIOMARKER_ENV=production`, wildcard origins (`*`) are rejected. If `DEBUG` is false and `SECRET_KEY` is still the built-in default placeholder, the app refuses to start (except under tests).

| Area | Variables |
|------|-----------|
| App / API | `APP_NAME`, `APP_VERSION`, `DEBUG`, `API_V1_STR`, `BASE_URL`, `ALLOWED_ORIGINS` |
| Database | `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| Redis | `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` |
| Data layout | `DATA_DIR`, `UPLOAD_DIR`, `PROCESSED_DIR`, `REPORTS_DIR`, `EXPORT_DIR`, `VISUALIZATION_DIR`, `MODELS_DIR`, `STATIC_DIR`, `TEMP_DIR` |
| Security / auth | `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM` |
| External APIs | `COSMIC_API_KEY`, `ONCOKB_API_KEY`, `PUBMED_API_KEY`, `OPENAI_API_KEY`, `HUGGINGFACE_HUB_TOKEN` |
| PubMed (optional) | `ENABLE_PUBMED_GROUNDING`, `NCBI_EMAIL`, `NCBI_TOOL`, `NCBI_API_KEY` |
| Federated | `FEDERATED_REQUIRE_API_KEY` |
| Rate limiting | `RATE_LIMIT_ENABLED` (reserved on `Settings`; **per-request limits** are toggled with `BIOMARKER_DISABLE_RATE_LIMIT`: set to `1`, `true`, or `yes` to disable SlowAPI limits) |
| Production checks | `BIOMARKER_ENV`, `STRICT_CONFIG_CHECK` |
| Docker / monitoring | `BIOMARKER_PROMETHEUS_ENABLED`, `BIOMARKER_GRAFANA_ENABLED`, `BIOMARKER_DOCKER_USERNAME` |
| Logging | `LOG_LEVEL`, `LOG_FILE`, `LOG_JSON` |
| Health | `HEALTH_CHECK_CELERY` (adds Celery inspect latency when true) |
| CGAS integration | `CGAS_BASE_URL`, `CGAS_MUTATION_API`, `CGAS_PATHWAY_API` |
| Email (optional) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` |
| Reports | `REPORT_TEMPLATE_DIR`, `REPORT_OUTPUT_FORMATS` (use a JSON array string in env, e.g. `["html","pdf"]`) |

### Analysis and ML parameters

These map to the same names in `Settings` (defaults suit most installs):

```bash
# Analysis limits
MAX_FILE_SIZE=104857600   # 100MB (default in code)
MAX_SAMPLES=1000
MAX_GENES=50000
DEFAULT_RANDOM_SEED=42

# Machine learning
CV_FOLDS=5
STABILITY_BOOTSTRAPS=100
PERMUTATION_TESTS=100
FEATURE_SELECTION_THRESHOLD=0.6

# Preprocessing / statistics
MIN_VARIANCE_GENES=10000
MIN_EXPRESSION_THRESHOLD=1.0
MAX_MISSING_RATE=0.1
BATCH_CORRECTION_METHOD=combat
FDR_METHOD=benjamini_hochberg
EFFECT_SIZE_METRIC=cohens_d
```

## 📖 Usage

### 1. User Registration and Login

- Register a new account or login with existing credentials
- Admin users can manage other users and system settings

### 2. Data Upload

- Upload gene expression data (CSV/TSV format)
- Upload clinical data with sample annotations
- Configure analysis parameters

### 3. Analysis Execution

- Start biomarker analysis with real-time progress tracking
- Monitor analysis status and results
- View intermediate results and logs

### 4. Results and Visualization

- Explore identified biomarkers with interactive charts
- Filter and sort results by statistical significance
- Export results in various formats

### 5. Clinical Annotation

- Annotate biomarkers with clinical databases
- View clinical relevance scores
- Access literature and database links

### 6. Report Generation

- Generate comprehensive HTML and PDF reports
- Customize report templates and content
- Download and share reports

## 📚 API Documentation

### Authentication Endpoints

```bash
POST /api/auth/register     # User registration
POST /api/auth/login        # User login
POST /api/auth/logout       # User logout
GET  /api/auth/me          # Get current user
PUT  /api/auth/me          # Update user profile
```

### Biomarker analysis endpoints (examples; prefer `/api/v1/...` for new code)

The backend mounts the same routes under unversioned paths, `/api/v1/...`, and `/api/v2/...` (see `backend/app/main.py`).

```bash
GET  /api/biomarkers/runs                    # List analysis runs
POST /api/biomarkers/run                     # Start a new analysis run
GET  /api/biomarkers/runs/{run_id}          # Get run details
GET  /api/biomarkers/runs/{run_id}/status   # Get run status
GET  /api/biomarkers/runs/{run_id}/results  # Get analysis results
GET  /api/biomarkers/runs/{run_id}/biomarkers
```

### Clinical Annotation Endpoints

```bash
POST /api/clinical/annotate                 # Annotate biomarkers
GET  /api/clinical/databases                # List available databases
POST /api/clinical/annotate-run/{run_id}    # Annotate run biomarkers
```

### WebSocket (real-time progress)

```bash
WS /api/ws/progress/{run_id}
```

### Interactive API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🛠️ Development

### Project Structure

```
biomarker_identifier/
├── backend/                 # FastAPI backend (Celery: app.services.celery_service)
│   ├── app/                 # Application package (api, core, models, pipelines, services)
│   ├── alembic/             # DB migrations
│   ├── tests/
│   └── requirements*.txt
├── frontend/                # React (Craco) web UI
├── data_collection/         # Optional public-data helpers (see README there)
├── deployment/              # Historical deployment notes; prefer root HOW_TO_RUN / DEPLOYMENT
├── docker-compose.yml       # Default local stack (Postgres, Redis, migrate, API, workers, Flower, UI)
├── docker-compose.prod.yml  # Production-style compose (nginx, scaling, Prometheus, Grafana)
├── docker-compose.spark.yml # Optional Spark integration
├── docs/                    # User guides, API reference, runbooks, roadmap
├── k8s/                     # Example Kubernetes manifests
├── mobile/                  # Mobile client (see mobile/README.md)
├── monitoring/              # Prometheus / Grafana configs used by prod compose
├── nginx/                   # Nginx config for production compose
├── services/spark_jobs/     # Spark job notes
└── ...
```

### Development setup

1. **Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm ci
   npm start
   ```

3. **Database**
   ```bash
   docker compose up -d postgres redis
   cd backend
   python -m alembic upgrade head
   ```

### Code Quality

```bash
# Backend linting and formatting
cd backend
black app/
flake8 app/
mypy app/

# Frontend linting
cd frontend
npm run lint
npm run type-check
```

## 🧪 Testing

### Running Tests

```bash
# Backend - all tests
cd backend
pytest

# Backend - with coverage (min 80%)
pytest --cov=app --cov-report=html --cov-fail-under=80
open htmlcov/index.html  # View coverage report

# Backend - unit tests only
pytest tests/unit/ -v

# Backend - integration tests (requires Postgres + Redis for full run)
pytest tests/integration/ -v

# Frontend - all tests
cd frontend
npm test -- --watchAll=false

# Frontend - with coverage (min 55%)
npm test -- --watchAll=false --coverage

# Frontend - type check
npm run type-check
```

### Test Categories

- **Backend**: Unit (`tests/unit/`), integration (`tests/integration/`), API routes, error-path tests
- **Frontend**: Pages (Login, Models, Settings, Reports, ClinicalAnnotation), components (Header, Sidebar), charts (BiomarkerResultsChart, PathwayAnalysisChart)

### Additional Backend Commands

```bash
pytest -m e2e              # End-to-end tests
pytest -n auto             # Run in parallel
pytest tests/unit/test_auth_service.py -v  # Specific file
python backend/run_tests.py --type unit --coverage  # Test runner script
```

### Test Structure

- **Unit Tests**: Test individual components and functions
- **Integration Tests**: Test API endpoints and database interactions
- **End-to-End Tests**: Test complete user workflows
- **Performance Tests**: Load testing with Locust

### Test coverage

- **Backend:** `pytest` is configured in `backend/pytest.ini` (and often run with a `--cov-fail-under=80` target in scripts and CI; check your pipeline).
- **Frontend:** Jest global minimums are in `frontend/package.json` under `jest.coverageThreshold` (intentionally modest for global gates; use `test:coverage` to see a full report).

## 🚀 Deployment

### Docker Deployment

```bash
# Production-style compose (read docker-compose.prod.yml and HOW_TO_RUN first)
docker compose -f docker-compose.prod.yml up -d

# Scaling depends on your orchestrator and images; the prod file uses `deploy` replicas
```

### Kubernetes deployment

Example manifests live under `k8s/`. Your namespace and image names will differ; adjust before applying.

### Cloud Deployment

- **AWS**: ECS, EKS, or EC2 deployment
- **Google Cloud**: GKE or Compute Engine
- **Azure**: AKS or Virtual Machines

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## 📊 Monitoring

### Metrics and Monitoring

- **Prometheus**: Metrics collection and alerting
- **Grafana**: Dashboards and visualization
- **Flower**: Celery task monitoring
- **Health Checks**: Application health monitoring

### Logging

- **Structured Logging**: JSON-formatted logs
- **Log Aggregation**: Centralized log collection
- **Log Rotation**: Automatic log management
- **Error Tracking**: Exception monitoring

### Performance Monitoring

- **Response Times**: API endpoint performance
- **Resource Usage**: CPU, memory, and disk usage
- **Database Performance**: Query performance and optimization
- **Cache Performance**: Redis cache hit rates

## 🔒 Security

### Authentication and Authorization

- **JWT Tokens**: Secure token-based authentication
- **Role-based Access**: User roles and permissions
- **Session Management**: Secure session handling
- **Password Security**: Bcrypt password hashing

### Data Security

- **Data Encryption**: Encryption at rest and in transit
- **Input Validation**: Comprehensive input sanitization
- **SQL Injection Prevention**: Parameterized queries
- **XSS Protection**: Cross-site scripting prevention

### Infrastructure Security

- **HTTPS**: SSL/TLS encryption
- **Firewall**: Network security rules
- **Container Security**: Secure container configurations
- **Secrets Management**: Secure credential storage

## 🤝 Contributing

### Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint for JavaScript/TypeScript
- Write comprehensive tests
- Update documentation
- Follow semantic versioning

### Code Review Process

- All changes require code review
- Tests must pass before merging
- Documentation must be updated
- Security review for sensitive changes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation

- [How to run (step-by-step)](HOW_TO_RUN.md)
- [Quick start scenarios](docs/QUICK_START_GUIDE.md)
- [API documentation (running server)](http://localhost:8000/docs) · [REST reference](docs/API_DOCUMENTATION.md)
- [Deployment](DEPLOYMENT.md) · [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)
- [Testing guide](TESTING_GUIDE.md) · [Contributor testing guide](docs/CONTRIBUTOR_TESTING_GUIDE.md)
- [Product roadmap and status](docs/PRODUCT_ROADMAP.md)
- [Contributing guidelines](CONTRIBUTING.md)

### Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/jbInf-08/biomarker_identifier/issues)
- **GitHub Discussions**: [Community discussions](https://github.com/jbInf-08/biomarker_identifier/discussions)
- **Email Support**: jbautista0055@gmail.com

### Professional Support

For enterprise support and consulting services, contact:
- **Email**: jbautista0055@gmail.com
- **Phone**: See GitHub profile for contact info

## 🙏 Acknowledgments

- **Scientific Community**: For biomarker research and validation
- **Open Source Projects**: For the amazing tools and libraries
- **Contributors**: For their valuable contributions
- **Users**: For feedback and feature requests

## 📈 Roadmap

Product themes (README), phased maintenance plan, and conference research next steps are **consolidated with implementation status** in [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md). Update that file when priorities change; this section stays high level.

**Themes:** multi-tenant isolation, advanced ML, real-time collaboration, mobile clients, API versioning (`/api/v1` and `/api/v2` mirrors in the backend), cloud-native scaling, AI-assisted interpretation, integrations, multi-region ops, collaborative research.

**Research / pipeline:** cryptographic secure aggregation (planned; see `GET /api/v1/federated/capabilities`), optional deeper GNN stage, LLM literature grounding, non-TCGA validation harnesses, raw counts + DESeq2/edgeR via optional rpy2.

---

**Made with ❤️ for the cancer research community**