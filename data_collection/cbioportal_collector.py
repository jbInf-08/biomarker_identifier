"""
cBioPortal Data Collector.

Public REST API: https://www.cbioportal.org/api (cancer types, studies, sample lists).
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class cBioPortalCollector(DataCollectorBase):
    """
    Data collector for cBioPortal.
    
    cBioPortal data collector
    """
    
    def __init__(self, **kwargs):
        """Initialize cBioPortal collector."""
        super().__init__(**kwargs)
        
        self.base_url = "https://www.cbioportal.org/api"
        
        self.data_types = {
            "cancer_types": "Tumor types in cBioPortal",
            "studies": "Public studies (paginated)",
            "studies_keyword": "Studies matching a keyword (e.g. CCLE, BRCA)",
        }
        
        # cBioPortal specific configuration
        self.config = kwargs.get('config', {})
    
    def _setup_authentication(self):
        """Setup cBioPortal API authentication."""
        # Add authentication headers, tokens, etc.
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available cBioPortal datasets."""
        datasets = []
        
        try:
            # Implement dataset discovery logic
            for dt, description in self.data_types.items():
                datasets.append({
                    "id": f"cBioPortal-{dt}",
                    "name": f"cBioPortal {description}",
                    "description": description,
                    "data_type": dt,
                    "source": "cBioPortal"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(
        self,
        data_type: str = "cancer_types",
        page_size: int = 50,
        study_keyword: str = "brca",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Pull real metadata from the public cBioPortal API.
        """
        results: Dict[str, Any] = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {},
        }

        if data_type == "cancer_types":
            r = self._make_request(f"{self.base_url}/cancer-types", timeout=60)
            records = r.json()
        elif data_type in ("studies", "cancer_genomics", "clinical_data", "multi_omics_data"):
            # legacy names -> studies listing
            r = self._make_request(
                f"{self.base_url}/studies",
                params={
                    "pageSize": min(max(page_size, 1), 500),
                    "pageNumber": 0,
                    "direction": "ASC",
                },
                timeout=120,
            )
            records = r.json()
        elif data_type in ("studies_keyword", "studies_search"):
            r = self._make_request(
                f"{self.base_url}/studies",
                params={
                    "keyword": study_keyword,
                    "pageSize": min(max(page_size, 1), 100),
                },
                timeout=120,
            )
            records = r.json()
        else:
            raise ValueError(
                f"Unknown cBioPortal data_type '{data_type}'. "
                "Use cancer_types, studies, or studies_keyword."
            )

        if not isinstance(records, list):
            raise ValueError("Unexpected cBioPortal API response shape")

        df = pd.DataFrame(records)
        results["data"] = df
        results["records_collected"] = len(df)
        self._save_data(df, f"cbioportal_{data_type}_{len(df)}_records.csv")
        return results
