"""
CCLE Data Collector.

Cell line identifiers from the CCLE study hosted on cBioPortal (public API).
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class CCLECollector(DataCollectorBase):
    """
    Data collector for CCLE.
    
    Cancer Cell Line Encyclopedia collector
    """
    
    def __init__(self, **kwargs):
        """Initialize CCLE collector."""
        super().__init__(**kwargs)
        
        self.cbioportal_api = "https://www.cbioportal.org/api"
        
        # CCLE data types
        self.data_types = {
            "cell_line_data": "Cell Line Data",
            "expression_data": "Expression Data",
            "drug_response_data": "Drug Response Data",
        }
        
        # Ccle specific configuration
        self.config = kwargs.get('config', {})
    
    def _setup_authentication(self):
        """Setup Ccle API authentication."""
        # Add authentication headers, tokens, etc.
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available Ccle datasets."""
        datasets = []
        
        try:
            # Implement dataset discovery logic
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"CCLE-{data_type}",
                    "name": f"Ccle {description}",
                    "description": description,
                    "data_type": data_type,
                    "source": "Ccle"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(
        self,
        data_type: str = "cell_line_data",
        study_id: str = "ccle_broad_2019",
        sample_list_id: str = "ccle_broad_2019_all",
        max_samples: Optional[int] = 2000,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Download CCLE sample identifiers (cell line + tissue) from cBioPortal.
        """
        results: Dict[str, Any] = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {"study_id": study_id, "sample_list_id": sample_list_id},
        }

        if data_type not in ("cell_line_data", "expression_data", "drug_response_data", "default"):
            raise ValueError(f"Unsupported CCLE data_type: {data_type}")

        url = f"{self.cbioportal_api}/sample-lists/{sample_list_id}"
        r = self._make_request(url, timeout=180)
        payload = r.json()
        raw_ids = payload.get("sampleIds") or []
        if max_samples is not None:
            raw_ids = raw_ids[: int(max_samples)]

        rows = []
        for sid in raw_ids:
            if "_" in sid:
                cell, tissue = sid.rsplit("_", 1)
            else:
                cell, tissue = sid, ""
            rows.append(
                {
                    "sample_id": sid,
                    "cell_line": cell,
                    "tissue_site": tissue,
                }
            )

        df = pd.DataFrame(rows)
        results["data"] = df
        results["records_collected"] = len(df)
        self._save_data(df, f"ccle_samples_{study_id}_{len(df)}.csv")
        return results
