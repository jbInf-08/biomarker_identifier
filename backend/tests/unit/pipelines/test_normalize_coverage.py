"""
Self-contained coverage tests for app.pipelines.normalize.

Runs with --noconftest: no shared fixtures are used, all data is built inline.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


def _install_statsmodels_stub():
    """Install a minimal statsmodels stub ONLY when the real package is absent.

    ``app.data_processing`` imports ``statsmodels.stats.multitest.multipletests``
    at module import time. CI has the real dependency; this keeps the module
    importable in leaner local environments without shadowing the real package.
    """
    try:  # pragma: no cover - depends on the environment
        import statsmodels.stats.multitest  # noqa: F401

        return
    except ImportError:
        pass

    import types

    def multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
        pvals = np.asarray(pvals, dtype=float)
        n = pvals.size
        if n == 0:
            return np.array([], dtype=bool), np.array([]), alpha, alpha
        order = np.argsort(pvals)
        ranked = pvals[order] * n / (np.arange(n) + 1)
        adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
        out = np.empty(n, dtype=float)
        out[order] = np.clip(adjusted, 0.0, 1.0)
        return out < alpha, out, alpha, alpha

    statsmodels = types.ModuleType("statsmodels")
    stats_mod = types.ModuleType("statsmodels.stats")
    multitest_mod = types.ModuleType("statsmodels.stats.multitest")
    multitest_mod.multipletests = multipletests
    stats_mod.multitest = multitest_mod
    statsmodels.stats = stats_mod
    sys.modules.setdefault("statsmodels", statsmodels)
    sys.modules.setdefault("statsmodels.stats", stats_mod)
    sys.modules.setdefault("statsmodels.stats.multitest", multitest_mod)


_install_statsmodels_stub()

from app.pipelines.normalize import Normalization  # noqa: E402

RNG = np.random.RandomState(42)


def make_expression(n_genes=12, n_samples=8, seed=0):
    """Genes x samples matrix with strictly positive values."""
    rng = np.random.RandomState(seed)
    values = rng.lognormal(mean=3.0, sigma=0.4, size=(n_genes, n_samples))
    return pd.DataFrame(
        values,
        index=[f"GENE_{i}" for i in range(n_genes)],
        columns=[f"S{j}" for j in range(n_samples)],
    )


def make_batches(n_samples=8):
    return pd.Series(
        ["B1"] * (n_samples // 2) + ["B2"] * (n_samples - n_samples // 2),
        index=[f"S{j}" for j in range(n_samples)],
    )


def make_labels(n_samples=8):
    return pd.Series(
        [0] * (n_samples // 2) + [1] * (n_samples - n_samples // 2),
        index=[f"S{j}" for j in range(n_samples)],
    )


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_config(self):
        norm = Normalization()
        assert norm.config == {}
        assert norm.normalization_results == {}
        assert norm.transformer is not None
        assert norm.batch_corrector is not None

    def test_custom_config_is_stored(self):
        cfg = {"foo": "bar"}
        norm = Normalization(cfg)
        assert norm.config is cfg


# ---------------------------------------------------------------------------
# normalize_data
# ---------------------------------------------------------------------------


class TestNormalizeData:
    def test_log2_happy_path(self):
        data = make_expression()
        norm = Normalization()
        results = norm.normalize_data(data, normalization_method="log2")

        for key in (
            "original_data",
            "transformed_data",
            "corrected_data",
            "final_data",
            "summary",
            "plots",
            "transformation_params",
        ):
            assert key in results
        assert results["normalization_method"] == "log2"
        assert results["batch_correction"] is None
        assert results["final_data"].shape == data.shape
        # no batch correction requested -> corrected == transformed
        pd.testing.assert_frame_equal(
            results["corrected_data"], results["transformed_data"]
        )
        assert norm.normalization_results is results

    def test_method_none_skips_transformation(self):
        data = make_expression()
        norm = Normalization()
        results = norm.normalize_data(data, normalization_method="none")

        assert "transformation_params" not in results
        pd.testing.assert_frame_equal(results["transformed_data"], data)
        assert results["summary"]["steps_applied"] == []

    def test_with_batch_correction(self):
        data = make_expression(n_genes=15, n_samples=10)
        batches = make_batches(10)
        labels = make_labels(10)
        norm = Normalization()

        results = norm.normalize_data(
            data,
            labels=labels,
            batch_info=batches,
            normalization_method="log2",
            batch_correction="mean_centering",
        )

        assert "batch_correction_params" in results
        assert results["batch_correction"] == "mean_centering"
        assert results["corrected_data"].shape == data.shape
        steps = results["summary"]["steps_applied"]
        assert "Transformation: log2" in steps
        assert "Batch correction: mean_centering" in steps
        assert "batch_correction" in results["summary"]["improvements"]

    def test_batch_info_without_method_is_ignored(self):
        data = make_expression()
        norm = Normalization()
        results = norm.normalize_data(
            data, batch_info=make_batches(8), normalization_method="log2"
        )
        assert "batch_correction_params" not in results

    def test_final_normalization_kwarg_is_forwarded(self):
        data = make_expression()
        norm = Normalization()
        results = norm.normalize_data(
            data, normalization_method="log2", final_normalization="zscore"
        )
        final = results["final_data"]
        # z-scored per gene (rows) -> row means ~ 0
        assert np.allclose(final.mean(axis=1).values, 0.0, atol=1e-8)

    def test_unknown_transformation_method_propagates(self):
        data = make_expression()
        norm = Normalization()
        with pytest.raises(ValueError, match="Unknown transformation method"):
            norm.normalize_data(data, normalization_method="definitely_not_real")

    def test_failure_inside_summary_is_reraised(self):
        data = make_expression()
        norm = Normalization()
        with patch.object(
            norm,
            "_generate_normalization_summary",
            side_effect=RuntimeError("summary boom"),
        ):
            with pytest.raises(RuntimeError, match="summary boom"):
                norm.normalize_data(data, normalization_method="log2")


# ---------------------------------------------------------------------------
# _apply_transformation / _apply_batch_correction
# ---------------------------------------------------------------------------


class TestApplyTransformation:
    def test_returns_dataframe(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_transformation(data, "log2")
        assert isinstance(out, pd.DataFrame)
        assert out.shape == data.shape

    def test_kwargs_are_filtered_to_known_names(self):
        data = make_expression()
        norm = Normalization()
        with patch.object(
            norm.transformer, "transform_data", return_value=data
        ) as mocked:
            norm._apply_transformation(
                data, "log2", offset=2, not_a_transform_kwarg=99, pseudocount=1
            )
        _, kwargs = mocked.call_args
        assert kwargs == {"offset": 2, "pseudocount": 1}

    def test_transformation_error_is_reraised(self):
        data = make_expression()
        norm = Normalization()
        with patch.object(
            norm.transformer, "transform_data", side_effect=ValueError("nope")
        ):
            with pytest.raises(ValueError, match="nope"):
                norm._apply_transformation(data, "log2")


class TestApplyBatchCorrection:
    def test_runs_detect_correct_and_evaluate(self):
        data = make_expression(n_genes=15, n_samples=10)
        batches = make_batches(10)
        norm = Normalization()

        out = norm._apply_batch_correction(data, batches, "mean_centering")
        assert isinstance(out, pd.DataFrame)
        assert out.shape == data.shape

    def test_error_is_reraised(self):
        data = make_expression()
        norm = Normalization()
        with patch.object(
            norm.batch_corrector, "detect_batch_effects", side_effect=RuntimeError("bc")
        ):
            with pytest.raises(RuntimeError, match="bc"):
                norm._apply_batch_correction(data, make_batches(8), "mean_centering")


# ---------------------------------------------------------------------------
# _apply_final_normalization
# ---------------------------------------------------------------------------


class TestFinalNormalization:
    def test_none_returns_copy(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(data)
        pd.testing.assert_frame_equal(out, data)
        assert out is not data

    def test_zscore(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(data, final_normalization="zscore")
        assert out.shape == data.shape
        assert out.mean(axis=1).abs().max() == pytest.approx(0.0, abs=1e-8)

    def test_robust_zscore(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(data, final_normalization="robust_zscore")
        assert out.shape == data.shape
        assert out.median(axis=1).abs().max() == pytest.approx(0.0, abs=1e-8)

    def test_quantile(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(data, final_normalization="quantile")
        assert out.shape == data.shape
        # every column ends up with the same multiset of values
        col_sums = out.sum(axis=0).values
        assert np.allclose(col_sums, col_sums[0])

    def test_median_ratio(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(data, final_normalization="median_ratio")
        assert out.shape == data.shape
        assert np.isfinite(out.values).all()

    def test_unknown_method_warns_and_returns_copy(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(data, final_normalization="banana")
        pd.testing.assert_frame_equal(out, data)

    def test_exception_falls_back_to_copy(self):
        # empty frame makes StandardScaler raise -> handler returns a copy
        empty = pd.DataFrame()
        norm = Normalization()
        out = norm._apply_final_normalization(empty, final_normalization="zscore")
        assert out.empty

    def test_extra_kwargs_are_tolerated(self):
        data = make_expression()
        norm = Normalization()
        out = norm._apply_final_normalization(
            data, final_normalization="zscore", unrelated=1
        )
        assert out.shape == data.shape


class TestQuantileNormalize:
    def test_empty_frame_short_circuits(self):
        norm = Normalization()
        empty = pd.DataFrame(index=[], columns=["a", "b"], dtype=float)
        out = norm._quantile_normalize(empty)
        assert out.shape == empty.shape

    def test_no_columns_short_circuits(self):
        norm = Normalization()
        empty = pd.DataFrame(index=["g1", "g2"], dtype=float)
        out = norm._quantile_normalize(empty)
        assert out.shape == empty.shape

    def test_single_row(self):
        norm = Normalization()
        data = pd.DataFrame([[1.0, 5.0, 3.0]], index=["g1"], columns=["a", "b", "c"])
        out = norm._quantile_normalize(data)
        assert out.shape == (1, 3)
        assert out.values.ravel() == pytest.approx([3.0, 3.0, 3.0])

    def test_single_column_preserves_values(self):
        norm = Normalization()
        data = pd.DataFrame([[3.0], [1.0], [2.0]], index=list("xyz"), columns=["a"])
        out = norm._quantile_normalize(data)
        assert sorted(out["a"].tolist()) == pytest.approx([1.0, 2.0, 3.0])

    def test_index_and_columns_preserved(self):
        data = make_expression(n_genes=6, n_samples=4)
        norm = Normalization()
        out = norm._quantile_normalize(data)
        assert list(out.index) == list(data.index)
        assert list(out.columns) == list(data.columns)


class TestMedianRatioNormalize:
    def test_shapes_and_finiteness(self):
        data = make_expression(n_genes=10, n_samples=6)
        norm = Normalization()
        out = norm._median_ratio_normalize(data)
        assert out.shape == data.shape
        assert list(out.index) == list(data.index)
        assert np.isfinite(out.values).all()

    def test_single_sample_is_identity_scaled(self):
        data = pd.DataFrame([[2.0], [4.0], [8.0]], index=list("abc"), columns=["s1"])
        norm = Normalization()
        out = norm._median_ratio_normalize(data)
        # with one sample the size factor is 1 -> values unchanged
        assert out["s1"].tolist() == pytest.approx([2.0, 4.0, 8.0], rel=1e-6)


# ---------------------------------------------------------------------------
# summary generation
# ---------------------------------------------------------------------------


class TestSummary:
    def _minimal_results(self):
        data = make_expression(n_genes=6, n_samples=4)
        return {
            "original_data": data,
            "final_data": data * 2,
            "normalization_method": "log2",
            "batch_correction": None,
        }

    def test_minimal_results(self):
        norm = Normalization()
        summary = norm._generate_normalization_summary(self._minimal_results())
        assert summary["status"] == "completed"
        assert summary["steps_applied"] == []
        assert set(summary["data_statistics"]) == {"original", "final"}
        assert set(summary["data_statistics"]["original"]) == {
            "mean",
            "std",
            "min",
            "max",
            "median",
        }
        assert summary["improvements"] == {}

    def test_transformation_and_batch_branches(self):
        results = self._minimal_results()
        results["transformed_data"] = results["original_data"] + 1
        results["corrected_data"] = results["original_data"] + 2
        results["transformation_params"] = {"method": "log2"}
        results["batch_correction_params"] = {"method": "combat"}
        results["batch_correction"] = "combat"

        norm = Normalization()
        summary = norm._generate_normalization_summary(results)

        assert summary["steps_applied"] == [
            "Transformation: log2",
            "Batch correction: combat",
        ]
        assert set(summary["improvements"]["transformation"]) == {
            "mean",
            "std",
            "skewness",
            "kurtosis",
        }
        assert (
            summary["improvements"]["batch_correction"]["batch_effect_reduction"]
            == "Applied"
        )

    def test_corrected_without_params_skips_batch_improvement(self):
        results = self._minimal_results()
        results["transformed_data"] = results["original_data"]
        results["corrected_data"] = results["original_data"]
        norm = Normalization()
        summary = norm._generate_normalization_summary(results)
        assert "batch_correction" not in summary["improvements"]
        assert "transformation" in summary["improvements"]


class TestGetNormalizationSummary:
    def test_no_run_yet(self):
        norm = Normalization()
        assert norm.get_normalization_summary() == {
            "status": "No normalization performed"
        }

    def test_missing_summary_key(self):
        norm = Normalization()
        norm.normalization_results = {"final_data": make_expression()}
        assert norm.get_normalization_summary() == {"status": "unknown"}

    def test_after_run(self):
        norm = Normalization()
        norm.normalize_data(make_expression(), normalization_method="log2")
        assert norm.get_normalization_summary()["status"] == "completed"


# ---------------------------------------------------------------------------
# plots
# ---------------------------------------------------------------------------


class TestComparisonPlots:
    def test_all_plot_sections_created(self):
        data = make_expression(n_genes=10, n_samples=6)
        results = {"original_data": data, "final_data": data * 2}
        norm = Normalization()
        plots = norm._generate_comparison_plots(results)
        assert set(plots) == {
            "sample_distributions",
            "pca_comparison",
            "distribution_comparison",
        }

    def test_colors_from_labels(self):
        data = make_expression(n_genes=10, n_samples=6)
        results = {"original_data": data, "final_data": data}
        norm = Normalization()
        plots = norm._generate_comparison_plots(results, labels=make_labels(6))
        assert "pca_comparison" in plots

    def test_colors_from_batch_info_when_no_labels(self):
        data = make_expression(n_genes=10, n_samples=6)
        results = {"original_data": data, "final_data": data}
        norm = Normalization()
        plots = norm._generate_comparison_plots(results, batch_info=make_batches(6))
        assert "pca_comparison" in plots

    def test_pca_skipped_for_two_samples(self):
        data = make_expression(n_genes=10, n_samples=2)
        results = {"original_data": data, "final_data": data}
        norm = Normalization()
        plots = norm._generate_comparison_plots(results)
        assert "pca_comparison" not in plots
        assert "sample_distributions" in plots

    def test_missing_keys_produce_no_plots(self):
        norm = Normalization()
        assert norm._generate_comparison_plots({}) == {}

    def test_plotly_missing_is_handled(self):
        data = make_expression(n_genes=6, n_samples=4)
        results = {"original_data": data, "final_data": data}
        norm = Normalization()
        blocked = {
            name: None
            for name in (
                "plotly",
                "plotly.express",
                "plotly.graph_objects",
                "plotly.subplots",
            )
        }
        with patch.dict(sys.modules, blocked):
            plots = norm._generate_comparison_plots(results)
        assert plots == {}


# ---------------------------------------------------------------------------
# saving
# ---------------------------------------------------------------------------


class TestSaveNormalizedData:
    def _fitted(self):
        norm = Normalization()
        norm.normalize_data(
            make_expression(n_genes=6, n_samples=4), normalization_method="log2"
        )
        return norm

    def test_no_results_raises(self, tmp_path):
        norm = Normalization()
        with pytest.raises(ValueError, match="No normalized data to save"):
            norm.save_normalized_data(str(tmp_path / "out.tsv"))

    def test_results_without_final_data_raises(self, tmp_path):
        norm = Normalization()
        norm.normalization_results = {"summary": {}}
        with pytest.raises(ValueError, match="No normalized data to save"):
            norm.save_normalized_data(str(tmp_path / "out.tsv"))

    def test_tsv(self, tmp_path):
        norm = self._fitted()
        out = tmp_path / "out.tsv"
        assert norm.save_normalized_data(str(out)) == str(out)
        assert "\t" in out.read_text()

    def test_csv_case_insensitive(self, tmp_path):
        norm = self._fitted()
        out = tmp_path / "out.csv"
        norm.save_normalized_data(str(out), format="CSV")
        loaded = pd.read_csv(out, index_col=0)
        assert loaded.shape == (6, 4)

    def test_h5_delegates_to_to_hdf(self, tmp_path):
        norm = self._fitted()
        fake = MagicMock()
        norm.normalization_results["final_data"] = fake
        out = tmp_path / "out.h5"
        assert norm.save_normalized_data(str(out), format="h5") == str(out)
        fake.to_hdf.assert_called_once_with(str(out), key="normalized_data")

    def test_unsupported_format_raises(self, tmp_path):
        norm = self._fitted()
        with pytest.raises(ValueError, match="Unsupported format"):
            norm.save_normalized_data(str(tmp_path / "out.xyz"), format="xyz")

    def test_write_failure_is_reraised(self, tmp_path):
        norm = self._fitted()
        fake = MagicMock()
        fake.to_csv.side_effect = OSError("disk full")
        norm.normalization_results["final_data"] = fake
        with pytest.raises(OSError, match="disk full"):
            norm.save_normalized_data(str(tmp_path / "out.tsv"))


class TestSaveNormalizationReport:
    def _fitted(self):
        norm = Normalization()
        norm.normalize_data(
            make_expression(n_genes=6, n_samples=4),
            normalization_method="log2",
            final_normalization="zscore",
        )
        return norm

    def test_no_results_raises(self, tmp_path):
        norm = Normalization()
        with pytest.raises(ValueError, match="No normalization results to save"):
            norm.save_normalization_report(str(tmp_path / "r.html"))

    def test_html(self, tmp_path):
        norm = self._fitted()
        out = tmp_path / "r.html"
        assert norm.save_normalization_report(str(out)) == str(out)
        content = out.read_text()
        assert "<h1>Normalization Report</h1>" in content
        assert "Transformation: log2" in content

    def test_json(self, tmp_path):
        norm = self._fitted()
        out = tmp_path / "r.json"
        norm.save_normalization_report(str(out), format="JSON")
        payload = json.loads(out.read_text())
        assert payload["normalization_method"] == "log2"
        assert "summary" in payload

    def test_unsupported_format_raises(self, tmp_path):
        norm = self._fitted()
        with pytest.raises(ValueError, match="Unsupported format"):
            norm.save_normalization_report(str(tmp_path / "r.pdf"), format="pdf")

    def test_generation_failure_is_reraised(self, tmp_path):
        norm = self._fitted()
        with patch.object(
            norm, "_generate_html_report", side_effect=RuntimeError("render boom")
        ):
            with pytest.raises(RuntimeError, match="render boom"):
                norm.save_normalization_report(str(tmp_path / "r.html"))


class TestHtmlReport:
    def test_empty_results_still_renders(self):
        norm = Normalization()
        norm.normalization_results = {}
        html = norm._generate_html_report()
        assert "<h1>Normalization Report</h1>" in html
        assert "<ul></ul>" in html

    def test_statistics_and_improvements_rendered(self):
        norm = Normalization()
        norm.normalization_results = {
            "summary": {
                "steps_applied": ["Transformation: log2"],
                "data_statistics": {
                    "original": {"mean": 1.0, "std": 2.0, "min": 0.0},
                    "final": {"mean": 3.0, "std": 4.0, "min": 0.5},
                },
                "improvements": {
                    "batch_correction": {
                        "mean": 1.23456,
                        "batch_effect_reduction": "Applied",
                    }
                },
            }
        }
        html = norm._generate_html_report()
        assert "<li>Transformation: log2</li>" in html
        assert "<td>mean</td><td>1.0000</td><td>3.0000</td>" in html
        # max/median missing on both sides -> skipped
        assert "<td>median</td>" not in html
        assert "<h3>Batch_Correction</h3>" in html
        assert "<li>mean: 1.2346</li>" in html
        assert "<li>batch_effect_reduction: Applied</li>" in html

    def test_partial_statistics_are_skipped(self):
        norm = Normalization()
        norm.normalization_results = {
            "summary": {"data_statistics": {"original": {"mean": 1.0}}}
        }
        html = norm._generate_html_report()
        assert "<td>mean</td>" not in html
