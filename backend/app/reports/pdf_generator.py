"""
PDF report generator for biomarker analysis results.
"""

import base64
import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from ..utils.logging_config import get_logger
from .html_generator import HTMLReportGenerator

logger = get_logger(__name__)


class PDFReportGenerator:
    """Generates PDF reports for biomarker analysis."""

    def __init__(self):
        """Initialize PDF report generator."""
        if not REPORTLAB_AVAILABLE:
            logger.warning(
                "ReportLab not available. PDF generation will use HTML conversion."
            )

        self.html_generator = HTMLReportGenerator()
        self.styles = self._setup_styles() if REPORTLAB_AVAILABLE else None

    def _setup_styles(self):
        """Setup ReportLab styles."""
        styles = getSampleStyleSheet()

        # Custom styles - only add if they don't exist
        if "CustomTitle" not in styles.byName:
            styles.add(
                ParagraphStyle(
                    name="CustomTitle",
                    parent=styles["Heading1"],
                    fontSize=24,
                    spaceAfter=30,
                    alignment=TA_CENTER,
                    textColor=colors.darkblue,
                )
            )

        if "SectionHeader" not in styles.byName:
            styles.add(
                ParagraphStyle(
                    name="SectionHeader",
                    parent=styles["Heading2"],
                    fontSize=16,
                    spaceAfter=12,
                    textColor=colors.darkblue,
                )
            )

        if "BodyText" not in styles.byName:
            styles.add(
                ParagraphStyle(
                    name="BodyText", parent=styles["Normal"], fontSize=10, spaceAfter=6
                )
            )

        return styles

    def generate_report(
        self,
        analysis_run: Any,
        results: List[Any],
        clinical_annotations: Optional[Dict] = None,
        title: Optional[str] = None,
        output_path: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate a PDF report.

        Args:
            analysis_run: Analysis run object
            results: List of biomarker results
            clinical_annotations: Clinical annotation data
            title: Report title
            output_path: Output file path
            **kwargs: Additional context variables

        Returns:
            Path to generated PDF file
        """
        if not REPORTLAB_AVAILABLE:
            # Fallback to HTML generation
            logger.info("Using HTML fallback for PDF generation")
            return self._generate_html_fallback(
                analysis_run, results, clinical_annotations, title, **kwargs
            )

        try:
            if output_path is None:
                output_path = f"reports/{analysis_run.id}/biomarker_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []

            # Add content
            story.extend(self._create_header(analysis_run, title))
            story.extend(self._create_summary_section(analysis_run, results))
            story.extend(self._create_statistics_section(results))
            story.extend(self._create_biomarkers_table(results))

            if clinical_annotations:
                story.extend(self._create_clinical_section(clinical_annotations))

            story.extend(self._create_footer())

            # Build PDF
            doc.build(story)

            logger.info(f"Generated PDF report: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            # Fallback to HTML
            return self._generate_html_fallback(
                analysis_run, results, clinical_annotations, title, **kwargs
            )

    def _create_header(self, analysis_run: Any, title: Optional[str] = None) -> List:
        """Create report header."""
        elements = []

        # Title
        title_text = title or f"Biomarker Analysis Report - {analysis_run.project_name}"
        elements.append(Paragraph(title_text, self.styles["CustomTitle"]))
        elements.append(Spacer(1, 20))

        # Meta information table
        meta_data = [
            ["Run ID:", analysis_run.id],
            ["Project:", analysis_run.project_name],
            ["Analysis Type:", analysis_run.analysis_type],
            ["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ]

        meta_table = Table(meta_data, colWidths=[1.5 * inch, 3 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(meta_table)
        elements.append(Spacer(1, 20))

        return elements

    def _create_summary_section(self, analysis_run: Any, results: List[Any]) -> List:
        """Create executive summary section."""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))

        # Summary statistics
        total_biomarkers = len(results)
        significant_biomarkers = len([r for r in results if r.p_value < 0.05])
        high_confidence_biomarkers = len(
            [r for r in results if getattr(r, "final_score", 0) > 0.7]
        )

        summary_text = f"""
        This biomarker analysis identified {total_biomarkers} potential biomarkers from the dataset. 
        Of these, {significant_biomarkers} biomarkers showed statistical significance (p < 0.05), 
        and {high_confidence_biomarkers} biomarkers achieved high confidence scores (>0.7).
        """

        elements.append(Paragraph(summary_text, self.styles["BodyText"]))
        elements.append(Spacer(1, 12))

        # Summary table
        summary_data = [
            ["Metric", "Count"],
            ["Total Biomarkers", str(total_biomarkers)],
            ["Significant (p<0.05)", str(significant_biomarkers)],
            ["High Confidence (>0.7)", str(high_confidence_biomarkers)],
            [
                "Significance Rate",
                f"{(significant_biomarkers / max(total_biomarkers, 1) * 100):.1f}%",
            ],
        ]

        summary_table = Table(summary_data, colWidths=[2.5 * inch, 1.5 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        return elements

    def _create_statistics_section(self, results: List[Any]) -> List:
        """Create statistical analysis section."""
        elements = []

        elements.append(Paragraph("Statistical Analysis", self.styles["SectionHeader"]))

        # Calculate statistics
        p_values = [r.p_value for r in results if r.p_value is not None]
        log2_fold_changes = [
            r.log2_fold_change for r in results if r.log2_fold_change is not None
        ]
        fold_changes = (
            [2**fc for fc in log2_fold_changes] if log2_fold_changes else []
        )

        import numpy as np

        if p_values and fold_changes:
            stats_text = f"""
        Statistical analysis of {len(results)} biomarkers revealed the following distributions:
        
        P-values: minimum = {min(p_values):.2e}, maximum = {max(p_values):.2e}, 
        median = {np.median(p_values):.2e}
        
        Fold Changes: minimum = {min(fold_changes):.2f}, maximum = {max(fold_changes):.2f}, 
        median = {np.median(fold_changes):.2f}
        """
        elif p_values:
            stats_text = f"""
        Statistical analysis of {len(results)} biomarkers revealed the following distributions:
        
        P-values: minimum = {min(p_values):.2e}, maximum = {max(p_values):.2e}, 
        median = {np.median(p_values):.2e}
        
        Fold Changes: Not available
        """
        else:
            stats_text = f"""
        Statistical analysis of {len(results)} biomarkers: No statistical data available.
        """

        elements.append(Paragraph(stats_text, self.styles["BodyText"]))
        elements.append(Spacer(1, 20))

        return elements

    def _create_biomarkers_table(self, results: List[Any]) -> List:
        """Create top biomarkers table."""
        elements = []

        elements.append(Paragraph("Top Biomarkers", self.styles["SectionHeader"]))

        # Prepare table data
        top_biomarkers = results[:20]  # Top 20
        table_data = [["Rank", "Gene", "P-value", "Fold Change", "Score"]]

        for i, result in enumerate(top_biomarkers):
            # Convert log2_fold_change to fold_change
            fold_change = None
            if (
                hasattr(result, "log2_fold_change")
                and result.log2_fold_change is not None
            ):
                fold_change = 2**result.log2_fold_change
            fold_change_str = f"{fold_change:.2f}" if fold_change is not None else "N/A"

            p_value_str = (
                f"{result.p_value:.2e}"
                if hasattr(result, "p_value") and result.p_value is not None
                else "N/A"
            )

            table_data.append(
                [
                    str(i + 1),
                    getattr(result, "gene_symbol", "N/A"),
                    p_value_str,
                    fold_change_str,
                    f"{getattr(result, 'confidence_score', 0):.3f}",
                ]
            )

        # Create table
        biomarkers_table = Table(
            table_data, colWidths=[0.5 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch]
        )
        biomarkers_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    # Highlight significant biomarkers
                    (
                        "BACKGROUND",
                        (0, 1),
                        (-1, 1),
                        colors.lightgreen,
                    ),  # First row (rank 1)
                ]
            )
        )

        elements.append(biomarkers_table)
        elements.append(Spacer(1, 20))

        return elements

    def _create_clinical_section(self, clinical_annotations: Dict) -> List:
        """Create clinical annotations section."""
        elements = []

        elements.append(Paragraph("Clinical Annotations", self.styles["SectionHeader"]))

        if "annotation_summary" in clinical_annotations:
            summary = clinical_annotations["annotation_summary"]
            clinical_text = f"""
            Clinical database annotation identified {summary.get('total_biomarkers', 0)} biomarkers 
            with clinical relevance information. {summary.get('high_relevance_count', 0)} biomarkers 
            showed high clinical relevance scores.
            """
            elements.append(Paragraph(clinical_text, self.styles["BodyText"]))

        elements.append(Spacer(1, 20))

        return elements

    def _create_footer(self) -> List:
        """Create report footer."""
        elements = []

        elements.append(Spacer(1, 30))
        elements.append(
            Paragraph("Cancer Biomarker Identifier", self.styles["BodyText"])
        )
        elements.append(
            Paragraph(
                f"Generated on {datetime.now().strftime('%B %d, %Y')}",
                self.styles["BodyText"],
            )
        )

        return elements

    def _generate_html_fallback(
        self,
        analysis_run: Any,
        results: List[Any],
        clinical_annotations: Optional[Dict] = None,
        title: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate HTML report as fallback when PDF generation is not available."""
        try:
            html_content = self.html_generator.generate_report(
                analysis_run, results, clinical_annotations, "standard", title, **kwargs
            )

            # Save HTML file
            output_path = f"reports/{analysis_run.id}/biomarker_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.info(f"Generated HTML report as PDF fallback: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate HTML fallback: {str(e)}")
            raise
