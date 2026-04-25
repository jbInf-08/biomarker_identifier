"""
Annotation module for clinical and biological context from cancer databases.
"""

import time
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import requests

from ..services.clinical_api_client import (
    fetch_clinvar_variants,
    fetch_cosmic_mutations,
    fetch_oncokb_cancer_genes,
)
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class GeneAnnotation:
    """
    Handles gene annotation from various cancer databases and knowledge bases.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the GeneAnnotation module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.annotation_results = {}
        self.cache = {}

    def annotate_genes(
        self,
        gene_list: List[str],
        databases: List[str] = None,
        include_expression: bool = True,
        include_mutations: bool = True,
        include_pathways: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Annotate genes with clinical and biological context.

        Args:
            gene_list: List of genes to annotate
            databases: List of databases to query
            include_expression: Include expression data
            include_mutations: Include mutation data
            include_pathways: Include pathway data
            **kwargs: Additional parameters

        Returns:
            Annotation results
        """
        try:
            if databases is None:
                databases = ["COSMIC", "ClinVar", "OncoKB"]

            results = {
                "gene_list": gene_list,
                "databases": databases,
                "annotations": {},
                "summary": {},
            }

            # Annotate each gene
            for gene in gene_list:
                gene_annotation = {
                    "gene": gene,
                    "basic_info": {},
                    "cancer_info": {},
                    "clinical_info": {},
                    "expression_info": {},
                    "mutation_info": {},
                    "pathway_info": {},
                }

                # Basic gene information
                basic_info = self._get_basic_gene_info(gene)
                gene_annotation["basic_info"] = basic_info

                # Cancer-specific information
                cancer_info = self._get_cancer_info(gene, databases)
                gene_annotation["cancer_info"] = cancer_info

                # Clinical information
                clinical_info = self._get_clinical_info(gene, databases)
                gene_annotation["clinical_info"] = clinical_info

                # Expression information (if requested)
                if include_expression:
                    expression_info = self._get_expression_info(gene)
                    gene_annotation["expression_info"] = expression_info

                # Mutation information (if requested)
                if include_mutations:
                    mutation_info = self._get_mutation_info(gene, databases)
                    gene_annotation["mutation_info"] = mutation_info

                # Pathway information (if requested)
                if include_pathways:
                    pathway_info = self._get_pathway_info(gene)
                    gene_annotation["pathway_info"] = pathway_info

                results["annotations"][gene] = gene_annotation

                # Rate limiting
                time.sleep(0.1)

            # Generate summary
            summary = self._generate_annotation_summary(results)
            results["summary"] = summary

            self.annotation_results = results
            logger.info(f"Gene annotation completed for {len(gene_list)} genes")

            return results

        except Exception as e:
            logger.error(f"Failed to annotate genes: {str(e)}")
            raise

    def _get_basic_gene_info(self, gene: str) -> Dict[str, Any]:
        """
        Get basic gene information.

        Args:
            gene: Gene symbol

        Returns:
            Basic gene information
        """
        return {
            "symbol": gene,
            "name": "",
            "chromosome": "",
            "position": "",
            "strand": "",
            "description": "",
            "aliases": [],
            "status": "no_external_source",
        }

    def _get_cancer_info(self, gene: str, databases: List[str]) -> Dict[str, Any]:
        """
        Get cancer-specific information for a gene.

        Args:
            gene: Gene symbol
            databases: List of databases to query

        Returns:
            Cancer information
        """
        cancer_info = {}

        for database in databases:
            try:
                if database == "COSMIC":
                    cosmic_info = self._query_cosmic(gene)
                    cancer_info["COSMIC"] = cosmic_info
                elif database == "OncoKB":
                    oncokb_info = self._query_oncokb(gene)
                    cancer_info["OncoKB"] = oncokb_info
                elif database == "DepMap":
                    depmap_info = self._query_depmap(gene)
                    cancer_info["DepMap"] = depmap_info
                else:
                    cancer_info[database] = {"status": "database_not_implemented"}

            except Exception as e:
                logger.warning(f"Failed to query {database} for {gene}: {str(e)}")
                cancer_info[database] = {"status": "error", "error": str(e)}

        return cancer_info

    def _get_clinical_info(self, gene: str, databases: List[str]) -> Dict[str, Any]:
        """
        Get clinical information for a gene.

        Args:
            gene: Gene symbol
            databases: List of databases to query

        Returns:
            Clinical information
        """
        clinical_info = {}

        for database in databases:
            try:
                if database == "ClinVar":
                    clinvar_info = self._query_clinvar(gene)
                    clinical_info["ClinVar"] = clinvar_info
                elif database == "OncoKB":
                    oncokb_clinical = self._query_oncokb_clinical(gene)
                    clinical_info["OncoKB"] = oncokb_clinical
                else:
                    clinical_info[database] = {"status": "database_not_implemented"}

            except Exception as e:
                logger.warning(f"Failed to query {database} for {gene}: {str(e)}")
                clinical_info[database] = {"status": "error", "error": str(e)}

        return clinical_info

    def _get_expression_info(self, gene: str) -> Dict[str, Any]:
        """
        Get expression information for a gene.

        Args:
            gene: Gene symbol

        Returns:
            Expression information
        """
        # This would typically query databases like Human Protein Atlas, GTEx, etc.
        return {
            "tissue_expression": "",
            "cancer_expression": "",
            "expression_level": "",
            "status": "no_external_source",
        }

    def _get_mutation_info(self, gene: str, databases: List[str]) -> Dict[str, Any]:
        """
        Get mutation information for a gene.

        Args:
            gene: Gene symbol
            databases: List of databases to query

        Returns:
            Mutation information
        """
        mutation_info = {}

        for database in databases:
            try:
                if database == "COSMIC":
                    cosmic_mutations = self._query_cosmic_mutations(gene)
                    mutation_info["COSMIC"] = cosmic_mutations
                elif database == "ClinVar":
                    clinvar_mutations = self._query_clinvar_mutations(gene)
                    mutation_info["ClinVar"] = clinvar_mutations
                else:
                    mutation_info[database] = {"status": "database_not_implemented"}

            except Exception as e:
                logger.warning(f"Failed to query {database} for {gene}: {str(e)}")
                mutation_info[database] = {"status": "error", "error": str(e)}

        return mutation_info

    def _get_pathway_info(self, gene: str) -> Dict[str, Any]:
        """
        Get pathway information for a gene.

        Args:
            gene: Gene symbol

        Returns:
            Pathway information
        """
        # This would typically query databases like KEGG, Reactome, etc.
        return {
            "kegg_pathways": [],
            "reactome_pathways": [],
            "go_terms": [],
            "status": "no_external_source",
        }

    def _query_cosmic(self, gene: str) -> Dict[str, Any]:
        """Query COSMIC via real API. Returns empty when unavailable."""
        data = fetch_cosmic_mutations(gene_symbol=gene, limit=20)
        if data.get("data_source") == "unavailable" or not data.get("mutations"):
            return {"mutations": [], "status": data.get("data_source", "unavailable")}
        return {"mutations": data["mutations"], "status": "api", "total_count": data.get("total_count", 0)}

    def _query_oncokb(self, gene: str) -> Dict[str, Any]:
        """Query OncoKB via real API. Returns empty when unavailable."""
        data = fetch_oncokb_cancer_genes(limit=100)
        genes = [g for g in data.get("cancer_genes", []) if g.get("gene_symbol") == gene]
        if data.get("data_source") == "unavailable" or not genes:
            return {"genes": [], "status": data.get("data_source", "unavailable")}
        return {"genes": genes, "status": "api"}

    def _query_depmap(self, gene: str) -> Dict[str, Any]:
        """DepMap API not integrated. Returns empty."""
        return {"status": "unavailable", "error": "DepMap API not integrated"}

    def _query_clinvar(self, gene: str) -> Dict[str, Any]:
        """Query ClinVar via real API. Returns empty when unavailable."""
        data = fetch_clinvar_variants(gene_symbol=gene, limit=20)
        if data.get("data_source") == "unavailable" or not data.get("variants"):
            return {"variants": [], "status": data.get("data_source", "unavailable")}
        return {"variants": data["variants"], "status": "api", "total_count": data.get("total_count", 0)}

    def _query_oncokb_clinical(self, gene: str) -> Dict[str, Any]:
        """Query OncoKB via real API. Delegates to _query_oncokb."""
        return self._query_oncokb(gene)

    def _query_cosmic_mutations(self, gene: str) -> Dict[str, Any]:
        """Query COSMIC mutations via real API."""
        return self._query_cosmic(gene)

    def _query_clinvar_mutations(self, gene: str) -> Dict[str, Any]:
        """
        Query ClinVar for mutation information via real API.

        Args:
            gene: Gene symbol

        Returns:
            ClinVar mutation information (real data only)
        """
        data = fetch_clinvar_variants(gene_symbol=gene, limit=50)
        if data.get("data_source") == "unavailable" or not data.get("variants"):
            return {"pathogenic_variants": [], "status": data.get("data_source", "unavailable")}
        pathogenic = [
            {"variant": v.get("title", ""), "significance": v.get("clinical_significance", "Unknown")}
            for v in data["variants"]
        ]
        return {"pathogenic_variants": pathogenic, "status": "api", "total_count": len(pathogenic)}

    def _generate_annotation_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate annotation summary.

        Args:
            results: Annotation results

        Returns:
            Summary dictionary
        """
        summary = {
            "n_genes": len(results["gene_list"]),
            "databases_queried": results["databases"],
            "annotation_stats": {},
            "cancer_genes": [],
            "clinical_genes": [],
        }

        # Analyze annotations
        cancer_genes = []
        clinical_genes = []

        for gene, annotation in results["annotations"].items():
            # Check if it's a cancer gene
            cancer_info = annotation.get("cancer_info", {})
            if any(
                db_info.get("status") == "api"
                and (db_info.get("genes") or db_info.get("mutations") or db_info.get("variants"))
                for db_info in list(cancer_info.values()) + list(annotation.get("clinical_info", {}).values())
            ):
                cancer_genes.append(gene)

            # Check if it has clinical significance (real data from API)
            clinical_info = annotation.get("clinical_info", {})
            if any(
                db_info.get("status") == "api"
                and (db_info.get("genes") or db_info.get("variants") or db_info.get("clinical_significance"))
                for db_info in clinical_info.values()
            ):
                clinical_genes.append(gene)

        summary["cancer_genes"] = cancer_genes
        summary["clinical_genes"] = clinical_genes
        summary["annotation_stats"] = {
            "cancer_genes_count": len(cancer_genes),
            "clinical_genes_count": len(clinical_genes),
            "annotated_genes_count": len(results["annotations"]),
        }

        return summary

    def get_gene_annotation(self, gene: str) -> Dict[str, Any]:
        """
        Get annotation for a specific gene.

        Args:
            gene: Gene symbol

        Returns:
            Gene annotation
        """
        if not self.annotation_results or "annotations" not in self.annotation_results:
            return {"error": "No annotation results available"}

        annotations = self.annotation_results["annotations"]
        if gene not in annotations:
            return {"error": f"Gene {gene} not found in annotations"}

        return annotations[gene]

    def get_cancer_genes(self) -> List[str]:
        """
        Get list of cancer-related genes from annotations.

        Returns:
            List of cancer genes
        """
        if not self.annotation_results or "summary" not in self.annotation_results:
            return []

        summary = self.annotation_results["summary"]
        return summary.get("cancer_genes", [])

    def get_clinical_genes(self) -> List[str]:
        """
        Get list of clinically significant genes from annotations.

        Returns:
            List of clinical genes
        """
        if not self.annotation_results or "summary" not in self.annotation_results:
            return []

        summary = self.annotation_results["summary"]
        return summary.get("clinical_genes", [])

    def save_annotation_results(self, output_path: str, format: str = "json") -> str:
        """
        Save annotation results to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if not self.annotation_results:
            raise ValueError("No annotation results to save")

        try:
            if format.lower() == "json":
                import json

                with open(output_path, "w") as f:
                    json.dump(self.annotation_results, f, indent=2, default=str)
            elif format.lower() == "csv":
                # Save summary as CSV
                summary = self.annotation_results.get("summary", {})
                if summary:
                    # Create a flattened summary for CSV
                    flat_summary = {
                        "n_genes": summary.get("n_genes", 0),
                        "cancer_genes_count": summary.get("annotation_stats", {}).get(
                            "cancer_genes_count", 0
                        ),
                        "clinical_genes_count": summary.get("annotation_stats", {}).get(
                            "clinical_genes_count", 0
                        ),
                        "databases": ",".join(summary.get("databases_queried", [])),
                    }
                    df = pd.DataFrame([flat_summary])
                    df.to_csv(output_path, index=False)
                else:
                    # Create empty CSV with headers
                    pd.DataFrame(
                        columns=[
                            "n_genes",
                            "cancer_genes_count",
                            "clinical_genes_count",
                            "databases",
                        ]
                    ).to_csv(output_path, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Annotation results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save annotation results: {str(e)}")
            raise

    def get_annotation_summary(self) -> Dict[str, Any]:
        """
        Get annotation summary.

        Returns:
            Annotation summary dictionary
        """
        if not self.annotation_results:
            return {"status": "No annotation performed"}

        return self.annotation_results.get("summary", {"status": "unknown"})

    def create_evidence_card(self, gene: str) -> Dict[str, Any]:
        """
        Create an evidence card for a gene.

        Args:
            gene: Gene symbol

        Returns:
            Evidence card data
        """
        if not self.annotation_results or "annotations" not in self.annotation_results:
            return {"error": "No annotation results available"}

        annotations = self.annotation_results["annotations"]
        if gene not in annotations:
            return {"error": f"Gene {gene} not found in annotations"}

        annotation = annotations[gene]

        # Create evidence card
        evidence_card = {
            "gene": gene,
            "basic_info": annotation.get("basic_info", {}),
            "cancer_evidence": {
                "cosmic": annotation.get("cancer_info", {}).get("COSMIC", {}),
                "oncokb": annotation.get("cancer_info", {}).get("OncoKB", {}),
                "depmap": annotation.get("cancer_info", {}).get("DepMap", {}),
            },
            "clinical_evidence": {
                "clinvar": annotation.get("clinical_info", {}).get("ClinVar", {}),
                "oncokb_clinical": annotation.get("clinical_info", {}).get(
                    "OncoKB", {}
                ),
            },
            "mutation_evidence": annotation.get("mutation_info", {}),
            "pathway_evidence": annotation.get("pathway_info", {}),
            "expression_evidence": annotation.get("expression_info", {}),
        }

        return evidence_card
