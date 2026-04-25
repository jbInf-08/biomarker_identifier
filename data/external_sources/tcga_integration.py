"""
TCGA (The Cancer Genome Atlas) Data Integration Module

This module provides functionality to download, process, and integrate TCGA datasets
for biomarker discovery validation and benchmarking.
"""

import pandas as pd
import numpy as np
import requests
import os
import gzip
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import logging
from datetime import datetime

from ..utils.logging_config import get_logger

logger = get_logger(__name__)

class TCGADataIntegrator:
    """
    Integrates TCGA datasets for biomarker discovery validation.
    """
    
    def __init__(self, data_dir: str = "data/external_sources/tcga"):
        """
        Initialize TCGA data integrator.
        
        Args:
            data_dir: Directory to store TCGA data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # TCGA API endpoints
        self.tcga_api_base = "https://api.gdc.cancer.gov"
        self.tcga_data_base = "https://api.gdc.cancer.gov/data"
        
        # Known cancer biomarkers for validation
        self.known_biomarkers = {
            'breast_cancer': ['TP53', 'BRCA1', 'BRCA2', 'PIK3CA', 'GATA3', 'CDH1', 'MAP3K1'],
            'lung_cancer': ['TP53', 'KRAS', 'EGFR', 'ALK', 'BRAF', 'MET', 'RET'],
            'colon_cancer': ['APC', 'TP53', 'KRAS', 'PIK3CA', 'SMAD4', 'BRAF', 'CTNNB1'],
            'prostate_cancer': ['TP53', 'PTEN', 'RB1', 'AR', 'MYC', 'ERG', 'TMPRSS2']
        }
        
    def get_tcga_projects(self) -> pd.DataFrame:
        """
        Get list of available TCGA projects.
        
        Returns:
            DataFrame with project information
        """
        try:
            url = f"{self.tcga_api_base}/projects"
            response = requests.get(url, params={'size': 1000})
            response.raise_for_status()
            
            data = response.json()
            projects = []
            
            for project in data['data']:
                if project['id'].startswith('TCGA-'):
                    projects.append({
                        'project_id': project['id'],
                        'name': project['name'],
                        'primary_site': project.get('primary_site', 'Unknown'),
                        'disease_type': project.get('disease_type', 'Unknown'),
                        'summary': project.get('summary', {}).get('case_count', 0)
                    })
            
            return pd.DataFrame(projects)
            
        except Exception as e:
            logger.error(f"Failed to get TCGA projects: {str(e)}")
            raise
    
    def get_expression_data(self, project_id: str, 
                          data_type: str = "Gene Expression Quantification",
                          workflow_type: str = "STAR - Counts") -> Dict[str, Any]:
        """
        Get gene expression data for a TCGA project.
        
        Args:
            project_id: TCGA project ID (e.g., 'TCGA-BRCA')
            data_type: Type of expression data
            workflow_type: Workflow type for data processing
            
        Returns:
            Dictionary with file information and download URLs
        """
        try:
            # Query for expression files
            query = {
                "filters": {
                    "op": "and",
                    "content": [
                        {
                            "op": "in",
                            "content": {
                                "field": "cases.submitter_id",
                                "value": [f"{project_id}-*"]
                            }
                        },
                        {
                            "op": "in",
                            "content": {
                                "field": "files.data_type",
                                "value": [data_type]
                            }
                        },
                        {
                            "op": "in",
                            "content": {
                                "field": "files.analysis.workflow_type",
                                "value": [workflow_type]
                            }
                        }
                    ]
                },
                "format": "json",
                "size": 1000
            }
            
            url = f"{self.tcga_api_base}/files"
            response = requests.post(url, json=query)
            response.raise_for_status()
            
            data = response.json()
            
            # Process file information
            files_info = []
            for file_info in data['data']['hits']:
                files_info.append({
                    'file_id': file_info['id'],
                    'file_name': file_info['file_name'],
                    'file_size': file_info['file_size'],
                    'cases': [case['submitter_id'] for case in file_info['cases']],
                    'download_url': f"{self.tcga_data_base}/{file_info['id']}"
                })
            
            logger.info(f"Found {len(files_info)} expression files for {project_id}")
            
            return {
                'project_id': project_id,
                'files': files_info,
                'total_files': len(files_info),
                'query_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get expression data for {project_id}: {str(e)}")
            raise
    
    def download_expression_file(self, file_info: Dict[str, Any], 
                               output_dir: Optional[str] = None) -> str:
        """
        Download a single expression file.
        
        Args:
            file_info: File information dictionary
            output_dir: Output directory (defaults to self.data_dir)
            
        Returns:
            Path to downloaded file
        """
        try:
            if output_dir is None:
                output_dir = self.data_dir / "expression"
            else:
                output_dir = Path(output_dir)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = output_dir / file_info['file_name']
            
            # Skip if file already exists
            if file_path.exists():
                logger.info(f"File already exists: {file_path}")
                return str(file_path)
            
            # Download file
            logger.info(f"Downloading {file_info['file_name']}...")
            response = requests.get(file_info['download_url'], stream=True)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to download {file_info['file_name']}: {str(e)}")
            raise
    
    def process_expression_file(self, file_path: str) -> pd.DataFrame:
        """
        Process a downloaded TCGA expression file.
        
        Args:
            file_path: Path to the expression file
            
        Returns:
            Processed expression DataFrame
        """
        try:
            file_path = Path(file_path)
            
            # Handle compressed files
            if file_path.suffix == '.gz':
                with gzip.open(file_path, 'rt') as f:
                    df = pd.read_csv(f, sep='\t', index_col=0)
            else:
                df = pd.read_csv(file_path, sep='\t', index_col=0)
            
            # Clean up gene names (remove version numbers)
            df.index = df.index.str.split('.').str[0]
            
            # Remove duplicate genes (keep first occurrence)
            df = df[~df.index.duplicated(keep='first')]
            
            # Filter out low-expression genes
            # Keep genes with at least 1 CPM in at least 10% of samples
            min_samples = max(1, int(0.1 * df.shape[1]))
            df = df[(df > 1).sum(axis=1) >= min_samples]
            
            logger.info(f"Processed expression data: {df.shape[0]} genes, {df.shape[1]} samples")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to process expression file {file_path}: {str(e)}")
            raise
    
    def get_clinical_data(self, project_id: str) -> pd.DataFrame:
        """
        Get clinical data for a TCGA project.
        
        Args:
            project_id: TCGA project ID
            
        Returns:
            Clinical data DataFrame
        """
        try:
            # Query for clinical files
            query = {
                "filters": {
                    "op": "and",
                    "content": [
                        {
                            "op": "in",
                            "content": {
                                "field": "cases.submitter_id",
                                "value": [f"{project_id}-*"]
                            }
                        },
                        {
                            "op": "in",
                            "content": {
                                "field": "files.data_type",
                                "value": ["Clinical Supplement"]
                            }
                        }
                    ]
                },
                "format": "json",
                "size": 100
            }
            
            url = f"{self.tcga_api_base}/files"
            response = requests.post(url, json=query)
            response.raise_for_status()
            
            data = response.json()
            
            if not data['data']['hits']:
                logger.warning(f"No clinical data found for {project_id}")
                return pd.DataFrame()
            
            # Download and process clinical data
            clinical_data = []
            for file_info in data['data']['hits']:
                try:
                    file_path = self.download_expression_file(file_info, 
                                                           self.data_dir / "clinical")
                    
                    # Process clinical file
                    if file_path.endswith('.gz'):
                        with gzip.open(file_path, 'rt') as f:
                            clinical_df = pd.read_csv(f, sep='\t', index_col=0)
                    else:
                        clinical_df = pd.read_csv(file_path, sep='\t', index_col=0)
                    
                    clinical_data.append(clinical_df)
                    
                except Exception as e:
                    logger.warning(f"Failed to process clinical file: {str(e)}")
                    continue
            
            if clinical_data:
                # Combine all clinical data
                combined_clinical = pd.concat(clinical_data, axis=1)
                logger.info(f"Processed clinical data: {combined_clinical.shape}")
                return combined_clinical
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Failed to get clinical data for {project_id}: {str(e)}")
            raise
    
    def create_validation_dataset(self, project_id: str, 
                                cancer_type: str,
                                max_files: int = 50) -> Dict[str, Any]:
        """
        Create a validation dataset for biomarker discovery.
        
        Args:
            project_id: TCGA project ID
            cancer_type: Type of cancer (for known biomarkers)
            max_files: Maximum number of files to download
            
        Returns:
            Dictionary with dataset information
        """
        try:
            logger.info(f"Creating validation dataset for {project_id} ({cancer_type})")
            
            # Get expression data
            expression_info = self.get_expression_data(project_id)
            
            # Limit number of files for testing
            files_to_download = expression_info['files'][:max_files]
            
            # Download and process expression files
            expression_data = []
            sample_metadata = []
            
            for i, file_info in enumerate(files_to_download):
                try:
                    logger.info(f"Processing file {i+1}/{len(files_to_download)}: {file_info['file_name']}")
                    
                    # Download file
                    file_path = self.download_expression_file(file_info)
                    
                    # Process file
                    expr_df = self.process_expression_file(file_path)
                    
                    if not expr_df.empty:
                        expression_data.append(expr_df)
                        
                        # Extract sample metadata
                        for case_id in file_info['cases']:
                            sample_metadata.append({
                                'sample_id': case_id,
                                'file_id': file_info['file_id'],
                                'file_name': file_info['file_name']
                            })
                    
                except Exception as e:
                    logger.warning(f"Failed to process file {file_info['file_name']}: {str(e)}")
                    continue
            
            if not expression_data:
                raise ValueError(f"No valid expression data found for {project_id}")
            
            # Combine expression data
            combined_expression = pd.concat(expression_data, axis=1)
            
            # Get clinical data
            clinical_data = self.get_clinical_data(project_id)
            
            # Create sample labels (simplified for validation)
            sample_labels = []
            for sample_id in combined_expression.columns:
                # Simple binary classification: tumor vs normal
                if 'Tumor' in sample_id or 'TP' in sample_id:
                    sample_labels.append('TUMOR')
                elif 'Normal' in sample_id or 'NT' in sample_id:
                    sample_labels.append('NORMAL')
                else:
                    sample_labels.append('UNKNOWN')
            
            # Create labels DataFrame
            labels_df = pd.DataFrame({
                'sample_id': combined_expression.columns,
                'class_label': sample_labels,
                'cancer_type': cancer_type,
                'project_id': project_id
            })
            
            # Save dataset
            dataset_dir = self.data_dir / "validation_datasets" / project_id
            dataset_dir.mkdir(parents=True, exist_ok=True)
            
            # Save expression data
            expr_file = dataset_dir / f"{project_id}_expression.tsv"
            combined_expression.to_csv(expr_file, sep='\t')
            
            # Save labels
            labels_file = dataset_dir / f"{project_id}_labels.tsv"
            labels_df.to_csv(labels_file, sep='\t', index=False)
            
            # Save clinical data if available
            if not clinical_data.empty:
                clinical_file = dataset_dir / f"{project_id}_clinical.tsv"
                clinical_data.to_csv(clinical_file, sep='\t')
            
            # Create dataset summary
            dataset_summary = {
                'project_id': project_id,
                'cancer_type': cancer_type,
                'expression_shape': combined_expression.shape,
                'n_tumor_samples': (labels_df['class_label'] == 'TUMOR').sum(),
                'n_normal_samples': (labels_df['class_label'] == 'NORMAL').sum(),
                'known_biomarkers': self.known_biomarkers.get(cancer_type, []),
                'files_processed': len(expression_data),
                'dataset_dir': str(dataset_dir),
                'created_timestamp': datetime.now().isoformat()
            }
            
            # Save summary
            summary_file = dataset_dir / f"{project_id}_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(dataset_summary, f, indent=2)
            
            logger.info(f"Created validation dataset: {dataset_summary}")
            
            return dataset_summary
            
        except Exception as e:
            logger.error(f"Failed to create validation dataset for {project_id}: {str(e)}")
            raise
    
    def validate_known_biomarkers(self, expression_data: pd.DataFrame,
                                labels: pd.Series,
                                cancer_type: str) -> Dict[str, Any]:
        """
        Validate that known biomarkers show differential expression.
        
        Args:
            expression_data: Gene expression DataFrame
            labels: Sample labels
            cancer_type: Type of cancer
            
        Returns:
            Validation results
        """
        try:
            known_genes = self.known_biomarkers.get(cancer_type, [])
            
            if not known_genes:
                logger.warning(f"No known biomarkers defined for {cancer_type}")
                return {}
            
            # Find available genes
            available_genes = [gene for gene in known_genes if gene in expression_data.index]
            missing_genes = [gene for gene in known_genes if gene not in expression_data.index]
            
            logger.info(f"Found {len(available_genes)}/{len(known_genes)} known biomarkers")
            if missing_genes:
                logger.warning(f"Missing biomarkers: {missing_genes}")
            
            # Calculate differential expression for known biomarkers
            validation_results = {}
            
            for gene in available_genes:
                try:
                    # Get expression values
                    tumor_expr = expression_data.loc[gene, labels == 'TUMOR']
                    normal_expr = expression_data.loc[gene, labels == 'NORMAL']
                    
                    # Calculate statistics
                    tumor_mean = tumor_expr.mean()
                    normal_mean = normal_expr.mean()
                    fold_change = tumor_mean / normal_mean if normal_mean > 0 else np.inf
                    log2_fold_change = np.log2(fold_change) if fold_change != np.inf else np.inf
                    
                    # Simple t-test
                    from scipy import stats
                    t_stat, p_value = stats.ttest_ind(tumor_expr, normal_expr)
                    
                    validation_results[gene] = {
                        'tumor_mean': tumor_mean,
                        'normal_mean': normal_mean,
                        'fold_change': fold_change,
                        'log2_fold_change': log2_fold_change,
                        't_statistic': t_stat,
                        'p_value': p_value,
                        'significant': p_value < 0.05,
                        'available': True
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to validate {gene}: {str(e)}")
                    validation_results[gene] = {
                        'available': False,
                        'error': str(e)
                    }
            
            # Add missing genes
            for gene in missing_genes:
                validation_results[gene] = {
                    'available': False,
                    'error': 'Gene not found in expression data'
                }
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Failed to validate known biomarkers: {str(e)}")
            raise


def main():
    """Main function for testing TCGA integration."""
    integrator = TCGADataIntegrator()
    
    # Test with breast cancer data
    try:
        # Get available projects
        projects = integrator.get_tcga_projects()
        print("Available TCGA projects:")
        print(projects[['project_id', 'name', 'primary_site', 'summary']].head(10))
        
        # Create validation dataset for breast cancer
        dataset_summary = integrator.create_validation_dataset(
            project_id='TCGA-BRCA',
            cancer_type='breast_cancer',
            max_files=10  # Limit for testing
        )
        
        print(f"\nCreated validation dataset:")
        print(json.dumps(dataset_summary, indent=2))
        
    except Exception as e:
        logger.error(f"TCGA integration test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
