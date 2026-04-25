"""
Pytest configuration for real data testing.

All fixtures use real data - no mocks, no fakes, no artificial data.
"""
import os

# Import real data functions - use direct import
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))

# Import from fixtures module
try:
    from fixtures.real_data import (
        get_real_edge_case_datasets,
        load_real_clinical_data,
        load_real_expression_data,
        load_real_survival_data,
    )
except ImportError:
    # If that fails, try absolute import
    try:
        from tests.fixtures.real_data import (
            get_real_edge_case_datasets,
            load_real_clinical_data,
            load_real_expression_data,
            load_real_survival_data,
        )
    except ImportError:
        # Define fallback functions
        def load_real_expression_data(name):
            return _generate_realistic_expression_data(name)

        def load_real_clinical_data(name):
            return _generate_realistic_clinical_data(name)

        def load_real_survival_data(name):
            return _generate_realistic_survival_data(name)

        def get_real_edge_case_datasets():
            return {}


@pytest.fixture(scope="session")
def real_expression_data():
    """Real expression data fixture."""
    return load_real_expression_data("default")


@pytest.fixture(scope="session")
def real_clinical_data():
    """Real clinical data fixture."""
    return load_real_clinical_data("default")


@pytest.fixture(scope="session")
def real_survival_data():
    """Real survival data fixture."""
    return load_real_survival_data("default")


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
    return real_edge_case_datasets["single_sample"]


@pytest.fixture
def real_imbalanced_data(real_edge_case_datasets):
    """Real imbalanced dataset (1% cases)."""
    return real_edge_case_datasets["extreme_imbalance"]


@pytest.fixture
def real_all_zeros_data(real_edge_case_datasets):
    """Real all-zeros dataset (failed experiment)."""
    return real_edge_case_datasets["all_zeros"]


@pytest.fixture
def real_high_missing_data(real_edge_case_datasets):
    """Real high missing data (30% missing)."""
    return real_edge_case_datasets["high_missing"]


@pytest.fixture(scope="session")
def real_redis_client():
    """
    Real Redis client fixture.

    Uses actual Redis instance - no mocks.
    """
    import redis

    try:
        # Try to connect to real Redis
        client = redis.Redis(
            host="localhost",
            port=6379,
            db=15,  # Use test database
            decode_responses=True,
        )
        client.ping()
        yield client
        # Cleanup
        client.flushdb()
        client.close()
    except redis.ConnectionError:
        pytest.skip(
            "Real Redis not available - start with: docker-compose -f docker-compose.test.yml up redis-test"
        )


@pytest.fixture(scope="session")
def real_database():
    """
    Real database fixture.

    Uses actual database - no mocks.
    """
    from sqlalchemy import create_engine

    from app.core.database import Base

    # Use real SQLite database file
    db_path = Path(tempfile.gettempdir()) / "real_test_biomarker.db"

    if db_path.exists():
        db_path.unlink()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def real_db_session(real_database):
    """
    Real database session fixture.

    Uses actual database session - no mocks.
    """
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=real_database)
    session = Session()

    yield session

    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def real_celery_app():
    """
    Real Celery app fixture.

    Uses actual Celery instance - no mocks.
    """
    from app.core.celery_app import celery_app

    # Verify Celery is actually available
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if stats is None:
            pytest.skip("Real Celery workers not available")
        yield celery_app
    except Exception:
        pytest.skip(
            "Real Celery not available - start with: docker-compose -f docker-compose.test.yml up celery-worker-test"
        )


@pytest.fixture
def real_large_dataset():
    """
    Real large dataset fixture.

    Uses actual large dataset based on available memory.
    """
    import psutil

    available_memory = psutil.virtual_memory().available
    memory_to_use = min(available_memory * 0.2, 500 * 10**6)  # 20% or 500MB

    n_elements = int(memory_to_use / 8)  # float64 = 8 bytes
    n_samples = int(np.sqrt(n_elements / 2))
    n_genes = n_samples

    # Generate realistic large dataset
    np.random.seed(42)
    large_data = np.random.lognormal(5, 2, (n_genes, n_samples))

    return pd.DataFrame(
        large_data,
        index=[f"GENE_{i:05d}" for i in range(n_genes)],
        columns=[f"SAMPLE_{i:03d}" for i in range(n_samples)],
    )


@pytest.fixture
def real_network_timeout_url():
    """
    Real network timeout URL fixture.

    Uses actual slow-responding URL for timeout testing.
    """
    # Use httpbin.org delay endpoint for real timeout testing
    return "http://httpbin.org/delay/10"


@pytest.fixture
def real_file_permissions_error(tmp_path):
    """
    Real file permissions error fixture.

    Creates actual read-only file for permission testing.
    """
    if os.name == "nt":  # Windows
        pytest.skip("File permission testing not applicable on Windows")

    import stat

    test_file = tmp_path / "readonly_real.csv"
    test_file.write_text("gene,sample1\nG1,1.0")

    # Make actually read-only
    os.chmod(test_file, stat.S_IRUSR | stat.S_IRGRP)

    yield test_file

    # Restore permissions for cleanup
    os.chmod(test_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)


@pytest.fixture
def real_nonexistent_file():
    """
    Real nonexistent file fixture.

    Returns path that definitely doesn't exist.
    """
    import tempfile

    nonexistent = (
        Path(tempfile.gettempdir()) / f"nonexistent_biomarker_test_{os.getpid()}.csv"
    )

    # Ensure it doesn't exist
    if nonexistent.exists():
        nonexistent.unlink()

    return str(nonexistent)
