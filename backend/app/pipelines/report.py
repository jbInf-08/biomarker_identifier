"""
Report generation module for creating comprehensive HTML/PDF reports.
"""

import base64
import io
import json
import os
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import yaml

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """
    Handles generation of comprehensive reports for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ReportGenerator module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.report_data = {}

    def generate_report(
        self,
        pipeline_results: Dict[str, Any],
        output_path: str,
        report_format: str = "html",
        template_path: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate a comprehensive report from pipeline results.

        Args:
            pipeline_results: Results from biomarker pipeline
            output_path: Output file path
            report_format: Report format ("html", "pdf")
            template_path: Custom template path (optional)
            **kwargs: Additional parameters

        Returns:
            Path to generated report
        """
        try:
            # Prepare report data
            report_data = self._prepare_report_data(pipeline_results, **kwargs)

            # Generate report based on format
            if report_format.lower() == "html":
                report_file = self._generate_html_report(
                    report_data, output_path, template_path
                )
            elif report_format.lower() == "pdf":
                report_file = self._generate_pdf_report(
                    report_data, output_path, template_path
                )
            else:
                raise ValueError(f"Unsupported report format: {report_format}")

            logger.info(f"Report generated successfully: {report_file}")
            return report_file

        except Exception as e:
            logger.error(f"Failed to generate report: {str(e)}")
            raise

    def _prepare_report_data(
        self, pipeline_results: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """
        Prepare data for report generation.

        Args:
            pipeline_results: Pipeline results
            **kwargs: Additional parameters

        Returns:
            Report data dictionary
        """
        report_data = {
            "metadata": {
                "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pipeline_version": "1.0.0",
                "report_title": kwargs.get(
                    "report_title", "Biomarker Identification Report"
                ),
                "project_name": kwargs.get("project_name", "Biomarker Analysis"),
                "investigator": kwargs.get("investigator", "Unknown"),
                "institution": kwargs.get("institution", "Unknown"),
            },
            "pipeline_summary": pipeline_results.get("pipeline_summary", {}),
            "data_summary": {},
            "results_summary": {},
            "figures": {},
            "tables": {},
            "methods": {},
            "appendices": {},
        }

        # Extract data summary
        if "data_loading" in pipeline_results:
            data_loading = pipeline_results["data_loading"]
            report_data["data_summary"] = {
                "n_genes": data_loading["expression_data"].shape[0],
                "n_samples": data_loading["expression_data"].shape[1],
                "n_classes": len(data_loading["labels"].unique()),
                "validation_status": data_loading["validation_results"]["status"],
            }

        # Extract results summary
        if "biomarker_list" in pipeline_results:
            biomarker_list = pipeline_results["biomarker_list"]
            report_data["results_summary"] = biomarker_list["summary"]

        # Extract methods information
        report_data["methods"] = self._extract_methods_info(pipeline_results)

        # Extract figures and tables
        report_data["figures"] = self._extract_figures(pipeline_results)
        report_data["tables"] = self._extract_tables(pipeline_results)

        # Extract appendices
        report_data["appendices"] = self._extract_appendices(pipeline_results)

        return report_data

    def _extract_methods_info(self, pipeline_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract methods information from pipeline results.

        Args:
            pipeline_results: Pipeline results

        Returns:
            Methods information
        """
        methods = {
            "data_processing": {
                "quality_control": {
                    "status": "not_run",
                    "n_warnings": 0,
                    "n_recommendations": 0,
                },
                "normalization": {
                    "method": "unknown",
                    "batch_correction": False,
                },
            },
            "statistical_analysis": {},
            "machine_learning": {},
            "pathway_analysis": {},
            "annotation": {},
        }

        # Data processing methods
        if "quality_control" in pipeline_results:
            qc_results = pipeline_results["quality_control"]
            methods["data_processing"]["quality_control"] = {
                "status": qc_results.get("summary", {}).get("status", "unknown"),
                "n_warnings": len(qc_results.get("summary", {}).get("warnings", [])),
                "n_recommendations": len(
                    qc_results.get("summary", {}).get("recommendations", [])
                ),
            }

        if "normalization" in pipeline_results:
            norm_results = pipeline_results["normalization"]
            methods["data_processing"]["normalization"] = {
                "method": norm_results.get("normalization_method", "unknown"),
                "batch_correction": norm_results.get("batch_correction_applied", False),
            }

        # Statistical analysis methods
        if "statistical_analysis" in pipeline_results:
            stats_results = pipeline_results["statistical_analysis"]
            methods["statistical_analysis"] = {
                "methods_applied": stats_results.get("summary", {}).get(
                    "methods_applied", []
                ),
                "alpha": stats_results.get("alpha", 0.05),
                "n_significant": stats_results.get("summary", {}).get(
                    "total_significant_features", 0
                ),
            }

        # Machine learning methods
        if "ml_selection" in pipeline_results:
            ml_results = pipeline_results["ml_selection"]
            methods["machine_learning"] = {
                "methods_applied": ml_results.get("summary", {}).get(
                    "methods_applied", []
                ),
                "consensus_features": ml_results.get("summary", {}).get(
                    "consensus_features_count", 0
                ),
                "stability_bootstraps": ml_results.get("stability_bootstraps", 100),
            }

        return methods

    def _extract_figures(self, pipeline_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract figures from pipeline results.

        Args:
            pipeline_results: Pipeline results

        Returns:
            Figures dictionary
        """
        figures = {}

        # QC figures
        if "quality_control" in pipeline_results:
            qc_results = pipeline_results["quality_control"]
            if "plots" in qc_results:
                figures["quality_control"] = qc_results["plots"]

        # Statistical analysis figures
        if "statistical_analysis" in pipeline_results:
            stats_results = pipeline_results["statistical_analysis"]
            if "plots" in stats_results:
                figures["statistical_analysis"] = stats_results["plots"]

        # ML selection figures
        if "ml_selection" in pipeline_results:
            ml_results = pipeline_results["ml_selection"]
            if "plots" in ml_results:
                figures["machine_learning"] = ml_results["plots"]

        # Pathway analysis figures
        if "pathway_analysis" in pipeline_results:
            pathway_results = pipeline_results["pathway_analysis"]
            if "plots" in pathway_results:
                figures["pathway_analysis"] = pathway_results["plots"]

        return figures

    def _extract_tables(self, pipeline_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tables from pipeline results.

        Args:
            pipeline_results: Pipeline results

        Returns:
            Tables dictionary
        """
        tables = {}

        # Biomarker list table
        if "biomarker_list" in pipeline_results:
            biomarker_list = pipeline_results["biomarker_list"]
            if "biomarkers" in biomarker_list:
                # Convert to DataFrame for easier handling
                biomarkers_df = pd.DataFrame(biomarker_list["biomarkers"])
                tables["biomarker_list"] = biomarkers_df.head(50).to_dict(
                    "records"
                )  # Top 50 biomarkers

        # Statistical results table
        if "statistical_analysis" in pipeline_results:
            stats_results = pipeline_results["statistical_analysis"]
            if "method_results" in stats_results:
                # Extract top significant features
                significant_features = []
                for method, result in stats_results["method_results"].items():
                    if (
                        "error" not in result
                        and "significant_features_adjusted" in result
                    ):
                        features = result["significant_features_adjusted"][
                            :20
                        ]  # Top 20
                        for feature in features:
                            significant_features.append(
                                {"gene": feature, "method": method, "significant": True}
                            )
                tables["significant_features"] = significant_features

        return tables

    def _extract_appendices(self, pipeline_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract appendices from pipeline results.

        Args:
            pipeline_results: Pipeline results

        Returns:
            Appendices dictionary
        """
        appendices = {
            "configuration": pipeline_results.get("config", {}),
            "pipeline_steps": pipeline_results.get("pipeline_steps", []),
            "run_metadata": {
                "run_id": pipeline_results.get("run_id"),
                "run_name": pipeline_results.get("run_name"),
                "timestamp": pipeline_results.get("timestamp"),
            },
        }

        return appendices

    def _generate_html_report(
        self,
        report_data: Dict[str, Any],
        output_path: str,
        template_path: Optional[str] = None,
    ) -> str:
        """
        Generate HTML report using Jinja2 templating.

        Args:
            report_data: Report data
            output_path: Output file path
            template_path: Custom template path

        Returns:
            Path to generated HTML report
        """
        try:
            from jinja2 import Environment, FileSystemLoader, Template

            # Use default template if none provided
            if template_path is None:
                template_content = self._get_default_html_template()
                template = Template(template_content)
            else:
                env = Environment(
                    loader=FileSystemLoader(os.path.dirname(template_path))
                )
                template = env.get_template(os.path.basename(template_path))

            # Render template
            html_content = template.render(**report_data)

            # Save HTML file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            return output_path

        except ImportError:
            logger.error(
                "Jinja2 not available. Please install with: pip install jinja2"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {str(e)}")
            raise

    def _generate_pdf_report(
        self,
        report_data: Dict[str, Any],
        output_path: str,
        template_path: Optional[str] = None,
    ) -> str:
        """
        Generate PDF report.

        Args:
            report_data: Report data
            output_path: Output file path
            template_path: Custom template path

        Returns:
            Path to generated PDF report
        """
        try:
            # First generate HTML
            html_path = output_path.replace(".pdf", ".html")
            html_path = self._generate_html_report(
                report_data, html_path, template_path
            )

            # Convert HTML to PDF
            try:
                import weasyprint

                weasyprint.HTML(filename=html_path).write_pdf(output_path)
            except ImportError:
                try:
                    import pdfkit

                    pdfkit.from_file(html_path, output_path)
                except ImportError:
                    logger.warning(
                        "Neither weasyprint nor pdfkit available. PDF generation skipped."
                    )
                    return html_path

            # Clean up temporary HTML file
            if os.path.exists(html_path):
                os.remove(html_path)

            return output_path

        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            raise

    def _get_default_html_template(self) -> str:
        """
        Get default HTML template for reports.

        Returns:
            Default HTML template
        """
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ metadata.report_title }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #2c3e50;
            margin: 0;
            font-size: 2.5em;
        }
        .header p {
            color: #7f8c8d;
            margin: 5px 0;
        }
        .section {
            margin-bottom: 40px;
            padding: 20px;
            border-left: 4px solid #3498db;
            background-color: #f8f9fa;
        }
        .section h2 {
            color: #2c3e50;
            margin-top: 0;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-top: 4px solid #3498db;
        }
        .summary-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .summary-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }
        .table-container {
            overflow-x: auto;
            margin: 20px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #e8f4f8;
        }
        .figure {
            text-align: center;
            margin: 20px 0;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .figure img {
            max-width: 100%;
            height: auto;
        }
        .methods-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .method-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            color: #7f8c8d;
        }
        .disclaimer {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ metadata.report_title }}</h1>
            <p><strong>Project:</strong> {{ metadata.project_name }}</p>
            <p><strong>Investigator:</strong> {{ metadata.investigator }} | <strong>Institution:</strong> {{ metadata.institution }}</p>
            <p><strong>Generated:</strong> {{ metadata.generation_date }}</p>
        </div>

        <div class="disclaimer">
            <strong>Disclaimer:</strong> This report is for research purposes only. Results should be validated in independent cohorts before clinical application.
        </div>

        <div class="section">
            <h2>Executive Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <h3>Data Overview</h3>
                    <div class="value">{{ data_summary.n_genes }}</div>
                    <p>Genes Analyzed</p>
                </div>
                <div class="summary-card">
                    <h3>Samples</h3>
                    <div class="value">{{ data_summary.n_samples }}</div>
                    <p>Total Samples</p>
                </div>
                <div class="summary-card">
                    <h3>Biomarkers</h3>
                    <div class="value">{{ results_summary.total_biomarkers }}</div>
                    <p>Identified</p>
                </div>
                <div class="summary-card">
                    <h3>High Confidence</h3>
                    <div class="value">{{ results_summary.high_confidence }}</div>
                    <p>Biomarkers</p>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Methods</h2>
            <div class="methods-grid">
                <div class="method-card">
                    <h3>Data Processing</h3>
                    <p><strong>Quality Control:</strong> {{ methods.data_processing.quality_control.status }}</p>
                    <p><strong>Normalization:</strong> {{ methods.data_processing.normalization.method }}</p>
                    <p><strong>Batch Correction:</strong> {{ "Applied" if methods.data_processing.normalization.batch_correction else "Not Applied" }}</p>
                </div>
                <div class="method-card">
                    <h3>Statistical Analysis</h3>
                    <p><strong>Methods:</strong> {{ methods.statistical_analysis.methods_applied | join(", ") }}</p>
                    <p><strong>Significance Level:</strong> α = {{ methods.statistical_analysis.alpha }}</p>
                    <p><strong>Significant Features:</strong> {{ methods.statistical_analysis.n_significant }}</p>
                </div>
                <div class="method-card">
                    <h3>Machine Learning</h3>
                    <p><strong>Methods:</strong> {{ methods.machine_learning.methods_applied | join(", ") }}</p>
                    <p><strong>Consensus Features:</strong> {{ methods.machine_learning.consensus_features }}</p>
                    <p><strong>Stability Bootstraps:</strong> {{ methods.machine_learning.stability_bootstraps }}</p>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Results</h2>
            
            {% if tables.biomarker_list %}
            <h3>Top Biomarkers</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Gene</th>
                            <th>Final Score</th>
                            <th>Consensus Score</th>
                            <th>Statistical Evidence</th>
                            <th>ML Evidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for biomarker in tables.biomarker_list[:20] %}
                        <tr>
                            <td>{{ biomarker.final_rank }}</td>
                            <td><strong>{{ biomarker.gene }}</strong></td>
                            <td>{{ "%.3f"|format(biomarker.final_score) }}</td>
                            <td>{{ "%.3f"|format(biomarker.consensus_score) }}</td>
                            <td>{{ biomarker.statistical_evidence | length }} methods</td>
                            <td>{{ biomarker.ml_evidence | length }} methods</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
        </div>

        <div class="section">
            <h2>Figures</h2>
            
            {% if figures.quality_control %}
            <h3>Quality Control</h3>
            <div class="figure">
                <p><em>Quality control plots and metrics</em></p>
                <!-- QC figures would be embedded here -->
            </div>
            {% endif %}
            
            {% if figures.statistical_analysis %}
            <h3>Statistical Analysis</h3>
            <div class="figure">
                <p><em>Volcano plots and statistical results</em></p>
                <!-- Statistical figures would be embedded here -->
            </div>
            {% endif %}
            
            {% if figures.machine_learning %}
            <h3>Machine Learning Results</h3>
            <div class="figure">
                <p><em>Feature selection and model performance</em></p>
                <!-- ML figures would be embedded here -->
            </div>
            {% endif %}
        </div>

        <div class="section">
            <h2>Appendices</h2>
            
            <h3>Pipeline Configuration</h3>
            <pre>{{ appendices.configuration | tojson(indent=2) }}</pre>
            
            <h3>Pipeline Steps</h3>
            <ul>
                {% for step in appendices.pipeline_steps %}
                <li>{{ step }}</li>
                {% endfor %}
            </ul>
            
            <h3>Run Metadata</h3>
            <p><strong>Run ID:</strong> {{ appendices.run_metadata.run_id }}</p>
            <p><strong>Run Name:</strong> {{ appendices.run_metadata.run_name }}</p>
            <p><strong>Timestamp:</strong> {{ appendices.run_metadata.timestamp }}</p>
        </div>

        <div class="footer">
            <p>Report generated by Cancer Biomarker Identifier v{{ metadata.pipeline_version }}</p>
            <p>For research use only. Please cite appropriately.</p>
        </div>
    </div>
</body>
</html>
        """

    def create_run_bundle(
        self,
        pipeline_results: Dict[str, Any],
        output_dir: str,
        include_data: bool = False,
        **kwargs,
    ) -> str:
        """
        Create a complete run bundle with all artifacts.

        Args:
            pipeline_results: Pipeline results
            output_dir: Output directory
            include_data: Whether to include input data
            **kwargs: Additional parameters

        Returns:
            Path to run bundle
        """
        try:
            import shutil
            import zipfile

            # Create bundle directory
            run_id = pipeline_results.get("run_id", "unknown_run")
            bundle_dir = os.path.join(output_dir, f"{run_id}_bundle")
            os.makedirs(bundle_dir, exist_ok=True)

            # Create subdirectories
            subdirs = ["reports", "data", "figures", "configs", "logs"]
            for subdir in subdirs:
                os.makedirs(os.path.join(bundle_dir, subdir), exist_ok=True)

            # Save pipeline results
            results_file = os.path.join(bundle_dir, "pipeline_results.json")
            with open(results_file, "w") as f:
                json.dump(pipeline_results, f, indent=2, default=str)

            # Generate and save reports
            report_file = os.path.join(bundle_dir, "reports", "biomarker_report.html")
            self.generate_report(pipeline_results, report_file, "html", **kwargs)

            # Save configuration
            config_file = os.path.join(bundle_dir, "configs", "pipeline_config.yaml")
            with open(config_file, "w") as f:
                yaml.dump(
                    pipeline_results.get("config", {}), f, default_flow_style=False
                )

            # Save environment info
            env_file = os.path.join(bundle_dir, "configs", "environment.txt")
            self._save_environment_info(env_file)

            # Create README
            readme_file = os.path.join(bundle_dir, "README.md")
            self._create_bundle_readme(readme_file, pipeline_results)

            # Create ZIP archive
            zip_path = f"{bundle_dir}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(bundle_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, bundle_dir)
                        zipf.write(file_path, arcname)

            # Clean up bundle directory
            shutil.rmtree(bundle_dir)

            logger.info(f"Run bundle created: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"Failed to create run bundle: {str(e)}")
            raise

    def _save_environment_info(self, output_file: str):
        """
        Save environment information.

        Args:
            output_file: Output file path
        """
        try:
            import subprocess
            import sys

            with open(output_file, "w") as f:
                f.write(f"Python version: {sys.version}\n")
                f.write(f"Platform: {sys.platform}\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n\n")

                # Try to get package versions
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "freeze"],
                        capture_output=True,
                        text=True,
                    )
                    f.write("Installed packages:\n")
                    f.write(result.stdout)
                except:
                    f.write("Could not retrieve package information\n")

        except Exception as e:
            logger.warning(f"Failed to save environment info: {str(e)}")

    def _create_bundle_readme(self, output_file: str, pipeline_results: Dict[str, Any]):
        """
        Create README file for run bundle.

        Args:
            output_file: Output file path
            pipeline_results: Pipeline results
        """
        try:
            with open(output_file, "w") as f:
                f.write("# Biomarker Identification Run Bundle\n\n")
                f.write(f"**Run ID:** {pipeline_results.get('run_id', 'Unknown')}\n")
                f.write(
                    f"**Generated:** {pipeline_results.get('timestamp', 'Unknown')}\n\n"
                )

                f.write("## Contents\n\n")
                f.write("- `pipeline_results.json`: Complete pipeline results\n")
                f.write("- `reports/biomarker_report.html`: HTML report\n")
                f.write("- `configs/pipeline_config.yaml`: Pipeline configuration\n")
                f.write("- `configs/environment.txt`: Environment information\n")
                f.write("- `README.md`: This file\n\n")

                f.write("## Usage\n\n")
                f.write("1. Extract the ZIP file\n")
                f.write("2. Open `reports/biomarker_report.html` in a web browser\n")
                f.write("3. Review `pipeline_results.json` for detailed results\n\n")

                f.write("## Reproducibility\n\n")
                f.write("To reproduce this analysis:\n")
                f.write(
                    "1. Install the required packages (see `configs/environment.txt`)\n"
                )
                f.write("2. Use the configuration in `configs/pipeline_config.yaml`\n")
                f.write("3. Run the biomarker identification pipeline\n\n")

                f.write("## Citation\n\n")
                f.write(
                    "If you use these results in your research, please cite appropriately.\n"
                )

        except Exception as e:
            logger.warning(f"Failed to create bundle README: {str(e)}")

    def get_report_summary(self) -> Dict[str, Any]:
        """
        Get report generation summary.

        Returns:
            Report summary dictionary
        """
        if not self.report_data:
            return {"status": "No report generated"}

        return {
            "metadata": self.report_data.get("metadata", {}),
            "data_summary": self.report_data.get("data_summary", {}),
            "results_summary": self.report_data.get("results_summary", {}),
        }
