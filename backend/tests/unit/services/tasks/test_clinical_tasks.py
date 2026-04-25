"""
Comprehensive unit tests for clinical tasks.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.tasks.clinical_tasks import (
    annotate_biomarkers,
    update_clinical_databases,
)


class TestClinicalTasks:
    """Test cases for clinical tasks."""

    def test_annotate_biomarkers(self):
        """Test annotating biomarkers."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        run_id = "test_run_1"
        biomarker_ids = ["biomarker_1", "biomarker_2"]
        databases = ["COSMIC", "ClinVar"]
        parameters = {}

        with patch("app.services.tasks.clinical_tasks.current_task", mock_task):
            with patch("app.services.tasks.clinical_tasks.manager") as mock_manager:
                mock_manager.send_to_run = MagicMock()

                with patch(
                    "app.services.clinical_annotation.ClinicalAnnotationService"
                ) as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service.return_value = mock_service_instance
                    mock_service_instance.annotate_biomarker.return_value = {
                        "biomarker_id": "biomarker_1",
                        "annotations": {},
                    }

                    result = annotate_biomarkers.__wrapped__(
                        run_id=run_id,
                        biomarker_ids=biomarker_ids,
                        databases=databases,
                        parameters=parameters,
                    )

                    assert result is not None
                    assert result["run_id"] == run_id
                    assert result["status"] == "completed"
                    assert "annotated_biomarkers" in result
                    assert "task_id" in result

    def test_annotate_biomarkers_with_errors(self):
        """Test annotating biomarkers with some errors."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        run_id = "test_run_1"
        biomarker_ids = ["biomarker_1", "biomarker_2"]
        databases = ["COSMIC"]
        parameters = {}

        with patch("app.services.tasks.clinical_tasks.current_task", mock_task):
            with patch("app.services.tasks.clinical_tasks.manager") as mock_manager:
                mock_manager.send_to_run = MagicMock()

                with patch(
                    "app.services.clinical_annotation.ClinicalAnnotationService"
                ) as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service.return_value = mock_service_instance
                    mock_service_instance.annotate_biomarker.side_effect = [
                        {"biomarker_id": "biomarker_1", "annotations": {}},
                        Exception("Test error"),
                    ]

                    result = annotate_biomarkers.__wrapped__(
                        run_id=run_id,
                        biomarker_ids=biomarker_ids,
                        databases=databases,
                        parameters=parameters,
                    )

                    assert result is not None
                    assert result["status"] == "completed"
                    assert result["total_annotated"] == 1

    def test_update_clinical_databases(self, db_session):
        """Test updating clinical databases."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        databases = ["COSMIC", "ClinVar"]

        with patch("app.services.tasks.clinical_tasks.current_task", mock_task):
            with patch(
                "app.services.clinical_annotation.ClinicalAnnotationService"
            ) as mock_service:
                mock_service_instance = MagicMock()
                mock_service.return_value = mock_service_instance
                mock_service_instance.update_database.return_value = {
                    "status": "updated"
                }

                result = update_clinical_databases.__wrapped__(databases=databases)

                assert result is not None
                assert result["status"] == "completed"
                assert "task_id" in result
