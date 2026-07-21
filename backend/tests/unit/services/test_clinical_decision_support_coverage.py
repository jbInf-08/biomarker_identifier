"""
Self-contained coverage tests for app.services.clinical_decision_support.

Runs with --noconftest: no fixtures from tests/conftest.py are used.
All DB access is mocked; all async entry points are driven with asyncio.run().
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.clinical_decision_support as cds
from app.services.clinical_decision_support import (
    ClinicalDecisionSupportService,
    ClinicalEvidence,
    ClinicalRecommendation,
    ClinicalRecommendationEngine,
    ClinicalValidationFramework,
    clinical_recommendation_to_dict,
    ensure_cds_ready,
)

MODULE = "app.services.clinical_decision_support"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def run(coro):
    """Drive a coroutine without depending on pytest-asyncio."""
    return asyncio.run(coro)


def make_evidence(
    evidence_id="ev1",
    biomarker="TP53",
    disease="lung_cancer",
    evidence_level="A",
    clinical_significance="high",
    study_type="RCT",
    sample_size=2000,
    p_value=0.01,
    effect_size=1.5,
    confidence_interval=(1.1, 2.0),
    publication_year=2023,
    journal_impact_factor=30.0,
    citation_count=120,
):
    return ClinicalEvidence(
        evidence_id=evidence_id,
        biomarker=biomarker,
        disease=disease,
        evidence_level=evidence_level,
        clinical_significance=clinical_significance,
        study_type=study_type,
        sample_size=sample_size,
        p_value=p_value,
        effect_size=effect_size,
        confidence_interval=confidence_interval,
        publication_year=publication_year,
        journal_impact_factor=journal_impact_factor,
        citation_count=citation_count,
    )


def make_recommendation(
    strength="strong", evidence_level="A", biomarker="TP53"
) -> ClinicalRecommendation:
    return ClinicalRecommendation(
        recommendation_id=f"rec_{biomarker}",
        biomarker=biomarker,
        clinical_context="lung_cancer",
        recommendation="text",
        evidence_level=evidence_level,
        strength=strength,
        contraindications=["c1"],
        monitoring_requirements=["m1"],
        follow_up_period=6,
        cost_effectiveness="Cost-effective",
        implementation_notes="notes",
    )


@contextlib.contextmanager
def patched_db(query_result):
    """Patch the module-level db_session with a context manager yielding a mock db."""
    db = MagicMock()
    db.query.return_value.all.return_value = query_result

    @contextlib.contextmanager
    def fake_session():
        yield db

    with patch(f"{MODULE}.db_session", fake_session):
        yield db


@pytest.fixture()
def service():
    return ClinicalDecisionSupportService()


# --------------------------------------------------------------------------
# dataclasses / helpers
# --------------------------------------------------------------------------


def test_clinical_evidence_dataclass_fields():
    ev = make_evidence()
    assert ev.evidence_id == "ev1"
    assert ev.confidence_interval == (1.1, 2.0)
    assert ev.citation_count == 120


def test_clinical_recommendation_to_dict_shape():
    rec = make_recommendation()
    d = clinical_recommendation_to_dict(rec)
    assert set(d) == {
        "recommendation_id",
        "biomarker",
        "clinical_context",
        "recommendation",
        "evidence_level",
        "strength",
        "contraindications",
        "monitoring_requirements",
        "follow_up_period_months",
        "cost_effectiveness",
        "implementation_notes",
    }
    assert d["follow_up_period_months"] == 6
    assert d["contraindications"] == ["c1"]


def test_service_initial_state(service):
    assert service.evidence_database == {}
    assert service.clinical_guidelines == {}
    assert service.recommendation_engine is None
    assert service.validation_framework is None


# --------------------------------------------------------------------------
# _calculate_evidence_strength
# --------------------------------------------------------------------------


def test_calculate_evidence_strength_empty(service):
    assert service._calculate_evidence_strength([]) == 0.0


def test_calculate_evidence_strength_positive(service):
    score = service._calculate_evidence_strength([make_evidence()])
    assert score == pytest.approx(0.99 * 1.5)


def test_calculate_evidence_strength_zero_weight_returns_zero(service):
    # sample_size 0 -> sample_weight 0 -> total_weight 0 -> guarded branch
    ev = make_evidence(sample_size=0)
    assert service._calculate_evidence_strength([ev]) == 0.0


def test_calculate_evidence_strength_unknown_level_and_study_type(service):
    ev = make_evidence(
        evidence_level="Z", study_type="unknown-design", publication_year=1990
    )
    score = service._calculate_evidence_strength([ev])
    assert score > 0.0


def test_calculate_evidence_strength_multiple_studies(service):
    evs = [
        make_evidence(evidence_level="B", study_type="cohort"),
        make_evidence(evidence_level="C", study_type="case-control", effect_size=-0.8),
        make_evidence(evidence_level="D", study_type="meta-analysis"),
    ]
    score = service._calculate_evidence_strength(evs)
    assert 0.0 < score < 5.0


# --------------------------------------------------------------------------
# text / classification helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "strength,needle",
    [
        ("strong", "Strong evidence supports"),
        ("moderate", "Moderate evidence supports"),
        ("weak", "Weak evidence for"),
    ],
)
def test_generate_recommendation_text_branches(service, strength, needle):
    text = service._generate_recommendation_text("TP53", "lung_cancer", [], strength)
    assert needle in text
    assert "TP53" in text and "lung_cancer" in text


def test_determine_contraindications_none(service):
    out = service._determine_contraindications(
        "TP53", "lung_cancer", {"age": 55, "comorbidities": [], "medications": []}
    )
    assert out == []


def test_determine_contraindications_all_branches(service):
    out = service._determine_contraindications(
        "TP53",
        "lung_cancer",
        {
            "age": 10,
            "comorbidities": ["liver_disease"],
            "medications": ["warfarin"],
        },
    )
    assert len(out) == 3
    assert any("pediatric" in c for c in out)
    assert any("liver disease" in c for c in out)
    assert any("warfarin" in c for c in out)


def test_determine_contraindications_missing_keys_defaults(service):
    # age defaults to 0 -> pediatric contraindication fires
    out = service._determine_contraindications("TP53", "lung_cancer", {})
    assert out == ["Not recommended for pediatric patients"]


def test_determine_monitoring_requirements_all(service):
    out = service._determine_monitoring_requirements("TP53", "d", [make_evidence()])
    assert len(out) == 3


def test_determine_monitoring_requirements_none(service):
    ev = make_evidence(
        evidence_level="C", clinical_significance="low", study_type="cohort"
    )
    assert service._determine_monitoring_requirements("TP53", "d", [ev]) == []


@pytest.mark.parametrize(
    "levels,expected",
    [
        ([], 12),
        (["A"], 6),
        (["B"], 12),
        (["C", "D"], 24),
    ],
)
def test_determine_follow_up_period(service, levels, expected):
    evidence = [make_evidence(evidence_level=lv) for lv in levels]
    assert service._determine_follow_up_period(evidence) == expected


def test_assess_cost_effectiveness_unknown(service):
    assert service._assess_cost_effectiveness([]) == "Unknown"


def test_assess_cost_effectiveness_cost_effective(service):
    ev = make_evidence(evidence_level="A", sample_size=5000)
    assert service._assess_cost_effectiveness([ev]) == "Cost-effective"


def test_assess_cost_effectiveness_moderate(service):
    ev = make_evidence(evidence_level="B", sample_size=50)
    assert service._assess_cost_effectiveness([ev]) == "Moderately cost-effective"


def test_assess_cost_effectiveness_unclear(service):
    ev = make_evidence(evidence_level="C", sample_size=50)
    assert service._assess_cost_effectiveness([ev]) == "Cost-effectiveness unclear"


def test_generate_implementation_notes(service):
    notes = service._generate_implementation_notes("TP53", "lung_cancer")
    assert "TP53" in notes and "lung_cancer" in notes
    assert "Implementation Notes" in notes


def test_get_highest_evidence_level_empty(service):
    assert service._get_highest_evidence_level([]) == "D"


def test_get_highest_evidence_level_mixed(service):
    evs = [make_evidence(evidence_level=lv) for lv in ["C", "A", "D"]]
    assert service._get_highest_evidence_level(evs) == "A"


def test_get_highest_evidence_level_unknown_label(service):
    evs = [make_evidence(evidence_level="Z"), make_evidence(evidence_level="C")]
    assert service._get_highest_evidence_level(evs) == "C"


def test_rank_recommendations_orders_descending(service):
    weak = make_recommendation(strength="weak", evidence_level="D", biomarker="A1")
    strong = make_recommendation(strength="strong", evidence_level="A", biomarker="A2")
    mod = make_recommendation(strength="moderate", evidence_level="B", biomarker="A3")
    ranked = service._rank_recommendations([weak, strong, mod])
    assert [r.biomarker for r in ranked] == ["A2", "A3", "A1"]


def test_rank_recommendations_unknown_labels(service):
    rec = make_recommendation(strength="???", evidence_level="???")
    assert service._rank_recommendations([rec]) == [rec]


def test_calculate_validation_score_weighting(service):
    score = service._calculate_validation_score(
        {"compliance_score": 1.0}, {"evidence_score": 0.5}
    )
    assert score == pytest.approx(0.6 * 1.0 + 0.4 * 0.5)


def test_calculate_validation_score_missing_keys(service):
    assert service._calculate_validation_score({}, {}) == pytest.approx(0.0)


def test_generate_validation_recommendations_all_fire(service):
    out = service._generate_validation_recommendations(0.1, {}, {})
    assert len(out) == 3


def test_generate_validation_recommendations_none_fire(service):
    out = service._generate_validation_recommendations(
        0.9, {"guideline_compliance": True}, {"evidence_support": True}
    )
    assert out == []


# --------------------------------------------------------------------------
# async evidence loaders
# --------------------------------------------------------------------------


def test_external_evidence_loaders_return_empty(service):
    assert run(service._load_pubmed_evidence()) == []
    assert run(service._load_clinical_trials_evidence()) == []
    assert run(service._load_guideline_evidence()) == []


def test_load_evidence_database_empty_sources(service):
    run(service._load_evidence_database())
    assert service.evidence_database == {}


def test_load_evidence_database_groups_by_key(service):
    ev_a = make_evidence(biomarker="TP53", disease="lung_cancer")
    ev_b = make_evidence(biomarker="TP53", disease="lung_cancer", evidence_id="ev2")
    ev_c = make_evidence(biomarker="EGFR", disease="lung_cancer")
    with patch.object(
        service, "_load_pubmed_evidence", AsyncMock(return_value=[ev_a, ev_b])
    ), patch.object(
        service, "_load_clinical_trials_evidence", AsyncMock(return_value=[ev_c])
    ), patch.object(
        service, "_load_guideline_evidence", AsyncMock(return_value=[])
    ):
        run(service._load_evidence_database())

    assert set(service.evidence_database) == {"TP53_lung_cancer", "EGFR_lung_cancer"}
    assert len(service.evidence_database["TP53_lung_cancer"]) == 2


def test_load_evidence_database_raises_on_source_error(service):
    with patch.object(
        service, "_load_pubmed_evidence", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        with pytest.raises(RuntimeError):
            run(service._load_evidence_database())


def test_load_clinical_guidelines_success(service):
    g1 = MagicMock()
    g1.guideline_id = "G1"
    g2 = MagicMock()
    g2.guideline_id = "G2"
    with patched_db([g1, g2]):
        run(service._load_clinical_guidelines())
    assert set(service.clinical_guidelines) == {"G1", "G2"}


def test_load_clinical_guidelines_raises(service):
    with patch(f"{MODULE}.db_session", side_effect=RuntimeError("db down")):
        with pytest.raises(RuntimeError):
            run(service._load_clinical_guidelines())


# --------------------------------------------------------------------------
# initialization
# --------------------------------------------------------------------------


def test_initialize_recommendation_engine(service):
    engine = MagicMock()
    engine.initialize = AsyncMock()
    with patch(f"{MODULE}.ClinicalRecommendationEngine", return_value=engine):
        run(service._initialize_recommendation_engine())
    assert service.recommendation_engine is engine
    engine.initialize.assert_awaited_once()


def test_initialize_recommendation_engine_raises(service):
    with patch(
        f"{MODULE}.ClinicalRecommendationEngine", side_effect=RuntimeError("nope")
    ):
        with pytest.raises(RuntimeError):
            run(service._initialize_recommendation_engine())


def test_initialize_validation_framework(service):
    fw = MagicMock()
    fw.initialize = AsyncMock()
    with patch(f"{MODULE}.ClinicalValidationFramework", return_value=fw):
        run(service._initialize_validation_framework())
    assert service.validation_framework is fw


def test_initialize_validation_framework_raises(service):
    with patch(
        f"{MODULE}.ClinicalValidationFramework", side_effect=RuntimeError("nope")
    ):
        with pytest.raises(RuntimeError):
            run(service._initialize_validation_framework())


def test_initialize_service_success(service):
    with patch.object(service, "_load_evidence_database", AsyncMock()), patch.object(
        service, "_load_clinical_guidelines", AsyncMock()
    ), patch.object(
        service, "_initialize_recommendation_engine", AsyncMock()
    ), patch.object(
        service, "_initialize_validation_framework", AsyncMock()
    ):
        run(service.initialize_service())


def test_initialize_service_raises(service):
    with patch.object(
        service, "_load_evidence_database", AsyncMock(side_effect=RuntimeError("x"))
    ):
        with pytest.raises(RuntimeError):
            run(service.initialize_service())


# --------------------------------------------------------------------------
# recommendation generation
# --------------------------------------------------------------------------


def test_get_evidence_for_biomarker_hit_and_miss(service):
    ev = make_evidence()
    service.evidence_database["TP53_lung_cancer"] = [ev]
    assert run(service._get_evidence_for_biomarker("TP53", "lung_cancer")) == [ev]
    assert run(service._get_evidence_for_biomarker("EGFR", "lung_cancer")) == []


def test_generate_recommendation_strong(service):
    ev = make_evidence()
    rec = run(
        service._generate_recommendation(
            "TP53", "lung_cancer", [ev], {"age": 40, "comorbidities": []}
        )
    )
    assert isinstance(rec, ClinicalRecommendation)
    assert rec.strength == "strong"
    assert rec.evidence_level == "A"
    assert rec.follow_up_period == 6
    assert rec.cost_effectiveness == "Cost-effective"
    assert rec.recommendation_id.startswith("rec_TP53_lung_cancer_")


def test_generate_recommendation_moderate(service):
    # tune effect size so evidence strength lands in [0.6, 0.8)
    ev = make_evidence(effect_size=0.7)
    rec = run(service._generate_recommendation("TP53", "d", [ev], {"age": 40}))
    assert rec.strength == "moderate"


def test_generate_recommendation_weak(service):
    ev = make_evidence(effect_size=0.1, evidence_level="C", study_type="cohort")
    rec = run(service._generate_recommendation("TP53", "d", [ev], {"age": 40}))
    assert rec.strength == "weak"
    assert "Weak evidence" in rec.recommendation


def test_generate_clinical_recommendations_with_evidence(service):
    service.evidence_database["TP53_lung_cancer"] = [make_evidence()]
    service.evidence_database["EGFR_lung_cancer"] = [
        make_evidence(
            biomarker="EGFR", evidence_level="C", effect_size=0.1, study_type="cohort"
        )
    ]
    results = [
        {"gene_symbol": "TP53"},
        {"gene_symbol": "EGFR"},
        {"gene_symbol": "KRAS"},
    ]
    recs = run(
        service.generate_clinical_recommendations(
            results, {"disease_type": "lung_cancer", "age": 60}
        )
    )
    assert [r.biomarker for r in recs] == ["TP53", "EGFR"]
    assert recs[0].strength == "strong"


def test_generate_clinical_recommendations_no_evidence(service):
    recs = run(
        service.generate_clinical_recommendations(
            [{"gene_symbol": "TP53"}], {"disease_type": "lung_cancer"}
        )
    )
    assert recs == []


def test_generate_clinical_recommendations_empty_input(service):
    assert run(service.generate_clinical_recommendations([], {})) == []


def test_generate_clinical_recommendations_raises_on_bad_shape(service):
    with pytest.raises(AttributeError):
        run(service.generate_clinical_recommendations([None], {"disease_type": "d"}))


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def test_validate_against_guidelines_no_guidelines(service):
    out = run(service._validate_against_guidelines("TP53", "treat", {}))
    assert out["guideline_compliance"] is None
    assert out["compliance_score"] == 0.0
    assert "No clinical guidelines loaded" in out["message"]


def test_validate_against_guidelines_with_guidelines(service):
    service.clinical_guidelines = {"G1": MagicMock()}
    out = run(service._validate_against_guidelines("TP53", "treat", {}))
    assert "rule matching" in out["message"]
    assert out["guideline_references"] == []


def test_validate_against_evidence_empty(service):
    out = run(service._validate_against_evidence("TP53", "treat", []))
    assert out == {
        "evidence_support": False,
        "evidence_quality": "low",
        "evidence_score": 0.0,
    }


def test_validate_against_evidence_supported(service):
    out = run(service._validate_against_evidence("TP53", "treat", [make_evidence()]))
    # numpy bool_ (np.mean result comparison), so compare by value not identity
    assert bool(out["evidence_support"]) is True
    assert out["evidence_quality"] == "A"
    assert out["evidence_score"] == pytest.approx(0.99 * 1.5)
    assert out["num_studies"] == 1


def test_validate_against_evidence_unsupported(service):
    ev = make_evidence(effect_size=0.1, evidence_level="D")
    out = run(service._validate_against_evidence("TP53", "treat", [ev]))
    assert bool(out["evidence_support"]) is False
    assert out["evidence_quality"] == "D"


def test_validate_clinical_decision_full(service):
    service.evidence_database["TP53_lung_cancer"] = [make_evidence()]
    out = run(
        service.validate_clinical_decision(
            "TP53", "start therapy", {"disease_type": "lung_cancer"}
        )
    )
    assert out["biomarker"] == "TP53"
    assert out["clinical_decision"] == "start therapy"
    assert out["validation_score"] == pytest.approx(0.4 * 0.99 * 1.5)
    assert "timestamp" in out
    assert isinstance(out["recommendations"], list)
    assert out["evidence_validation"]["num_studies"] == 1


def test_validate_clinical_decision_no_evidence(service):
    out = run(service.validate_clinical_decision("TP53", "watch", {}))
    assert out["validation_score"] == pytest.approx(0.0)
    assert len(out["recommendations"]) == 3


def test_validate_clinical_decision_raises(service):
    with patch.object(
        service,
        "_get_evidence_for_biomarker",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(RuntimeError):
            run(service.validate_clinical_decision("TP53", "watch", {}))


# --------------------------------------------------------------------------
# assess_evidence_quality
# --------------------------------------------------------------------------


def test_assess_evidence_quality_basic(service):
    service.evidence_database["TP53_lung_cancer"] = [make_evidence()]
    out = run(
        service.assess_evidence_quality(
            ["TP53", "", None, "EGFR"], {"disease_type": "lung_cancer"}
        )
    )
    assert [row["gene"] for row in out] == ["TP53", "EGFR"]
    assert out[0]["evidence_tier"] == "A"
    assert out[0]["study_count"] == 1
    assert out[0]["evidence_strength_score"] == pytest.approx(1.485, abs=1e-3)
    assert out[0]["has_guideline_match"] is False
    assert out[1]["evidence_tier"] == "D"
    assert out[1]["study_count"] == 0


def test_assess_evidence_quality_disease_fallback_key(service):
    service.evidence_database["TP53_colon"] = [make_evidence(disease="colon")]
    service.clinical_guidelines = {"G1": MagicMock()}
    out = run(service.assess_evidence_quality(["TP53"], {"disease": "colon"}))
    assert out[0]["study_count"] == 1
    assert out[0]["has_guideline_match"] is True


def test_assess_evidence_quality_empty_gene_list(service):
    assert run(service.assess_evidence_quality([], {})) == []


# --------------------------------------------------------------------------
# ClinicalRecommendationEngine
# --------------------------------------------------------------------------


def test_engine_initial_state():
    engine = ClinicalRecommendationEngine()
    assert engine.model is None
    assert engine.feature_encoder is None


def test_engine_initialize_with_insufficient_data():
    engine = ClinicalRecommendationEngine()
    with patch.object(engine, "_load_training_data", AsyncMock(return_value=[])):
        run(engine.initialize())
    assert engine.model is not None
    assert engine.feature_encoder is None


def test_engine_initialize_raises():
    engine = ClinicalRecommendationEngine()
    with patch.object(
        engine, "_load_training_data", AsyncMock(side_effect=RuntimeError("x"))
    ):
        with pytest.raises(RuntimeError):
            run(engine.initialize())


def test_engine_load_training_data_success():
    engine = ClinicalRecommendationEngine()
    rec = MagicMock()
    rec.biomarker = "TP53"
    rec.clinical_context = "lung_cancer"
    rec.evidence_level = "A"
    rec.strength = "strong"
    with patched_db([rec, rec]):
        data = run(engine._load_training_data())
    assert len(data) == 2
    assert data[0] == {
        "biomarker": "TP53",
        "disease": "lung_cancer",
        "evidence_level": "A",
        "strength": "strong",
        "outcome": "success",
    }


def test_engine_load_training_data_returns_empty_on_error():
    engine = ClinicalRecommendationEngine()
    with patch(f"{MODULE}.db_session", side_effect=RuntimeError("db down")):
        assert run(engine._load_training_data()) == []


def test_engine_train_model_trains_on_sufficient_data():
    engine = ClinicalRecommendationEngine()
    training = [
        {
            "biomarker": f"B{i % 3}",
            "disease": f"D{i % 2}",
            "evidence_level": "AB"[i % 2],
            "strength": "strong" if i % 2 else "weak",
            "outcome": "success",
        }
        for i in range(20)
    ]
    run(engine._train_model(training))
    assert engine.model is not None
    assert set(engine.feature_encoder) == {"biomarker", "disease", "evidence_level"}
    assert len(engine.model.predict([[0, 0, 0]])) == 1


def test_engine_train_model_falls_back_on_error():
    engine = ClinicalRecommendationEngine()
    # 'strength' column missing -> KeyError inside try -> fallback model
    training = [
        {"biomarker": "B", "disease": "D", "evidence_level": "A"} for _ in range(12)
    ]
    run(engine._train_model(training))
    assert engine.model is not None
    assert not hasattr(engine.model, "classes_")


# --------------------------------------------------------------------------
# ClinicalValidationFramework
# --------------------------------------------------------------------------


def test_framework_initialize_and_load_rules_success():
    fw = ClinicalValidationFramework()
    g = MagicMock()
    g.disease_type = "lung_cancer"
    g.biomarker_type = "TP53"
    g.min_evidence_level = "B"
    g.required_validation = True
    g.validation_criteria = {"k": "v"}
    g.compliance_requirements = ["CLIA"]
    with patched_db([g]):
        run(fw.initialize())
    assert "lung_cancer_TP53" in fw.validation_rules
    rule = fw.validation_rules["lung_cancer_TP53"]
    assert rule["min_evidence_level"] == "B"
    assert rule["required_validation"] is True
    assert rule["compliance_requirements"] == ["CLIA"]


def test_framework_initialize_reraises_rule_loading_error():
    fw = ClinicalValidationFramework()
    with patch.object(
        fw, "_load_validation_rules", AsyncMock(side_effect=RuntimeError("bad rules"))
    ):
        with pytest.raises(RuntimeError):
            run(fw.initialize())


def test_framework_load_rules_applies_defaults_for_null_columns():
    fw = ClinicalValidationFramework()
    g = MagicMock()
    g.disease_type = "d"
    g.biomarker_type = "b"
    g.min_evidence_level = None
    g.required_validation = None
    g.validation_criteria = None
    g.compliance_requirements = None
    with patched_db([g]):
        run(fw._load_validation_rules())
    rule = fw.validation_rules["d_b"]
    assert rule == {
        "min_evidence_level": "C",
        "required_validation": False,
        "validation_criteria": {},
        "compliance_requirements": [],
    }


def test_framework_load_rules_falls_back_to_default_on_error():
    fw = ClinicalValidationFramework()
    with patch(f"{MODULE}.db_session", side_effect=RuntimeError("db down")):
        run(fw._load_validation_rules())
    assert fw.validation_rules == {
        "default": {
            "min_evidence_level": "C",
            "required_validation": False,
            "validation_criteria": {},
            "compliance_requirements": [],
        }
    }


def test_framework_validate_decision_all_pass():
    fw = ClinicalValidationFramework()
    fw.validation_rules = {
        "default": {
            "min_evidence_level": "C",
            "required_validation": False,
            "compliance_requirements": [],
        }
    }
    out = run(
        fw.validate_clinical_decision("TP53", "lung_cancer", {"evidence_level": "A"})
    )
    assert out["valid"] is True
    assert out["errors"] == []
    assert out["warnings"] == []
    assert out["compliance_score"] == pytest.approx(1.0)


def test_framework_validate_decision_all_penalties():
    fw = ClinicalValidationFramework()
    fw.validation_rules = {
        "lung_cancer_TP53": {
            "min_evidence_level": "A",
            "required_validation": True,
            "compliance_requirements": ["CLIA"],
        }
    }
    out = run(
        fw.validate_clinical_decision(
            "TP53", "lung_cancer", {"evidence_level": "D", "compliance": []}
        )
    )
    assert out["valid"] is False
    assert len(out["errors"]) == 1
    assert len(out["warnings"]) == 2
    assert out["compliance_score"] == pytest.approx(0.4)


def test_framework_validate_decision_score_clamped_at_zero():
    fw = ClinicalValidationFramework()
    fw.validation_rules = {
        "default": {
            "min_evidence_level": "A",
            "required_validation": True,
            "compliance_requirements": [f"req{i}" for i in range(10)],
        }
    }
    out = run(fw.validate_clinical_decision("b", "d", {"evidence_level": "D"}))
    assert out["compliance_score"] == 0.0


def test_framework_validate_decision_compliance_requirement_met():
    fw = ClinicalValidationFramework()
    fw.validation_rules = {
        "default": {
            "min_evidence_level": "D",
            "required_validation": True,
            "compliance_requirements": ["CLIA"],
        }
    }
    out = run(
        fw.validate_clinical_decision(
            "b", "d", {"evidence_level": "D", "validated": True, "compliance": ["CLIA"]}
        )
    )
    assert out["warnings"] == []
    assert out["compliance_score"] == pytest.approx(1.0)


def test_framework_validate_decision_error_path():
    fw = ClinicalValidationFramework()
    fw.validation_rules = None  # attribute error inside try block
    out = run(fw.validate_clinical_decision("b", "d", {}))
    assert out["valid"] is False
    assert out["compliance_score"] == 0.0
    assert out["errors"] and out["errors"][0].startswith("Validation error:")


# --------------------------------------------------------------------------
# module-level singleton / ensure_cds_ready
# --------------------------------------------------------------------------


def test_module_singleton_is_service_instance():
    assert isinstance(
        cds.clinical_decision_support_service, ClinicalDecisionSupportService
    )


def test_ensure_cds_ready_swallows_failure_and_is_idempotent():
    original = cds._cds_initialized
    cds._cds_initialized = False
    try:
        init = AsyncMock(side_effect=RuntimeError("partial"))

        async def scenario():
            # fresh lock bound to this event loop
            with patch.object(cds, "_cds_init_lock", asyncio.Lock()), patch.object(
                cds.clinical_decision_support_service, "initialize_service", init
            ):
                await ensure_cds_ready()
                assert cds._cds_initialized is True
                assert init.await_count == 1
                # second call short-circuits
                await ensure_cds_ready()
                assert init.await_count == 1

        run(scenario())
    finally:
        cds._cds_initialized = original


def test_ensure_cds_ready_success_path():
    original = cds._cds_initialized
    cds._cds_initialized = False
    try:
        init = AsyncMock()

        async def scenario():
            with patch.object(cds, "_cds_init_lock", asyncio.Lock()), patch.object(
                cds.clinical_decision_support_service, "initialize_service", init
            ):
                await ensure_cds_ready()

        run(scenario())
        init.assert_awaited_once()
        assert cds._cds_initialized is True
    finally:
        cds._cds_initialized = original
