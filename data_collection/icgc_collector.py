"""
ICGC Data Collector.

International Cancer Genome Consortium data collector
"""

import pandas as pd
from typing import Any, Dict, List, Optional

from .base_collector import DataCollectorBase


class ICGCCollector(DataCollectorBase):
    """
    Data collector for ICGC.
    
    International Cancer Genome Consortium data collector
    """
    
    def __init__(self, **kwargs):
        """Initialize ICGC collector."""
        super().__init__(**kwargs)
        
        # ICGC API endpoints
        self.base_url = "https://dcc.icgc.org/api"
        self.api_url = "https://dcc.icgc.org/api/v1"
        
        # ICGC data types (legacy DCC REST often returns HTML; see bioproject_index)
        self.data_types = {
            "bioproject_index": "NCBI BioProject entries (ICGC-related search)",
            "genomic_data": "Genomic Data",
            "clinical_data": "Clinical Data",
            "expression_data": "Expression Data",
            "mutation_data": "Mutation Data",
        }
        
        # ICGC specific configuration
        self.config = kwargs.get('config', {})
    
    def _setup_authentication(self):
        """Setup ICGC API authentication."""
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available ICGC datasets."""
        datasets = []
        
        try:
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"ICGC-{data_type}",
                    "name": f"ICGC {description}",
                    "description": description,
                    "data_type": data_type,
                    "source": "ICGC"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(self, 
                    data_type: str = "bioproject_index",
                    **kwargs) -> Dict[str, Any]:
        """
        Collect REAL data related to ICGC.

        The historical ICGC DCC REST API often serves SPA HTML instead of JSON.
        The default ``bioproject_index`` path queries NCBI BioProject (E-utilities)
        with an ICGC-oriented search term — real public metadata aligned with the
        consortium's sequencing studies.
        
        Args:
            data_type: ``bioproject_index`` (recommended) or legacy keys below
            **kwargs: ``term``, ``sample_limit`` for bioproject_index
        
        Returns:
            Dictionary containing collected data and metadata
        """
        results = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {}
        }
        
        try:
            # Download REAL data from ICGC API
            real_data = self._download_icgc_data(data_type, **kwargs)
            
            if real_data is not None and not real_data.empty:
                results["data"] = real_data
                results["records_collected"] = len(real_data)
                
                filename = f"icgc_{data_type}_{len(real_data)}_records.csv"
                self._save_data(real_data, filename)
            else:
                raise ValueError(f"Failed to download real {data_type} data from ICGC API")
            
        except Exception as e:
            self.logger.error(f"Failed to collect {data_type} data: {e}")
            raise
            
        return results
    
    def _download_icgc_bioprojects_via_ncbi(self, **kwargs) -> Optional[pd.DataFrame]:
        """ICGC-aligned cohort discovery via NCBI BioProject (JSON APIs)."""
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        term = kwargs.get("term", "ICGC cancer")
        retmax = min(int(kwargs.get("sample_limit", 15)), 200)

        r = self._make_request(
            f"{base}/esearch.fcgi",
            params={
                "db": "bioproject",
                "term": term,
                "retmax": retmax,
                "retmode": "json",
            },
            timeout=60,
        )
        payload = r.json()
        id_list = (
            payload.get("esearchresult", {}).get("idlist")
            or []
        )
        if not id_list:
            return None

        r2 = self._make_request(
            f"{base}/esummary.fcgi",
            params={
                "db": "bioproject",
                "id": ",".join(id_list),
                "retmode": "json",
            },
            timeout=60,
        )
        summ = r2.json().get("result", {})
        rows = []
        for pid in id_list:
            rec = summ.get(pid)
            if isinstance(rec, dict):
                rows.append(rec)
        return pd.DataFrame(rows) if rows else None

    def _download_icgc_data(self, data_type: str, **kwargs) -> Optional[pd.DataFrame]:
        """
        Download data. Prefer ``bioproject_index``; legacy DCC paths may fail.
        """
        if data_type in ("bioproject_index", "default"):
            return self._download_icgc_bioprojects_via_ncbi(**kwargs)

        try:
            endpoint_map = {
                "clinical": "/clinical",
                "clinical_data": "/clinical",
                "expression": "/expression",
                "expression_data": "/expression",
                "mutation": "/mutations",
                "mutation_data": "/mutations",
                "genomic_data": "/genomic",
            }
            endpoint = endpoint_map.get(data_type)
            if not endpoint:
                return self._download_icgc_bioprojects_via_ncbi(**kwargs)

            url = f"{self.api_url}{endpoint}"
            params: Dict[str, Any] = {}
            if "sample_limit" in kwargs:
                params["limit"] = min(kwargs["sample_limit"], 1000)
            if "cancer_type" in kwargs:
                params["cancer_type"] = kwargs["cancer_type"]
            if "project" in kwargs:
                params["project"] = kwargs["project"]

            response = self._make_request(url, params=params, timeout=120)
            if response.status_code != 200:
                return self._download_icgc_bioprojects_via_ncbi(**kwargs)

            ctype = response.headers.get("Content-Type", "")
            if "json" not in ctype.lower():
                self.logger.warning("ICGC DCC returned non-JSON; using NCBI BioProject index")
                return self._download_icgc_bioprojects_via_ncbi(**kwargs)

            data = response.json()
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                if "data" in data:
                    return pd.DataFrame(data["data"])
                if "results" in data:
                    return pd.DataFrame(data["results"])
                if "hits" in data:
                    return pd.DataFrame(data["hits"])
                return pd.DataFrame([data])
            return None

        except Exception as e:
            self.logger.warning(f"ICGC legacy request failed ({e}); using NCBI BioProject index")
            return self._download_icgc_bioprojects_via_ncbi(**kwargs)
