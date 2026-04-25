"""
HTML report generator for biomarker analysis results.
"""

import base64
import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from ..utils.logging_config import get_logger
from .template_manager import TemplateManager

logger = get_logger(__name__)


class HTMLReportGenerator:
    """Generates comprehensive HTML reports for biomarker analysis."""

    def __init__(self, template_dir: str = None):
        """
        Initialize HTML report generator.

        Args:
            template_dir: Directory containing HTML templates
        """
        self.template_manager = TemplateManager(template_dir)
        self.setup_matplotlib()

    def setup_matplotlib(self):
        """Setup matplotlib for report generation."""
        plt.style.use("default")
        sns.set_palette("husl")

    def generate_report(
        self,
        analysis_run: Any,
        results: List[Any],
        clinical_annotations: Optional[Dict] = None,
        template_name: str = "standard",
        title: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate a comprehensive HTML report.

        Args:
            analysis_run: Analysis run object
            results: List of biomarker results
            clinical_annotations: Clinical annotation data
            template_name: Template to use
            title: Report title
            **kwargs: Additional context variables

        Returns:
            Generated HTML content
        """
        try:
            # Prepare context data
            context = self._prepare_context(
                analysis_run, results, clinical_annotations, title, **kwargs
            )

            # Generate visualizations
            context["visualizations"] = self._generate_visualizations(results)

            # Render template
            html_content = self.template_manager.render_template(template_name, context)

            logger.info(f"Generated HTML report using template: {template_name}")
            return html_content

        except Exception as e:
            logger.error(f"Failed to generate HTML report: {str(e)}")
            raise

    def _prepare_context(
        self,
        analysis_run: Any,
        results: List[Any],
        clinical_annotations: Optional[Dict] = None,
        title: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare context data for template rendering."""

        # Basic analysis information
        context = {
            "title": title
            or f"Biomarker Analysis Report - {analysis_run.project_name}",
            "run_id": analysis_run.id,
            "project_name": analysis_run.project_name,
            "analysis_type": analysis_run.analysis_type,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "generated_date": datetime.now().strftime("%B %d, %Y"),
            "total_biomarkers": len(results),
            "significant_biomarkers": len([r for r in results if r.p_value < 0.05]),
            "high_confidence_biomarkers": len(
                [r for r in results if getattr(r, "final_score", 0) > 0.7]
            ),
            "configuration": analysis_run.configuration or {},
            "clinical_annotations": clinical_annotations,
            **kwargs,
        }

        # Top biomarkers data
        top_biomarkers = results[:50] if results else []  # Top 50
        context["top_biomarkers"] = [
            {
                "rank": i + 1,
                "gene_symbol": result.gene_symbol,
                "p_value": result.p_value,
                "fold_change": 2**result.log2_fold_change
                if result.log2_fold_change is not None
                else None,
                "log2_fold_change": result.log2_fold_change,
                "final_score": getattr(result, "confidence_score", 0),
                "evidence_level": getattr(result, "evidence_level", "Unknown"),
                "description": getattr(result, "gene_name", ""),
                "is_significant": result.p_value < 0.05 if result.p_value else False,
                "is_high_confidence": getattr(result, "confidence_score", 0) > 0.7,
            }
            for i, result in enumerate(top_biomarkers)
        ]

        # Statistical summary - handle empty results
        p_values = [r.p_value for r in results if r.p_value is not None]
        log2_fold_changes = [
            r.log2_fold_change for r in results if r.log2_fold_change is not None
        ]
        fold_changes = (
            [2**fc for fc in log2_fold_changes] if log2_fold_changes else []
        )

        if p_values:
            context["statistics"] = {
                "p_value_stats": {
                    "min": min(p_values),
                    "max": max(p_values),
                    "mean": np.mean(p_values),
                    "median": np.median(p_values),
                    "significant_count": len([p for p in p_values if p < 0.05]),
                }
            }
        else:
            context["statistics"] = {
                "p_value_stats": {
                    "min": None,
                    "max": None,
                    "mean": None,
                    "median": None,
                    "significant_count": 0,
                }
            }

        if fold_changes:
            context["statistics"]["fold_change_stats"] = {
                "min": min(fold_changes),
                "max": max(fold_changes),
                "mean": np.mean(fold_changes),
                "median": np.median(fold_changes),
                "upregulated_count": len([fc for fc in fold_changes if fc > 1]),
                "downregulated_count": len([fc for fc in fold_changes if fc < 1]),
            }
        else:
            context["statistics"]["fold_change_stats"] = {
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "upregulated_count": 0,
                "downregulated_count": 0,
            }

        # Clinical summary if available
        if clinical_annotations:
            context["clinical_summary"] = {
                "total_annotated": len(
                    clinical_annotations.get("annotated_biomarkers", [])
                ),
                "cancer_genes": len(
                    [
                        b
                        for b in clinical_annotations.get("annotated_biomarkers", [])
                        if b.get("clinical_summary", {}).get("is_cancer_gene", False)
                    ]
                ),
                "therapeutic_targets": len(
                    [
                        b
                        for b in clinical_annotations.get("annotated_biomarkers", [])
                        if b.get("clinical_summary", {}).get(
                            "has_therapeutic_implications", False
                        )
                    ]
                ),
                "high_relevance": len(
                    [
                        b
                        for b in clinical_annotations.get("annotated_biomarkers", [])
                        if b.get("clinical_summary", {}).get(
                            "clinical_relevance_score", 0
                        )
                        > 0.5
                    ]
                ),
            }

        return context

    def _generate_visualizations(self, results: List[Any]) -> Dict[str, str]:
        """Generate visualization plots as base64 encoded images."""
        visualizations = {}

        if not results:
            return visualizations

        try:
            # P-value distribution
            p_values = [r.p_value for r in results if r.p_value is not None]
            if p_values:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.hist(
                    p_values,
                    bins=min(50, len(p_values)),
                    alpha=0.7,
                    color="skyblue",
                    edgecolor="black",
                )
                ax.axvline(x=0.05, color="red", linestyle="--", label="p=0.05")
                ax.set_xlabel("P-value")
                ax.set_ylabel("Frequency")
                ax.set_title("P-value Distribution")
                ax.legend()
                ax.set_yscale("log")
                visualizations["pvalue_distribution"] = self._fig_to_base64(fig)
                plt.close(fig)

            # Fold change distribution
            log2_fold_changes = [
                r.log2_fold_change for r in results if r.log2_fold_change is not None
            ]
            if log2_fold_changes:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.hist(
                    log2_fold_changes,
                    bins=min(50, len(log2_fold_changes)),
                    alpha=0.7,
                    color="lightgreen",
                    edgecolor="black",
                )
                ax.axvline(x=0, color="red", linestyle="--", label="FC=1")
                ax.set_xlabel("Log2 Fold Change")
                ax.set_ylabel("Frequency")
                ax.set_title("Fold Change Distribution")
                ax.legend()
                visualizations["foldchange_distribution"] = self._fig_to_base64(fig)
                plt.close(fig)

            # Volcano plot
            if (
                p_values
                and log2_fold_changes
                and len(p_values) == len(log2_fold_changes)
            ):
                fig, ax = plt.subplots(figsize=(10, 8))
                colors_list = [
                    "red" if p < 0.05 and abs(fc) > 1 else "gray"
                    for p, fc in zip(p_values, log2_fold_changes)
                ]
                ax.scatter(
                    log2_fold_changes,
                    [-np.log10(p) for p in p_values],
                    c=colors_list,
                    alpha=0.6,
                )
                ax.axhline(y=-np.log10(0.05), color="red", linestyle="--", alpha=0.5)
                ax.axvline(x=0, color="red", linestyle="--", alpha=0.5)
                ax.set_xlabel("Log2 Fold Change")
                ax.set_ylabel("-Log10 P-value")
                ax.set_title("Volcano Plot")
                visualizations["volcano_plot"] = self._fig_to_base64(fig)
                plt.close(fig)

            # Top biomarkers bar plot
            top_20 = results[:20]
            if top_20:
                fig, ax = plt.subplots(figsize=(12, 8))
                genes = [r.gene_symbol for r in top_20]
                scores = [
                    getattr(
                        r, "confidence_score", -np.log10(r.p_value) if r.p_value else 0
                    )
                    for r in top_20
                ]
                bars = ax.barh(range(len(genes)), scores, color="steelblue")
                ax.set_yticks(range(len(genes)))
                ax.set_yticklabels(genes)
                ax.set_xlabel("Score")
                ax.set_title("Top 20 Biomarkers")
                ax.invert_yaxis()
                visualizations["top_biomarkers"] = self._fig_to_base64(fig)
                plt.close(fig)

        except Exception as e:
            logger.error(f"Failed to generate visualizations: {str(e)}")
            # Return empty dict if visualization generation fails
            visualizations = {}

        return visualizations

    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 encoded string."""
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        buffer.close()
        return f"data:image/png;base64,{image_base64}"
