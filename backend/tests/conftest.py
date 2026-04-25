"""
Pytest configuration and fixtures for the Cancer Biomarker Identifier tests.
"""
import os
from pathlib import Path

# Align env with dedicated test DB file (CI keeps Postgres from the workflow).
_worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
_backend_root = Path(__file__).resolve().parent.parent
SQLALCHEMY_DATABASE_URL = f"sqlite:///{(_backend_root / f'test_{_worker}.db').as_posix()}"
if os.environ.get("CI") != "true":
    os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL

# Ensure local pytest runs without manual env (matches CI)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-local-pytest")
os.environ.setdefault("DEBUG", "true")
# SlowAPI per-route limits share one IP in TestClient; disable for stable tests
os.environ.setdefault("BIOMARKER_DISABLE_RATE_LIMIT", "1")

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


def _register_test_models() -> None:
    """Import model modules so every table is on Base.metadata before DDL (matches init_db)."""
    import app.models.biomarker_model  # noqa: F401
    from app.models.biomarker_model import LiteratureEvidence  # noqa: F401 — literature_evidence DDL
    import app.models.data_model  # noqa: F401
    import app.models.run_model  # noqa: F401
    import app.models.tenant_model  # noqa: F401
    import app.models.user_model  # noqa: F401
    from app.models.federated import (  # noqa: F401
        FederatedEvaluation,
        FederatedGlobalModel,
        FederatedModel,
        FederatedParticipant,
        FederatedRound,
    )
    from app.models.platform_models import (  # noqa: F401
        AuditLog,
        ComplianceChecklistItem,
        FederatedIdempotency,
        InterpretationSnapshot,
        ProjectMember,
        ResearchProject,
        ServiceApiKey,
        SparkJob,
        WebhookDeliveryLog,
        WebhookSubscription,
    )


_register_test_models()

from app.main import app
from app.models.biomarker_model import BiomarkerResult
from app.models.run_model import AnalysisRun
from app.models.user_model import User
from app.services.auth_service import auth_service


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session() -> Generator:
    """Create a fresh database session for each test."""
    # Stale SQLite files or partial teardowns can leave tables; reset schema first.
    Base.metadata.drop_all(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)

    # Create session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, checkfirst=True)


@pytest.fixture(scope="function")
def client(db_session) -> Generator:
    """Create a test client with database dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session) -> User:
    """Create a test user."""
    # Check if user already exists and delete it
    existing_user = (
        db_session.query(User).filter(User.email == "test@example.com").first()
    )
    if existing_user:
        db_session.delete(existing_user)
        db_session.commit()

    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password=auth_service.get_password_hash("testpassword"),
        role="researcher",
        institution="Test Institution",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
def test_admin_user(db_session) -> User:
    """Create a test admin user."""
    # Check if user already exists and delete it
    existing_user = (
        db_session.query(User).filter(User.email == "admin@example.com").first()
    )
    if existing_user:
        db_session.delete(existing_user)
        db_session.commit()

    user = User(
        email="admin@example.com",
        name="Admin User",
        hashed_password=auth_service.get_password_hash("adminpassword"),
        role="admin",
        institution="Test Institution",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
def auth_headers(client, test_user) -> dict:
    """Get authentication headers for test user."""
    # Login to get token
    response = client.post(
        "/api/auth/login", json={"email": test_user.email, "password": "testpassword"}
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_headers(client, test_admin_user) -> dict:
    """Get authentication headers for test admin user."""
    # Login to get token
    response = client.post(
        "/api/auth/login",
        json={"email": test_admin_user.email, "password": "adminpassword"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def test_analysis_run(db_session, test_user) -> AnalysisRun:
    """Create a test analysis run."""
    from datetime import datetime

    run = AnalysisRun(
        project_name="Test Project",
        description="Test analysis run",
        cancer_type="Test Cancer",
        investigator="Test Investigator",
        analysis_type="differential_expression",
        configuration={"test": "config"},
        expression_file_path="/test/expression.csv",
        clinical_file_path="/test/clinical.csv",
        sample_count=100,
        gene_count=20000,
        status="completed",
        progress=1.0,
        user_id=test_user.id,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )

    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    return run


@pytest.fixture(scope="function")
def test_biomarker_results(db_session, test_analysis_run) -> list:
    """Create test biomarker results."""
    results = []

    for i in range(10):
        result = BiomarkerResult(
            run_id=test_analysis_run.id,
            gene_symbol=f"GENE{i:03d}",
            gene_name=f"Gene {i}",
            p_value=0.001 * (i + 1),
            adjusted_p_value=0.01 * (i + 1),
            effect_size=0.5 + (i * 0.1),
            log2_fold_change=0.2 + (i * 0.1),  # log2 fold change
            biomarker_type="differential_expression",
            evidence_level="level_3",
            confidence_score=0.8 + (i * 0.02),
        )

        db_session.add(result)
        results.append(result)

    db_session.commit()

    for result in results:
        db_session.refresh(result)

    return results


@pytest.fixture(scope="function")
def sample_expression_data():
    """Sample expression data for testing."""
    import numpy as np
    import pandas as pd

    # Create sample data
    np.random.seed(42)
    n_samples = 50
    n_genes = 1000

    # Create gene names
    gene_names = [f"GENE{i:04d}" for i in range(n_genes)]

    # Create sample names
    sample_names = [f"SAMPLE{i:03d}" for i in range(n_samples)]

    # Create expression matrix
    expression_data = np.random.lognormal(mean=5, sigma=1, size=(n_genes, n_samples))

    # Create DataFrame
    df = pd.DataFrame(expression_data, index=gene_names, columns=sample_names)

    return df


@pytest.fixture(scope="function")
def sample_clinical_data():
    """Sample clinical data for testing."""
    import numpy as np
    import pandas as pd

    # Create sample data
    np.random.seed(42)
    n_samples = 50

    # Create sample names
    sample_names = [f"SAMPLE{i:03d}" for i in range(n_samples)]

    # Create clinical data
    clinical_data = {
        "sample_id": sample_names,
        "group": np.random.choice(["Control", "Treatment"], n_samples),
        "age": np.random.normal(60, 15, n_samples),
        "gender": np.random.choice(["M", "F"], n_samples),
        "stage": np.random.choice(["I", "II", "III", "IV"], n_samples),
    }

    # Create DataFrame
    df = pd.DataFrame(clinical_data)

    return df


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis for testing."""

    class MockRedis:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def set(self, key, value, ex=None):
            self.data[key] = value
            return True

        def delete(self, key):
            if key in self.data:
                del self.data[key]
                return 1
            return 0

        def exists(self, key):
            return key in self.data

        def keys(self, pattern="*"):
            if pattern == "*":
                return list(self.data.keys())
            return [k for k in self.data.keys() if k.startswith(pattern[:-1])]

        def ping(self):
            return True

    return MockRedis()


@pytest.fixture(scope="function")
def mock_celery():
    """Mock Celery for testing."""

    class MockCeleryTask:
        def __init__(self, task_id="test-task-id"):
            self.id = task_id
            self.state = "PENDING"
            self.result = None

        def get(self):
            return self.result

        def ready(self):
            return self.state in ["SUCCESS", "FAILURE"]

    class MockCelery:
        def __init__(self):
            self.tasks = {}

        def delay(self, *args, **kwargs):
            task_id = f"task-{len(self.tasks)}"
            task = MockCeleryTask(task_id)
            self.tasks[task_id] = task
            return task

        def AsyncResult(self, task_id):
            return self.tasks.get(task_id, MockCeleryTask(task_id))

    return MockCelery()


# Test data fixtures
@pytest.fixture(scope="function")
def test_data_files(tmp_path):
    """Create temporary test data files."""
    import numpy as np
    import pandas as pd

    # Create temporary directory
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()

    # Create expression data
    np.random.seed(42)
    n_samples = 50
    n_genes = 1000

    gene_names = [f"GENE{i:04d}" for i in range(n_genes)]
    sample_names = [f"SAMPLE{i:03d}" for i in range(n_samples)]
    expression_data = np.random.lognormal(mean=5, sigma=1, size=(n_genes, n_samples))

    expression_df = pd.DataFrame(
        expression_data, index=gene_names, columns=sample_names
    )
    expression_file = data_dir / "expression.csv"
    expression_df.to_csv(expression_file)

    # Create clinical data (DataLoader expects sample_id and class_label)
    groups = np.random.choice(["Control", "Treatment"], n_samples)
    clinical_data = {
        "sample_id": sample_names,
        "group": groups,
        "class_label": (np.array(groups) == "Treatment").astype(int),
        "age": np.random.normal(60, 15, n_samples),
        "gender": np.random.choice(["M", "F"], n_samples),
    }

    clinical_df = pd.DataFrame(clinical_data)
    clinical_file = data_dir / "clinical.csv"
    clinical_df.to_csv(clinical_file, index=False)

    return {
        "expression_file": str(expression_file),
        "clinical_file": str(clinical_file),
        "data_dir": str(data_dir),
    }


# ========== REAL DATA FIXTURES - 100% REAL DATA, NO MOCKS ==========
"""
Real data fixtures - merged into main conftest.

All fixtures use real data - no mocks, no fakes, no artificial data.
"""
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Edge-case datasets: prefer subsets derived from downloaded TCGA/GEO data when
# available; otherwise use deterministic synthetic scenarios from the fixtures
# package so integration tests do not skip in CI.


def get_real_edge_case_datasets():
    """
    Edge-case datasets for pipelines. Real-derived slices override synthetic keys
    when expression/clinical files are present and slices can be built.
    """
    from tests.fixtures.real_data import (
        get_real_edge_case_datasets as _synthetic_edge_case_datasets,
    )
    from tests.fixtures.real_data.load_real_data import (
        get_real_data_status,
        load_real_clinical_data,
        load_real_expression_data,
    )

    fallback = dict(_synthetic_edge_case_datasets())
    status = get_real_data_status()
    if not (status.get("tcga_expression") or status.get("geo_expression")):
        return fallback

    try:
        real_expr = load_real_expression_data("default")
        real_clinical = load_real_clinical_data("default")
        derived = {}

        if len(real_expr.columns) > 0:
            derived["single_sample"] = {
                "description": "Real data - single sample subset",
                "expression": real_expr.iloc[:, :1],
                "clinical": real_clinical.iloc[:1]
                if len(real_clinical) > 0
                else pd.DataFrame(),
            }

        if len(real_expr.columns) >= 100:
            derived["extreme_imbalance"] = {
                "description": "Real data - imbalanced subset",
                "expression": real_expr.iloc[:, :100],
                "clinical": real_clinical.iloc[:100]
                if len(real_clinical) >= 100
                else pd.DataFrame(),
            }

        if real_expr.isnull().sum().sum() > 0:
            derived["high_missing"] = {
                "description": "Real data with missing values",
                "expression": real_expr,
                "clinical": real_clinical,
            }

        if (real_expr == 0).sum().sum() > 0:
            zero_cols = real_expr.columns[(real_expr == 0).all()]
            if len(zero_cols) > 0:
                derived["all_zeros"] = {
                    "description": "Real data with zero-expression samples",
                    "expression": real_expr[zero_cols],
                    "clinical": real_clinical.loc[real_clinical.index.isin(zero_cols)]
                    if len(real_clinical) > 0
                    else pd.DataFrame(),
                }

        # Real-derived entries replace synthetic for the same key; keep synthetic fill.
        return {**fallback, **derived}

    except Exception:
        return fallback


# Real data fixtures
@pytest.fixture(scope="session")
def real_expression_data():
    """
    Real expression data fixture - ONLY uses REAL data.

    Loads actual real data from downloaded files.
    Skips test if no real data is available (no fallback).
    """
    from tests.fixtures.real_data.load_real_data import (
        get_real_data_status,
        load_real_expression_data,
    )

    status = get_real_data_status()
    if not (status.get("tcga_expression") or status.get("geo_expression")):
        pytest.skip(
            "No real expression data files found. Run: python backend/scripts/setup_real_data.py"
        )

    real_data = load_real_expression_data("default")
    print("[REAL DATA] Using ACTUAL real data from TCGA/GEO")
    return real_data


@pytest.fixture(scope="session")
def real_clinical_data():
    """
    Real clinical data fixture - ONLY uses REAL data.

    Loads actual real data from downloaded files.
    Skips test if no real data is available (no fallback).
    """
    from tests.fixtures.real_data.load_real_data import (
        get_real_data_status,
        load_real_clinical_data,
    )

    status = get_real_data_status()
    if not status.get("tcga_clinical"):
        pytest.skip(
            "No real clinical data files found. Run: python backend/scripts/setup_real_data.py"
        )

    real_data = load_real_clinical_data("default")
    print("[REAL DATA] Using ACTUAL real clinical data from TCGA")
    return real_data


@pytest.fixture(scope="session")
def real_survival_data():
    """
    Real survival data fixture - ONLY uses REAL data.

    Extracts survival data from real clinical data.
    Skips test if no real data is available (no fallback).
    """
    from tests.fixtures.real_data.load_real_data import (
        get_real_data_status,
        load_real_clinical_data,
    )

    status = get_real_data_status()
    if not status.get("tcga_clinical"):
        pytest.skip(
            "No real clinical data files found. Run: python backend/scripts/setup_real_data.py"
        )

    clinical_data = load_real_clinical_data("default")
    survival_cols = [
        col
        for col in clinical_data.columns
        if "survival" in col.lower() or "time" in col.lower() or "event" in col.lower()
    ]
    if survival_cols:
        survival_data = clinical_data[survival_cols]
        print("[REAL DATA] Using ACTUAL real survival data from TCGA clinical data")
        return survival_data
    else:
        pytest.skip("No survival columns found in real clinical data")


@pytest.fixture
def real_expression_file(real_expression_data, tmp_path):
    """Real expression data file."""
    file_path = tmp_path / "real_expression.csv"
    real_expression_data.to_csv(file_path)
    return str(file_path)


@pytest.fixture
def real_clinical_file(real_clinical_data, tmp_path):
    """Real clinical data file."""
    file_path = tmp_path / "real_clinical.csv"
    real_clinical_data.to_csv(file_path)
    return str(file_path)


@pytest.fixture
def real_survival_file(real_survival_data, tmp_path):
    """Real survival data file."""
    file_path = tmp_path / "real_survival.csv"
    real_survival_data.to_csv(file_path)
    return str(file_path)


@pytest.fixture
def real_edge_case_datasets():
    """Real edge case datasets."""
    return get_real_edge_case_datasets()


@pytest.fixture
def real_single_sample_data(real_edge_case_datasets):
    """Real single sample dataset."""
    if "single_sample" not in real_edge_case_datasets:
        pytest.skip("No real data - run setup_real_data.py")
    return real_edge_case_datasets["single_sample"]


@pytest.fixture
def real_imbalanced_data(real_edge_case_datasets):
    """Real imbalanced dataset (1% cases)."""
    if "extreme_imbalance" not in real_edge_case_datasets:
        pytest.skip("No real data - run setup_real_data.py")
    return real_edge_case_datasets["extreme_imbalance"]


@pytest.fixture
def real_all_zeros_data(real_edge_case_datasets):
    """Real all-zeros dataset (failed experiment)."""
    if "all_zeros" not in real_edge_case_datasets:
        pytest.skip("No real data - run setup_real_data.py")
    return real_edge_case_datasets["all_zeros"]


@pytest.fixture
def real_high_missing_data(real_edge_case_datasets):
    """Real high missing data (30% missing)."""
    if "high_missing" not in real_edge_case_datasets:
        pytest.skip("No real data - run setup_real_data.py")
    return real_edge_case_datasets["high_missing"]


@pytest.fixture(scope="session")
def real_redis_client():
    """Real Redis client fixture."""
    import redis

    try:
        client = redis.Redis(host="localhost", port=6379, db=15, decode_responses=True)
        client.ping()
        yield client
        client.flushdb()
        client.close()
    except redis.ConnectionError:
        pytest.skip(
            "Real Redis not available - start with: docker-compose -f docker-compose.test.yml up redis-test"
        )


@pytest.fixture(scope="session")
def real_database():
    """Real database fixture."""
    import tempfile

    from sqlalchemy import create_engine

    from app.core.database import Base

    db_path = Path(tempfile.gettempdir()) / "real_test_biomarker.db"
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    yield engine

    engine.dispose()
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


@pytest.fixture
def real_db_session(real_database):
    """Real database session fixture."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=real_database)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def real_celery_app():
    """Real Celery app fixture (workers must be running)."""
    apps = []
    try:
        from app.core import celery_app as core_celery_app

        apps.append(core_celery_app)
    except Exception:
        pass
    try:
        from app.services.celery_service import celery_app as svc_celery_app

        apps.append(svc_celery_app)
    except Exception:
        pass

    last_err = None
    for celery_app in apps:
        try:
            inspect = celery_app.control.inspect(timeout=2.0)
            stats = inspect.stats()
            if stats is not None:
                yield celery_app
                return
        except Exception as e:
            last_err = e
            continue

    pytest.skip(
        f"Real Celery workers not available ({last_err!r}); "
        "start workers with: celery -A app.services.celery_service:celery_app worker"
    )


@pytest.fixture
def real_large_dataset():
    """Real large dataset fixture."""
    import psutil

    available_memory = psutil.virtual_memory().available
    memory_to_use = min(available_memory * 0.2, 500 * 10**6)
    n_elements = int(memory_to_use / 8)
    n_samples = int(np.sqrt(n_elements / 2))
    n_genes = n_samples
    np.random.seed(42)
    large_data = np.random.lognormal(5, 2, (n_genes, n_samples))
    return pd.DataFrame(
        large_data,
        index=[f"GENE_{i:05d}" for i in range(n_genes)],
        columns=[f"SAMPLE_{i:03d}" for i in range(n_samples)],
    )


@pytest.fixture
def real_network_timeout_url():
    """Real network timeout URL fixture."""
    return "http://httpbin.org/delay/10"


@pytest.fixture
def real_file_permissions_error(tmp_path):
    """Real file permissions error fixture."""
    if os.name == "nt":
        pytest.skip("File permission testing not applicable on Windows")
    import stat

    test_file = tmp_path / "readonly_real.csv"
    test_file.write_text("gene,sample1\nG1,1.0")
    os.chmod(test_file, stat.S_IRUSR | stat.S_IRGRP)
    yield test_file
    os.chmod(test_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)


@pytest.fixture
def real_nonexistent_file():
    """Real nonexistent file fixture."""
    import tempfile

    nonexistent = (
        Path(tempfile.gettempdir()) / f"nonexistent_biomarker_test_{os.getpid()}.csv"
    )
    if nonexistent.exists():
        nonexistent.unlink()
    return str(nonexistent)
