"""
Unit tests for HTML report generator module.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.models.biomarker_model import BiomarkerResult
from app.models.run_model import AnalysisRun, RunStatus
from app.reports.html_generator import HTMLReportGenerator


@pytest.fixture
def sample_analysis_run(db_session, test_user):
    """Create sample analysis run."""
    from datetime import datetime

    run = AnalysisRun(
        project_name="Test Project",
        description="Test analysis",
        cancer_type="Test Cancer",
        investigator="Test Investigator",
        analysis_type="differential_expression",
        configuration={"test": "config"},
        expression_file_path="/test/expression.csv",
        clinical_file_path="/test/clinical.csv",
        sample_count=100,
        gene_count=20000,
        status=RunStatus.COMPLETED.value,
        progress=1.0,
        user_id=test_user.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


@pytest.fixture
def sample_biomarker_results(db_session, sample_analysis_run):
    """Create sample biomarker results."""
    import numpy as np

    results = []

    for i in range(10):
        result = BiomarkerResult(
            run_id=sample_analysis_run.id,
            gene_symbol=f"GENE{i:03d}",
            gene_name=f"Gene {i}",
            p_value=0.001 * (i + 1),
            adjusted_p_value=0.01 * (i + 1),
            effect_size=0.5 + (i * 0.1),
            log2_fold_change=np.log2(1.2 + (i * 0.1)),
            biomarker_type="differential_expression",
            evidence_level="high",
            confidence_score=0.8 + (i * 0.02),
        )
        db_session.add(result)
        results.append(result)

    db_session.commit()
    for result in results:
        db_session.refresh(result)

    return results


class TestHTMLReportGenerator:
    """Test HTMLReportGenerator class."""

    def test_init(self):
        """Test HTMLReportGenerator initialization."""
        generator = HTMLReportGenerator()
        assert generator is not None

    def test_generate_report(
        self, db_session, sample_analysis_run, sample_biomarker_results, tmp_path
    ):
        """Test generating HTML report."""
        generator = HTMLReportGenerator()

        output_path = tmp_path / "report.html"

        # Get biomarker results from database
        from app.models.biomarker_model import BiomarkerResult

        results = (
            db_session.query(BiomarkerResult)
            .filter(BiomarkerResult.run_id == sample_analysis_run.id)
            .all()
        )

        html_content = generator.generate_report(
            analysis_run=sample_analysis_run, results=results
        )

        # Write to file
        output_path.write_text(html_content)

        assert output_path.exists()

        # Check that report contains expected content
        content = output_path.read_text()
        assert "Test Project" in content or "biomarker" in content.lower()

    def test_generate_report_empty_results(
        self, db_session, sample_analysis_run, tmp_path
    ):
        """Test generating HTML report with empty results."""
        generator = HTMLReportGenerator()

        output_path = tmp_path / "report_empty.html"

        # Use empty results list
        html_content = generator.generate_report(
            analysis_run=sample_analysis_run, results=[]
        )

        # Write to file
        output_path.write_text(html_content)

        assert output_path.exists()
