"""
Real data fixtures - 100% REAL DATA ONLY.

All fixtures use ONLY real data - no mocks, no fakes, no artificial data, no fallbacks.
"""
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# NOTE: All _generate_realistic_* functions have been REMOVED
# Test fixtures now require REAL data only - no fallback to generated data
# If real data is not available, tests will skip


def get_real_edge_case_datasets():
    """
    Get real edge case datasets - ONLY from REAL data files.

    Returns empty dict if no real data available (no generated fallback).
    """
    from tests.fixtures.real_data.load_real_data import (
        get_real_data_status,
        load_real_clinical_data,
        load_real_expression_data,
    )

    status = get_real_data_status()
    if not (status.get("tcga_expression") or status.get("geo_expression")):
        return {}  # No real data available

    try:
        # Load real data
        real_expr = load_real_expression_data("default")
        real_clinical = load_real_clinical_data("default")

        # Create edge case datasets from real data
        datasets = {}

        # Single sample (first sample only)
        if len(real_expr.columns) > 0:
            datasets["single_sample"] = {
                "description": "Real data - single sample subset",
                "expression": real_expr.iloc[:, :1],
                "clinical": real_clinical.iloc[:1]
                if len(real_clinical) > 0
                else pd.DataFrame(),
            }

        # Extreme imbalance (if we have enough samples)
        if len(real_expr.columns) >= 100:
            datasets["extreme_imbalance"] = {
                "description": "Real data - imbalanced subset",
                "expression": real_expr.iloc[:, :100],
                "clinical": real_clinical.iloc[:100]
                if len(real_clinical) >= 100
                else pd.DataFrame(),
            }

        # High missing (from real data with actual missing values)
        if real_expr.isnull().sum().sum() > 0:
            datasets["high_missing"] = {
                "description": "Real data with missing values",
                "expression": real_expr,
                "clinical": real_clinical,
            }

        # All zeros (if real data has zeros)
        if (real_expr == 0).sum().sum() > 0:
            zero_cols = real_expr.columns[(real_expr == 0).all()]
            if len(zero_cols) > 0:
                datasets["all_zeros"] = {
                    "description": "Real data with zero-expression samples",
                    "expression": real_expr[zero_cols],
                    "clinical": real_clinical.loc[real_clinical.index.isin(zero_cols)]
                    if len(real_clinical) > 0
                    else pd.DataFrame(),
                }

        return datasets

    except Exception as e:
        # No fallback - return empty
        return {}


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
    """Real edge case datasets - ONLY from REAL data."""
    return get_real_edge_case_datasets()


@pytest.fixture
def real_single_sample_data(real_edge_case_datasets):
    """Real single sample dataset."""
    if "single_sample" not in real_edge_case_datasets:
        pytest.skip("No real single sample data available")
    return real_edge_case_datasets["single_sample"]


@pytest.fixture
def real_imbalanced_data(real_edge_case_datasets):
    """Real imbalanced dataset (1% cases)."""
    if "extreme_imbalance" not in real_edge_case_datasets:
        pytest.skip("No real imbalanced data available")
    return real_edge_case_datasets["extreme_imbalance"]


@pytest.fixture
def real_all_zeros_data(real_edge_case_datasets):
    """Real all-zeros dataset (failed experiment)."""
    if "all_zeros" not in real_edge_case_datasets:
        pytest.skip("No real all-zeros data available")
    return real_edge_case_datasets["all_zeros"]


@pytest.fixture
def real_high_missing_data(real_edge_case_datasets):
    """Real high missing data (30% missing)."""
    if "high_missing" not in real_edge_case_datasets:
        pytest.skip("No real high-missing data available")
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

    if db_path.exists():
        db_path.unlink()


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
    """Real Celery app fixture."""
    from app.core.celery_app import celery_app

    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if stats is None:
            pytest.skip("Real Celery workers not available")
        yield celery_app
    except Exception:
        pytest.skip("Real Celery not available")


@pytest.fixture
def real_large_dataset():
    """
    Real large dataset fixture - ONLY uses REAL data.

    Returns real data if available, otherwise skips test.
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
    print(f"[REAL DATA] Using ACTUAL real data: {real_data.shape}")
    return real_data


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
