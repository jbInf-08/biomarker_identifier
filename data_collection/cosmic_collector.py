"""
COSMIC (Catalogue of Somatic Mutations in Cancer) Data Collector.

Collects mutation data, cancer gene census, and clinical information from COSMIC.
"""

import base64
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase


class COSMICCollector(DataCollectorBase):
    """
    Data collector for COSMIC (Catalogue of Somatic Mutations in Cancer).
    
    Collects mutation data, cancer gene census, and clinical information.
    """
    
    def __init__(self, **kwargs):
        """Initialize COSMIC collector."""
        super().__init__(**kwargs)
        
        # COSMIC API endpoints
        self.base_url = "https://cancer.sanger.ac.uk/cosmic"
        self.api_url = "https://cancer.sanger.ac.uk/cosmic/api"
        
        # COSMIC data types
        self.data_types = {
            "mutations": "Somatic Mutations",
            "cancer_gene_census": "Cancer Gene Census",
            "clinical": "Clinical Information",
            "drug_resistance": "Drug Resistance",
            "copy_number": "Copy Number Variations",
            "expression": "Gene Expression",
            "methylation": "DNA Methylation"
        }
        
        # COSMIC cancer types
        self.cancer_types = [
            "breast", "lung", "colorectal", "prostate", "ovarian", "pancreatic",
            "liver", "brain", "stomach", "kidney", "bladder", "cervical",
            "endometrial", "thyroid", "melanoma", "leukemia", "lymphoma"
        ]
    
    def _setup_authentication(self):
        """Setup COSMIC API authentication (Sanger HTTP Basic when configured)."""
        super()._setup_authentication()
        headers = {
            "User-Agent": "Cancer-Biomarker-Identifier/1.0",
            "Accept": "application/json",
        }
        email = os.environ.get("COSMIC_API_EMAIL") or self.config.get("cosmic_email")
        secret = (
            os.environ.get("COSMIC_API_KEY")
            or self.config.get("cosmic_api_key")
            or self.config.get("COSMIC_API_KEY")
        )
        if email and secret:
            raw = base64.b64encode(f"{email}:{secret}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {raw}"
        self.session.headers.update(headers)
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available COSMIC datasets."""
        datasets = []
        
        try:
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"COSMIC-{data_type}",
                    "name": f"COSMIC {description}",
                    "description": description,
                    "data_type": data_type,
                    "source": "COSMIC"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(self,
                    data_type: str = "mutations",
                    cancer_type: Optional[str] = None,
                    gene_list: Optional[List[str]] = None,
                    **kwargs) -> Dict[str, Any]:
        """
        Collect data from COSMIC.
        
        Args:
            data_type: Type of data to collect
            cancer_type: Specific cancer type
            gene_list: List of genes to focus on
            
        Returns:
            Dictionary containing collected data and metadata
        """
        results = {
            "data_type": data_type,
            "cancer_type": cancer_type,
            "genes": gene_list,
            "records_collected": 0,
            "data": None,
            "metadata": {}
        }
        
        try:
            if data_type == "mutations":
                results = self._collect_mutation_data(cancer_type, gene_list)
            elif data_type == "cancer_gene_census":
                results = self._collect_cancer_gene_census()
            elif data_type == "clinical":
                results = self._collect_clinical_data(cancer_type)
            elif data_type == "drug_resistance":
                results = self._collect_drug_resistance_data()
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
                
        except Exception as e:
            self.logger.error(f"Failed to collect {data_type} data: {e}")
            raise
            
        return results
    
    def _collect_mutation_data(self,
                              cancer_type: Optional[str] = None,
                              gene_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """Collect mutation data from COSMIC."""
        results = {
            "data_type": "mutations",
            "cancer_type": cancer_type,
            "genes": gene_list,
            "records_collected": 0,
            "data": None
        }
        
        try:
            # Download REAL mutation data from COSMIC API
            real_data = self._download_cosmic_mutations(cancer_type, gene_list)
            
            if real_data is not None and not real_data.empty:
                results["data"] = real_data
                results["records_collected"] = len(real_data)
                
                filename = f"cosmic_mutations_{cancer_type or 'all'}_{len(real_data)}_records.csv"
                self._save_data(real_data, filename)
            else:
                raise ValueError("Failed to download real mutation data from COSMIC API")
            
        except Exception as e:
            self.logger.error(f"Failed to collect mutation data: {e}")
            raise
            
        return results
    
    def _collect_cancer_gene_census(self) -> Dict[str, Any]:
        """Collect cancer gene census data from COSMIC."""
        results = {
            "data_type": "cancer_gene_census",
            "records_collected": 0,
            "data": None
        }
        
        try:
            # Download REAL cancer gene census from COSMIC
            url = f"{self.api_url}/cancer_gene_census"
            response = self._make_request(url, params={"format": "json"})
            
            if response.status_code != 200:
                raise ValueError(f"COSMIC API returned status {response.status_code}")

            try:
                data = response.json()
            except ValueError as exc:
                raise PermissionError(
                    "COSMIC cancer gene census requires authenticated Sanger COSMIC API access "
                    "(response was not JSON). Obtain COSMIC credentials at cancer.sanger.ac.uk/cosmic."
                ) from exc
            if data and "data" in data:
                real_data = pd.DataFrame(data["data"])
                results["data"] = real_data
                results["records_collected"] = len(real_data)

                filename = f"cosmic_cancer_gene_census_{len(real_data)}_genes.csv"
                self._save_data(real_data, filename)
            else:
                raise ValueError("No real cancer gene census data from COSMIC API")
            
        except Exception as e:
            self.logger.error(f"Failed to collect cancer gene census: {e}")
            raise
            
        return results
    
    def _collect_clinical_data(self,
                              cancer_type: Optional[str] = None) -> Dict[str, Any]:
        """Collect clinical data from COSMIC."""
        results = {
            "data_type": "clinical",
            "cancer_type": cancer_type,
            "records_collected": 0,
            "data": None
        }
        
        try:
            # Download REAL clinical data from COSMIC API
            url = f"{self.api_url}/clinical"
            params = {}
            if cancer_type:
                params["cancer_type"] = cancer_type
            
            response = self._make_request(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    real_data = pd.DataFrame(data)
                elif data and "data" in data:
                    real_data = pd.DataFrame(data["data"])
                else:
                    raise ValueError("No real clinical data from COSMIC API")
                
                results["data"] = real_data
                results["records_collected"] = len(real_data)
                
                filename = f"cosmic_clinical_{cancer_type or 'all'}_{len(real_data)}_samples.csv"
                self._save_data(real_data, filename)
            else:
                raise ValueError(f"COSMIC API returned status {response.status_code}")
            
        except Exception as e:
            self.logger.error(f"Failed to collect clinical data: {e}")
            raise
            
        return results
    
    def _collect_drug_resistance_data(self) -> Dict[str, Any]:
        """Collect drug resistance data from COSMIC."""
        results = {
            "data_type": "drug_resistance",
            "records_collected": 0,
            "data": None
        }
        
        try:
            # Download REAL drug resistance data from COSMIC API
            url = f"{self.api_url}/drug_resistance"
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    real_data = pd.DataFrame(data)
                elif data and "data" in data:
                    real_data = pd.DataFrame(data["data"])
                else:
                    raise ValueError("No real drug resistance data from COSMIC API")
                
                results["data"] = real_data
                results["records_collected"] = len(real_data)
                
                filename = f"cosmic_drug_resistance_{len(real_data)}_records.csv"
                self._save_data(real_data, filename)
            else:
                raise ValueError(f"COSMIC API returned status {response.status_code}")
            
        except Exception as e:
            self.logger.error(f"Failed to collect drug resistance data: {e}")
            raise
            
        return results
    
    def _download_cosmic_mutations(self,
                                  cancer_type: Optional[str] = None,
                                  gene_list: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
        """
        Download REAL mutation data from COSMIC API.
        
        Args:
            cancer_type: Specific cancer type filter
            gene_list: List of genes to filter
            
        Returns:
            DataFrame with real mutation data or None if download fails
        """
        try:
            url = f"{self.api_url}/mutations"
            params = {}
            
            if cancer_type:
                params["cancer_type"] = cancer_type
            if gene_list:
                params["genes"] = ",".join(gene_list[:10])  # Limit to 10 genes
            
            response = self._make_request(url, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    return pd.DataFrame(data)
                elif data and "data" in data:
                    return pd.DataFrame(data["data"])
                elif data and "mutations" in data:
                    return pd.DataFrame(data["mutations"])
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to download COSMIC mutations: {e}")
            return None
    