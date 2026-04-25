"""
Celery tasks for report generation.
"""
import logging
from typing import Any, Dict, Optional

from celery import current_task

from app.services.celery_service import celery_app
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.services.tasks.report_tasks.generate_report")
def generate_report(
    self,
    run_id: str,
    report_format: str,
    template_name: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Background task for generating reports.

    Args:
        run_id: Unique identifier for the analysis run
        report_format: Format of the report (html, pdf)
        template_name: Name of the template to use
        parameters: Report generation parameters

    Returns:
        Dict containing report generation results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting report generation..."},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "report_progress",
                "progress": 0,
                "status": "Starting report generation...",
                "task_id": self.request.id,
            },
        )

        # Import report generators
        from app.reports.html_generator import HTMLReportGenerator
        from app.reports.pdf_generator import PDFReportGenerator

        current_task.update_state(
            state="PROGRESS", meta={"progress": 25, "status": "Gathering data..."}
        )

        manager.send_to_run(
            run_id,
            {
                "type": "report_progress",
                "progress": 25,
                "status": "Gathering data...",
                "task_id": self.request.id,
            },
        )

        # Get analysis data
        from app.core.database import db_session
        from app.models.biomarker_model import BiomarkerResult
        from app.models.run_model import AnalysisRun

        with db_session() as db:
            analysis_run = (
                db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            )
            if not analysis_run:
                raise ValueError(f"Analysis run {run_id} not found")

            results = (
                db.query(BiomarkerResult)
                .filter(BiomarkerResult.run_id == run_id)
                .order_by(BiomarkerResult.p_value.asc())
                .all()
            )

        current_task.update_state(
            state="PROGRESS", meta={"progress": 50, "status": "Generating report..."}
        )

        manager.send_to_run(
            run_id,
            {
                "type": "report_progress",
                "progress": 50,
                "status": "Generating report...",
                "task_id": self.request.id,
            },
        )

        # Generate report based on format
        if report_format.lower() == "html":
            generator = HTMLReportGenerator()
            report_content = generator.generate_report(
                analysis_run=analysis_run,
                results=results,
                template_name=template_name,
                title=parameters.get("title"),
                clinical_annotations=parameters.get("clinical_annotations"),
            )

            # Save HTML report
            import os
            from datetime import datetime

            from app.core.config import settings

            reports_dir = f"{settings.REPORTS_DIR}/{run_id}"
            os.makedirs(reports_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"biomarker_report_{run_id}_{timestamp}.html"
            report_path = f"{reports_dir}/{report_filename}"

            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

        elif report_format.lower() == "pdf":
            generator = PDFReportGenerator()
            report_path = generator.generate_report(
                analysis_run=analysis_run,
                results=results,
                title=parameters.get("title"),
                output_path=parameters.get("output_path"),
                clinical_annotations=parameters.get("clinical_annotations"),
            )
        else:
            raise ValueError(f"Unsupported report format: {report_format}")

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Report generation completed"},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "report_progress",
                "progress": 100,
                "status": "Report generation completed",
                "task_id": self.request.id,
            },
        )

        logger.info(f"Report generation completed for run {run_id}")
        return {
            "run_id": run_id,
            "status": "completed",
            "report_path": report_path,
            "report_format": report_format,
            "template_name": template_name,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Report generation failed for run {run_id}: {str(e)}")

        manager.send_to_run(
            run_id,
            {
                "type": "report_progress",
                "progress": 0,
                "status": f"Report generation failed: {str(e)}",
                "task_id": self.request.id,
                "error": str(e),
            },
        )

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Report generation failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(
    bind=True, name="app.services.tasks.report_tasks.generate_batch_reports"
)
def generate_batch_reports(
    self,
    run_ids: list,
    report_format: str,
    template_name: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Background task for generating multiple reports in batch.

    Args:
        run_ids: List of run IDs to generate reports for
        report_format: Format of the reports (html, pdf)
        template_name: Name of the template to use
        parameters: Report generation parameters

    Returns:
        Dict containing batch report generation results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting batch report generation..."},
        )

        report_results = []
        total_runs = len(run_ids)

        for i, run_id in enumerate(run_ids):
            try:
                progress = int((i / total_runs) * 100)

                current_task.update_state(
                    state="PROGRESS",
                    meta={
                        "progress": progress,
                        "status": f"Generating report for run {run_id}...",
                    },
                )

                # Generate individual report
                result = generate_report.apply_async(
                    args=[run_id, report_format, template_name, parameters]
                ).get()

                report_results.append(result)

            except Exception as e:
                logger.warning(f"Failed to generate report for run {run_id}: {str(e)}")
                report_results.append(
                    {"run_id": run_id, "status": "failed", "error": str(e)}
                )
                continue

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Batch report generation completed"},
        )

        logger.info("Batch report generation completed")
        return {
            "status": "completed",
            "report_results": report_results,
            "total_generated": len(
                [r for r in report_results if r.get("status") == "completed"]
            ),
            "total_failed": len(
                [r for r in report_results if r.get("status") == "failed"]
            ),
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Batch report generation failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Batch report generation failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.report_tasks.cleanup_old_reports")
def cleanup_old_reports(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Background task for cleaning up old reports.

    Args:
        days_old: Number of days after which reports should be deleted

    Returns:
        Dict containing cleanup results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting report cleanup..."},
        )

        import os
        import time
        from datetime import datetime, timedelta

        from app.core.config import settings

        reports_dir = settings.REPORTS_DIR
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)

        deleted_files = []
        total_size_freed = 0

        if os.path.exists(reports_dir):
            for root, dirs, files in os.walk(reports_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.getmtime(file_path) < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_files.append(file_path)
                            total_size_freed += file_size
                    except OSError as e:
                        logger.warning(f"Failed to delete file {file_path}: {str(e)}")
                        continue

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Report cleanup completed"},
        )

        logger.info(
            f"Report cleanup completed: {len(deleted_files)} files deleted, {total_size_freed} bytes freed"
        )
        return {
            "status": "completed",
            "deleted_files": len(deleted_files),
            "total_size_freed": total_size_freed,
            "days_old": days_old,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Report cleanup failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Report cleanup failed: {str(e)}",
                "error": str(e),
            },
        )

        raise
