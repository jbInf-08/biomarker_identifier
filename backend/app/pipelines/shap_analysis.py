"""
SHAP analysis entrypoint used by Celery tasks.

Delegates to :class:`SHAPExplainer` in ``shap_tools``. Results for identical
``(model_path, data_path, parameters)`` are cached in-process (bounded) to
avoid duplicate heavy work when clients retry.

**Timeouts:** SHAP can take from tens of seconds to many minutes depending on
``n_samples`` and ``n_features``; use the background task ``run_shap_analysis``
rather than synchronous HTTP for large jobs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

import joblib
import pandas as pd

from app.pipelines.shap_tools import SHAPExplainer

_CACHE: Dict[str, Any] = {}
_MAX_CACHE = 64


def _cache_key(model_path: str, data_path: str, parameters: Dict[str, Any]) -> str:
    raw = f"{model_path}|{data_path}|{json.dumps(parameters, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()


class SHAPAnalyzer:
    """Load model + tabular data from disk and run SHAP."""

    def compute_shap_values(
        self,
        *,
        model_path: str = "",
        data_path: str = "",
        parameters: Dict[str, Any] | None = None,
        **kwargs,
    ) -> Dict[str, Any]:
        parameters = parameters or dict(kwargs)
        if not model_path or not data_path:
            raise ValueError("model_path and data_path are required for SHAP analysis")
        key = _cache_key(model_path, data_path, parameters)
        if key in _CACHE:
            return _CACHE[key]

        model = joblib.load(model_path)
        df = pd.read_csv(data_path)
        explainer = SHAPExplainer(config=parameters)
        out = explainer.compute_shap_values(model=model, X=df)

        if len(_CACHE) >= _MAX_CACHE:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = out
        return out
