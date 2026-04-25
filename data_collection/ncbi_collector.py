"""
NCBI Data Collector.

National Center for Biotechnology Information — gene summaries via E-utilities.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class NCBICollector(DataCollectorBase):
    """
    Data collector for NCBI.
    
    National Center for Biotechnology Information data collector
    """
    
    def __init__(self, **kwargs):
        """Initialize NCBI collector."""
        super().__init__(**kwargs)
        
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        self.data_types = {
            "gene": "Gene database (summaries)",
            "genomic_data": "Gene summaries (alias of gene)",
            "protein_data": "Protein Data",
            "literature": "Literature (use PubMed collector)",
        }
        
        # Ncbi specific configuration
        self.config = kwargs.get('config', {})
    
    def _setup_authentication(self):
        """Setup Ncbi API authentication."""
        # Add authentication headers, tokens, etc.
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available Ncbi datasets."""
        datasets = []
        
        try:
            # Implement dataset discovery logic
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"NCBI-{data_type}",
                    "name": f"Ncbi {description}",
                    "description": description,
                    "data_type": data_type,
                    "source": "Ncbi"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(
        self,
        data_type: str = "gene",
        gene_symbol: str = "TP53",
        organism: str = "human",
        max_ids: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Collect gene records from NCBI Gene via esearch + esummary (JSON).
        """
        results: Dict[str, Any] = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {},
        }

        if data_type in ("genomic_data",):
            data_type = "gene"

        if data_type != "gene":
            raise ValueError(
                f"Unsupported NCBI data_type '{data_type}'; use 'gene' or PubMed collector for literature."
            )

        term = f"{gene_symbol}[Gene Name] AND {organism}[Organism]"
        retmax = min(max(1, int(max_ids)), 100)

        r = self._make_request(
            f"{self.base_url}/esearch.fcgi",
            params={
                "db": "gene",
                "term": term,
                "retmax": retmax,
                "retmode": "json",
            },
            timeout=60,
        )
        search = r.json()
        ids = search.get("esearchresult", {}).get("idlist") or []
        if not ids:
            raise ValueError(f"No NCBI Gene IDs for query: {term}")

        r2 = self._make_request(
            f"{self.base_url}/esummary.fcgi",
            params={
                "db": "gene",
                "id": ",".join(ids),
                "retmode": "json",
            },
            timeout=60,
        )
        summ = r2.json().get("result", {})
        rows = [summ[i] for i in ids if isinstance(summ.get(i), dict)]
        df = pd.DataFrame(rows)
        results["data"] = df
        results["records_collected"] = len(df)
        self._save_data(df, f"ncbi_gene_{gene_symbol}_{len(df)}_records.csv")
        return results
