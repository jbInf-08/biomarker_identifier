"""
GDSC Data Collector.

The CancerRxGene web portal has been retired (HTTP 410). This collector loads
curated GDSC drug annotation tables from a public Zenodo record (supplementary
data from a peer-reviewed drug-response modeling paper; same field names as GDSC).
"""

from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase

# Zenodo: systematic assessment paper — includes GDSC_DrugAnnotation.csv
GDSC_DRUG_ANNOTATION_ZENODO = (
    "https://zenodo.org/records/7264573/files/GDSC_DrugAnnotation.csv?download=1"
)


class GDSCCollector(DataCollectorBase):
    """
    Data collector for GDSC.
    
    Genomics of Drug Sensitivity in Cancer collector
    """
    
    def __init__(self, **kwargs):
        """Initialize GDSC collector."""
        super().__init__(**kwargs)
        
        self.base_url = "https://www.cancerrxgene.org"
        
        self.data_types = {
            "drug_annotation": "GDSC drug annotation table (Zenodo mirror)",
            "drug_sensitivity_data": "Alias of drug_annotation",
            "genomic_data": "Not available via retired portal — use COSMIC/CCLE",
            "cell_line_data": "Not available via retired portal — use CCLE collector",
        }
        
        # Gdsc specific configuration
        self.config = kwargs.get('config', {})
    
    def _setup_authentication(self):
        """Setup Gdsc API authentication."""
        # Add authentication headers, tokens, etc.
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available Gdsc datasets."""
        datasets = []
        
        try:
            # Implement dataset discovery logic
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"GDSC-{data_type}",
                    "name": f"Gdsc {description}",
                    "description": description,
                    "data_type": data_type,
                    "source": "Gdsc"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(
        self,
        data_type: str = "drug_annotation",
        max_rows: int = 500,
        zenodo_csv_url: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Load a slice of the public GDSC drug annotation CSV.
        """
        results: Dict[str, Any] = {
            "data_type": data_type,
            "records_collected": 0,
            "data": None,
            "metadata": {
                "source_note": "CancerRxGene.org retired; data from Zenodo supplementary CSV",
            },
        }

        if data_type in ("drug_sensitivity_data",):
            data_type = "drug_annotation"
        if data_type == "genomic_data":
            raise ValueError(
                "GDSC genomic downloads require COSMIC credentials; use icgc/cosmic/ccle collectors."
            )
        if data_type == "cell_line_data":
            raise ValueError("Use CCLE collector for cell line panels.")

        if data_type != "drug_annotation":
            raise ValueError(f"Unsupported GDSC data_type: {data_type}")

        url = zenodo_csv_url or GDSC_DRUG_ANNOTATION_ZENODO
        cap = min(max(1, int(max_rows)), 50_000)
        r = self._make_request(url, timeout=180)
        df = pd.read_csv(StringIO(r.text), nrows=cap)
        results["data"] = df
        results["records_collected"] = len(df)
        self._save_data(df, f"gdsc_drug_annotation_{len(df)}_rows.csv")
        return results
