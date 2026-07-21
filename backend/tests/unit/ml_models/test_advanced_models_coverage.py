"""Self-contained coverage tests for ``app.ml_models.advanced_models``.

Runnable with ``--noconftest``: no shared fixtures are used, every input is
built locally, all randomness is seeded and every external clinical API call is
mocked.
"""

import asyncio
import os

import numpy as np
import pytest

if not hasattr(np.dtypes, "VoidDType"):  # pragma: no cover
    # Environment repair, not a behaviour change. When this test run is started
    # under ``pytest --cov`` the coverage bootstrap causes numpy to be imported a
    # second time; the C-level registration that populates ``numpy.dtypes`` is
    # skipped on re-import, leaving the module empty. scikit-learn's bundled
    # array_api_compat does ``getattr(numpy.dtypes, "VoidDType")`` on every
    # ``fit``/``predict``, so repopulate it from the live dtype classes.
    for _code in "?bBhHiIlLqQefdgFDGSUVOMm":
        _dtype_cls = type(np.dtype(_code))
        setattr(np.dtypes, _dtype_cls.__name__, _dtype_cls)

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")

from app.ml_models import advanced_models as am  # noqa: E402
from app.ml_models.advanced_models import (  # noqa: E402
    AdvancedBiomarkerModel,
    ClinicalAnnotationService,
    ModelPerformance,
    advanced_biomarker_model,
    clinical_annotation_service,
)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def make_binary_data(n=40, p=6, seed=0):
    """Small, well separated, deterministic binary classification problem."""
    rng = np.random.RandomState(seed)
    half = n // 2
    X = np.vstack(
        [
            rng.normal(loc=0.0, scale=0.5, size=(half, p)),
            rng.normal(loc=2.5, scale=0.5, size=(n - half, p)),
        ]
    )
    y = np.array([0] * half + [1] * (n - half))
    return X, y


def make_multiclass_data(n=45, p=5, seed=1):
    rng = np.random.RandomState(seed)
    third = n // 3
    X = np.vstack(
        [
            rng.normal(loc=0.0, scale=0.4, size=(third, p)),
            rng.normal(loc=3.0, scale=0.4, size=(third, p)),
            rng.normal(loc=6.0, scale=0.4, size=(n - 2 * third, p)),
        ]
    )
    y = np.array([0] * third + [1] * third + [2] * (n - 2 * third))
    return X, y


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# ModelPerformance dataclass
# --------------------------------------------------------------------------


def test_model_performance_dataclass_fields():
    perf = ModelPerformance(
        accuracy=0.9,
        precision=0.8,
        recall=0.7,
        f1_score=0.75,
        roc_auc=0.95,
        confusion_matrix=np.array([[1, 0], [0, 1]]),
        classification_report="report",
        cross_val_scores=[0.9, 0.8],
        training_time=1.0,
        prediction_time=0.01,
    )
    assert perf.accuracy == pytest.approx(0.9)
    assert perf.classification_report == "report"
    assert perf.confusion_matrix.shape == (2, 2)
    assert perf.cross_val_scores == [0.9, 0.8]


# --------------------------------------------------------------------------
# module globals
# --------------------------------------------------------------------------


def test_module_level_singletons():
    assert isinstance(advanced_biomarker_model, AdvancedBiomarkerModel)
    assert advanced_biomarker_model.model_type == "ensemble"
    assert advanced_biomarker_model.is_trained is False
    assert isinstance(clinical_annotation_service, ClinicalAnnotationService)
    assert set(clinical_annotation_service.annotation_sources) == {
        "cosmic",
        "clinvar",
        "oncokb",
        "pubmed",
    }


def test_init_defaults():
    m = AdvancedBiomarkerModel()
    assert m.model_type == "ensemble"
    assert m.model is None
    assert m.feature_importance is None
    assert m.feature_names is None
    assert m.is_trained is False
    assert m.performance_metrics is None


# --------------------------------------------------------------------------
# model factory helpers
# --------------------------------------------------------------------------


def test_create_ensemble_model_structure():
    ens = AdvancedBiomarkerModel()._create_ensemble_model()
    assert [name for name, _ in ens.estimators] == ["rf", "gb", "svm"]
    assert ens.voting == "soft"
    assert ens.weights == [2, 2, 1]


def test_create_neural_network_structure():
    nn = AdvancedBiomarkerModel()._create_neural_network()
    assert nn.hidden_layer_sizes == (100, 50)
    assert nn.activation == "relu"
    assert nn.max_iter == 500


# --------------------------------------------------------------------------
# train() - one test per model_type branch
# --------------------------------------------------------------------------


def test_train_default_random_forest_branch_without_tuning():
    X, y = make_binary_data()
    m = AdvancedBiomarkerModel(model_type="something_unknown")
    perf = m.train(X, y, hyperparameter_tuning=False)

    assert isinstance(perf, ModelPerformance)
    assert m.is_trained is True
    assert m.performance_metrics is perf
    assert 0.0 <= perf.accuracy <= 1.0
    assert 0.0 <= perf.f1_score <= 1.0
    assert 0.0 <= perf.roc_auc <= 1.0
    assert perf.confusion_matrix.shape == (2, 2)
    assert isinstance(perf.classification_report, str)
    assert len(perf.cross_val_scores) == 5
    assert perf.training_time >= 0.0
    assert perf.prediction_time >= 0.0
    # default feature names generated from X.shape[1]
    assert m.feature_names == [f"feature_{i}" for i in range(X.shape[1])]
    # RandomForest exposes feature_importances_
    assert set(m.feature_importance) == set(m.feature_names)


def test_train_with_explicit_feature_names():
    X, y = make_binary_data(n=30, p=4)
    names = ["g1", "g2", "g3", "g4"]
    m = AdvancedBiomarkerModel(model_type="random_forest")
    m.train(X, y, feature_names=names, hyperparameter_tuning=False)
    assert m.feature_names == names
    assert set(m.feature_importance) == set(names)


def test_train_gradient_boosting_branch():
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="gradient_boosting")
    perf = m.train(X, y, hyperparameter_tuning=False)
    assert m.model.__class__.__name__ == "GradientBoostingClassifier"
    assert perf.accuracy == pytest.approx(1.0, abs=0.5)


def test_train_svm_branch():
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="svm")
    perf = m.train(X, y, hyperparameter_tuning=False)
    assert m.model.__class__.__name__ == "SVC"
    # SVC has no feature_importances_ and no named_estimators_
    assert m.feature_importance is None
    assert isinstance(perf.roc_auc, float)


def test_train_neural_network_branch():
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="neural_network")
    perf = m.train(X, y, hyperparameter_tuning=False)
    assert m.model.__class__.__name__ == "MLPClassifier"
    assert m.feature_importance is None
    assert isinstance(perf.cross_val_scores, list)


def test_train_ensemble_uses_named_estimators_for_importance():
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="ensemble")
    perf = m.train(X, y, hyperparameter_tuning=False)

    assert m.model.__class__.__name__ == "VotingClassifier"
    # averaged over rf + gb (svm has no importances)
    assert set(m.feature_importance) == set(m.feature_names)
    assert sum(m.feature_importance.values()) == pytest.approx(1.0, abs=1e-6)
    assert perf.confusion_matrix.shape == (2, 2)


def test_train_multiclass_leaves_roc_auc_zero():
    X, y = make_multiclass_data()
    m = AdvancedBiomarkerModel(model_type="random_forest")
    perf = m.train(X, y, hyperparameter_tuning=False)
    # roc_auc only computed for binary problems -> falls back to 0.0
    assert perf.roc_auc == 0.0
    assert perf.confusion_matrix.shape == (3, 3)


def test_train_roc_auc_exception_is_swallowed(monkeypatch):
    X, y = make_binary_data(n=30, p=4)

    def boom(*args, **kwargs):
        raise RuntimeError("roc failed")

    monkeypatch.setattr(am, "roc_auc_score", boom)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    perf = m.train(X, y, hyperparameter_tuning=False)
    assert perf.roc_auc == 0.0


def test_train_with_tuning_random_forest_returns_best_estimator():
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    perf = m.train(X, y, hyperparameter_tuning=True)
    assert m.is_trained is True
    assert m.model.__class__.__name__ == "RandomForestClassifier"
    assert 0.0 <= perf.accuracy <= 1.0


def test_train_with_tuning_svm_returns_untuned_model():
    """SVM has no param grid: _tune_hyperparameters returns the model as-is."""
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="svm")
    m.train(X, y, hyperparameter_tuning=True)
    assert m.model.__class__.__name__ == "SVC"


def test_train_raises_and_logs_on_bad_input():
    """Only 1 sample per class -> 5-fold stratified CV explodes."""
    X = np.array([[0.0, 1.0], [1.0, 0.0]])
    y = np.array([0, 1])
    m = AdvancedBiomarkerModel(model_type="random_forest")
    with pytest.raises(Exception):
        m.train(X, y, hyperparameter_tuning=False)
    assert m.is_trained is False


# --------------------------------------------------------------------------
# _tune_hyperparameters direct coverage
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_type,expected",
    [
        ("ensemble", "VotingClassifier"),
        ("neural_network", "MLPClassifier"),
        ("svm", "SVC"),
        ("mystery", "RandomForestClassifier"),
    ],
)
def test_tune_hyperparameters_lazily_builds_model_when_none(model_type, expected):
    X, y = make_binary_data(n=20, p=3)
    m = AdvancedBiomarkerModel(model_type=model_type)
    assert m.model is None
    out = m._tune_hyperparameters(X, y)
    assert out.__class__.__name__ == expected


def test_tune_hyperparameters_gradient_boosting_grid_search():
    X, y = make_binary_data(n=20, p=3)
    m = AdvancedBiomarkerModel(model_type="gradient_boosting")
    best = m._tune_hyperparameters(X, y)
    assert best.__class__.__name__ == "GradientBoostingClassifier"
    assert best.n_estimators in (50, 100)
    assert best.max_depth in (3, 5, 7)


def test_tune_hyperparameters_falls_back_when_grid_search_fails(monkeypatch):
    X, y = make_binary_data(n=20, p=3)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    sentinel = m._create_neural_network()
    m.model = sentinel

    def boom(*args, **kwargs):
        raise RuntimeError("grid search unavailable")

    monkeypatch.setattr(am, "GridSearchCV", boom)
    assert m._tune_hyperparameters(X, y) is sentinel


# --------------------------------------------------------------------------
# predict / predict_proba
# --------------------------------------------------------------------------


def test_predict_requires_training():
    m = AdvancedBiomarkerModel()
    with pytest.raises(ValueError, match="must be trained"):
        m.predict(np.zeros((2, 3)))


def test_predict_proba_requires_training():
    m = AdvancedBiomarkerModel()
    with pytest.raises(ValueError, match="must be trained"):
        m.predict_proba(np.zeros((2, 3)))


def test_predict_and_predict_proba_after_training():
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    m.train(X, y, hyperparameter_tuning=False)

    preds = m.predict(X)
    assert preds.shape == (30,)
    assert set(np.unique(preds)).issubset({0, 1})

    proba = m.predict_proba(X)
    assert proba.shape == (30, 2)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_predict_proba_raises_when_model_lacks_support():
    class NoProba:
        def predict(self, X):
            return np.zeros(len(X))

    m = AdvancedBiomarkerModel()
    m.model = NoProba()
    m.is_trained = True
    with pytest.raises(ValueError, match="does not support probability"):
        m.predict_proba(np.zeros((2, 3)))


# --------------------------------------------------------------------------
# get_feature_importance
# --------------------------------------------------------------------------


def test_get_feature_importance_empty_returns_empty_dict():
    m = AdvancedBiomarkerModel()
    assert m.get_feature_importance() == {}
    m.feature_importance = {}
    assert m.get_feature_importance(top_n=5) == {}


def test_get_feature_importance_sorted_and_truncated():
    m = AdvancedBiomarkerModel()
    m.feature_importance = {"a": 0.1, "b": 0.5, "c": 0.3, "d": 0.05}
    top2 = m.get_feature_importance(top_n=2)
    assert list(top2.keys()) == ["b", "c"]
    assert top2["b"] == pytest.approx(0.5)
    assert len(m.get_feature_importance()) == 4


# --------------------------------------------------------------------------
# save / load
# --------------------------------------------------------------------------


def test_save_requires_trained_model(tmp_path):
    m = AdvancedBiomarkerModel()
    with pytest.raises(ValueError, match="must be trained before saving"):
        m.save(str(tmp_path / "model.joblib"))

    m.is_trained = True  # model still None -> still rejected
    with pytest.raises(ValueError, match="must be trained before saving"):
        m.save(str(tmp_path / "model.joblib"))


def test_save_creates_parent_directories_and_load_roundtrip(tmp_path):
    X, y = make_binary_data(n=30, p=4)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    m.train(X, y, feature_names=["a", "b", "c", "d"], hyperparameter_tuning=False)

    path = tmp_path / "nested" / "dir" / "model.joblib"
    m.save(str(path))
    assert path.exists()

    loaded = AdvancedBiomarkerModel.load(str(path))
    assert loaded.model_type == "random_forest"
    assert loaded.feature_names == ["a", "b", "c", "d"]
    assert loaded.is_trained is True
    assert set(loaded.feature_importance) == {"a", "b", "c", "d"}
    assert np.array_equal(loaded.predict(X), m.predict(X))


def test_save_without_parent_directory(tmp_path, monkeypatch):
    """A bare filename means os.path.dirname() is empty -> makedirs skipped."""
    X, y = make_binary_data(n=20, p=3)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    m.train(X, y, hyperparameter_tuning=False)

    monkeypatch.chdir(tmp_path)
    m.save("bare_model.joblib")
    assert (tmp_path / "bare_model.joblib").exists()


def test_save_propagates_dump_errors(tmp_path, monkeypatch):
    X, y = make_binary_data(n=20, p=3)
    m = AdvancedBiomarkerModel(model_type="random_forest")
    m.train(X, y, hyperparameter_tuning=False)

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(am.joblib, "dump", boom)
    with pytest.raises(OSError, match="disk full"):
        m.save(str(tmp_path / "model.joblib"))


def test_load_propagates_errors(tmp_path):
    with pytest.raises(Exception):
        AdvancedBiomarkerModel.load(str(tmp_path / "does_not_exist.joblib"))


def test_save_model_and_load_model_aliases(tmp_path):
    X, y = make_binary_data(n=20, p=3)
    trained = AdvancedBiomarkerModel(model_type="random_forest")
    trained.train(X, y, hyperparameter_tuning=False)

    path = str(tmp_path / "alias.joblib")
    trained.save_model(path)

    target = AdvancedBiomarkerModel(model_type="ensemble")
    target.load_model(path)

    assert target.model_type == "random_forest"
    assert target.is_trained is True
    assert target.feature_names == trained.feature_names
    assert target.performance_metrics.accuracy == pytest.approx(
        trained.performance_metrics.accuracy
    )
    assert np.array_equal(target.predict(X), trained.predict(X))


# --------------------------------------------------------------------------
# ClinicalAnnotationService - individual sources
# --------------------------------------------------------------------------


def test_annotate_cosmic_unavailable(monkeypatch):
    monkeypatch.setattr(
        am, "fetch_cosmic_mutations", lambda **kw: {"data_source": "unavailable"}
    )
    out = run(ClinicalAnnotationService()._annotate_cosmic("TP53"))
    assert out == {
        "source": "cosmic",
        "mutations": [],
        "cancer_types": [],
        "frequency": None,
        "clinical_significance": "unknown",
    }


def test_annotate_cosmic_with_mutations(monkeypatch):
    payload = {
        "data_source": "api",
        "mutations": [
            {"cancer_type": "lung"},
            {"cancer_type": "lung"},
            {"cancer_type": "breast"},
            {"no_cancer_type": True},
        ],
        "total_count": 42,
    }
    monkeypatch.setattr(am, "fetch_cosmic_mutations", lambda **kw: payload)
    out = run(ClinicalAnnotationService()._annotate_cosmic("TP53"))
    assert out["source"] == "cosmic"
    assert out["frequency"] == 42
    assert out["clinical_significance"] == "high"
    assert sorted(out["cancer_types"]) == ["breast", "lung"]


def test_annotate_cosmic_api_with_no_mutations(monkeypatch):
    monkeypatch.setattr(
        am,
        "fetch_cosmic_mutations",
        lambda **kw: {"data_source": "api", "mutations": [], "total_count": 0},
    )
    out = run(ClinicalAnnotationService()._annotate_cosmic("XYZ"))
    assert out["clinical_significance"] == "unknown"
    assert out["cancer_types"] == []


def test_annotate_clinvar_unavailable(monkeypatch):
    monkeypatch.setattr(
        am, "fetch_clinvar_variants", lambda **kw: {"data_source": "unavailable"}
    )
    out = run(ClinicalAnnotationService()._annotate_clinvar("BRCA1"))
    assert out == {
        "source": "clinvar",
        "variants": [],
        "clinical_significance": "unknown",
        "review_status": "unknown",
    }


def test_annotate_clinvar_with_variants(monkeypatch):
    monkeypatch.setattr(
        am,
        "fetch_clinvar_variants",
        lambda **kw: {"data_source": "api", "variants": [{"id": "v1"}]},
    )
    out = run(ClinicalAnnotationService()._annotate_clinvar("BRCA1"))
    assert out["variants"] == [{"id": "v1"}]
    assert out["clinical_significance"] == "high"
    assert out["review_status"] == "reviewed"


def test_annotate_clinvar_api_without_variants(monkeypatch):
    monkeypatch.setattr(
        am,
        "fetch_clinvar_variants",
        lambda **kw: {"data_source": "api", "variants": []},
    )
    out = run(ClinicalAnnotationService()._annotate_clinvar("BRCA1"))
    assert out["clinical_significance"] == "unknown"
    assert out["review_status"] == "unknown"


def test_annotate_oncokb_match_by_gene_symbol(monkeypatch):
    monkeypatch.setattr(
        am,
        "fetch_oncokb_cancer_genes",
        lambda **kw: {
            "data_source": "api",
            "cancer_genes": [
                {"gene_symbol": "EGFR", "oncogenic": "Oncogenic"},
                {"gene_symbol": "KRAS", "oncogenic": "Likely Oncogenic"},
            ],
        },
    )
    monkeypatch.setattr(
        am,
        "fetch_oncokb_drugs",
        lambda **kw: {
            "data_source": "api",
            "drugs": [{"drug_name": "Erlotinib"}, {"drug_name": ""}, {}],
        },
    )
    out = run(ClinicalAnnotationService()._annotate_oncokb("EGFR"))
    assert out["source"] == "oncokb"
    assert out["oncogenic"] == "Oncogenic"
    assert out["therapeutic_implications"] == ["Erlotinib"]
    assert out["drug_targets"] == ["Erlotinib"]


def test_annotate_oncokb_match_by_hugo_symbol(monkeypatch):
    monkeypatch.setattr(
        am,
        "fetch_oncokb_cancer_genes",
        lambda **kw: {
            "data_source": "api",
            "cancer_genes": [{"hugoSymbol": "BRAF", "oncogenic": "Oncogenic"}],
        },
    )
    monkeypatch.setattr(
        am, "fetch_oncokb_drugs", lambda **kw: {"data_source": "api", "drugs": []}
    )
    out = run(ClinicalAnnotationService()._annotate_oncokb("BRAF"))
    assert out["oncogenic"] == "Oncogenic"
    assert out["therapeutic_implications"] == []


def test_annotate_oncokb_non_api_sources(monkeypatch):
    monkeypatch.setattr(
        am, "fetch_oncokb_cancer_genes", lambda **kw: {"data_source": "unavailable"}
    )
    monkeypatch.setattr(
        am,
        "fetch_oncokb_drugs",
        lambda **kw: {"data_source": "unavailable", "drugs": [{"drug_name": "X"}]},
    )
    out = run(ClinicalAnnotationService()._annotate_oncokb("EGFR"))
    assert out["oncogenic"] == "unknown"
    assert out["therapeutic_implications"] == []
    assert out["drug_targets"] == []


def test_annotate_pubmed_returns_empty_placeholder():
    out = run(ClinicalAnnotationService()._annotate_pubmed("TP53"))
    assert out == {
        "source": "pubmed",
        "publications": [],
        "citation_count": 0,
        "recent_publications": [],
    }


# --------------------------------------------------------------------------
# ClinicalAnnotationService.annotate_biomarker
# --------------------------------------------------------------------------


def _stub_all_sources(monkeypatch):
    monkeypatch.setattr(
        am,
        "fetch_cosmic_mutations",
        lambda **kw: {
            "data_source": "api",
            "mutations": [{"cancer_type": "lung"}],
            "total_count": 5,
        },
    )
    monkeypatch.setattr(
        am,
        "fetch_clinvar_variants",
        lambda **kw: {"data_source": "api", "variants": [{"id": "v1"}]},
    )
    monkeypatch.setattr(
        am,
        "fetch_oncokb_cancer_genes",
        lambda **kw: {
            "data_source": "api",
            "cancer_genes": [{"gene_symbol": "EGFR", "oncogenic": "Oncogenic"}],
        },
    )
    monkeypatch.setattr(
        am,
        "fetch_oncokb_drugs",
        lambda **kw: {"data_source": "api", "drugs": [{"drug_name": "Erlotinib"}]},
    )


def test_annotate_biomarker_all_default_sources(monkeypatch):
    _stub_all_sources(monkeypatch)
    out = run(ClinicalAnnotationService().annotate_biomarker("EGFR"))

    assert out["biomarker"] == "EGFR"
    assert out["sources"] == ["cosmic", "clinvar", "oncokb", "pubmed"]
    assert out["clinical_significance"] == "high"
    assert out["confidence_score"] == pytest.approx(1.0)
    assert out["therapeutic_implications"] == ["Erlotinib"]
    assert out["publications"] == []
    assert isinstance(out["timestamp"], str)


def test_annotate_biomarker_subset_and_unknown_source_ignored(monkeypatch):
    _stub_all_sources(monkeypatch)
    out = run(
        ClinicalAnnotationService().annotate_biomarker(
            "EGFR", sources=["cosmic", "not_a_real_source"]
        )
    )
    assert out["sources"] == ["cosmic"]
    assert out["clinical_significance"] == "high"


def test_annotate_biomarker_empty_source_list(monkeypatch):
    out = run(ClinicalAnnotationService().annotate_biomarker("EGFR", sources=[]))
    assert out["sources"] == []
    assert out["clinical_significance"] == "unknown"
    assert out["confidence_score"] == 0.0


def test_annotate_biomarker_captures_per_source_errors(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("cosmic down")

    monkeypatch.setattr(am, "fetch_cosmic_mutations", boom)
    svc = ClinicalAnnotationService()
    captured = {}
    original = svc._combine_annotations

    def spy(biomarker, annotations):
        captured.update(annotations)
        return original(biomarker, annotations)

    svc._combine_annotations = spy
    out = run(svc.annotate_biomarker("EGFR", sources=["cosmic"]))

    assert captured["cosmic"] == {"error": "cosmic down"}
    assert out["clinical_significance"] == "unknown"


def test_annotate_biomarker_propagates_unexpected_errors():
    svc = ClinicalAnnotationService()

    def boom(biomarker, annotations):
        raise RuntimeError("combine exploded")

    svc._combine_annotations = boom
    with pytest.raises(RuntimeError, match="combine exploded"):
        run(svc.annotate_biomarker("EGFR", sources=["pubmed"]))


# --------------------------------------------------------------------------
# _combine_annotations
# --------------------------------------------------------------------------


def test_combine_annotations_empty():
    out = ClinicalAnnotationService()._combine_annotations("TP53", {})
    assert out["biomarker"] == "TP53"
    assert out["sources"] == []
    assert out["clinical_significance"] == "unknown"
    assert out["confidence_score"] == 0.0
    assert out["therapeutic_implications"] == []
    assert out["publications"] == []


@pytest.mark.parametrize(
    "sigs,expected,expected_conf",
    [
        (["high", "high"], "high", 1.0),
        (["high", "moderate"], "high", 5.0 / 6.0),
        (["moderate", "moderate"], "moderate", 2.0 / 3.0),
        (["low", "moderate"], "moderate", 0.5),
        (["low", "low"], "low", 1.0 / 3.0),
    ],
)
def test_combine_annotations_significance_thresholds(sigs, expected, expected_conf):
    annotations = {
        f"s{i}": {"clinical_significance": sig} for i, sig in enumerate(sigs)
    }
    out = ClinicalAnnotationService()._combine_annotations("TP53", annotations)
    assert out["clinical_significance"] == expected
    assert out["confidence_score"] == pytest.approx(expected_conf)


def test_combine_annotations_unrecognised_significance_is_scoreless():
    out = ClinicalAnnotationService()._combine_annotations(
        "TP53", {"a": {"clinical_significance": "unknown"}}
    )
    assert out["clinical_significance"] == "unknown"
    assert out["confidence_score"] == 0.0


def test_combine_annotations_merges_and_dedupes_therapeutics_and_publications():
    annotations = {
        "oncokb": {
            "therapeutic_implications": ["DrugA", "DrugB"],
            "drug_targets": ["DrugA"],
        },
        "pubmed": {"publications": [{"pmid": "1"}, {"pmid": "2"}]},
        "other": {"publications": [{"pmid": "3"}]},
        "bad_shape": "not-a-dict",
    }
    out = ClinicalAnnotationService()._combine_annotations("EGFR", annotations)
    assert sorted(out["therapeutic_implications"]) == ["DrugA", "DrugB"]
    assert len(out["publications"]) == 3
    assert "bad_shape" in out["sources"]
