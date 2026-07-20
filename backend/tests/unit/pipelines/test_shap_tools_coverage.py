"""
Self-contained coverage tests for ``app.pipelines.shap_tools``.

These tests deliberately avoid every fixture from ``tests/conftest.py`` so the
file can be run with ``--noconftest``.  Heavy / non-deterministic dependencies
(real SHAP explainers, plotly) are replaced with light fakes.
"""

import importlib.util
import json
import os
import sys
import types

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Import the module under test WITHOUT executing ``app/pipelines/__init__.py``.
# That package __init__ eagerly imports the whole biomarker pipeline (and with
# it statsmodels & friends), which is unrelated to shap_tools.  Registering a
# stub package object keeps the relative import ``..utils.logging_config``
# working while skipping the heavy side effects.
# ---------------------------------------------------------------------------
import app as _app  # noqa: E402

if "app.pipelines" not in sys.modules:
    _pkg_path = os.path.join(os.path.dirname(_app.__file__), "pipelines")
    _spec = importlib.util.spec_from_file_location(
        "app.pipelines",
        os.path.join(_pkg_path, "__init__.py"),
        submodule_search_locations=[_pkg_path],
    )
    _pkg = importlib.util.module_from_spec(_spec)
    sys.modules["app.pipelines"] = _pkg
    setattr(_app, "pipelines", _pkg)

from app.pipelines.shap_tools import SHAPExplainer  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

N_SAMPLES = 24
N_FEATURES = 6


def make_X(n_samples=N_SAMPLES, n_features=N_FEATURES, seed=0):
    rng = np.random.RandomState(seed)
    return pd.DataFrame(
        rng.randn(n_samples, n_features),
        columns=[f"GENE_{i}" for i in range(n_features)],
    )


def make_shap(n_samples=N_SAMPLES, n_features=N_FEATURES, seed=1):
    rng = np.random.RandomState(seed)
    return rng.randn(n_samples, n_features)


class FakeExplainer:
    """Stand-in for a SHAP explainer object."""

    def __init__(self, values, expected_value=0.25):
        self._values = values
        self.expected_value = expected_value
        self.calls = []

    def shap_values(self, X):
        self.calls.append("shap_values")
        return self._values

    def __call__(self, X):
        self.calls.append("__call__")
        return self._values


class ExplodingExplainer(FakeExplainer):
    def __call__(self, X):
        raise RuntimeError("boom during shap computation")


class DummyModel:
    def predict(self, X):  # pragma: no cover - only referenced, never called
        return np.zeros(len(X))


def _named_model(class_name):
    """Build an instance of a throw-away class with the given class name."""
    return type(class_name, (), {})()


@pytest.fixture
def X():
    return make_X()


@pytest.fixture
def shap_values():
    return make_shap()


@pytest.fixture
def explainer():
    return SHAPExplainer()


@pytest.fixture
def fitted_explainer(explainer, X, shap_values):
    """A SHAPExplainer whose ``shap_results`` are already populated."""
    explainer.shap_results = {
        "explainer_type": "tree",
        "feature_names": list(X.columns),
        "expected_value": 0.25,
        "global_analysis": explainer._compute_global_analysis(shap_values, X),
        "local_analysis": explainer._compute_local_analysis(shap_values, X),
    }
    return explainer


@pytest.fixture
def fake_plotly(monkeypatch):
    """Install a minimal in-memory plotly so the plotting branches execute."""

    class FakeFigure:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.layout = {}
            self.annotations = []

        def add_annotation(self, **kwargs):
            self.annotations.append(kwargs)

        def update_layout(self, **kwargs):
            self.layout.update(kwargs)

    class FakeWaterfall:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    plotly = types.ModuleType("plotly")
    px = types.ModuleType("plotly.express")
    go = types.ModuleType("plotly.graph_objects")
    subplots = types.ModuleType("plotly.subplots")

    px.bar = lambda *a, **k: FakeFigure(*a, **k)
    px.scatter = lambda *a, **k: FakeFigure(*a, **k)
    go.Figure = FakeFigure
    go.Waterfall = FakeWaterfall
    subplots.make_subplots = lambda *a, **k: FakeFigure(*a, **k)

    plotly.express = px
    plotly.graph_objects = go
    plotly.subplots = subplots

    monkeypatch.setitem(sys.modules, "plotly", plotly)
    monkeypatch.setitem(sys.modules, "plotly.express", px)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", go)
    monkeypatch.setitem(sys.modules, "plotly.subplots", subplots)
    return FakeFigure


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_config(self):
        exp = SHAPExplainer()
        assert exp.config == {}
        assert exp.shap_results == {}

    def test_explicit_config(self):
        cfg = {"top_features": 3}
        exp = SHAPExplainer(config=cfg)
        assert exp.config is cfg

    def test_none_config_falls_back_to_empty_dict(self):
        assert SHAPExplainer(config=None).config == {}


# ---------------------------------------------------------------------------
# _determine_explainer_type
# ---------------------------------------------------------------------------


class TestDetermineExplainerType:
    @pytest.mark.parametrize(
        "class_name",
        [
            "DecisionTreeClassifier",
            "RandomForestRegressor",
            "XGBoostClassifier",
            "LightGBMModel",
        ],
    )
    def test_tree_family(self, explainer, class_name):
        assert explainer._determine_explainer_type(_named_model(class_name)) == "tree"

    @pytest.mark.parametrize("class_name", ["LinearRegression", "LogisticRegression"])
    def test_linear_family(self, explainer, class_name):
        assert explainer._determine_explainer_type(_named_model(class_name)) == "linear"

    @pytest.mark.parametrize("class_name", ["SVC", "MLPClassifier", "KNeighbours"])
    def test_kernel_fallback(self, explainer, class_name):
        assert explainer._determine_explainer_type(_named_model(class_name)) == "kernel"


# ---------------------------------------------------------------------------
# _create_explainer
# ---------------------------------------------------------------------------


class TestCreateExplainer:
    def test_tree_explainer(self, explainer, X, monkeypatch):
        import shap

        created = {}

        def fake_tree(model, **kwargs):
            created["model"] = model
            created["kwargs"] = kwargs
            return "TREE"

        monkeypatch.setattr(shap, "TreeExplainer", fake_tree)
        model = DummyModel()
        out = explainer._create_explainer(model, X, None, "tree")
        assert out == "TREE"
        assert created["model"] is model

    def test_linear_explainer_receives_X(self, explainer, X, monkeypatch):
        import shap

        seen = {}

        def fake_linear(model, data, **kwargs):
            seen["data"] = data
            return "LINEAR"

        monkeypatch.setattr(shap, "LinearExplainer", fake_linear)
        assert explainer._create_explainer(DummyModel(), X, None, "linear") == "LINEAR"
        pd.testing.assert_frame_equal(seen["data"], X)

    def test_kernel_explainer_uses_kmeans_when_no_background(
        self, explainer, X, monkeypatch
    ):
        import shap

        seen = {}
        monkeypatch.setattr(shap, "kmeans", lambda data, k: f"KMEANS-{k}")

        def fake_kernel(fn, background, **kwargs):
            seen["background"] = background
            return "KERNEL"

        monkeypatch.setattr(shap, "KernelExplainer", fake_kernel)
        assert explainer._create_explainer(DummyModel(), X, None, "kernel") == "KERNEL"
        assert seen["background"] == "KMEANS-100"

    def test_kernel_explainer_uses_supplied_background(self, explainer, X, monkeypatch):
        import shap

        seen = {}

        def fake_kernel(fn, background, **kwargs):
            seen["background"] = background
            return "KERNEL"

        monkeypatch.setattr(shap, "KernelExplainer", fake_kernel)
        monkeypatch.setattr(
            shap, "kmeans", lambda *a, **k: pytest.fail("kmeans must not be called")
        )
        bg = X.head(3)
        explainer._create_explainer(DummyModel(), X, bg, "kernel")
        pd.testing.assert_frame_equal(seen["background"], bg)

    def test_unsupported_type_raises(self, explainer, X):
        with pytest.raises(ValueError, match="Unsupported explainer type: deep"):
            explainer._create_explainer(DummyModel(), X, None, "deep")


# ---------------------------------------------------------------------------
# compute_shap_values
# ---------------------------------------------------------------------------


class TestComputeShapValues:
    def test_auto_type_and_callable_explainer(
        self, explainer, X, shap_values, monkeypatch
    ):
        fake = FakeExplainer(shap_values)
        monkeypatch.setattr(explainer, "_create_explainer", lambda *a, **k: fake)

        results = explainer.compute_shap_values(
            model=_named_model("RandomForestClassifier"), X=X
        )

        # explainer_type key keeps the *requested* value ("auto"): the resolved
        # type is only used locally.  Asserting current behaviour.
        assert results["explainer_type"] == "auto"
        assert fake.calls == ["__call__"]
        assert results["feature_names"] == list(X.columns)
        assert results["expected_value"] == 0.25
        assert results["explainer"] is fake
        assert set(results["global_analysis"]) == {
            "feature_importance",
            "summary_stats",
            "interaction_analysis",
            "top_features",
        }
        assert set(results["local_analysis"]) == {
            "sample_analysis",
            "dependence_analysis",
        }
        assert explainer.shap_results is results

    def test_background_data_uses_shap_values_method(
        self, explainer, X, shap_values, monkeypatch
    ):
        fake = FakeExplainer(shap_values)
        monkeypatch.setattr(explainer, "_create_explainer", lambda *a, **k: fake)

        results = explainer.compute_shap_values(
            model=DummyModel(),
            X=X,
            background_data=X.head(4),
            explainer_type="kernel",
        )
        assert fake.calls == ["shap_values"]
        assert results["explainer_type"] == "kernel"
        assert np.asarray(results["shap_values"]).shape == (N_SAMPLES, N_FEATURES)

    def test_list_output_multiclass_picks_second_element(
        self, explainer, X, monkeypatch
    ):
        class_0 = np.zeros((N_SAMPLES, N_FEATURES))
        class_1 = make_shap()
        fake = FakeExplainer([class_0, class_1])
        monkeypatch.setattr(explainer, "_create_explainer", lambda *a, **k: fake)

        results = explainer.compute_shap_values(
            model=DummyModel(), X=X, explainer_type="tree"
        )
        np.testing.assert_allclose(results["shap_values"], class_1)

    def test_list_output_single_element_picks_first(self, explainer, X, monkeypatch):
        only = make_shap()
        fake = FakeExplainer([only])
        monkeypatch.setattr(explainer, "_create_explainer", lambda *a, **k: fake)

        results = explainer.compute_shap_values(
            model=DummyModel(), X=X, explainer_type="tree"
        )
        np.testing.assert_allclose(results["shap_values"], only)

    def test_single_row_input(self, explainer, monkeypatch):
        X_one = make_X(n_samples=1)
        fake = FakeExplainer(make_shap(n_samples=1))
        monkeypatch.setattr(explainer, "_create_explainer", lambda *a, **k: fake)

        results = explainer.compute_shap_values(
            model=DummyModel(), X=X_one, explainer_type="tree"
        )
        assert len(results["local_analysis"]["sample_analysis"]) == 1
        # corrcoef on a single point is undefined -> interaction analysis bails out
        assert results["global_analysis"]["interaction_analysis"] == {}

    def test_explainer_failure_is_reraised(self, explainer, X, monkeypatch):
        fake = ExplodingExplainer(make_shap())
        monkeypatch.setattr(explainer, "_create_explainer", lambda *a, **k: fake)

        with pytest.raises(RuntimeError, match="boom during shap computation"):
            explainer.compute_shap_values(
                model=DummyModel(), X=X, explainer_type="tree"
            )
        assert explainer.shap_results == {}

    def test_create_explainer_valueerror_propagates(self, explainer, X):
        with pytest.raises(ValueError, match="Unsupported explainer type"):
            explainer.compute_shap_values(
                model=DummyModel(), X=X, explainer_type="not-a-type"
            )

    def test_missing_shap_library_raises_import_error(self, explainer, X, monkeypatch):
        monkeypatch.setitem(sys.modules, "shap", None)
        with pytest.raises(ImportError):
            explainer.compute_shap_values(model=DummyModel(), X=X)

    def test_real_tree_explainer_end_to_end(self, explainer):
        """One genuine integration run against the real shap library."""
        from sklearn.ensemble import RandomForestClassifier

        X_small = make_X(n_samples=20, n_features=5, seed=7)
        y = np.array([0, 1] * 10)
        model = RandomForestClassifier(n_estimators=5, random_state=42)
        model.fit(X_small, y)

        results = explainer.compute_shap_values(
            model=model,
            X=X_small,
            background_data=X_small.head(5),
            explainer_type="tree",
        )
        assert results["shap_values"] is not None
        importance = results["global_analysis"]["feature_importance"]
        assert len(importance) == 5
        assert all(rec["importance"] >= 0 for rec in importance)


# ---------------------------------------------------------------------------
# _compute_global_analysis
# ---------------------------------------------------------------------------


class TestGlobalAnalysis:
    def test_structure_and_ordering(self, explainer, X, shap_values):
        out = explainer._compute_global_analysis(shap_values, X)

        importance = out["feature_importance"]
        assert len(importance) == N_FEATURES
        scores = [rec["importance"] for rec in importance]
        assert scores == sorted(scores, reverse=True)

        for key in ("mean_shap", "std_shap", "min_shap", "max_shap"):
            assert isinstance(out["summary_stats"][key], list)
            assert len(out["summary_stats"][key]) == N_FEATURES

        assert out["summary_stats"]["mean_shap"][0] == pytest.approx(
            float(shap_values[:, 0].mean())
        )
        assert len(out["top_features"]) == N_FEATURES  # fewer than the 20 cap

    def test_top_features_capped_at_20(self, explainer):
        X_wide = make_X(n_samples=10, n_features=25)
        out = explainer._compute_global_analysis(make_shap(10, 25), X_wide)
        assert len(out["top_features"]) == 20
        assert len(out["feature_importance"]) == 25


# ---------------------------------------------------------------------------
# _compute_local_analysis
# ---------------------------------------------------------------------------


class TestLocalAnalysis:
    def test_caps_at_ten_samples(self, explainer, X, shap_values):
        out = explainer._compute_local_analysis(shap_values, X)
        samples = out["sample_analysis"]
        assert len(samples) == 10
        assert [s["sample_index"] for s in samples] == list(range(10))

        first = samples[0]
        assert len(first["top_contributors"]) == N_FEATURES
        abs_vals = [c["abs_contribution"] for c in first["top_contributors"]]
        assert abs_vals == sorted(abs_vals, reverse=True)
        assert first["total_contribution"] == pytest.approx(
            float(np.sum(shap_values[0]))
        )

    def test_fewer_samples_than_cap(self, explainer):
        X_small = make_X(n_samples=3)
        out = explainer._compute_local_analysis(make_shap(3), X_small)
        assert len(out["sample_analysis"]) == 3

    def test_top_contributors_capped_at_ten(self, explainer):
        X_wide = make_X(n_samples=4, n_features=30)
        out = explainer._compute_local_analysis(make_shap(4, 30), X_wide)
        assert len(out["sample_analysis"][0]["top_contributors"]) == 10

    def test_empty_frame_returns_no_samples(self, explainer):
        X_empty = pd.DataFrame(columns=["A", "B"], dtype=float)
        out = explainer._compute_local_analysis(np.empty((0, 2)), X_empty)
        assert out["sample_analysis"] == []


# ---------------------------------------------------------------------------
# _compute_interaction_analysis
# ---------------------------------------------------------------------------


class TestInteractionAnalysis:
    def test_happy_path(self, explainer, X, shap_values):
        out = explainer._compute_interaction_analysis(shap_values, X)
        assert set(out) == set(X.columns)
        for stats in out.values():
            assert -1.0 <= stats["correlation"] <= 1.0
            assert stats["mutual_info"] >= 0.0
            assert isinstance(stats["correlation"], float)
            assert isinstance(stats["mutual_info"], float)

    def test_constant_feature_yields_zero_correlation(self, explainer):
        X_const = make_X(n_samples=20, n_features=2)
        X_const["GENE_0"] = 1.0
        out = explainer._compute_interaction_analysis(make_shap(20, 2), X_const)
        assert out["GENE_0"]["correlation"] == 0.0

    def test_nan_column_is_handled(self, explainer):
        X_nan = make_X(n_samples=20, n_features=2)
        X_nan.loc[0, "GENE_0"] = np.nan
        out = explainer._compute_interaction_analysis(make_shap(20, 2), X_nan)
        # NaNs poison corrcoef -> the 0.0 fallback kicks in, or the whole
        # analysis bails out; both are acceptable current behaviour.
        assert out == {} or out["GENE_0"]["correlation"] == 0.0

    def test_bad_shape_is_swallowed(self, explainer, X):
        out = explainer._compute_interaction_analysis(np.arange(5.0), X)
        assert out == {}


# ---------------------------------------------------------------------------
# _compute_dependence_analysis
# ---------------------------------------------------------------------------


class TestDependenceAnalysis:
    def test_defaults_to_top_ten(self, explainer):
        X_wide = make_X(n_samples=20, n_features=15)
        out = explainer._compute_dependence_analysis(make_shap(20, 15), X_wide)
        assert len(out) == 10
        for data in out.values():
            assert len(data["feature_values"]) == 20
            assert len(data["shap_values"]) == 20
            assert data["feature_values"] == sorted(data["feature_values"])
            assert isinstance(data["correlation"], float)

    def test_respects_top_features_kwarg(self, explainer, X, shap_values):
        out = explainer._compute_dependence_analysis(shap_values, X, top_features=2)
        assert len(out) == 2

    def test_fewer_features_than_requested(self, explainer):
        X_narrow = make_X(n_samples=12, n_features=3)
        out = explainer._compute_dependence_analysis(make_shap(12, 3), X_narrow)
        assert set(out) == set(X_narrow.columns)


# ---------------------------------------------------------------------------
# generate_shap_plots
# ---------------------------------------------------------------------------


class TestGenerateShapPlots:
    def _results(self, explainer, X, shap_values, expected_value=0.25):
        return {
            "shap_values": shap_values,
            "feature_names": list(X.columns),
            "expected_value": expected_value,
            "global_analysis": explainer._compute_global_analysis(shap_values, X),
            "local_analysis": explainer._compute_local_analysis(shap_values, X),
        }

    def test_all_plot_branches(self, explainer, X, shap_values, fake_plotly):
        results = self._results(explainer, X, shap_values)
        plots = explainer.generate_shap_plots(results)

        assert "shap_summary" in plots
        assert "shap_waterfall" in plots
        assert "shap_force" in plots
        dependence_keys = [k for k in plots if k.startswith("dependence_")]
        assert 0 < len(dependence_keys) <= 5

    def test_dependence_plots_capped_at_five(self, explainer, fake_plotly):
        X_wide = make_X(n_samples=15, n_features=15)
        sv = make_shap(15, 15)
        plots = explainer.generate_shap_plots(self._results(explainer, X_wide, sv))
        assert len([k for k in plots if k.startswith("dependence_")]) == 5

    def test_expected_value_list_multiclass(
        self, explainer, X, shap_values, fake_plotly
    ):
        results = self._results(explainer, X, shap_values, expected_value=[0.1, 0.9])
        plots = explainer.generate_shap_plots(results)
        assert "Expected Value: 0.900" in plots["shap_force"].annotations[0]["text"]

    def test_expected_value_single_element_list(
        self, explainer, X, shap_values, fake_plotly
    ):
        results = self._results(explainer, X, shap_values, expected_value=[0.4])
        plots = explainer.generate_shap_plots(results)
        assert "Expected Value: 0.400" in plots["shap_force"].annotations[0]["text"]

    def test_minimal_results_only_force_plot(self, explainer, shap_values, fake_plotly):
        plots = explainer.generate_shap_plots(
            {"shap_values": shap_values, "expected_value": 0.0}
        )
        assert list(plots) == ["shap_force"]

    def test_empty_sample_analysis_skips_waterfall(self, explainer, fake_plotly):
        plots = explainer.generate_shap_plots(
            {
                "shap_values": None,
                "local_analysis": {"sample_analysis": [], "dependence_analysis": {}},
            }
        )
        assert "shap_waterfall" not in plots

    def test_global_analysis_without_importance(self, explainer, fake_plotly):
        plots = explainer.generate_shap_plots(
            {"shap_values": None, "global_analysis": {}}
        )
        assert "shap_summary" not in plots

    def test_missing_plotly_returns_empty_dict(
        self, explainer, X, shap_values, monkeypatch
    ):
        monkeypatch.setitem(sys.modules, "plotly", None)
        monkeypatch.setitem(sys.modules, "plotly.express", None)
        assert (
            explainer.generate_shap_plots(self._results(explainer, X, shap_values))
            == {}
        )


# ---------------------------------------------------------------------------
# get_feature_importance
# ---------------------------------------------------------------------------


class TestGetFeatureImportance:
    def test_no_results(self, explainer):
        assert explainer.get_feature_importance() == []

    def test_missing_global_analysis(self, explainer):
        explainer.shap_results = {"explainer_type": "tree"}
        assert explainer.get_feature_importance() == []

    def test_missing_feature_importance_key(self, explainer):
        explainer.shap_results = {"global_analysis": {"top_features": []}}
        assert explainer.get_feature_importance() == []

    def test_returns_top_n(self, fitted_explainer):
        assert len(fitted_explainer.get_feature_importance(top_n=3)) == 3
        assert len(fitted_explainer.get_feature_importance()) == N_FEATURES

    def test_top_n_larger_than_available(self, fitted_explainer):
        assert len(fitted_explainer.get_feature_importance(top_n=999)) == N_FEATURES


# ---------------------------------------------------------------------------
# get_sample_explanation
# ---------------------------------------------------------------------------


class TestGetSampleExplanation:
    def test_no_results(self, explainer):
        assert explainer.get_sample_explanation() == {
            "error": "No SHAP analysis results available"
        }

    def test_missing_local_analysis(self, explainer):
        explainer.shap_results = {"global_analysis": {}}
        assert "error" in explainer.get_sample_explanation()

    def test_missing_sample_analysis(self, explainer):
        explainer.shap_results = {"local_analysis": {"dependence_analysis": {}}}
        assert explainer.get_sample_explanation() == {
            "error": "No sample analysis available"
        }

    def test_index_out_of_range(self, fitted_explainer):
        out = fitted_explainer.get_sample_explanation(sample_index=500)
        assert out == {"error": "Sample index 500 out of range"}

    def test_happy_path(self, fitted_explainer):
        out = fitted_explainer.get_sample_explanation(sample_index=2)
        assert out["sample_index"] == 2
        assert "top_contributors" in out


# ---------------------------------------------------------------------------
# save_shap_results / _prepare_results_for_serialization
# ---------------------------------------------------------------------------


class TestSaveShapResults:
    def test_no_results_raises(self, explainer, tmp_path):
        with pytest.raises(ValueError, match="No SHAP results to save"):
            explainer.save_shap_results(str(tmp_path / "out.json"))

    def test_json_roundtrip(self, fitted_explainer, tmp_path):
        target = tmp_path / "shap.json"
        returned = fitted_explainer.save_shap_results(str(target))
        assert returned == str(target)

        payload = json.loads(target.read_text())
        assert payload["explainer_type"] == "tree"
        assert len(payload["global_analysis"]["feature_importance"]) == N_FEATURES

    def test_format_is_case_insensitive(self, fitted_explainer, tmp_path):
        target = tmp_path / "shap_upper.json"
        fitted_explainer.save_shap_results(str(target), format="JSON")
        assert target.exists()

    def test_unsupported_format_raises(self, fitted_explainer, tmp_path):
        with pytest.raises(ValueError, match="Unsupported format: pickle"):
            fitted_explainer.save_shap_results(
                str(tmp_path / "out.pkl"), format="pickle"
            )

    def test_unwritable_path_reraises(self, fitted_explainer, tmp_path):
        bad = tmp_path / "does" / "not" / "exist.json"
        with pytest.raises(OSError):
            fitted_explainer.save_shap_results(str(bad))

    def test_numpy_arrays_are_converted(self, fitted_explainer, tmp_path):
        fitted_explainer.shap_results["raw"] = {
            "matrix": np.arange(4).reshape(2, 2),
            "nested": [np.array([1.5, 2.5]), {"inner": np.array([3])}],
        }
        target = tmp_path / "np.json"
        fitted_explainer.save_shap_results(str(target))
        payload = json.loads(target.read_text())
        assert payload["raw"]["matrix"] == [[0, 1], [2, 3]]
        assert payload["raw"]["nested"][0] == [1.5, 2.5]
        assert payload["raw"]["nested"][1]["inner"] == [3]


class TestPrepareResultsForSerialization:
    def test_converts_nested_numpy(self, explainer):
        out = explainer._prepare_results_for_serialization(
            {
                "arr": np.array([1, 2, 3]),
                "d": {"inner": np.array([[1.0]])},
                "l": [np.array([4]), "text", 7],
                "scalar": 1.25,
            }
        )
        assert out["arr"] == [1, 2, 3]
        assert out["d"]["inner"] == [[1.0]]
        assert out["l"] == [[4], "text", 7]
        assert out["scalar"] == 1.25

    def test_does_not_mutate_input(self, explainer):
        original = {"arr": np.array([1, 2])}
        explainer._prepare_results_for_serialization(original)
        assert isinstance(original["arr"], np.ndarray)


# ---------------------------------------------------------------------------
# get_shap_summary
# ---------------------------------------------------------------------------


class TestGetShapSummary:
    def test_without_analysis(self, explainer):
        assert explainer.get_shap_summary() == {"status": "No SHAP analysis performed"}

    def test_with_full_results(self, fitted_explainer):
        summary = fitted_explainer.get_shap_summary()
        assert summary["explainer_type"] == "tree"
        assert summary["n_features"] == N_FEATURES
        assert summary["expected_value"] == 0.25
        assert len(summary["top_features"]) == N_FEATURES

    def test_top_features_capped_at_ten(self, explainer):
        X_wide = make_X(n_samples=12, n_features=25)
        explainer.shap_results = {
            "explainer_type": "kernel",
            "feature_names": list(X_wide.columns),
            "global_analysis": explainer._compute_global_analysis(
                make_shap(12, 25), X_wide
            ),
        }
        summary = explainer.get_shap_summary()
        assert len(summary["top_features"]) == 10
        assert summary["expected_value"] is None

    def test_without_global_analysis(self, explainer):
        explainer.shap_results = {"explainer_type": "linear", "feature_names": ["A"]}
        summary = explainer.get_shap_summary()
        assert "top_features" not in summary
        assert summary["n_features"] == 1

    def test_global_analysis_without_top_features(self, explainer):
        explainer.shap_results = {
            "explainer_type": "linear",
            "global_analysis": {"feature_importance": []},
        }
        assert "top_features" not in explainer.get_shap_summary()
