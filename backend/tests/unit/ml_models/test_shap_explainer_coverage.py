"""Coverage-focused unit tests for ``app.ml_models.shap_explainer``.

Fully self-contained: no fixtures from tests/conftest.py are used, so the file
runs with ``--noconftest`` locally and unchanged in CI.
"""

import matplotlib
import numpy as np
import pandas as pd
import pytest
import shap
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression

matplotlib.use("Agg")

from app.ml_models import shap_explainer as se  # noqa: E402
from app.ml_models.shap_explainer import SHAPExplainer, SHAPVisualizer  # noqa: E402

N_SAMPLES = 30
N_FEATURES = 6


# --------------------------------------------------------------------------
# helpers / fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def X():
    rng = np.random.RandomState(0)
    return pd.DataFrame(
        rng.randn(N_SAMPLES, N_FEATURES),
        columns=[f"feat_{i}" for i in range(N_FEATURES)],
    )


@pytest.fixture
def y(X):
    rng = np.random.RandomState(1)
    return pd.Series((X["feat_0"] + rng.randn(len(X)) * 0.1 > 0).astype(int))


class FakeExplainer:
    """Minimal stand-in for a fitted SHAP explainer."""

    def __init__(self, values, expected_value=0.5, interactions=None):
        self._values = values
        self.expected_value = expected_value
        self._interactions = interactions

    def shap_values(self, X):
        return self._values

    def shap_interaction_values(self, X):
        if self._interactions is None:
            raise RuntimeError("interactions unsupported")
        return self._interactions


def make_fitted(values, expected_value=0.5, interactions=None):
    exp = SHAPExplainer(random_state=7)
    exp.explainer_ = FakeExplainer(values, expected_value, interactions)
    return exp


# --------------------------------------------------------------------------
# __init__
# --------------------------------------------------------------------------
def test_init_sets_defaults():
    exp = SHAPExplainer()
    assert exp.random_state == 42
    assert exp.explainer_ is None
    assert exp.shap_values_ is None
    assert exp.explanation_results_ == {}


def test_init_custom_random_state():
    assert SHAPExplainer(random_state=123).random_state == 123


# --------------------------------------------------------------------------
# fit_explainer
# --------------------------------------------------------------------------
def test_fit_explainer_random_forest_classifier(X, y):
    model = RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    assert isinstance(exp.explainer_, shap.TreeExplainer)


def test_fit_explainer_random_forest_regressor(X, y):
    model = RandomForestRegressor(n_estimators=5, random_state=0).fit(X, y)
    exp = SHAPExplainer()
    assert exp.fit_explainer(model, X) is exp
    assert isinstance(exp.explainer_, shap.TreeExplainer)


def test_fit_explainer_logistic_regression(X, y):
    model = LogisticRegression(max_iter=200).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    assert isinstance(exp.explainer_, shap.LinearExplainer)


def test_fit_explainer_subsamples_background(X, y, monkeypatch):
    """len(X) > sample_size triggers the random background subsample branch."""
    captured = {}
    real_linear = shap.LinearExplainer

    def spy(model, background_data, *a, **kw):
        captured["n"] = len(background_data)
        return real_linear(model, background_data, *a, **kw)

    monkeypatch.setattr(se.shap, "LinearExplainer", spy)
    model = LogisticRegression(max_iter=200).fit(X, y)
    SHAPExplainer().fit_explainer(model, X, sample_size=8)
    assert captured["n"] == 8


def test_fit_explainer_xgboost_branch(X, monkeypatch):
    """xgboost is a namespace package here, so XGBClassifier is injected."""

    class FakeXGB:
        pass

    created = {}

    def fake_tree(model):
        created["model"] = model
        return "tree-explainer"

    monkeypatch.setattr(se.xgb, "XGBClassifier", FakeXGB, raising=False)
    monkeypatch.setattr(se.shap, "TreeExplainer", fake_tree)

    model = FakeXGB()
    exp = SHAPExplainer().fit_explainer(model, X)
    assert exp.explainer_ == "tree-explainer"
    assert created["model"] is model


def test_fit_explainer_kernel_fallback(X, monkeypatch):
    """Unknown model types fall back to KernelExplainer(predict_proba)."""

    class FakeXGB:
        pass

    class OtherModel:
        def predict_proba(self, data):
            return np.zeros((len(data), 2))

    created = {}

    def fake_kernel(fn, background):
        created["fn"] = fn
        created["rows"] = len(background)
        return "kernel-explainer"

    monkeypatch.setattr(se.xgb, "XGBClassifier", FakeXGB, raising=False)
    monkeypatch.setattr(se.shap, "KernelExplainer", fake_kernel)

    model = OtherModel()
    exp = SHAPExplainer().fit_explainer(model, X, sample_size=1000)
    assert exp.explainer_ == "kernel-explainer"
    assert created["rows"] == N_SAMPLES
    assert created["fn"] == model.predict_proba


# --------------------------------------------------------------------------
# explain_global
# --------------------------------------------------------------------------
def test_explain_global_requires_fitted_explainer(X):
    with pytest.raises(ValueError, match="Explainer not fitted"):
        SHAPExplainer().explain_global(X)


def test_explain_global_happy_path(X):
    values = np.arange(N_SAMPLES * N_FEATURES, dtype=float).reshape(
        N_SAMPLES, N_FEATURES
    )
    exp = make_fitted(values)
    result = exp.explain_global(X)

    assert set(result) == {
        "feature_importance",
        "top_features",
        "summary_stats",
        "shap_values",
    }
    assert len(result["feature_importance"]) == N_FEATURES
    stats = result["summary_stats"]
    assert stats["total_features"] == N_FEATURES
    assert (
        stats["max_importance"] >= stats["mean_importance"] >= stats["min_importance"]
    )
    assert stats["std_importance"] >= 0
    # importance is monotonically increasing across columns for this input
    assert result["feature_importance"][0]["feature"] == "feat_5"
    # descending order
    imps = [r["importance"] for r in result["feature_importance"]]
    assert imps == sorted(imps, reverse=True)
    assert np.array(result["shap_values"]).shape == (N_SAMPLES, N_FEATURES)
    assert exp.explanation_results_["global"] is result


def test_explain_global_multiclass_list_uses_first_class(X):
    first = np.ones((N_SAMPLES, N_FEATURES))
    second = np.full((N_SAMPLES, N_FEATURES), 99.0)
    exp = make_fitted([first, second])
    result = exp.explain_global(X)
    assert all(r["importance"] == pytest.approx(1.0) for r in result["top_features"])
    assert isinstance(exp.shap_values_, list)


def test_explain_global_max_display_truncates(X):
    values = np.random.RandomState(3).randn(N_SAMPLES, N_FEATURES)
    result = make_fitted(values).explain_global(X, max_display=2)
    assert len(result["top_features"]) == 2
    assert len(result["feature_importance"]) == N_FEATURES


def test_explain_global_single_row_single_feature():
    X_one = pd.DataFrame({"only": [1.5]})
    result = make_fitted(np.array([[2.0]])).explain_global(X_one)
    assert result["summary_stats"]["total_features"] == 1
    assert result["summary_stats"]["max_importance"] == pytest.approx(2.0)
    assert result["summary_stats"]["std_importance"] == pytest.approx(0.0)


def test_explain_global_with_nans(X):
    values = np.zeros((N_SAMPLES, N_FEATURES))
    values[0, 0] = np.nan
    result = make_fitted(values).explain_global(X)
    imps = {r["feature"]: r["importance"] for r in result["feature_importance"]}
    assert np.isnan(imps["feat_0"])


def test_explain_global_real_tree_explainer(X, y):
    model = RandomForestRegressor(n_estimators=5, random_state=0).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    result = exp.explain_global(X, max_display=3)
    assert len(result["top_features"]) == 3
    assert result["summary_stats"]["total_features"] == N_FEATURES


# --------------------------------------------------------------------------
# explain_local
# --------------------------------------------------------------------------
def test_explain_local_requires_fitted_explainer(X):
    with pytest.raises(ValueError, match="Explainer not fitted"):
        SHAPExplainer().explain_local(X)


def test_explain_local_explicit_indices(X):
    values = np.random.RandomState(5).randn(N_SAMPLES, N_FEATURES)
    exp = make_fitted(values, expected_value=0.25)
    result = exp.explain_local(X, sample_indices=[0, 2], max_display=3)

    assert set(result) == {"sample_0", "sample_2"}
    sample = result["sample_0"]
    assert len(sample["explanation"]) == N_FEATURES
    assert len(sample["top_features"]) == 3
    stats = sample["sample_stats"]
    assert stats["sample_index"] == 0
    assert stats["sum_shap_values"] == pytest.approx(values[0].sum())
    assert stats["prediction"] == pytest.approx(0.25 + values[0].sum())
    assert stats["max_contribution"] == pytest.approx(np.abs(values[0]).max())
    assert stats["n_positive_features"] + stats["n_negative_features"] <= N_FEATURES
    # top features sorted by |shap value| descending
    abs_vals = [abs(f["shap_value"]) for f in sample["top_features"]]
    assert abs_vals == sorted(abs_vals, reverse=True)
    assert exp.explanation_results_["local"] is result


def test_explain_local_skips_out_of_range_indices(X):
    values = np.zeros((N_SAMPLES, N_FEATURES))
    result = make_fitted(values).explain_local(X, sample_indices=[1, 999])
    assert list(result) == ["sample_1"]


def test_explain_local_all_indices_out_of_range(X):
    result = make_fitted(np.zeros((N_SAMPLES, N_FEATURES))).explain_local(
        X, sample_indices=[500]
    )
    assert result == {}


def test_explain_local_default_indices_random_sample(X):
    values = np.zeros((N_SAMPLES, N_FEATURES))
    np.random.seed(0)
    result = make_fitted(values).explain_local(X)
    assert len(result) == 10


def test_explain_local_default_indices_fewer_rows_than_ten():
    X_small = pd.DataFrame(np.zeros((3, 2)), columns=["a", "b"])
    np.random.seed(0)
    result = make_fitted(np.zeros((3, 2))).explain_local(X_small)
    assert len(result) == 3


def test_explain_local_reuses_cached_shap_values(X):
    cached = np.full((N_SAMPLES, N_FEATURES), 3.0)
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)))
    exp.shap_values_ = cached
    result = exp.explain_local(X, sample_indices=[0])
    assert result["sample_0"]["sample_stats"]["sum_shap_values"] == pytest.approx(
        3.0 * N_FEATURES
    )


def test_explain_local_multiclass_list(X):
    first = np.full((N_SAMPLES, N_FEATURES), 2.0)
    second = np.full((N_SAMPLES, N_FEATURES), -8.0)
    exp = make_fitted([first, second])
    result = exp.explain_local(X, sample_indices=[1])
    assert result["sample_1"]["sample_stats"]["sum_shap_values"] == pytest.approx(
        2.0 * N_FEATURES
    )


def test_explain_local_single_feature():
    X_one = pd.DataFrame({"only": [1.0, 2.0]})
    result = make_fitted(np.array([[1.0], [-1.0]])).explain_local(
        X_one, sample_indices=[1]
    )
    stats = result["sample_1"]["sample_stats"]
    assert stats["n_negative_features"] == 1
    assert stats["n_positive_features"] == 0


def test_explain_local_real_tree_explainer(X, y):
    model = RandomForestRegressor(n_estimators=5, random_state=0).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    result = exp.explain_local(X, sample_indices=[0, 1], max_display=2)
    assert len(result) == 2
    assert len(result["sample_0"]["top_features"]) == 2


# --------------------------------------------------------------------------
# explain_interactions
# --------------------------------------------------------------------------
def test_explain_interactions_requires_fitted_explainer(X):
    with pytest.raises(ValueError, match="Explainer not fitted"):
        SHAPExplainer().explain_interactions(X)


def test_explain_interactions_happy_path(X, y):
    model = RandomForestRegressor(n_estimators=5, random_state=0).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    result = exp.explain_interactions(X, max_display=4)

    expected_pairs = N_FEATURES * (N_FEATURES - 1) // 2
    assert result["summary_stats"]["total_interactions"] == expected_pairs
    assert len(result["interaction_importance"]) == expected_pairs
    assert len(result["top_interactions"]) == 4
    scores = [r["interaction_importance"] for r in result["interaction_importance"]]
    assert scores == sorted(scores, reverse=True)
    assert result["summary_stats"]["max_interaction_importance"] >= 0
    assert exp.explanation_results_["interactions"] is result


def test_explain_interactions_multiclass_list(X):
    n = N_FEATURES
    first = np.ones((N_SAMPLES, n, n))
    second = np.full((N_SAMPLES, n, n), 50.0)
    exp = make_fitted(np.zeros((N_SAMPLES, n)), interactions=[first, second])
    result = exp.explain_interactions(X)
    assert result["summary_stats"]["mean_interaction_importance"] == pytest.approx(1.0)


def test_explain_interactions_returns_error_dict_on_failure(X):
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)), interactions=None)
    result = exp.explain_interactions(X)
    assert result == {"error": "interactions unsupported"}
    assert "interactions" not in exp.explanation_results_


def test_explain_interactions_unsupported_explainer(X, y):
    """LinearExplainer has no shap_interaction_values -> error branch."""
    model = LogisticRegression(max_iter=200).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    result = exp.explain_interactions(X)
    assert "error" in result


# --------------------------------------------------------------------------
# accessors
# --------------------------------------------------------------------------
def test_get_feature_importance_ranking_requires_global():
    with pytest.raises(ValueError, match="Global explanations not available"):
        SHAPExplainer().get_feature_importance_ranking()


def test_get_feature_importance_ranking(X):
    values = np.random.RandomState(11).randn(N_SAMPLES, N_FEATURES)
    exp = make_fitted(values)
    exp.explain_global(X)
    ranking = exp.get_feature_importance_ranking()
    assert isinstance(ranking, pd.DataFrame)
    assert list(ranking.columns) == ["feature", "importance"]
    assert ranking["importance"].is_monotonic_decreasing


def test_get_sample_explanations_requires_local():
    with pytest.raises(ValueError, match="Local explanations not available"):
        SHAPExplainer().get_sample_explanations(0)


def test_get_sample_explanations_missing_sample(X):
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)))
    exp.explain_local(X, sample_indices=[0])
    with pytest.raises(ValueError, match="Sample 5 not found"):
        exp.get_sample_explanations(5)


def test_get_sample_explanations_happy_path(X):
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)))
    exp.explain_local(X, sample_indices=[0])
    sample = exp.get_sample_explanations(0)
    assert sample["sample_stats"]["sample_index"] == 0


# --------------------------------------------------------------------------
# generate_explanation_summary
# --------------------------------------------------------------------------
def test_generate_explanation_summary_requires_results():
    with pytest.raises(ValueError, match="No explanations available"):
        SHAPExplainer().generate_explanation_summary()


def test_generate_explanation_summary_all_sections(X, y):
    model = RandomForestRegressor(n_estimators=5, random_state=0).fit(X, y)
    exp = SHAPExplainer().fit_explainer(model, X)
    exp.explain_global(X)
    exp.explain_local(X, sample_indices=[0, 3])
    exp.explain_interactions(X)

    summary = exp.generate_explanation_summary()
    assert set(summary["explanation_types"]) == {"global", "local", "interactions"}
    assert "timestamp" in summary
    assert summary["global_summary"]["total_features"] == N_FEATURES
    assert summary["global_summary"]["top_feature"] in X.columns
    assert summary["local_summary"]["n_samples_explained"] == 2
    assert sorted(summary["local_summary"]["sample_indices"]) == [0, 3]
    assert summary["interaction_summary"]["total_interactions"] == 15
    assert summary["interaction_summary"]["top_interaction"] is not None


def test_generate_explanation_summary_only_local(X):
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)))
    exp.explain_local(X, sample_indices=[2])
    summary = exp.generate_explanation_summary()
    assert summary["explanation_types"] == ["local"]
    assert "global_summary" not in summary
    assert "interaction_summary" not in summary
    assert summary["local_summary"]["sample_indices"] == [2]


def test_generate_explanation_summary_empty_top_collections():
    """Covers the `else None` branches for empty top feature/interaction lists."""
    exp = SHAPExplainer()
    exp.explanation_results_ = {
        "global": {
            "top_features": [],
            "summary_stats": {"total_features": 0, "max_importance": 0.0},
        },
        "interactions": {
            "top_interactions": [],
            "summary_stats": {"total_interactions": 0},
        },
    }
    summary = exp.generate_explanation_summary()
    assert summary["global_summary"]["top_feature"] is None
    assert summary["interaction_summary"]["top_interaction"] is None


# --------------------------------------------------------------------------
# save / load
# --------------------------------------------------------------------------
def test_save_explanations_requires_results(tmp_path):
    with pytest.raises(ValueError, match="No explanations to save"):
        SHAPExplainer().save_explanations(str(tmp_path / "out.joblib"))


def test_save_and_load_round_trip(tmp_path, X):
    exp = make_fitted(np.random.RandomState(2).randn(N_SAMPLES, N_FEATURES))
    exp.explain_global(X)
    exp.feature_names_ = list(X.columns)

    path = tmp_path / "explanations.joblib"
    exp.save_explanations(str(path))
    assert path.exists()

    loaded = SHAPExplainer()
    loaded.load_explanations(str(path))
    assert "global" in loaded.explanation_results_
    assert loaded.feature_names_ == list(X.columns)


def test_save_explanations_without_feature_names(tmp_path, X):
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)))
    exp.explain_global(X)
    path = tmp_path / "no_names.joblib"
    exp.save_explanations(str(path))

    loaded = SHAPExplainer()
    loaded.load_explanations(str(path))
    assert loaded.feature_names_ is None


def test_load_explanations_payload_without_feature_names_key(tmp_path):
    import joblib

    path = tmp_path / "legacy.joblib"
    joblib.dump({"explanation_results": {"global": {"x": 1}}}, str(path))

    loaded = SHAPExplainer()
    loaded.load_explanations(str(path))
    assert loaded.explanation_results_ == {"global": {"x": 1}}
    assert not hasattr(loaded, "feature_names_")


# --------------------------------------------------------------------------
# SHAPVisualizer
# --------------------------------------------------------------------------
@pytest.fixture
def fitted_for_plots(X):
    exp = make_fitted(np.random.RandomState(9).randn(N_SAMPLES, N_FEATURES))
    exp.explain_global(X)
    exp.explain_local(X, sample_indices=[0, 1])
    return exp


def test_visualizer_init(fitted_for_plots):
    viz = SHAPVisualizer(fitted_for_plots)
    assert viz.explainer is fitted_for_plots


def test_plot_feature_importance_requires_global():
    viz = SHAPVisualizer(SHAPExplainer())
    with pytest.raises(ValueError, match="Global explanations not available"):
        viz.plot_feature_importance()


def test_plot_feature_importance_returns_figure(fitted_for_plots):
    import matplotlib.pyplot as plt

    fig = SHAPVisualizer(fitted_for_plots).plot_feature_importance(
        max_display=3, figsize=(4, 3)
    )
    assert fig is not None
    assert len(fig.axes[0].patches) == 3
    plt.close("all")


def test_plot_waterfall_requires_local(X):
    exp = make_fitted(np.zeros((N_SAMPLES, N_FEATURES)))
    exp.explain_global(X)
    with pytest.raises(ValueError, match="Local explanations not available"):
        SHAPVisualizer(exp).plot_waterfall(0)


def test_plot_waterfall_missing_sample(fitted_for_plots):
    with pytest.raises(ValueError, match="Sample 42 not found"):
        SHAPVisualizer(fitted_for_plots).plot_waterfall(42)


def test_plot_waterfall_returns_figure(fitted_for_plots):
    import matplotlib.pyplot as plt

    fig = SHAPVisualizer(fitted_for_plots).plot_waterfall(1, max_display=4)
    assert fig is not None
    assert len(fig.axes[0].patches) == 4
    plt.close("all")


def test_plot_waterfall_colors_by_sign():
    import matplotlib.pyplot as plt

    X_two = pd.DataFrame({"a": [1.0], "b": [2.0]})
    exp = make_fitted(np.array([[1.0, -1.0]]))
    exp.explain_local(X_two, sample_indices=[0])
    fig = SHAPVisualizer(exp).plot_waterfall(0)
    colors = {p.get_facecolor()[:3] for p in fig.axes[0].patches}
    assert len(colors) == 2
    plt.close("all")
