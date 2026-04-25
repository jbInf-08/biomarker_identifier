"""
Celery tasks for biomarker analysis.
"""
import logging
from typing import Any, Dict, List

from celery import current_task
from sqlalchemy.orm import Session

from app.core.database import db_session
from app.models.run_model import AnalysisRun, RunStatus
from app.pipelines.biomarker_pipeline import BiomarkerPipeline
from app.services.celery_service import celery_app
from app.services.webhook_dispatch import dispatch_webhooks_for_user
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True, name="app.services.tasks.biomarker_tasks.run_biomarker_analysis"
)
def run_biomarker_analysis(
    self,
    run_id: str,
    expression_file_path: str,
    label_file_path: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Background task for running biomarker analysis.

    Args:
        run_id: Unique identifier for the analysis run
        expression_file_path: Path to expression data file
        label_file_path: Path to label data file
        parameters: Analysis parameters

    Returns:
        Dict containing analysis results
    """
    try:
        # Update task status
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting biomarker analysis..."},
        )

        # Send WebSocket update
        manager.send_to_run(
            run_id,
            {
                "type": "progress_update",
                "progress": 0,
                "status": "Starting biomarker analysis...",
                "task_id": self.request.id,
            },
        )

        with db_session() as db:
            # Update run status to RUNNING
            analysis_run = (
                db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            )
            if analysis_run:
                analysis_run.status = RunStatus.RUNNING.value
                db.commit()

            # Update progress
            current_task.update_state(
                state="PROGRESS",
                meta={"progress": 10, "status": "Initializing pipeline..."},
            )

            manager.send_to_run(
                run_id,
                {
                    "type": "progress_update",
                    "progress": 10,
                    "status": "Initializing pipeline...",
                    "task_id": self.request.id,
                },
            )

            # Initialize pipeline
            pipeline = BiomarkerPipeline()

            # Update progress
            current_task.update_state(
                state="PROGRESS", meta={"progress": 20, "status": "Loading data..."}
            )

            manager.send_to_run(
                run_id,
                {
                    "type": "progress_update",
                    "progress": 20,
                    "status": "Loading data...",
                    "task_id": self.request.id,
                },
            )

            # Run analysis
            results = pipeline.run_pipeline(
                expression_file_path=expression_file_path,
                label_file_path=label_file_path,
                parameters=parameters,
                progress_callback=lambda progress, status: update_progress(
                    run_id, progress, status, self.request.id
                ),
            )

            # Update run status to COMPLETED
            if analysis_run:
                analysis_run.status = RunStatus.COMPLETED.value
                db.commit()
                uid = analysis_run.user_id
                if uid:
                    try:
                        dispatch_webhooks_for_user(
                            db,
                            user_id=uid,
                            event="run.completed",
                            payload={
                                "run_id": run_id,
                                "status": "completed",
                                "task_id": self.request.id,
                            },
                        )
                    except Exception as wh:
                        logger.warning("webhook dispatch failed: %s", wh)

            # Final progress update
            current_task.update_state(
                state="SUCCESS",
                meta={"progress": 100, "status": "Analysis completed successfully"},
            )

            manager.send_to_run(
                run_id,
                {
                    "type": "progress_update",
                    "progress": 100,
                    "status": "Analysis completed successfully",
                    "task_id": self.request.id,
                },
            )

            logger.info(f"Biomarker analysis completed successfully for run {run_id}")
            return {
                "run_id": run_id,
                "status": "completed",
                "results": results,
                "task_id": self.request.id,
            }

    except Exception as e:
        logger.error(f"Biomarker analysis failed for run {run_id}: {str(e)}")

        # Update run status to FAILED
        try:
            with db_session() as db:
                analysis_run = (
                    db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
                )
                if analysis_run:
                    analysis_run.status = RunStatus.FAILED.value
                    db.commit()
                    uid = analysis_run.user_id
                    if uid:
                        try:
                            dispatch_webhooks_for_user(
                                db,
                                user_id=uid,
                                event="run.failed",
                                payload={
                                    "run_id": run_id,
                                    "status": "failed",
                                    "error": str(e),
                                    "task_id": self.request.id,
                                },
                            )
                        except Exception as wh:
                            logger.warning("webhook dispatch failed: %s", wh)
        except Exception as db_error:
            logger.error(f"Failed to update run status: {str(db_error)}")

        # Send error update
        manager.send_to_run(
            run_id,
            {
                "type": "progress_update",
                "progress": 0,
                "status": f"Analysis failed: {str(e)}",
                "task_id": self.request.id,
                "error": str(e),
            },
        )

        # Update task state
        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Analysis failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


def update_progress(run_id: str, progress: int, status: str, task_id: str):
    """Update progress for biomarker analysis."""
    try:
        # Update Celery task state
        current_task.update_state(
            state="PROGRESS", meta={"progress": progress, "status": status}
        )

        # Send WebSocket update
        manager.send_to_run(
            run_id,
            {
                "type": "progress_update",
                "progress": progress,
                "status": status,
                "task_id": task_id,
            },
        )

    except Exception as e:
        logger.warning(f"Failed to update progress: {str(e)}")


@celery_app.task(
    bind=True, name="app.services.tasks.biomarker_tasks.run_pathway_analysis"
)
def run_pathway_analysis(
    self, run_id: str, biomarker_ids: List[str], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Background task for running pathway analysis.

    Args:
        run_id: Unique identifier for the analysis run
        biomarker_ids: List of biomarker IDs to analyze
        parameters: Pathway analysis parameters

    Returns:
        Dict containing pathway analysis results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting pathway analysis..."},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "pathway_progress",
                "progress": 0,
                "status": "Starting pathway analysis...",
                "task_id": self.request.id,
            },
        )

        # Import pathway analysis here to avoid circular imports
        from app.pipelines.pathway_analysis import PathwayAnalyzer

        analyzer = PathwayAnalyzer()

        current_task.update_state(
            state="PROGRESS", meta={"progress": 50, "status": "Analyzing pathways..."}
        )

        manager.send_to_run(
            run_id,
            {
                "type": "pathway_progress",
                "progress": 50,
                "status": "Analyzing pathways...",
                "task_id": self.request.id,
            },
        )

        # Run pathway analysis
        results = analyzer.analyze_pathways(
            biomarker_ids=biomarker_ids, parameters=parameters
        )

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Pathway analysis completed"},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "pathway_progress",
                "progress": 100,
                "status": "Pathway analysis completed",
                "task_id": self.request.id,
            },
        )

        logger.info(f"Pathway analysis completed for run {run_id}")
        return {
            "run_id": run_id,
            "status": "completed",
            "results": results,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Pathway analysis failed for run {run_id}: {str(e)}")

        manager.send_to_run(
            run_id,
            {
                "type": "pathway_progress",
                "progress": 0,
                "status": f"Pathway analysis failed: {str(e)}",
                "task_id": self.request.id,
                "error": str(e),
            },
        )

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Pathway analysis failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.biomarker_tasks.run_shap_analysis")
def run_shap_analysis(
    self, run_id: str, model_path: str, data_path: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Background task for running SHAP analysis.

    Args:
        run_id: Unique identifier for the analysis run
        model_path: Path to trained model
        data_path: Path to data for SHAP analysis
        parameters: SHAP analysis parameters

    Returns:
        Dict containing SHAP analysis results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting SHAP analysis..."},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "shap_progress",
                "progress": 0,
                "status": "Starting SHAP analysis...",
                "task_id": self.request.id,
            },
        )

        # Import SHAP analysis here to avoid circular imports
        from app.pipelines.shap_analysis import SHAPAnalyzer

        analyzer = SHAPAnalyzer()

        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 50, "status": "Computing SHAP values..."},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "shap_progress",
                "progress": 50,
                "status": "Computing SHAP values...",
                "task_id": self.request.id,
            },
        )

        # Run SHAP analysis
        results = analyzer.compute_shap_values(
            model_path=model_path, data_path=data_path, parameters=parameters
        )

        current_task.update_state(
            state="SUCCESS", meta={"progress": 100, "status": "SHAP analysis completed"}
        )

        manager.send_to_run(
            run_id,
            {
                "type": "shap_progress",
                "progress": 100,
                "status": "SHAP analysis completed",
                "task_id": self.request.id,
            },
        )

        logger.info(f"SHAP analysis completed for run {run_id}")
        return {
            "run_id": run_id,
            "status": "completed",
            "results": results,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"SHAP analysis failed for run {run_id}: {str(e)}")

        manager.send_to_run(
            run_id,
            {
                "type": "shap_progress",
                "progress": 0,
                "status": f"SHAP analysis failed: {str(e)}",
                "task_id": self.request.id,
                "error": str(e),
            },
        )

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"SHAP analysis failed: {str(e)}",
                "error": str(e),
            },
        )

        raise
