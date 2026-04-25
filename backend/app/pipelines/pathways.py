"""
Pathway analysis module for gene set enrichment analysis (GSEA) and over-representation analysis (ORA).
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class PathwayAnalysis:
    """
    Handles pathway analysis including GSEA and ORA for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the PathwayAnalysis module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.pathway_results = {}

    def run_pathway_analysis(
        self,
        gene_list: List[str],
        expression_data: Optional[pd.DataFrame] = None,
        labels: Optional[pd.Series] = None,
        analysis_type: str = "both",
        gene_sets: List[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run pathway analysis on gene list.

        Args:
            gene_list: List of genes to analyze
            expression_data: Expression data matrix (for GSEA)
            labels: Sample labels (for GSEA)
            analysis_type: Type of analysis ("gsea", "ora", "both")
            gene_sets: List of gene set databases to use
            **kwargs: Additional parameters

        Returns:
            Pathway analysis results
        """
        try:
            if gene_sets is None:
                gene_sets = ["KEGG", "REACTOME", "GO_BP"]

            results = {
                "gene_list": gene_list,
                "analysis_type": analysis_type,
                "gene_sets": gene_sets,
                "gsea_results": {},
                "ora_results": {},
                "summary": {},
            }

            # Run GSEA if requested
            if (
                analysis_type in ["gsea", "both"]
                and expression_data is not None
                and labels is not None
            ):
                gsea_results = self._run_gsea(
                    expression_data, labels, gene_sets, **kwargs
                )
                results["gsea_results"] = gsea_results

            # Run ORA if requested
            if analysis_type in ["ora", "both"]:
                ora_results = self._run_ora(gene_list, gene_sets, **kwargs)
                results["ora_results"] = ora_results

            # Generate summary
            summary = self._generate_pathway_summary(results)
            results["summary"] = summary

            # Generate plots
            plots = self._generate_pathway_plots(results)
            results["plots"] = plots

            self.pathway_results = results
            logger.info("Pathway analysis completed")

            return results

        except Exception as e:
            logger.error(f"Failed to run pathway analysis: {str(e)}")
            raise

    def _run_gsea(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        gene_sets: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run Gene Set Enrichment Analysis (GSEA).

        Args:
            expression_data: Expression data matrix
            labels: Sample labels
            gene_sets: List of gene set databases
            **kwargs: Additional parameters

        Returns:
            GSEA results
        """
        try:
            import gseapy as gp

            results = {}

            # Prepare data for GSEA
            # Calculate differential expression statistics
            de_results = self._calculate_differential_expression(
                expression_data, labels
            )

            # Run GSEA for each gene set
            for gene_set in gene_sets:
                try:
                    # Map gene set name to gseapy format
                    gseapy_gene_set = self._map_gene_set_name(gene_set)

                    # Run GSEA
                    gsea_result = gp.gsea(
                        data=de_results,
                        gene_sets=gseapy_gene_set,
                        cls=labels,
                        outdir=None,  # Don't save files
                        min_size=kwargs.get("min_size", 15),
                        max_size=kwargs.get("max_size", 500),
                        permutation_num=kwargs.get("permutation_num", 1000),
                        weighted_score_type=kwargs.get("weighted_score_type", 1),
                        verbose=False,
                    )

                    # Extract results
                    if hasattr(gsea_result, "res2d") and gsea_result.res2d is not None:
                        gsea_df = gsea_result.res2d

                        # Convert to dictionary format
                        gsea_results = []
                        for _, row in gsea_df.iterrows():
                            gsea_results.append(
                                {
                                    "pathway": row.get("Name", ""),
                                    "es": float(row.get("ES", 0)),
                                    "nes": float(row.get("NES", 0)),
                                    "pval": float(row.get("NOM p-val", 1)),
                                    "fdr": float(row.get("FDR q-val", 1)),
                                    "fw_pval": float(row.get("FWER p-val", 1)),
                                    "size": int(row.get("SIZE", 0)),
                                    "leading_edge": row.get("LEADING EDGE", "").split(
                                        ","
                                    )
                                    if pd.notna(row.get("LEADING EDGE", ""))
                                    else [],
                                }
                            )

                        results[gene_set] = {
                            "results": gsea_results,
                            "status": "success",
                        }
                    else:
                        results[gene_set] = {"results": [], "status": "no_results"}

                except Exception as e:
                    logger.warning(f"GSEA failed for {gene_set}: {str(e)}")
                    results[gene_set] = {
                        "results": [],
                        "status": "error",
                        "error": str(e),
                    }

            return results

        except ImportError:
            logger.error(
                "gseapy not available. Please install with: pip install gseapy"
            )
            return {"error": "gseapy not available"}
        except Exception as e:
            logger.error(f"GSEA analysis failed: {str(e)}")
            return {"error": str(e)}

    def _run_ora(
        self, gene_list: List[str], gene_sets: List[str], **kwargs
    ) -> Dict[str, Any]:
        """
        Run Over-Representation Analysis (ORA).

        Args:
            gene_list: List of genes to analyze
            gene_sets: List of gene set databases
            **kwargs: Additional parameters

        Returns:
            ORA results
        """
        try:
            import gseapy as gp

            results = {}

            # Run ORA for each gene set
            for gene_set in gene_sets:
                try:
                    # Map gene set name to gseapy format
                    gseapy_gene_set = self._map_gene_set_name(gene_set)

                    # Run ORA
                    ora_result = gp.enrichr(
                        gene_list=gene_list,
                        gene_sets=gseapy_gene_set,
                        organism="Human",
                        outdir=None,  # Don't save files
                        verbose=False,
                    )

                    # Extract results
                    if (
                        hasattr(ora_result, "results")
                        and ora_result.results is not None
                    ):
                        ora_df = ora_result.results

                        # Convert to dictionary format
                        ora_results = []
                        for _, row in ora_df.iterrows():
                            ora_results.append(
                                {
                                    "pathway": row.get("Term", ""),
                                    "pval": float(row.get("P-value", 1)),
                                    "adj_pval": float(row.get("Adjusted P-value", 1)),
                                    "odds_ratio": float(row.get("Odds Ratio", 0)),
                                    "combined_score": float(
                                        row.get("Combined Score", 0)
                                    ),
                                    "genes": row.get("Genes", "").split(";")
                                    if pd.notna(row.get("Genes", ""))
                                    else [],
                                    "overlap_size": int(row.get("Overlap", 0)),
                                    "pathway_size": int(row.get("Pathway Size", 0)),
                                }
                            )

                        results[gene_set] = {
                            "results": ora_results,
                            "status": "success",
                        }
                    else:
                        results[gene_set] = {"results": [], "status": "no_results"}

                except Exception as e:
                    logger.warning(f"ORA failed for {gene_set}: {str(e)}")
                    results[gene_set] = {
                        "results": [],
                        "status": "error",
                        "error": str(e),
                    }

            return results

        except ImportError:
            logger.error(
                "gseapy not available. Please install with: pip install gseapy"
            )
            return {"error": "gseapy not available"}
        except Exception as e:
            logger.error(f"ORA analysis failed: {str(e)}")
            return {"error": str(e)}

    def _calculate_differential_expression(
        self, expression_data: pd.DataFrame, labels: pd.Series
    ) -> pd.DataFrame:
        """
        Calculate differential expression statistics for GSEA.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels

        Returns:
            Differential expression results DataFrame
        """
        from scipy import stats

        # Calculate t-test for each gene
        de_results = []
        for gene in expression_data.index:
            gene_expr = expression_data.loc[gene]

            # Split by labels
            unique_labels = labels.unique()
            if len(unique_labels) == 2:
                group1 = gene_expr[labels == unique_labels[0]]
                group2 = gene_expr[labels == unique_labels[1]]

                # T-test
                t_stat, p_val = stats.ttest_ind(group1, group2)

                # Log2 fold change
                log2fc = np.log2(group2.mean() + 1e-9) - np.log2(group1.mean() + 1e-9)

                de_results.append(
                    {"gene": gene, "log2fc": log2fc, "pval": p_val, "t_stat": t_stat}
                )

        # Create DataFrame and sort by p-value
        de_df = pd.DataFrame(de_results)
        de_df = de_df.sort_values("pval")

        # Create gseapy-compatible format
        gsea_df = pd.DataFrame(
            {"gene": de_df["gene"], "log2fc": de_df["log2fc"]}
        ).set_index("gene")

        return gsea_df

    def _map_gene_set_name(self, gene_set: str) -> str:
        """
        Map gene set name to gseapy format.

        Args:
            gene_set: Gene set name

        Returns:
            gseapy-compatible gene set name
        """
        mapping = {
            "KEGG": "KEGG_2021_Human",
            "REACTOME": "Reactome_2022",
            "GO_BP": "GO_Biological_Process_2021",
            "GO_MF": "GO_Molecular_Function_2021",
            "GO_CC": "GO_Cellular_Component_2021",
            "HALLMARK": "MSigDB_Hallmark_2020",
            "CURATED": "MSigDB_Curated_2020",
        }

        return mapping.get(gene_set, gene_set)

    def _generate_pathway_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate pathway analysis summary.

        Args:
            results: Pathway analysis results

        Returns:
            Summary dictionary
        """
        summary = {
            "n_genes": len(results.get("gene_list", [])),
            "analysis_type": results.get("analysis_type", "unknown"),
            "gene_sets": results.get("gene_sets", []),
            "gsea_summary": {},
            "ora_summary": {},
        }

        # GSEA summary
        if "gsea_results" in results:
            gsea_results = results["gsea_results"]
            for gene_set, result in gsea_results.items():
                if isinstance(result, dict) and "results" in result:
                    n_pathways = len(result["results"])
                    n_significant = sum(
                        1 for r in result["results"] if r.get("fdr", 1) < 0.05
                    )
                    summary["gsea_summary"][gene_set] = {
                        "n_pathways": n_pathways,
                        "n_significant": n_significant,
                        "status": result.get("status", "unknown"),
                    }

        # ORA summary
        if "ora_results" in results:
            ora_results = results["ora_results"]
            for gene_set, result in ora_results.items():
                if isinstance(result, dict) and "results" in result:
                    n_pathways = len(result["results"])
                    n_significant = sum(
                        1 for r in result["results"] if r.get("adj_pval", 1) < 0.05
                    )
                    summary["ora_summary"][gene_set] = {
                        "n_pathways": n_pathways,
                        "n_significant": n_significant,
                        "status": result.get("status", "unknown"),
                    }

        return summary

    def _generate_pathway_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate pathway analysis plots.

        Args:
            results: Pathway analysis results

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # GSEA plots
            if "gsea_results" in results:
                gsea_results = results["gsea_results"]
                for gene_set, result in gsea_results.items():
                    if (
                        isinstance(result, dict)
                        and "results" in result
                        and result["results"]
                    ):
                        # Enrichment score plot
                        gsea_df = pd.DataFrame(result["results"])
                        if not gsea_df.empty and "nes" in gsea_df.columns:
                            fig_gsea = px.bar(
                                gsea_df.head(20),
                                x="nes",
                                y="pathway",
                                orientation="h",
                                title=f"GSEA Results - {gene_set}",
                                labels={
                                    "nes": "Normalized Enrichment Score",
                                    "pathway": "Pathway",
                                },
                            )
                            plots[f"gsea_{gene_set}"] = fig_gsea

            # ORA plots
            if "ora_results" in results:
                ora_results = results["ora_results"]
                for gene_set, result in ora_results.items():
                    if (
                        isinstance(result, dict)
                        and "results" in result
                        and result["results"]
                    ):
                        # Enrichment plot
                        ora_df = pd.DataFrame(result["results"])
                        if not ora_df.empty and "adj_pval" in ora_df.columns:
                            # -log10(p-value) plot
                            ora_df["neg_log10_pval"] = -np.log10(ora_df["adj_pval"])

                            fig_ora = px.scatter(
                                ora_df.head(50),
                                x="odds_ratio",
                                y="neg_log10_pval",
                                size="overlap_size",
                                hover_data=["pathway"],
                                title=f"ORA Results - {gene_set}",
                                labels={
                                    "odds_ratio": "Odds Ratio",
                                    "neg_log10_pval": "-log10(Adjusted P-value)",
                                    "overlap_size": "Overlap Size",
                                },
                            )
                            plots[f"ora_{gene_set}"] = fig_ora

            # Combined summary plot
            summary = results.get("summary", {})
            if "gsea_summary" in summary and "ora_summary" in summary:
                # Create comparison plot
                comparison_data = []

                for gene_set in results["gene_sets"]:
                    if gene_set in summary["gsea_summary"]:
                        gsea_sig = summary["gsea_summary"][gene_set]["n_significant"]
                        comparison_data.append(
                            {
                                "gene_set": gene_set,
                                "method": "GSEA",
                                "n_significant": gsea_sig,
                            }
                        )

                    if gene_set in summary["ora_summary"]:
                        ora_sig = summary["ora_summary"][gene_set]["n_significant"]
                        comparison_data.append(
                            {
                                "gene_set": gene_set,
                                "method": "ORA",
                                "n_significant": ora_sig,
                            }
                        )

                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)
                    fig_comp = px.bar(
                        comparison_df,
                        x="gene_set",
                        y="n_significant",
                        color="method",
                        title="Significant Pathways by Method and Gene Set",
                        labels={
                            "gene_set": "Gene Set",
                            "n_significant": "Number of Significant Pathways",
                            "method": "Method",
                        },
                    )
                    plots["method_comparison"] = fig_comp

        except ImportError:
            logger.warning("Plotly not available, skipping pathway plots")

        return plots

    def get_significant_pathways(
        self, method: str = "both", gene_set: str = None, p_threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Get significant pathways from analysis.

        Args:
            method: Analysis method ("gsea", "ora", "both")
            gene_set: Specific gene set to filter by
            p_threshold: P-value threshold

        Returns:
            List of significant pathways
        """
        if not self.pathway_results:
            return []

        significant_pathways = []

        # GSEA results
        if method in ["gsea", "both"] and "gsea_results" in self.pathway_results:
            gsea_results = self.pathway_results["gsea_results"]
            for gs, result in gsea_results.items():
                if gene_set is None or gs == gene_set:
                    if isinstance(result, dict) and "results" in result:
                        for pathway in result["results"]:
                            if pathway.get("fdr", 1) < p_threshold:
                                pathway_info = pathway.copy()
                                pathway_info["method"] = "GSEA"
                                pathway_info["gene_set"] = gs
                                significant_pathways.append(pathway_info)

        # ORA results
        if method in ["ora", "both"] and "ora_results" in self.pathway_results:
            ora_results = self.pathway_results["ora_results"]
            for gs, result in ora_results.items():
                if gene_set is None or gs == gene_set:
                    if isinstance(result, dict) and "results" in result:
                        for pathway in result["results"]:
                            if pathway.get("adj_pval", 1) < p_threshold:
                                pathway_info = pathway.copy()
                                pathway_info["method"] = "ORA"
                                pathway_info["gene_set"] = gs
                                significant_pathways.append(pathway_info)

        # Sort by significance
        if significant_pathways:
            if "fdr" in significant_pathways[0]:
                significant_pathways.sort(key=lambda x: x.get("fdr", 1))
            elif "adj_pval" in significant_pathways[0]:
                significant_pathways.sort(key=lambda x: x.get("adj_pval", 1))

        return significant_pathways

    def save_pathway_results(self, output_path: str, format: str = "json") -> str:
        """
        Save pathway analysis results to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if not self.pathway_results:
            raise ValueError("No pathway results to save")

        try:
            if format.lower() == "json":
                import json

                with open(output_path, "w") as f:
                    json.dump(self.pathway_results, f, indent=2, default=str)
            elif format.lower() == "csv":
                # Save significant pathways as CSV
                significant_pathways = self.get_significant_pathways()
                if significant_pathways:
                    df = pd.DataFrame(significant_pathways)
                    df.to_csv(output_path, index=False)
                else:
                    # Create empty CSV with headers
                    pd.DataFrame(
                        columns=[
                            "pathway",
                            "method",
                            "gene_set",
                            "pval",
                            "fdr",
                            "adj_pval",
                        ]
                    ).to_csv(output_path, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Pathway results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save pathway results: {str(e)}")
            raise

    def get_pathway_summary(self) -> Dict[str, Any]:
        """
        Get pathway analysis summary.

        Returns:
            Pathway summary dictionary
        """
        if not self.pathway_results:
            return {"status": "No pathway analysis performed"}

        return self.pathway_results.get("summary", {"status": "unknown"})
