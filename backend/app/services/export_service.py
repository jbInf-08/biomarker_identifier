"""
Advanced Data Export and Sharing Service
Provides comprehensive data export capabilities for analysis results
"""

import base64
import json
import logging
import os
import smtplib
import tempfile
import zipfile
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import db_session
from app.models.biomarker_model import BiomarkerResult
from app.models.run_model import AnalysisRun

logger = logging.getLogger(__name__)


def _fmt_num(value, fmt: str = "{:.4f}") -> str:
    if value is None:
        return "N/A"
    try:
        return fmt.format(float(value))
    except (TypeError, ValueError):
        return "N/A"


def _biomarker_row_csv(result: BiomarkerResult) -> Dict[str, Any]:
    """Flatten BiomarkerResult fields for tabular export (matches ORM columns)."""
    return {
        "gene_symbol": result.gene_symbol,
        "p_value": result.p_value,
        "log2_fold_change": result.log2_fold_change,
        "adjusted_p_value": result.adjusted_p_value,
        "confidence_score": result.confidence_score,
        "clinical_significance": result.clinical_significance,
        "therapeutic_relevance": result.therapeutic_relevance,
    }


def _biomarker_row_excel(result: BiomarkerResult) -> Dict[str, Any]:
    """Human-readable column names for Excel."""
    return {
        "Gene Symbol": result.gene_symbol,
        "P-value": result.p_value,
        "Log2 Fold Change": result.log2_fold_change,
        "FDR (adj. p)": result.adjusted_p_value,
        "Confidence Score": result.confidence_score,
        "Clinical Significance": result.clinical_significance,
        "Therapeutic Relevance": result.therapeutic_relevance,
    }


class ExportService:
    """Service for handling data export and sharing operations"""

    def __init__(self):
        self.export_formats = {
            "csv": self._export_csv,
            "excel": self._export_excel,
            "json": self._export_json,
            "pdf": self._export_pdf,
            "zip": self._export_zip,
        }

    async def export_analysis_results(
        self,
        run_id: str,
        export_format: str,
        include_metadata: bool = True,
        include_visualizations: bool = True,
        include_raw_data: bool = False,
    ) -> Dict[str, Any]:
        """
        Export analysis results in specified format

        Args:
            run_id: Analysis run ID
            export_format: Export format (csv, excel, json, pdf, zip)
            include_metadata: Include analysis metadata
            include_visualizations: Include visualization files
            include_raw_data: Include raw input data

        Returns:
            Export result with file path and metadata
        """
        try:
            # Get analysis run data
            with db_session() as db:
                analysis_run = (
                    db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
                )

            if not analysis_run:
                raise ValueError(f"Analysis run {run_id} not found")

            # Create export directory
            export_dir = (
                Path(settings.EXPORT_DIR)
                / f"export_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            export_dir.mkdir(parents=True, exist_ok=True)

            # Export based on format
            if export_format in self.export_formats:
                result = await self.export_formats[export_format](
                    analysis_run,
                    export_dir,
                    include_metadata,
                    include_visualizations,
                    include_raw_data,
                )
            else:
                raise ValueError(f"Unsupported export format: {export_format}")

            # Generate export metadata
            export_metadata = {
                "run_id": run_id,
                "export_format": export_format,
                "export_timestamp": datetime.now().isoformat(),
                "file_size": result.get("file_size", 0),
                "file_path": str(result.get("file_path", "")),
                "download_url": f"/api/exports/download/{result.get('file_id', '')}",
            }

            logger.info(f"Export completed for run {run_id}: {export_format}")
            return export_metadata

        except Exception as e:
            logger.error(f"Export failed for run {run_id}: {str(e)}")
            raise

    async def _export_csv(
        self,
        analysis_run: AnalysisRun,
        export_dir: Path,
        include_metadata: bool,
        include_visualizations: bool,
        include_raw_data: bool,
    ) -> Dict[str, Any]:
        """Export results as CSV files"""

        # Get biomarker results
        with db_session() as db:
            biomarker_results = (
                db.query(BiomarkerResult)
                .filter(BiomarkerResult.run_id == analysis_run.id)
                .all()
            )

        # Convert to DataFrame
        results_data = [_biomarker_row_csv(r) for r in biomarker_results]

        df = pd.DataFrame(results_data)

        # Export main results
        csv_file = export_dir / "biomarker_results.csv"
        df.to_csv(csv_file, index=False)

        # Export metadata if requested
        if include_metadata:
            metadata = {
                "analysis_id": analysis_run.id,
                "analysis_type": analysis_run.analysis_type,
                "created_at": analysis_run.created_at.isoformat(),
                "status": analysis_run.status,
                "configuration": analysis_run.configuration,
            }

            metadata_file = export_dir / "analysis_metadata.csv"
            pd.DataFrame([metadata]).to_csv(metadata_file, index=False)

        return {
            "file_path": csv_file,
            "file_size": csv_file.stat().st_size,
            "file_id": f"csv_{analysis_run.id}_{int(datetime.now().timestamp())}",
        }

    async def _export_excel(
        self,
        analysis_run: AnalysisRun,
        export_dir: Path,
        include_metadata: bool,
        include_visualizations: bool,
        include_raw_data: bool,
    ) -> Dict[str, Any]:
        """Export results as Excel workbook"""

        excel_file = export_dir / "biomarker_analysis.xlsx"

        with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
            # Main results sheet
            with db_session() as db:
                biomarker_results = (
                    db.query(BiomarkerResult)
                    .filter(BiomarkerResult.run_id == analysis_run.id)
                    .all()
                )

            excel_columns = [
                "Gene Symbol",
                "P-value",
                "Log2 Fold Change",
                "FDR (adj. p)",
                "Confidence Score",
                "Clinical Significance",
                "Therapeutic Relevance",
            ]
            if biomarker_results:
                results_data = [_biomarker_row_excel(r) for r in biomarker_results]
                df_results = pd.DataFrame(results_data)
            else:
                df_results = pd.DataFrame(columns=excel_columns)

            df_results.to_excel(writer, sheet_name="Biomarker Results", index=False)

            # Metadata sheet
            if include_metadata:
                cfg = analysis_run.configuration
                metadata = {
                    "Analysis ID": analysis_run.id,
                    "Analysis Type": analysis_run.analysis_type,
                    "Created At": analysis_run.created_at.isoformat(),
                    "Status": analysis_run.status,
                    "Configuration": json.dumps(cfg) if cfg else "",
                }

                df_metadata = pd.DataFrame([metadata])
                df_metadata.to_excel(
                    writer, sheet_name="Analysis Metadata", index=False
                )

            # Summary statistics sheet
            if len(biomarker_results) > 0:
                results_data = [_biomarker_row_excel(r) for r in biomarker_results]
                pvals = [
                    r["P-value"]
                    for r in results_data
                    if r["P-value"] is not None
                ]
                scores = [
                    r["Confidence Score"]
                    for r in results_data
                    if r["Confidence Score"] is not None
                ]
                l2fc = [
                    abs(float(r["Log2 Fold Change"]))
                    for r in results_data
                    if r["Log2 Fold Change"] is not None
                ]
                summary_stats = {
                    "Total Biomarkers": len(results_data),
                    "Significant (p < 0.05)": len(
                        [
                            r
                            for r in results_data
                            if r["P-value"] is not None and r["P-value"] < 0.05
                        ]
                    ),
                    "High Confidence (score > 0.8)": len(
                        [
                            r
                            for r in results_data
                            if r["Confidence Score"] is not None
                            and r["Confidence Score"] > 0.8
                        ]
                    ),
                    "Mean P-value": float(np.mean(pvals)) if pvals else None,
                    "Mean |Log2 FC|": float(np.mean(l2fc)) if l2fc else None,
                }

                df_summary = pd.DataFrame([summary_stats])
                df_summary.to_excel(
                    writer, sheet_name="Summary Statistics", index=False
                )

        return {
            "file_path": excel_file,
            "file_size": excel_file.stat().st_size,
            "file_id": f"excel_{analysis_run.id}_{int(datetime.now().timestamp())}",
        }

    async def _export_json(
        self,
        analysis_run: AnalysisRun,
        export_dir: Path,
        include_metadata: bool,
        include_visualizations: bool,
        include_raw_data: bool,
    ) -> Dict[str, Any]:
        """Export results as JSON"""

        # Get all data
        with db_session() as db:
            biomarker_results = (
                db.query(BiomarkerResult)
                .filter(BiomarkerResult.run_id == analysis_run.id)
                .all()
            )

        # Build export data
        export_data = {
            "analysis_run": {
                "id": analysis_run.id,
                "analysis_type": analysis_run.analysis_type,
                "created_at": analysis_run.created_at.isoformat(),
                "status": analysis_run.status,
                "configuration": analysis_run.configuration,
            },
            "biomarker_results": [
                {
                    "gene_symbol": result.gene_symbol,
                    "p_value": float(result.p_value)
                    if result.p_value is not None
                    else None,
                    "log2_fold_change": float(result.log2_fold_change)
                    if result.log2_fold_change is not None
                    else None,
                    "adjusted_p_value": float(result.adjusted_p_value)
                    if result.adjusted_p_value is not None
                    else None,
                    "confidence_score": float(result.confidence_score)
                    if result.confidence_score is not None
                    else None,
                    "clinical_significance": result.clinical_significance,
                    "therapeutic_relevance": result.therapeutic_relevance,
                }
                for result in biomarker_results
            ],
            "export_metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "total_biomarkers": len(biomarker_results),
                "export_format": "json",
            },
        }

        # Add summary statistics
        if biomarker_results:
            p_values = [
                float(r.p_value)
                for r in biomarker_results
                if r.p_value is not None
            ]
            scores = [
                float(r.confidence_score)
                for r in biomarker_results
                if r.confidence_score is not None
            ]
            l2 = [
                abs(float(r.log2_fold_change))
                for r in biomarker_results
                if r.log2_fold_change is not None
            ]

            export_data["summary_statistics"] = {
                "significant_biomarkers": len([p for p in p_values if p < 0.05]),
                "high_confidence_biomarkers": len([s for s in scores if s > 0.8]),
                "mean_p_value": float(np.mean(p_values)) if p_values else None,
                "mean_confidence_score": float(np.mean(scores)) if scores else None,
                "median_abs_log2_fold_change": float(np.median(l2)) if l2 else None,
            }

        # Write JSON file
        json_file = export_dir / "biomarker_analysis.json"
        with open(json_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        return {
            "file_path": json_file,
            "file_size": json_file.stat().st_size,
            "file_id": f"json_{analysis_run.id}_{int(datetime.now().timestamp())}",
        }

    async def _export_pdf(
        self,
        analysis_run: AnalysisRun,
        export_dir: Path,
        include_metadata: bool,
        include_visualizations: bool,
        include_raw_data: bool,
    ) -> Dict[str, Any]:
        """Export results as PDF report"""

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        pdf_file = export_dir / "biomarker_report.pdf"
        doc = SimpleDocTemplate(str(pdf_file), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=30,
            alignment=1,
        )
        story.append(Paragraph("Biomarker Analysis Report", title_style))
        story.append(Spacer(1, 12))

        # Analysis metadata
        if include_metadata:
            story.append(Paragraph("Analysis Information", styles["Heading2"]))
            metadata_data = [
                ["Analysis ID:", analysis_run.id],
                ["Analysis Type:", analysis_run.analysis_type],
                ["Created At:", analysis_run.created_at.strftime("%Y-%m-%d %H:%M:%S")],
                ["Status:", analysis_run.status],
            ]

            metadata_table = Table(metadata_data, colWidths=[2 * inch, 4 * inch])
            metadata_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 14),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(metadata_table)
            story.append(Spacer(1, 12))

        # Biomarker results table
        with db_session() as db:
            biomarker_results = (
                db.query(BiomarkerResult)
                .filter(BiomarkerResult.run_id == analysis_run.id)
                .limit(50)
                .all()
            )  # Limit for PDF readability

        if biomarker_results:
            story.append(Paragraph("Top Biomarkers", styles["Heading2"]))

            # Table headers
            table_data = [["Gene", "P-value", "Log2 FC", "Conf.", "Relevance"]]

            # Add biomarker data
            for result in biomarker_results:
                table_data.append(
                    [
                        result.gene_symbol,
                        _fmt_num(result.p_value, "{:.4f}"),
                        _fmt_num(result.log2_fold_change, "{:.2f}"),
                        _fmt_num(result.confidence_score, "{:.3f}"),
                        result.clinical_significance
                        or result.therapeutic_relevance
                        or "N/A",
                    ]
                )

            # Create table
            biomarker_table = Table(
                table_data, colWidths=[1 * inch, 1 * inch, 1 * inch, 1 * inch, 2 * inch]
            )
            biomarker_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ]
                )
            )
            story.append(biomarker_table)

        # Build PDF
        doc.build(story)

        return {
            "file_path": pdf_file,
            "file_size": pdf_file.stat().st_size,
            "file_id": f"pdf_{analysis_run.id}_{int(datetime.now().timestamp())}",
        }

    async def _export_zip(
        self,
        analysis_run: AnalysisRun,
        export_dir: Path,
        include_metadata: bool,
        include_visualizations: bool,
        include_raw_data: bool,
    ) -> Dict[str, Any]:
        """Export results as ZIP archive"""

        zip_file = export_dir / "biomarker_analysis.zip"

        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add CSV export
            csv_result = await self._export_csv(
                analysis_run,
                export_dir,
                include_metadata,
                include_visualizations,
                include_raw_data,
            )
            zipf.write(csv_result["file_path"], "biomarker_results.csv")

            # Add JSON export
            json_result = await self._export_json(
                analysis_run,
                export_dir,
                include_metadata,
                include_visualizations,
                include_raw_data,
            )
            zipf.write(json_result["file_path"], "biomarker_analysis.json")

            # Add PDF report
            pdf_result = await self._export_pdf(
                analysis_run,
                export_dir,
                include_metadata,
                include_visualizations,
                include_raw_data,
            )
            zipf.write(pdf_result["file_path"], "biomarker_report.pdf")

            # Add visualizations if requested
            if include_visualizations:
                viz_dir = Path(settings.VISUALIZATION_DIR) / str(analysis_run.id)
                if viz_dir.exists():
                    for viz_file in viz_dir.glob("*"):
                        zipf.write(viz_file, f"visualizations/{viz_file.name}")

        return {
            "file_path": zip_file,
            "file_size": zip_file.stat().st_size,
            "file_id": f"zip_{analysis_run.id}_{int(datetime.now().timestamp())}",
        }

    async def share_analysis_results(
        self,
        run_id: str,
        recipient_emails: List[str],
        message: str = "",
        export_format: str = "zip",
    ) -> Dict[str, Any]:
        """
        Share analysis results via email

        Args:
            run_id: Analysis run ID
            recipient_emails: List of recipient email addresses
            message: Optional message to include
            export_format: Export format for sharing

        Returns:
            Sharing result
        """
        try:
            # Export results
            export_result = await self.export_analysis_results(
                run_id,
                export_format,
                include_metadata=True,
                include_visualizations=True,
                include_raw_data=False,
            )

            # Send email with attachment
            await self._send_email_with_attachment(
                recipient_emails,
                f"Biomarker Analysis Results - Run {run_id}",
                message
                or f"Please find attached the biomarker analysis results for run {run_id}.",
                export_result["file_path"],
            )

            logger.info(
                f"Analysis results shared for run {run_id} with {len(recipient_emails)} recipients"
            )

            return {
                "success": True,
                "recipients": recipient_emails,
                "export_format": export_format,
                "shared_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to share analysis results for run {run_id}: {str(e)}")
            raise

    async def _send_email_with_attachment(
        self,
        recipient_emails: List[str],
        subject: str,
        body: str,
        attachment_path: Path,
    ):
        """Send email with attachment"""

        path = Path(attachment_path)

        # Create message
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = ", ".join(recipient_emails)
        msg["Subject"] = subject

        # Add body
        msg.attach(MIMEText(body, "plain"))

        # Add attachment
        with open(path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f"attachment; filename={path.name}"
            )
            msg.attach(part)

        # Send email
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(settings.SMTP_FROM_EMAIL, recipient_emails, text)
        server.quit()

    async def generate_public_link(
        self, run_id: str, expiration_hours: int = 24, password_protected: bool = False
    ) -> Dict[str, Any]:
        """
        Generate public sharing link for analysis results

        Args:
            run_id: Analysis run ID
            expiration_hours: Link expiration time in hours
            password_protected: Whether to password protect the link

        Returns:
            Public link information
        """
        try:
            # Generate secure token
            import secrets

            token = secrets.token_urlsafe(32)

            # Set expiration
            expiration = datetime.now().timestamp() + (expiration_hours * 3600)

            # Store link in database (implement as needed)
            # For now, return the link structure

            public_link = {
                "token": token,
                "url": f"{settings.BASE_URL}/public/results/{token}",
                "expires_at": datetime.fromtimestamp(expiration).isoformat(),
                "password_protected": password_protected,
                "created_at": datetime.now().isoformat(),
            }

            logger.info(f"Public link generated for run {run_id}")
            return public_link

        except Exception as e:
            logger.error(f"Failed to generate public link for run {run_id}: {str(e)}")
            raise
