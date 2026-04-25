"""
PubMed Data Collector.

PubMed / MEDLINE via NCBI E-utilities (esearch + esummary).
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class PubMedCollector(DataCollectorBase):
    """
    Data collector for PubMed.
    
    PubMed literature data collector
    """
    
    def __init__(self, **kwargs):
        """Initialize PubMed collector."""
        super().__init__(**kwargs)
        
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # PubMed data types
        self.data_types = {
            "literature": "Literature",
            "biomarker_studies": "Biomarker Studies",
            "clinical_trials": "Clinical Trials",
        }
        
        # Pubmed specific configuration
        self.config = kwargs.get('config', {})
    
    def _setup_authentication(self):
        """Setup Pubmed API authentication."""
        # Add authentication headers, tokens, etc.
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available Pubmed datasets."""
        datasets = []
        
        try:
            # Implement dataset discovery logic
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"PUBMED-{data_type}",
                    "name": f"Pubmed {description}",
                    "description": description,
                    "data_type": data_type,
                    "source": "Pubmed"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(
        self,
        data_type: str = "literature",
        query: str = "cancer biomarker",
        max_records: int = 15,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Collect article metadata from PubMed (real E-utilities JSON).
        """
        results: Dict[str, Any] = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {},
        }

        if data_type not in ("literature", "biomarker_studies", "clinical_trials", "default"):
            raise ValueError(f"Unsupported PubMed data_type: {data_type}")

        retmax = min(max(1, int(max_records)), 100)
        r = self._make_request(
            f"{self.base_url}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": query,
                "retmax": retmax,
                "retmode": "json",
                "sort": "relevance",
            },
            timeout=60,
        )
        id_list = r.json().get("esearchresult", {}).get("idlist") or []
        if not id_list:
            raise ValueError(f"No PubMed articles for query: {query}")

        r2 = self._make_request(
            f"{self.base_url}/esummary.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            },
            timeout=60,
        )
        summ = r2.json().get("result", {})
        rows = [summ[i] for i in id_list if isinstance(summ.get(i), dict)]
        df = pd.DataFrame(rows)
        results["data"] = df
        results["records_collected"] = len(df)
        safe_q = "".join(c if c.isalnum() else "_" for c in query[:30])
        self._save_data(df, f"pubmed_{safe_q}_{len(df)}_records.csv")
        return results
