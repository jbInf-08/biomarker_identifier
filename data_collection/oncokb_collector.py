"""
OncoKB Data Collector.

OncoKB database collector with REAL API integration.
"""

import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class OncoKBCollector(DataCollectorBase):
    """
    Data collector for OncoKB.

    Uses the official OncoKB REST API to retrieve cancer gene and
    therapeutic implication annotations.
    """

    def __init__(self, **kwargs):
        """Initialize OncoKB collector."""
        super().__init__(**kwargs)

        # OncoKB API endpoints
        self.base_url = "https://www.oncokb.org/api"

        # OncoKB data types
        self.data_types = {
            "cancer_genes": "Cancer Genes",
            "drug_targets": "Drug Targets",
            "clinical_evidence": "Clinical Evidence",
        }

        # OncoKB specific configuration
        self.config = kwargs.get("config", {})

    def _setup_authentication(self):
        """Setup OncoKB API authentication."""
        super()._setup_authentication()

        headers = {
            "User-Agent": "Cancer-Biomarker-Identifier/1.0",
            "Accept": "application/json",
        }

        # OncoKB requires an API token (Bearer). Accept ONCOKB_API_KEY for parity with .env.example.
        token = (
            self.config.get("api_token")
            or os.getenv("ONCOKB_API_TOKEN")
            or os.getenv("ONCOKB_API_KEY")
        )
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self.session.headers.update(headers)

    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available OncoKB datasets."""
        datasets: List[Dict[str, Any]] = []

        try:
            for data_type, description in self.data_types.items():
                datasets.append(
                    {
                        "id": f"OncoKB-{data_type}",
                        "name": f"OncoKB {description}",
                        "description": description,
                        "data_type": data_type,
                        "source": "OncoKB",
                    }
                )

        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Failed to get available datasets: {exc}")

        return datasets

    def collect_data(self, data_type: str = "cancer_genes", **kwargs: Any) -> Dict[str, Any]:
        """
        Collect REAL data from OncoKB.

        Args:
            data_type: One of 'cancer_genes', 'drug_targets', 'clinical_evidence'
            **kwargs:
                - gene: Optional gene symbol filter
                - hugo_symbol: Alias for gene

        Returns:
            Dictionary containing collected data and metadata.
        """
        results: Dict[str, Any] = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {},
        }

        try:
            df = self._download_oncokb_data(data_type=data_type, **kwargs)

            if df is None or df.empty:
                raise ValueError(f"No data returned from OncoKB for data_type='{data_type}'")

            results["data"] = df
            results["records_collected"] = len(df)

            filename = f"oncokb_{data_type}_{results['records_collected']}_records.csv"
            self._save_data(df, filename)

        except Exception as exc:
            self.logger.error(f"Failed to collect {data_type} data from OncoKB: {exc}")
            raise

        return results

    def _download_oncokb_data(
        self,
        data_type: str,
        gene: Optional[str] = None,
        hugo_symbol: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Download REAL data from the OncoKB API.

        Args:
            data_type: Logical data type to retrieve
            gene: Optional gene symbol
            hugo_symbol: Optional gene symbol (alias for gene)

        Returns:
            DataFrame with real data or None if download fails.
        """
        endpoint_map = {
            "cancer_genes": "/v1/genes",
            "drug_targets": "/v1/genes",  # filtered by actionable levels
            "clinical_evidence": "/v1/evidences",
        }

        endpoint = endpoint_map.get(data_type, "/v1/genes")
        url = f"{self.base_url}{endpoint}"

        params: Dict[str, Any] = {}
        symbol = gene or hugo_symbol
        if symbol:
            params["hugoSymbol"] = symbol

        try:
            response = self._make_request(url, params=params, timeout=120)
            data = response.json()

            # OncoKB returns either a list or an object with 'data' / 'items'
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = data.get("data") or data.get("items") or []
            else:
                records = []

            if not records:
                return None

            df = pd.json_normalize(records)

            # For drug_targets, keep only records with actionable levels if present
            if data_type == "drug_targets":
                level_cols = [c for c in df.columns if "level" in c.lower()]
                if level_cols:
                    df = df[df[level_cols].notna().any(axis=1)]

            return df

        except Exception as exc:
            self.logger.warning(f"OncoKB API request failed: {exc}")
            err = str(exc).lower()
            if "401" in str(exc) or "unauthorized" in err:
                raise PermissionError(
                    "OncoKB requires ONCOKB_API_TOKEN or ONCOKB_API_KEY (Bearer token from https://www.oncokb.org/apiAccess)"
                ) from exc
            return None
