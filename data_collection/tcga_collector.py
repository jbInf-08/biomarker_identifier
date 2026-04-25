"""
TCGA (The Cancer Genome Atlas) Data Collector.

Collects genomic, transcriptomic, and clinical data from TCGA.
"""

import pandas as pd
import requests
from typing import Dict, List, Optional, Any
from .base_collector import DataCollectorBase
import json
import time
from urllib.parse import urljoin


class TCGACollector(DataCollectorBase):
    """
    Data collector for The Cancer Genome Atlas (TCGA).
    
    Collects gene expression, mutation, copy number, methylation,
    and clinical data from TCGA.
    """
    
    def __init__(self, **kwargs):
        """Initialize TCGA collector."""
        super().__init__(**kwargs)
        
        # TCGA API endpoints
        self.base_url = "https://api.gdc.cancer.gov"
        self.legacy_url = "https://api.gdc.cancer.gov/legacy"
        
        # TCGA data types
        self.data_types = {
            "gene_expression": "Gene Expression Quantification",
            "isoform_expression": "Isoform Expression Quantification", 
            "exon_expression": "Exon Expression Quantification",
            "mirna_expression": "miRNA Expression Quantification",
            "protein_expression": "Protein Expression Quantification",
            "copy_number": "Copy Number Segment",
            "masked_copy_number": "Masked Copy Number Segment",
            "mutation": "Simple Nucleotide Variation",
            "methylation": "DNA Methylation Beta Value",
            "clinical": "Clinical Supplement",
            "biospecimen": "Biospecimen Supplement"
        }
        
        # TCGA cancer types
        self.cancer_types = [
            "ACC", "BLCA", "BRCA", "CESC", "CHOL", "COAD", "DLBC", "ESCA",
            "GBM", "HNSC", "KICH", "KIRC", "KIRP", "LAML", "LGG", "LIHC",
            "LUAD", "LUSC", "MESO", "OV", "PAAD", "PCPG", "PRAD", "READ",
            "SARC", "SKCM", "STAD", "TGCT", "THCA", "THYM", "UCEC", "UCS", "UVM"
        ]
    
    def _setup_authentication(self):
        """Setup TCGA API authentication."""
        # TCGA API is generally open, but we can add token-based auth if needed
        self.session.headers.update({
            'User-Agent': 'Cancer-Biomarker-Identifier/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Get list of available TCGA datasets."""
        datasets = []
        
        try:
            # Get projects (cancer types)
            response = self._make_request(f"{self.base_url}/projects", params={"size": 500})
            projects_data = response.json()
            data_block = projects_data.get("data") or {}
            if isinstance(data_block, list):
                hits = data_block
            else:
                hits = data_block.get("hits") or []

            for project in hits:
                pid = project.get("id") or project.get("project_id") or ""
                if not str(pid).startswith("TCGA-"):
                    continue
                datasets.append({
                    "id": pid,
                    "name": project.get("name", pid),
                    "description": project.get("description", ""),
                    "primary_site": project.get("primary_site", []),
                    "disease_type": project.get("disease_type", []),
                    "data_type": "clinical",
                })
            
            # Add data type specific datasets
            for data_type, description in self.data_types.items():
                datasets.append({
                    "id": f"TCGA-{data_type}",
                    "name": f"TCGA {description}",
                    "description": description,
                    "data_type": data_type
                })
                
        except Exception as e:
            self.logger.error(f"Failed to get available datasets: {e}")
            
        return datasets
    
    def collect_data(self, 
                    data_type: str = "gene_expression",
                    cancer_type: Optional[str] = None,
                    sample_limit: int = 100,
                    **kwargs) -> Dict[str, Any]:
        """
        Collect data from TCGA.
        
        Args:
            data_type: Type of data to collect
            cancer_type: Specific cancer type (e.g., 'BRCA', 'LUAD')
            sample_limit: Maximum number of samples to collect
            
        Returns:
            Dictionary containing collected data and metadata
        """
        results = {
            "data_type": data_type,
            "cancer_type": cancer_type,
            "samples_collected": 0,
            "data": None,
            "metadata": {}
        }
        
        try:
            if data_type == "clinical":
                results = self._collect_clinical_data(cancer_type, sample_limit)
            elif data_type == "gene_expression":
                results = self._collect_gene_expression_data(
                    cancer_type, sample_limit, **kwargs
                )
            elif data_type == "mutation":
                results = self._collect_mutation_data(cancer_type, sample_limit)
            elif data_type == "copy_number":
                results = self._collect_copy_number_data(cancer_type, sample_limit)
            elif data_type == "methylation":
                results = self._collect_methylation_data(cancer_type, sample_limit)
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
                
        except Exception as e:
            self.logger.error(f"Failed to collect {data_type} data: {e}")
            raise
            
        return results
    
    def _collect_clinical_data(self, 
                              cancer_type: Optional[str] = None,
                              sample_limit: int = 100) -> Dict[str, Any]:
        """Collect clinical data from TCGA."""
        results = {
            "data_type": "clinical",
            "cancer_type": cancer_type,
            "samples_collected": 0,
            "data": None
        }
        
        try:
            # Build query for clinical data
            query = {
                "filters": {
                    "op": "and",
                    "content": [
                        {
                            "op": "in",
                            "content": {
                                "field": "cases.submitter_id",
                                "value": []
                            }
                        }
                    ]
                },
                "format": "json",
                "size": sample_limit
            }
            
            # Add cancer type filter if specified
            if cancer_type:
                query["filters"]["content"].append({
                    "op": "in",
                    "content": {
                        "field": "cases.project.program.name",
                        "value": ["TCGA"]
                    }
                })
                query["filters"]["content"].append({
                    "op": "in", 
                    "content": {
                        "field": "cases.project.project_id",
                        "value": [f"TCGA-{cancer_type}"]
                    }
                })
            
            # Get clinical data
            response = self._make_request(
                f"{self.base_url}/clinical",
                method="POST",
                data=json.dumps(query),
                headers={"Content-Type": "application/json"}
            )
            
            clinical_data = response.json()
            
            if clinical_data.get("data"):
                df = pd.DataFrame(clinical_data["data"])
                results["data"] = df
                results["samples_collected"] = len(df)
                
                # Save data
                filename = f"tcga_clinical_{cancer_type or 'all'}_{len(df)}_samples.csv"
                self._save_data(df, filename)
                
        except Exception as e:
            self.logger.error(f"Failed to collect clinical data: {e}")
            raise
            
        return results
    
    def _collect_gene_expression_data(
        self,
        cancer_type: Optional[str] = None,
        sample_limit: int = 100,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Collect gene expression data from TCGA."""
        results = {
            "data_type": "gene_expression",
            "cancer_type": cancer_type,
            "samples_collected": 0,
            "data": None
        }
        
        try:
            # First, get file IDs for gene expression data
            filters_root: Dict[str, Any] = {
                "op": "and",
                "content": [
                    {
                        "op": "in",
                        "content": {
                            "field": "files.data_type",
                            "value": ["Gene Expression Quantification"],
                        },
                    },
                    {
                        "op": "in",
                        "content": {
                            "field": "files.experimental_strategy",
                            "value": ["RNA-Seq"],
                        },
                    },
                ],
            }

            # Add cancer type filter
            if cancer_type:
                filters_root["content"].append(
                    {
                        "op": "in",
                        "content": {
                            "field": "cases.project.project_id",
                            "value": [f"TCGA-{cancer_type}"],
                        },
                    }
                )

            # Optional: restrict to a specific GDC analysis workflow (e.g. HTSeq - FPKM-UQ)
            workflow_type = kwargs.get("workflow_type")
            if workflow_type:
                filters_root["content"].append(
                    {
                        "op": "in",
                        "content": {
                            "field": "analysis.workflow_type",
                            "value": [workflow_type]
                            if isinstance(workflow_type, str)
                            else list(workflow_type),
                        },
                    }
                )

            # GDC caps page size; paginate until we have sample_limit files or exhaust results.
            gdc_page_size = int(kwargs.get("gdc_page_size", 500))
            gdc_page_size = max(1, min(gdc_page_size, 10_000))
            gdc_sort = kwargs.get("gdc_sort", "file_id:asc")

            file_list: List[Dict[str, Any]] = []
            from_idx = 0
            total_available: Optional[int] = None

            while len(file_list) < sample_limit:
                page_size = min(gdc_page_size, sample_limit - len(file_list))
                batch_query: Dict[str, Any] = {
                    "filters": filters_root,
                    "format": "json",
                    "fields": "file_id,file_name,cases.submitter_id",
                    "size": page_size,
                    "from": from_idx,
                }
                if gdc_sort:
                    batch_query["sort"] = gdc_sort

                response = self._make_request(
                    f"{self.base_url}/files",
                    method="POST",
                    data=json.dumps(batch_query),
                    headers={"Content-Type": "application/json"},
                )

                files_data = response.json()
                data_field = files_data.get("data", {})

                pagination = {}
                if isinstance(data_field, list):
                    hits = data_field
                elif isinstance(data_field, dict):
                    hits = data_field.get("hits", data_field.get("data", []))
                    pagination = data_field.get("pagination") or {}
                else:
                    self.logger.error(
                        f"Unexpected data field type: {type(data_field)}. "
                        f"Response keys: {list(files_data.keys())}"
                    )
                    raise ValueError("Invalid response format from GDC API")

                if not isinstance(hits, list):
                    self.logger.error(f"Expected list from GDC API, got {type(hits)}")
                    raise ValueError("Invalid response format from GDC API")

                if pagination and total_available is None:
                    t = pagination.get("total")
                    if t is not None:
                        total_available = int(t)

                if len(hits) == 0:
                    break

                file_list.extend(hits)
                from_idx += len(hits)

                if total_available is not None and from_idx >= total_available:
                    break
                if len(hits) < page_size:
                    break

            if len(file_list) == 0:
                self.logger.warning("No files found in GDC API response")
                raise ValueError("No files found matching query")

            file_list = file_list[:sample_limit]
            
            # Download and process REAL files from GDC
            real_data = self._download_and_process_gdc_files(
                file_list,
                data_type="gene_expression"
            )
            
            if real_data is not None and not real_data.empty:
                results["data"] = real_data
                results["samples_collected"] = len(real_data.columns) if isinstance(real_data, pd.DataFrame) else len(real_data)
                
                # Save REAL data
                filename = f"tcga_gene_expression_{cancer_type or 'all'}_{results['samples_collected']}_samples.csv"
                self._save_data(real_data, filename)
            else:
                self.logger.warning("No real data downloaded from GDC")
                raise ValueError("Failed to download real data from GDC API")
                
        except Exception as e:
            self.logger.error(f"Failed to collect gene expression data: {e}")
            raise
            
        return results
    
    def _collect_mutation_data(self,
                              cancer_type: Optional[str] = None,
                              sample_limit: int = 100) -> Dict[str, Any]:
        """Collect mutation data from TCGA."""
        results = {
            "data_type": "mutation",
            "cancer_type": cancer_type,
            "samples_collected": 0,
            "data": None
        }
        
        try:
            # Get file IDs for mutation data
            query = {
                "filters": {
                    "op": "and",
                    "content": [
                        {
                            "op": "in",
                            "content": {
                                "field": "files.data_type",
                                "value": ["Simple Nucleotide Variation"]
                            }
                        }
                    ]
                },
                "format": "json",
                "size": sample_limit,
                "fields": "file_id,file_name,cases.submitter_id"
            }
            
            if cancer_type:
                query["filters"]["content"].append({
                    "op": "in",
                    "content": {
                        "field": "cases.project.project_id",
                        "value": [f"TCGA-{cancer_type}"]
                    }
                })
            
            response = self._make_request(
                f"{self.base_url}/files",
                method="POST",
                data=json.dumps(query),
                headers={"Content-Type": "application/json"}
            )
            
            files_data = response.json()
            
            # GDC API returns data in "data" or "hits" field
            file_list = files_data.get("data") or files_data.get("hits", [])
            
            if file_list:
                if isinstance(file_list, list):
                    file_list = file_list[:sample_limit]
                real_data = self._download_and_process_gdc_files(file_list, "mutation")
                
                if real_data is not None and not real_data.empty:
                    results["data"] = real_data
                    results["samples_collected"] = len(real_data) if isinstance(real_data, pd.DataFrame) else len(real_data)
                    
                    filename = f"tcga_mutations_{cancer_type or 'all'}_{results['samples_collected']}_samples.csv"
                    self._save_data(real_data, filename)
                else:
                    raise ValueError("Failed to download real mutation data from GDC API")
            else:
                raise ValueError("No mutation files found in GDC")
            
        except Exception as e:
            self.logger.error(f"Failed to collect mutation data: {e}")
            raise
            
        return results
    
    def _collect_copy_number_data(self,
                                 cancer_type: Optional[str] = None,
                                 sample_limit: int = 100) -> Dict[str, Any]:
        """Collect copy number variation data from TCGA."""
        results = {
            "data_type": "copy_number",
            "cancer_type": cancer_type,
            "samples_collected": 0,
            "data": None
        }
        
        try:
            # Get file IDs for copy number data
            query = {
                "filters": {
                    "op": "and",
                    "content": [
                        {
                            "op": "in",
                            "content": {
                                "field": "files.data_type",
                                "value": ["Copy Number Segment"]
                            }
                        }
                    ]
                },
                "format": "json",
                "size": sample_limit,
                "fields": "file_id,file_name,cases.submitter_id"
            }
            
            if cancer_type:
                query["filters"]["content"].append({
                    "op": "in",
                    "content": {
                        "field": "cases.project.project_id",
                        "value": [f"TCGA-{cancer_type}"]
                    }
                })
            
            response = self._make_request(
                f"{self.base_url}/files",
                method="POST",
                data=json.dumps(query),
                headers={"Content-Type": "application/json"}
            )
            
            files_data = response.json()
            
            # GDC API returns data in "data" or "hits" field
            file_list = files_data.get("data") or files_data.get("hits", [])
            
            if file_list:
                if isinstance(file_list, list):
                    file_list = file_list[:sample_limit]
                real_data = self._download_and_process_gdc_files(file_list, "copy_number")
                
                if real_data is not None and not real_data.empty:
                    results["data"] = real_data
                    results["samples_collected"] = len(real_data) if isinstance(real_data, pd.DataFrame) else len(real_data)
                    
                    filename = f"tcga_copy_number_{cancer_type or 'all'}_{results['samples_collected']}_samples.csv"
                    self._save_data(real_data, filename)
                else:
                    raise ValueError("Failed to download real copy number data from GDC API")
            else:
                raise ValueError("No copy number files found in GDC")
            
        except Exception as e:
            self.logger.error(f"Failed to collect copy number data: {e}")
            raise
            
        return results
    
    def _collect_methylation_data(self,
                                 cancer_type: Optional[str] = None,
                                 sample_limit: int = 100) -> Dict[str, Any]:
        """Collect DNA methylation data from TCGA."""
        results = {
            "data_type": "methylation",
            "cancer_type": cancer_type,
            "samples_collected": 0,
            "data": None
        }
        
        try:
            # Create mock methylation data
            # Download REAL methylation data from GDC
            query = {
                "filters": {
                    "op": "and",
                    "content": [
                        {
                            "op": "in",
                            "content": {
                                "field": "files.data_type",
                                "value": ["DNA Methylation Beta Value"]
                            }
                        }
                    ]
                },
                "format": "json",
                "size": sample_limit,
                "fields": "file_id,file_name,cases.submitter_id"
            }
            
            if cancer_type:
                query["filters"]["content"].append({
                    "op": "in",
                    "content": {
                        "field": "cases.project.project_id",
                        "value": [f"TCGA-{cancer_type}"]
                    }
                })
            
            response = self._make_request(
                f"{self.base_url}/files",
                method="POST",
                data=json.dumps(query),
                headers={"Content-Type": "application/json"}
            )
            
            files_data = response.json()
            
            if files_data.get("data"):
                real_data = self._download_and_process_gdc_files(files_data["data"], "methylation")
                
                if real_data is not None and not real_data.empty:
                    results["data"] = real_data
                    results["samples_collected"] = len(real_data.columns) if isinstance(real_data, pd.DataFrame) else len(real_data)
                    
                    filename = f"tcga_methylation_{cancer_type or 'all'}_{results['samples_collected']}_samples.csv"
                    self._save_data(real_data, filename)
                else:
                    raise ValueError("Failed to download real methylation data from GDC API")
            else:
                raise ValueError("No methylation files found in GDC")
            
        except Exception as e:
            self.logger.error(f"Failed to collect methylation data: {e}")
            raise
            
        return results
    
    def _download_and_process_gdc_files(self,
                                        file_list: List[Dict[str, Any]],
                                        data_type: str) -> Optional[pd.DataFrame]:
        """
        Download and process REAL files from GDC API.
        
        Args:
            file_list: List of file metadata dictionaries from GDC
            data_type: Type of data being downloaded
            
        Returns:
            Processed DataFrame with real data or None if download fails
        """
        import io
        import gzip
        
        all_data = []
        
        for file_info in file_list:
            try:
                # Handle both dict and string formats
                if isinstance(file_info, dict):
                    # GDC API returns file_id or id field
                    file_id = file_info.get("file_id") or file_info.get("id")
                elif isinstance(file_info, str):
                    file_id = file_info
                else:
                    self.logger.warning(f"Unexpected file_info type: {type(file_info)}, value: {file_info}")
                    continue
                
                if not file_id:
                    self.logger.warning(f"No file_id found in file_info: {file_info}")
                    continue
                
                # Download file from GDC
                download_url = f"{self.base_url}/data/{file_id}"
                self.logger.info(f"Downloading real data file: {file_id}")
                
                response = self._make_request(download_url, method="GET", timeout=120)
                
                # Check if response is successful
                if not response or not hasattr(response, 'content'):
                    self.logger.warning(f"Invalid response for file {file_id}")
                    continue
                
                # Process downloaded file based on data type
                if data_type == "gene_expression":
                    # GDC gene expression files are typically TSV
                    content = response.content
                    
                    if not content or len(content) == 0:
                        self.logger.warning(f"Empty content for file {file_id}")
                        continue
                    
                    # Check if gzipped
                    if content[:2] == b'\x1f\x8b':
                        try:
                            content = gzip.decompress(content)
                        except Exception as e:
                            self.logger.warning(f"Failed to decompress file {file_id}: {e}")
                            continue
                    
                    # Parse TSV
                    try:
                        df = pd.read_csv(io.BytesIO(content), sep='\t', comment='#', low_memory=False)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse TSV for file {file_id}: {e}")
                        continue
                    
                    if df.empty:
                        self.logger.warning(f"Empty DataFrame after parsing file {file_id}")
                        continue
                    
                    # Extract gene expression values (typically column 1 or 2)
                    # Format: gene_id, normalized_count, etc.
                    if len(df.columns) < 2:
                        self.logger.warning(f"Insufficient columns in file {file_id}: {len(df.columns)}")
                        continue
                    
                    gene_col = df.columns[0]
                    # Find the expression value column (usually contains 'normalized', 'count', 'tpm', or 'fpkm')
                    value_col = None
                    for col in df.columns[1:]:
                        col_lower = col.lower()
                        if any(term in col_lower for term in ['normalized', 'count', 'tpm', 'fpkm', 'expression']):
                            value_col = col
                            break
                    
                    # If no expression column found, use the second column
                    if value_col is None:
                        value_col = df.columns[1]
                    
                    # Get sample ID from file info
                    cases = file_info.get("cases", [])
                    if cases and isinstance(cases, list) and len(cases) > 0:
                        case = cases[0] if isinstance(cases[0], dict) else {}
                        sample_id = case.get("submitter_id", file_id[:12])
                    else:
                        sample_id = file_id[:12]
                    
                    # Create sample dataframe with gene IDs as index and expression values as column
                    try:
                        # Convert expression values to numeric
                        expr_values = pd.to_numeric(df[value_col], errors='coerce')
                        
                        # Create Series with gene IDs as index and expression values as data
                        sample_series = pd.Series(expr_values.values, index=df[gene_col], name=sample_id)
                        
                        # Remove any rows with NaN values
                        sample_series = sample_series.dropna()
                        
                        if len(sample_series) == 0:
                            self.logger.warning(f"No valid expression values after processing file {file_id}")
                            continue
                        
                        # Convert to DataFrame with sample_id as column name
                        sample_df = sample_series.to_frame()
                        
                        all_data.append(sample_df)
                        self.logger.info(f"Successfully processed file {file_id}: {len(sample_series)} genes")
                    except Exception as e:
                        self.logger.warning(f"Error processing expression data from file {file_id}: {e}")
                        continue
                
                elif data_type == "mutation":
                    # MAF format (Mutation Annotation Format)
                    content = response.content
                    if content[:2] == b'\x1f\x8b':
                        content = gzip.decompress(content)
                    
                    df = pd.read_csv(io.BytesIO(content), sep='\t', comment='#', low_memory=False)
                    all_data.append(df)
                
                elif data_type == "copy_number":
                    # Copy number segment files
                    content = response.content
                    if content[:2] == b'\x1f\x8b':
                        content = gzip.decompress(content)
                    
                    df = pd.read_csv(io.BytesIO(content), sep='\t', comment='#')
                    all_data.append(df)
                
                elif data_type == "methylation":
                    # Methylation beta value files
                    content = response.content
                    if content[:2] == b'\x1f\x8b':
                        content = gzip.decompress(content)
                    
                    df = pd.read_csv(io.BytesIO(content), sep='\t', comment='#')
                    all_data.append(df)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                file_id_str = file_info.get('file_id', 'unknown') if isinstance(file_info, dict) else str(file_info)
                self.logger.warning(f"Failed to download/process file {file_id_str}: {e}")
                continue
        
        if not all_data:
            return None
        
        # Combine all downloaded data
        if data_type == "gene_expression":
            # Merge expression data by gene
            combined = pd.concat(all_data, axis=1)
            return combined
        else:
            # Concatenate mutation/copy number/methylation data
            combined = pd.concat(all_data, ignore_index=True)
            return combined
