"""
Celery tasks for clinical annotation.
"""
import logging
from typing import Any, Dict, List

from celery import current_task

from app.services.celery_service import celery_app
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True, name="app.services.tasks.clinical_tasks.annotate_biomarkers"
)
def annotate_biomarkers(
    self,
    run_id: str,
    biomarker_ids: List[str],
    databases: List[str],
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Background task for annotating biomarkers with clinical data.

    Args:
        run_id: Unique identifier for the analysis run
        biomarker_ids: List of biomarker IDs to annotate
        databases: List of databases to query
        parameters: Annotation parameters

    Returns:
        Dict containing annotation results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting clinical annotation..."},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "clinical_progress",
                "progress": 0,
                "status": "Starting clinical annotation...",
                "task_id": self.request.id,
            },
        )

        # Import clinical annotation here to avoid circular imports
        from app.services.clinical_annotation import ClinicalAnnotationService

        service = ClinicalAnnotationService()
        annotated_biomarkers = []

        total_biomarkers = len(biomarker_ids)

        for i, biomarker_id in enumerate(biomarker_ids):
            try:
                progress = int((i / total_biomarkers) * 100)

                current_task.update_state(
                    state="PROGRESS",
                    meta={
                        "progress": progress,
                        "status": f"Annotating biomarker {biomarker_id}...",
                    },
                )

                manager.send_to_run(
                    run_id,
                    {
                        "type": "clinical_progress",
                        "progress": progress,
                        "status": f"Annotating biomarker {biomarker_id}...",
                        "task_id": self.request.id,
                    },
                )

                # Annotate biomarker
                annotation = service.annotate_biomarker(
                    biomarker_id=biomarker_id,
                    databases=databases,
                    parameters=parameters,
                )

                annotated_biomarkers.append(annotation)

            except Exception as e:
                logger.warning(f"Failed to annotate biomarker {biomarker_id}: {str(e)}")
                # Continue with other biomarkers
                continue

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Clinical annotation completed"},
        )

        manager.send_to_run(
            run_id,
            {
                "type": "clinical_progress",
                "progress": 100,
                "status": "Clinical annotation completed",
                "task_id": self.request.id,
            },
        )

        logger.info(f"Clinical annotation completed for run {run_id}")
        return {
            "run_id": run_id,
            "status": "completed",
            "annotated_biomarkers": annotated_biomarkers,
            "total_annotated": len(annotated_biomarkers),
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Clinical annotation failed for run {run_id}: {str(e)}")

        manager.send_to_run(
            run_id,
            {
                "type": "clinical_progress",
                "progress": 0,
                "status": f"Clinical annotation failed: {str(e)}",
                "task_id": self.request.id,
                "error": str(e),
            },
        )

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Clinical annotation failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(
    bind=True, name="app.services.tasks.clinical_tasks.update_clinical_databases"
)
def update_clinical_databases(self, databases: List[str]) -> Dict[str, Any]:
    """
    Background task for updating clinical databases.

    Args:
        databases: List of databases to update

    Returns:
        Dict containing update results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting database update..."},
        )

        # Import clinical annotation service
        from app.services.clinical_annotation import ClinicalAnnotationService

        service = ClinicalAnnotationService()
        update_results = {}

        total_databases = len(databases)

        for i, database in enumerate(databases):
            try:
                progress = int((i / total_databases) * 100)

                current_task.update_state(
                    state="PROGRESS",
                    meta={"progress": progress, "status": f"Updating {database}..."},
                )

                # Update database
                result = service.update_database(database)
                update_results[database] = result

            except Exception as e:
                logger.warning(f"Failed to update database {database}: {str(e)}")
                update_results[database] = {"error": str(e)}
                continue

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Database update completed"},
        )

        logger.info("Clinical database update completed")
        return {
            "status": "completed",
            "update_results": update_results,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Clinical database update failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Database update failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.clinical_tasks.literature_mining")
def literature_mining(
    self, biomarker_ids: List[str], search_terms: List[str], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Background task for literature mining of biomarkers.

    Args:
        biomarker_ids: List of biomarker IDs to search
        search_terms: List of search terms
        parameters: Literature mining parameters

    Returns:
        Dict containing literature mining results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting literature mining..."},
        )

        # Import literature mining service
        from app.services.literature_mining import LiteratureMiningService

        service = LiteratureMiningService()
        mining_results = []

        total_biomarkers = len(biomarker_ids)

        for i, biomarker_id in enumerate(biomarker_ids):
            try:
                progress = int((i / total_biomarkers) * 100)

                current_task.update_state(
                    state="PROGRESS",
                    meta={
                        "progress": progress,
                        "status": f"Mining literature for {biomarker_id}...",
                    },
                )

                # Mine literature for biomarker
                result = service.mine_literature(
                    biomarker_id=biomarker_id,
                    search_terms=search_terms,
                    parameters=parameters,
                )

                mining_results.append(result)

            except Exception as e:
                logger.warning(
                    f"Failed to mine literature for biomarker {biomarker_id}: {str(e)}"
                )
                continue

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Literature mining completed"},
        )

        logger.info("Literature mining completed")
        return {
            "status": "completed",
            "mining_results": mining_results,
            "total_mined": len(mining_results),
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Literature mining failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Literature mining failed: {str(e)}",
                "error": str(e),
            },
        )

        raise
