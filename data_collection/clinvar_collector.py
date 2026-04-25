"""
ClinVar Data Collector.

ClinVar database collector with REAL API integration.
"""

import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class ClinVarCollector(DataCollectorBase):
    """
    Data collector for ClinVar.

    Uses NCBI E-utilities (esearch/esummary) to retrieve variant-level
    information and associated clinical significance.
    """

    def __init__(self, **kwargs):
        """Initialize ClinVar collector."""
        super().__init__(**kwargs)

        # ClinVar / NCBI E-utilities endpoints
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        # ClinVar data types
        self.data_types = {
            "genetic_variants": "Genetic Variants",
            "clinical_significance": "Clinical Significance",
            "disease_associations": "Disease Associations",
        }

        # ClinVar specific configuration
        self.config = kwargs.get("config", {})

    def _setup_authentication(self):
        """Setup ClinVar API authentication."""
        super()._setup_authentication()

        headers = {
            "User-Agent": "Cancer-Biomarker-Identifier/1.0",
            "Accept": "application/json",
        }

        # NCBI_API_KEY is automatically attached to E-utilities requests by
        # ``DataCollectorBase._install_ncbi_auth_hook`` — no header injection
        # needed here (E-utilities expects ``api_key`` as a query parameter,
        # not a header).

        self.session.headers.update(headers)

    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available ClinVar datasets."""
        datasets: List[Dict[str, Any]] = []

        try:
            for data_type, description in self.data_types.items():
                datasets.append(
                    {
                        "id": f"ClinVar-{data_type}",
                        "name": f"ClinVar {description}",
                        "description": description,
                        "data_type": data_type,
                        "source": "ClinVar",
                    }
                )

        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Failed to get available datasets: {exc}")

        return datasets

    def collect_data(self, data_type: str = "genetic_variants", **kwargs: Any) -> Dict[str, Any]:
        """
        Collect REAL data from ClinVar.

        Args:
            data_type: One of 'genetic_variants', 'clinical_significance',
                       or 'disease_associations'
            **kwargs:
                - gene_symbol: Optional HGNC gene symbol filter
                - disease_term: Optional disease/phenotype search term
                - max_records: Maximum number of records to retrieve (default 200)

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
            df = self._download_clinvar_data(data_type=data_type, **kwargs)

            if df is None or df.empty:
                raise ValueError(f"No data returned from ClinVar for data_type='{data_type}'")

            results["data"] = df
            results["records_collected"] = len(df)

            filename = f"clinvar_{data_type}_{results['records_collected']}_records.csv"
            self._save_data(df, filename)

        except Exception as exc:
            self.logger.error(f"Failed to collect {data_type} data from ClinVar: {exc}")
            raise

        return results

    def _download_clinvar_data(
        self,
        data_type: str,
        gene_symbol: Optional[str] = None,
        disease_term: Optional[str] = None,
        max_records: int = 200,
    ) -> Optional[pd.DataFrame]:
        """
        Download REAL data from ClinVar using E-utilities.

        Args:
            data_type: Logical data type to retrieve
            gene_symbol: Optional HGNC gene symbol
            disease_term: Optional disease/phenotype search term
            max_records: Maximum number of records to retrieve

        Returns:
            DataFrame with real data or None if download fails.
        """
        # Build search term
        terms = []
        if gene_symbol:
            terms.append(f"{gene_symbol}[gene]")
        if disease_term:
            terms.append(disease_term)
        if not terms:
            # Broad default query focusing on pathogenic/likely pathogenic variants
            terms.append("neoplasms[mesh] AND (pathogenic[clinical_significance] OR likely_pathogenic[clinical_significance])")

        search_term = " AND ".join(terms)

        try:
            # Step 1: esearch to get IDs
            esearch_url = f"{self.base_url}/esearch.fcgi"
            params = {
                "db": "clinvar",
                "term": search_term,
                "retmode": "json",
                "retmax": max_records,
            }

            search_response = self._make_request(esearch_url, params=params, timeout=60)
            search_data = search_response.json()

            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                self.logger.warning(f"ClinVar search returned no IDs for term: {search_term}")
                return None

            # Step 2: esummary in chunks — long id= lists hit HTTP 414 (URI Too Long).
            esummary_url = f"{self.base_url}/esummary.fcgi"
            chunk_size = 80
            records: List[Dict[str, Any]] = []

            for i in range(0, len(id_list), chunk_size):
                chunk = id_list[i : i + chunk_size]
                summary_params = {
                    "db": "clinvar",
                    "id": ",".join(chunk),
                    "retmode": "json",
                }
                summary_response = self._make_request(
                    esummary_url, params=summary_params, timeout=120
                )
                summary_data = summary_response.json()
                result = summary_data.get("result", {})
                uids = result.get("uids", [])

                for uid in uids:
                    if uid not in result:
                        continue
                    rec = result[uid]
                    record: Dict[str, Any] = {
                        "uid": uid,
                        "title": rec.get("title"),
                        "gene_symbol": None,
                        "clinical_significance": None,
                        "conditions": None,
                        "rcv_accession": rec.get("accession"),
                    }

                    genes = rec.get("gene", [])
                    if isinstance(genes, list) and genes:
                        record["gene_symbol"] = ",".join(
                            g.get("symbol", "") for g in genes if g.get("symbol")
                        )

                    clin_sig = rec.get("clinical_significance", {})
                    if isinstance(clin_sig, dict):
                        record["clinical_significance"] = clin_sig.get("description")

                    conditions = rec.get("trait", [])
                    if isinstance(conditions, list) and conditions:
                        record["conditions"] = ",".join(
                            c.get("trait_name", "")
                            for c in conditions
                            if c.get("trait_name")
                        )

                    records.append(record)

            if not records:
                return None

            return pd.DataFrame(records)

        except Exception as exc:
            self.logger.warning(f"ClinVar API request failed: {exc}")
            return None
