"""
Clinical Decision Support Service
Advanced clinical decision support features and validation frameworks
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import db_session
from app.models.clinical import (
    ClinicalEvidence,
    ClinicalGuideline,
    ClinicalRecommendation,
)

logger = logging.getLogger(__name__)


@dataclass
class ClinicalEvidence:
    """Clinical evidence data structure"""

    evidence_id: str
    biomarker: str
    disease: str
    evidence_level: str  # A, B, C, D
    clinical_significance: str  # high, moderate, low
    study_type: str  # RCT, cohort, case-control, meta-analysis
    sample_size: int
    p_value: float
    effect_size: float
    confidence_interval: Tuple[float, float]
    publication_year: int
    journal_impact_factor: float
    citation_count: int


@dataclass
class ClinicalRecommendation:
    """Clinical recommendation data structure"""

    recommendation_id: str
    biomarker: str
    clinical_context: str
    recommendation: str
    evidence_level: str
    strength: str  # strong, moderate, weak
    contraindications: List[str]
    monitoring_requirements: List[str]
    follow_up_period: int  # months
    cost_effectiveness: str
    implementation_notes: str


class ClinicalDecisionSupportService:
    """Clinical decision support service for biomarker interpretation"""

    def __init__(self):
        self.evidence_database = {}
        self.clinical_guidelines = {}
        self.recommendation_engine = None
        self.validation_framework = None

    async def initialize_service(self):
        """Initialize clinical decision support service"""
        try:
            # Load evidence database
            await self._load_evidence_database()

            # Load clinical guidelines
            await self._load_clinical_guidelines()

            # Initialize recommendation engine
            await self._initialize_recommendation_engine()

            # Initialize validation framework
            await self._initialize_validation_framework()

            logger.info("Clinical decision support service initialized")

        except Exception as e:
            logger.error(
                f"Error initializing clinical decision support service: {str(e)}"
            )
            raise

    async def _load_evidence_database(self):
        """Load clinical evidence database"""
        try:
            # Load from external sources
            evidence_sources = [
                await self._load_pubmed_evidence(),
                await self._load_clinical_trials_evidence(),
                await self._load_guideline_evidence(),
            ]

            # Combine evidence from all sources
            for evidence_list in evidence_sources:
                for evidence in evidence_list:
                    key = f"{evidence.biomarker}_{evidence.disease}"
                    if key not in self.evidence_database:
                        self.evidence_database[key] = []
                    self.evidence_database[key].append(evidence)

            logger.info(f"Loaded {len(self.evidence_database)} evidence entries")

        except Exception as e:
            logger.error(f"Error loading evidence database: {str(e)}")
            raise

    async def _load_pubmed_evidence(self) -> List[ClinicalEvidence]:
        """Load evidence from PubMed. No real API integration yet - returns empty to avoid fake data."""
        try:
            # PubMed E-utilities integration would go here
            return []
        except Exception as e:
            logger.error(f"Error loading PubMed evidence: {str(e)}")
            return []

    async def _load_clinical_trials_evidence(self) -> List[ClinicalEvidence]:
        """Load evidence from clinical trials databases. No real API integration yet - returns empty to avoid fake data."""
        try:
            # ClinicalTrials.gov API integration would go here
            return []
        except Exception as e:
            logger.error(f"Error loading clinical trials evidence: {str(e)}")
            return []

    async def _load_guideline_evidence(self) -> List[ClinicalEvidence]:
        """Load evidence from clinical guidelines. No real API integration yet - returns empty to avoid fake data."""
        try:
            # Guideline database integration would go here
            return []
        except Exception as e:
            logger.error(f"Error loading guideline evidence: {str(e)}")
            return []

    async def _load_clinical_guidelines(self):
        """Load clinical guidelines"""
        try:
            # Load from database
            with db_session() as db:
                guidelines = db.query(ClinicalGuideline).all()

            for guideline in guidelines:
                self.clinical_guidelines[guideline.guideline_id] = guideline

            logger.info(f"Loaded {len(self.clinical_guidelines)} clinical guidelines")

        except Exception as e:
            logger.error(f"Error loading clinical guidelines: {str(e)}")
            raise

    async def _initialize_recommendation_engine(self):
        """Initialize clinical recommendation engine"""
        try:
            # Create recommendation engine using machine learning
            self.recommendation_engine = ClinicalRecommendationEngine()
            await self.recommendation_engine.initialize()

        except Exception as e:
            logger.error(f"Error initializing recommendation engine: {str(e)}")
            raise

    async def _initialize_validation_framework(self):
        """Initialize clinical validation framework"""
        try:
            self.validation_framework = ClinicalValidationFramework()
            await self.validation_framework.initialize()

        except Exception as e:
            logger.error(f"Error initializing validation framework: {str(e)}")
            raise

    async def generate_clinical_recommendations(
        self, biomarker_results: List[Dict[str, Any]], patient_context: Dict[str, Any]
    ) -> List[ClinicalRecommendation]:
        """
        Generate clinical recommendations based on biomarker results

        Args:
            biomarker_results: List of biomarker analysis results
            patient_context: Patient clinical context

        Returns:
            List of clinical recommendations
        """
        try:
            recommendations = []

            for result in biomarker_results:
                biomarker = result.get("gene_symbol")
                disease = patient_context.get("disease_type")

                # Get evidence for biomarker-disease pair
                evidence = await self._get_evidence_for_biomarker(biomarker, disease)

                if evidence:
                    # Generate recommendation based on evidence
                    recommendation = await self._generate_recommendation(
                        biomarker, disease, evidence, patient_context
                    )
                    recommendations.append(recommendation)

            # Rank recommendations by clinical significance
            recommendations = self._rank_recommendations(recommendations)

            return recommendations

        except Exception as e:
            logger.error(f"Error generating clinical recommendations: {str(e)}")
            raise

    async def _get_evidence_for_biomarker(
        self, biomarker: str, disease: str
    ) -> List[ClinicalEvidence]:
        """Get clinical evidence for biomarker-disease pair"""

        key = f"{biomarker}_{disease}"
        return self.evidence_database.get(key, [])

    async def _generate_recommendation(
        self,
        biomarker: str,
        disease: str,
        evidence: List[ClinicalEvidence],
        patient_context: Dict[str, Any],
    ) -> ClinicalRecommendation:
        """Generate clinical recommendation based on evidence"""

        # Calculate evidence strength
        evidence_strength = self._calculate_evidence_strength(evidence)

        # Determine recommendation strength
        if evidence_strength >= 0.8:
            strength = "strong"
        elif evidence_strength >= 0.6:
            strength = "moderate"
        else:
            strength = "weak"

        # Generate recommendation text
        recommendation_text = self._generate_recommendation_text(
            biomarker, disease, evidence, strength
        )

        # Determine contraindications
        contraindications = self._determine_contraindications(
            biomarker, disease, patient_context
        )

        # Determine monitoring requirements
        monitoring_requirements = self._determine_monitoring_requirements(
            biomarker, disease, evidence
        )

        return ClinicalRecommendation(
            recommendation_id=f"rec_{biomarker}_{disease}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            biomarker=biomarker,
            clinical_context=disease,
            recommendation=recommendation_text,
            evidence_level=self._get_highest_evidence_level(evidence),
            strength=strength,
            contraindications=contraindications,
            monitoring_requirements=monitoring_requirements,
            follow_up_period=self._determine_follow_up_period(evidence),
            cost_effectiveness=self._assess_cost_effectiveness(evidence),
            implementation_notes=self._generate_implementation_notes(
                biomarker, disease
            ),
        )

    def _calculate_evidence_strength(self, evidence: List[ClinicalEvidence]) -> float:
        """Calculate evidence strength score"""

        if not evidence:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for e in evidence:
            # Weight by evidence level
            level_weight = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4}.get(
                e.evidence_level, 0.2
            )

            # Weight by study type
            study_weight = {
                "RCT": 1.0,
                "meta-analysis": 0.9,
                "cohort": 0.7,
                "case-control": 0.5,
                "guideline": 0.8,
            }.get(e.study_type, 0.3)

            # Weight by sample size
            sample_weight = min(1.0, e.sample_size / 1000)

            # Weight by journal impact factor
            impact_weight = min(1.0, e.journal_impact_factor / 20)

            # Weight by recency
            recency_weight = max(0.5, 1.0 - (2024 - e.publication_year) / 10)

            # Calculate weighted score
            weight = (
                level_weight
                * study_weight
                * sample_weight
                * impact_weight
                * recency_weight
            )
            score = weight * (1.0 - e.p_value) * abs(e.effect_size)

            total_score += score
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _generate_recommendation_text(
        self,
        biomarker: str,
        disease: str,
        evidence: List[ClinicalEvidence],
        strength: str,
    ) -> str:
        """Generate recommendation text"""

        if strength == "strong":
            return f"Strong evidence supports the use of {biomarker} as a biomarker for {disease}. Consider incorporating into clinical decision-making."
        elif strength == "moderate":
            return f"Moderate evidence supports the use of {biomarker} as a biomarker for {disease}. Consider for research or limited clinical use."
        else:
            return f"Weak evidence for {biomarker} as a biomarker for {disease}. Further research needed before clinical application."

    def _determine_contraindications(
        self, biomarker: str, disease: str, patient_context: Dict[str, Any]
    ) -> List[str]:
        """Determine contraindications"""

        contraindications = []

        # Age-related contraindications
        if patient_context.get("age", 0) < 18:
            contraindications.append("Not recommended for pediatric patients")

        # Comorbidity contraindications
        comorbidities = patient_context.get("comorbidities", [])
        if "liver_disease" in comorbidities:
            contraindications.append("Use with caution in patients with liver disease")

        # Medication contraindications
        medications = patient_context.get("medications", [])
        if "warfarin" in medications:
            contraindications.append("Monitor for drug interactions with warfarin")

        return contraindications

    def _determine_monitoring_requirements(
        self, biomarker: str, disease: str, evidence: List[ClinicalEvidence]
    ) -> List[str]:
        """Determine monitoring requirements"""

        monitoring = []

        # Based on evidence level
        if any(e.evidence_level == "A" for e in evidence):
            monitoring.append("Regular monitoring every 3-6 months")

        # Based on clinical significance
        if any(e.clinical_significance == "high" for e in evidence):
            monitoring.append("Close monitoring for treatment response")

        # Based on study type
        if any(e.study_type == "RCT" for e in evidence):
            monitoring.append("Monitor for adverse events")

        return monitoring

    def _determine_follow_up_period(self, evidence: List[ClinicalEvidence]) -> int:
        """Determine follow-up period in months"""

        if not evidence:
            return 12

        # Based on evidence level and study type
        if any(e.evidence_level == "A" for e in evidence):
            return 6
        elif any(e.evidence_level == "B" for e in evidence):
            return 12
        else:
            return 24

    def _assess_cost_effectiveness(self, evidence: List[ClinicalEvidence]) -> str:
        """Assess cost-effectiveness"""

        if not evidence:
            return "Unknown"

        # Simple cost-effectiveness assessment
        high_quality_evidence = any(e.evidence_level in ["A", "B"] for e in evidence)
        large_sample_size = any(e.sample_size > 1000 for e in evidence)

        if high_quality_evidence and large_sample_size:
            return "Cost-effective"
        elif high_quality_evidence:
            return "Moderately cost-effective"
        else:
            return "Cost-effectiveness unclear"

    def _generate_implementation_notes(self, biomarker: str, disease: str) -> str:
        """Generate implementation notes"""

        return f"""
        Implementation Notes for {biomarker} in {disease}:
        
        1. Ensure proper sample collection and handling
        2. Validate biomarker measurement methods
        3. Consider patient consent and privacy
        4. Document clinical decision-making process
        5. Monitor patient outcomes and biomarker performance
        """

    def _get_highest_evidence_level(self, evidence: List[ClinicalEvidence]) -> str:
        """Get highest evidence level"""

        if not evidence:
            return "D"

        levels = [e.evidence_level for e in evidence]
        level_order = {"A": 4, "B": 3, "C": 2, "D": 1}
        return max(levels, key=lambda x: level_order.get(x, 0))

    def _rank_recommendations(
        self, recommendations: List[ClinicalRecommendation]
    ) -> List[ClinicalRecommendation]:
        """Rank recommendations by clinical significance"""

        def ranking_score(rec):
            strength_scores = {"strong": 3, "moderate": 2, "weak": 1}
            evidence_scores = {"A": 4, "B": 3, "C": 2, "D": 1}

            return strength_scores.get(rec.strength, 0) + evidence_scores.get(
                rec.evidence_level, 0
            )

        return sorted(recommendations, key=ranking_score, reverse=True)

    async def validate_clinical_decision(
        self, biomarker: str, clinical_decision: str, patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate clinical decision against evidence and guidelines

        Args:
            biomarker: Biomarker name
            clinical_decision: Clinical decision made
            patient_context: Patient clinical context

        Returns:
            Validation result
        """
        try:
            # Get relevant evidence
            evidence = await self._get_evidence_for_biomarker(
                biomarker, patient_context.get("disease_type")
            )

            # Validate against guidelines
            guideline_validation = await self._validate_against_guidelines(
                biomarker, clinical_decision, patient_context
            )

            # Validate against evidence
            evidence_validation = await self._validate_against_evidence(
                biomarker, clinical_decision, evidence
            )

            # Calculate overall validation score
            validation_score = self._calculate_validation_score(
                guideline_validation, evidence_validation
            )

            return {
                "biomarker": biomarker,
                "clinical_decision": clinical_decision,
                "validation_score": validation_score,
                "guideline_validation": guideline_validation,
                "evidence_validation": evidence_validation,
                "recommendations": self._generate_validation_recommendations(
                    validation_score, guideline_validation, evidence_validation
                ),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error validating clinical decision: {str(e)}")
            raise

    async def assess_evidence_quality(
        self, genes: List[str], patient_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Summarize evidence strength per gene (for API / UI)."""
        disease = patient_context.get("disease_type") or patient_context.get("disease")
        out: List[Dict[str, Any]] = []
        for g in genes:
            if not g:
                continue
            evidence = await self._get_evidence_for_biomarker(g, disease)
            strength = self._calculate_evidence_strength(evidence)
            tier = self._get_highest_evidence_level(evidence) if evidence else "D"
            out.append(
                {
                    "gene": g,
                    "evidence_tier": tier,
                    "evidence_strength_score": round(float(strength), 4),
                    "study_count": len(evidence),
                    "has_guideline_match": bool(self.clinical_guidelines),
                }
            )
        return out

    async def _validate_against_guidelines(
        self, biomarker: str, clinical_decision: str, patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate against clinical guidelines. Returns neutral result when no guidelines loaded."""

        if not self.clinical_guidelines:
            return {
                "guideline_compliance": None,
                "guideline_references": [],
                "compliance_score": 0.0,
                "message": "No clinical guidelines loaded for validation",
            }
        # Actual guideline validation would compare against self.clinical_guidelines
        return {
            "guideline_compliance": None,
            "guideline_references": [],
            "compliance_score": 0.0,
            "message": "Guideline validation requires rule matching implementation",
        }

    async def _validate_against_evidence(
        self, biomarker: str, clinical_decision: str, evidence: List[ClinicalEvidence]
    ) -> Dict[str, Any]:
        """Validate against clinical evidence"""

        if not evidence:
            return {
                "evidence_support": False,
                "evidence_quality": "low",
                "evidence_score": 0.0,
            }

        # Calculate evidence support score
        evidence_scores = []
        for e in evidence:
            score = (1.0 - e.p_value) * abs(e.effect_size)
            evidence_scores.append(score)

        evidence_score = np.mean(evidence_scores)

        return {
            "evidence_support": evidence_score > 0.5,
            "evidence_quality": self._get_highest_evidence_level(evidence),
            "evidence_score": evidence_score,
            "num_studies": len(evidence),
        }

    def _calculate_validation_score(
        self, guideline_validation: Dict[str, Any], evidence_validation: Dict[str, Any]
    ) -> float:
        """Calculate overall validation score"""

        guideline_score = guideline_validation.get("compliance_score", 0.0)
        evidence_score = evidence_validation.get("evidence_score", 0.0)

        # Weighted average
        return 0.6 * guideline_score + 0.4 * evidence_score

    def _generate_validation_recommendations(
        self,
        validation_score: float,
        guideline_validation: Dict[str, Any],
        evidence_validation: Dict[str, Any],
    ) -> List[str]:
        """Generate validation recommendations"""

        recommendations = []

        if validation_score < 0.5:
            recommendations.append(
                "Consider additional evidence before making clinical decision"
            )

        if not guideline_validation.get("guideline_compliance", False):
            recommendations.append("Review clinical guidelines for compliance")

        if not evidence_validation.get("evidence_support", False):
            recommendations.append(
                "Limited evidence support - consider alternative approaches"
            )

        return recommendations


class ClinicalRecommendationEngine:
    """Clinical recommendation engine using machine learning"""

    def __init__(self):
        self.model = None
        self.feature_encoder = None

    async def initialize(self):
        """Initialize recommendation engine"""
        try:
            # Load training data
            training_data = await self._load_training_data()

            # Train model
            await self._train_model(training_data)

        except Exception as e:
            logger.error(f"Error initializing recommendation engine: {str(e)}")
            raise

    async def _load_training_data(self):
        """Load training data for recommendation engine"""
        try:
            with db_session() as db:
                # Load historical clinical recommendations
                from app.models.clinical import (
                    ClinicalRecommendation as ClinicalRecommendationModel,
                )

                recommendations = db.query(ClinicalRecommendationModel).all()

            # Convert to training format
            training_data = []
            for rec in recommendations:
                training_data.append(
                    {
                        "biomarker": rec.biomarker,
                        "disease": rec.clinical_context,
                        "evidence_level": rec.evidence_level,
                        "strength": rec.strength,
                        "outcome": "success",  # Simplified - would need actual outcome data
                    }
                )

            return training_data

        except Exception as e:
            logger.error(f"Error loading training data: {str(e)}")
            return []

    async def _train_model(self, training_data):
        """Train recommendation model"""
        try:
            if not training_data or len(training_data) < 10:
                logger.warning("Insufficient training data, using default model")
                self.model = RandomForestClassifier(n_estimators=100, random_state=42)
                return

            import pandas as pd

            df = pd.DataFrame(training_data)

            # Feature encoding
            from sklearn.preprocessing import LabelEncoder

            self.feature_encoder = {}

            for col in ["biomarker", "disease", "evidence_level"]:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col])
                self.feature_encoder[col] = le

            # Prepare features and target
            X = df[["biomarker", "disease", "evidence_level"]]
            y = df["strength"]

            # Train model
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.model.fit(X, y)

            logger.info("Recommendation model trained successfully")

        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            # Fallback to simple model
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)


class ClinicalValidationFramework:
    """Clinical validation framework"""

    def __init__(self):
        self.validation_rules = {}

    async def initialize(self):
        """Initialize validation framework"""
        try:
            # Load validation rules
            await self._load_validation_rules()

        except Exception as e:
            logger.error(f"Error initializing validation framework: {str(e)}")
            raise

    async def _load_validation_rules(self):
        """Load clinical validation rules"""
        try:
            with db_session() as db:
                # Load validation rules from database
                from app.models.clinical import ClinicalGuideline

                guidelines = db.query(ClinicalGuideline).all()

            # Build validation rules from guidelines
            self.validation_rules = {}
            for guideline in guidelines:
                rule_key = f"{guideline.disease_type}_{guideline.biomarker_type}"
                self.validation_rules[rule_key] = {
                    "min_evidence_level": guideline.min_evidence_level or "C",
                    "required_validation": guideline.required_validation or False,
                    "validation_criteria": guideline.validation_criteria or {},
                    "compliance_requirements": guideline.compliance_requirements or [],
                }

            logger.info(f"Loaded {len(self.validation_rules)} validation rules")

        except Exception as e:
            logger.error(f"Error loading validation rules: {str(e)}")
            # Default validation rules
            self.validation_rules = {
                "default": {
                    "min_evidence_level": "C",
                    "required_validation": False,
                    "validation_criteria": {},
                    "compliance_requirements": [],
                }
            }

    async def validate_clinical_decision(
        self, biomarker: str, disease: str, clinical_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate clinical decision against rules

        Args:
            biomarker: Biomarker name
            disease: Disease type
            clinical_decision: Clinical decision data

        Returns:
            Validation result
        """
        try:
            rule_key = f"{disease}_{biomarker}"
            rule = self.validation_rules.get(
                rule_key, self.validation_rules.get("default")
            )

            validation_result = {
                "valid": True,
                "warnings": [],
                "errors": [],
                "compliance_score": 1.0,
            }

            # Check evidence level
            evidence_level = clinical_decision.get("evidence_level", "D")
            min_level = rule.get("min_evidence_level", "C")

            level_order = {"A": 4, "B": 3, "C": 2, "D": 1}
            if level_order.get(evidence_level, 0) < level_order.get(min_level, 0):
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Evidence level {evidence_level} below required {min_level}"
                )
                validation_result["compliance_score"] -= 0.3

            # Check required validation
            if rule.get("required_validation", False):
                if not clinical_decision.get("validated", False):
                    validation_result["warnings"].append(
                        "Clinical validation required but not completed"
                    )
                    validation_result["compliance_score"] -= 0.2

            # Check compliance requirements
            compliance_reqs = rule.get("compliance_requirements", [])
            for req in compliance_reqs:
                if req not in clinical_decision.get("compliance", []):
                    validation_result["warnings"].append(
                        f"Compliance requirement not met: {req}"
                    )
                    validation_result["compliance_score"] -= 0.1

            validation_result["compliance_score"] = max(
                0.0, validation_result["compliance_score"]
            )

            return validation_result

        except Exception as e:
            logger.error(f"Error validating clinical decision: {str(e)}")
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "compliance_score": 0.0,
            }


# Global clinical decision support service instance
clinical_decision_support_service = ClinicalDecisionSupportService()

_cds_init_lock = asyncio.Lock()
_cds_initialized = False


async def ensure_cds_ready() -> None:
    """Lazy-init CDS (evidence DB may be empty; engine init may warn)."""
    global _cds_initialized
    async with _cds_init_lock:
        if _cds_initialized:
            return
        try:
            await clinical_decision_support_service.initialize_service()
        except Exception as e:
            logger.warning("CDS initialize_service partial failure: %s", e)
        _cds_initialized = True


def clinical_recommendation_to_dict(rec: ClinicalRecommendation) -> Dict[str, Any]:
    """JSON-serialize a recommendation dataclass."""
    return {
        "recommendation_id": rec.recommendation_id,
        "biomarker": rec.biomarker,
        "clinical_context": rec.clinical_context,
        "recommendation": rec.recommendation,
        "evidence_level": rec.evidence_level,
        "strength": rec.strength,
        "contraindications": list(rec.contraindications),
        "monitoring_requirements": list(rec.monitoring_requirements),
        "follow_up_period_months": rec.follow_up_period,
        "cost_effectiveness": rec.cost_effectiveness,
        "implementation_notes": rec.implementation_notes,
    }
