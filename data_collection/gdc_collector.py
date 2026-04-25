"""
GDC Data Collector.

Genomic Data Commons data collector with REAL API integration.
"""

import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class GDCCollector(DataCollectorBase):
    """
    Data collector for the NCI Genomic Data Commons (GDC).

    This implementation uses the public GDC REST API and is designed to
    replace all remaining mock data usage with real API calls.
    """

    def __init__(self, **kwargs):
        """Initialize GDC collector."""
        super().__init__(**kwargs)

        # GDC API endpoint
        self.base_url = "https://api.gdc.cancer.gov"

        # Logical data types exposed by this collector
        self.data_types = {
            "cases": "Case-level clinical data",
            "files": "File metadata",
            "mutations": "Masked somatic mutations",
            "expression": "Gene expression quantification",
        }

        # GDC specific configuration
        self.config = kwargs.get("config", {})

    def _setup_authentication(self):
        """Setup GDC API authentication."""
        super()._setup_authentication()

        headers = {
            "User-Agent": "Cancer-Biomarker-Identifier/1.0",
            "Accept": "application/json",
        }

        # Optional token-based auth (GDC supports tokens for higher rate limits)
        token = self.config.get("api_token") or os.getenv("GDC_API_TOKEN")
        if token:
            headers["X-Auth-Token"] = token

        self.session.headers.update(headers)

    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Return logical dataset groupings exposed by this collector."""
        datasets: List[Dict[str, Any]] = []

        try:
            for data_type, description in self.data_types.items():
                datasets.append(
                    {
                        "id": f"GDC-{data_type}",
                        "name": f"GDC {description}",
                        "description": description,
                        "data_type": data_type,
                        "source": "GDC",
                    }
                )

        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Failed to get available datasets: {exc}")

        return datasets

    def collect_data(self, data_type: str = "cases", **kwargs: Any) -> Dict[str, Any]:
        """
        Collect REAL data from the GDC API.

        Args:
            data_type: Logical data type to download (cases, files, mutations, expression)
            **kwargs: Additional collection parameters:
                - project (e.g., 'TCGA-BRCA')
                - size (max records, default 100)
                - filters (raw GDC filters JSON)

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
            df = self._download_gdc_data(data_type=data_type, **kwargs)

            if df is None or df.empty:
                raise ValueError(f"No data returned from GDC for data_type='{data_type}'")

            results["data"] = df
            results["records_collected"] = len(df)

            filename = f"gdc_{data_type}_{results['records_collected']}_records.csv"
            self._save_data(df, filename)

        except Exception as exc:
            self.logger.error(f"Failed to collect {data_type} data from GDC: {exc}")
            raise

        return results

    def _download_gdc_data(
        self,
        data_type: str,
        project: Optional[str] = None,
        size: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Download REAL data from the GDC API.

        This uses the standard GDC /cases and /files endpoints and supports
        basic project-level filtering.

        Args:
            data_type: One of 'cases', 'files', 'mutations', 'expression'
            project: Optional GDC project ID (e.g., 'TCGA-BRCA')
            size: Maximum number of records to return (up to 10,000)
            filters: Optional raw GDC filters JSON payload

        Returns:
            DataFrame with real data or None if download fails.
        """
        endpoint_map = {
            "cases": "/cases",
            "files": "/files",
            # For mutations and expression we still hit /cases or /files and
            # rely on filters / data_type_id; can be extended later.
            "mutations": "/cases",
            "expression": "/files",
        }

        endpoint = endpoint_map.get(data_type, "/cases")
        url = f"{self.base_url}{endpoint}"

        payload: Dict[str, Any] = {
            "size": min(max(size, 1), 10000),
            "from": 0,
        }

        if filters is not None:
            payload["filters"] = filters
        elif project:
            payload["filters"] = {
                "op": "and",
                "content": [
                    {
                        "op": "in",
                        "content": {
                            "field": "cases.project.project_id",
                            "value": [project],
                        },
                    }
                ],
            }

        # Request some common fields for files
        if data_type in ("files", "expression"):
            payload.setdefault(
                "fields",
                ",".join(
                    [
                        "file_id",
                        "file_name",
                        "data_category",
                        "data_type",
                        "experimental_strategy",
                        "cases.case_id",
                        "cases.submitter_id",
                        "cases.disease_type",
                        "cases.primary_site",
                    ]
                ),
            )

        try:
            # GDC expects JSON POST body for complex filters
            import json as _json

            response = self._make_request(
                url,
                method="POST",
                data=_json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=120,
            )

            data = response.json()
            if not isinstance(data, dict) or "data" not in data:
                self.logger.warning("Unexpected GDC response structure")
                return None

            hits = data["data"].get("hits") or []
            if not hits:
                return None

            return pd.json_normalize(hits)

        except Exception as exc:
            self.logger.warning(f"GDC API request failed for data_type='{data_type}': {exc}")
            return None
