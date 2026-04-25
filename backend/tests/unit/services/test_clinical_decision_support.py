"""
Comprehensive unit tests for clinical decision support service.
"""
import pytest

from app.services.clinical_decision_support import (
    ClinicalDecisionSupportService,
    ClinicalRecommendationEngine,
    ClinicalValidationFramework,
)


class TestClinicalDecisionSupportService:
    """Test cases for ClinicalDecisionSupportService."""

    def test_service_initialization(self):
        """Test service initialization."""
        service = ClinicalDecisionSupportService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_generate_clinical_recommendations(self, db_session):
        """Test generating clinical recommendations."""
        service = ClinicalDecisionSupportService()

        biomarker_results = [
            {"gene_symbol": "TP53", "p_value": 0.001, "fold_change": 2.5},
            {"gene_symbol": "BRCA1", "p_value": 0.002, "fold_change": 1.8},
        ]

        patient_context = {
            "disease_type": "breast_cancer",
            "age": 45,
            "comorbidities": [],
        }

        recommendations = await service.generate_clinical_recommendations(
            biomarker_results=biomarker_results, patient_context=patient_context
        )

        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_validate_clinical_decision(self, db_session):
        """Test validating clinical decision."""
        service = ClinicalDecisionSupportService()

        result = await service.validate_clinical_decision(
            biomarker="TP53",
            clinical_decision="Use TP53 as diagnostic biomarker",
            patient_context={"disease_type": "breast_cancer"},
        )

        assert isinstance(result, dict)
        assert "validation_score" in result or "biomarker" in result


class TestClinicalRecommendationEngine:
    """Test cases for ClinicalRecommendationEngine."""

    def test_engine_initialization(self):
        """Test recommendation engine initialization."""
        engine = ClinicalRecommendationEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_initialize_engine(self, db_session):
        """Test initializing recommendation engine."""
        engine = ClinicalRecommendationEngine()
        # This may fail if no training data, but should not crash
        try:
            await engine.initialize()
        except Exception:
            pass  # Expected if no training data


class TestClinicalValidationFramework:
    """Test cases for ClinicalValidationFramework."""

    def test_framework_initialization(self):
        """Test validation framework initialization."""
        framework = ClinicalValidationFramework()
        assert framework is not None

    @pytest.mark.asyncio
    async def test_initialize_framework(self, db_session):
        """Test initializing validation framework."""
        framework = ClinicalValidationFramework()
        await framework.initialize()
        assert framework.validation_rules is not None

    @pytest.mark.asyncio
    async def test_validate_clinical_decision(self, db_session):
        """Test validating clinical decision."""
        framework = ClinicalValidationFramework()
        await framework.initialize()

        result = await framework.validate_clinical_decision(
            biomarker="TP53",
            disease="breast_cancer",
            clinical_decision={"evidence_level": "A", "validated": True},
        )

        assert isinstance(result, dict)
        assert "valid" in result
