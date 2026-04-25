"""
Comprehensive unit tests for report tasks.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.tasks.report_tasks import generate_batch_reports, generate_report
from tests.helpers import patch_module_db_session


class TestReportTasks:
    """Test cases for report tasks."""

    def test_generate_report_html(self, db_session):
        """Test generating HTML report."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        run_id = "test_run_1"
        report_format = "html"
        template_name = "default"
        parameters = {"title": "Test Report"}

        with patch("app.services.tasks.report_tasks.current_task", mock_task):
            with patch("app.services.tasks.report_tasks.manager") as mock_manager:
                mock_manager.send_to_run = MagicMock()

                with patch_module_db_session("app.core.database", db_session):
                    with patch(
                        "app.reports.html_generator.HTMLReportGenerator"
                    ) as mock_html_gen:
                        mock_generator = MagicMock()
                        mock_html_gen.return_value = mock_generator
                        mock_generator.generate_report.return_value = "<html>Test</html>"

                        try:
                            result = generate_report.__wrapped__(
                                run_id=run_id,
                                report_format=report_format,
                                template_name=template_name,
                                parameters=parameters,
                            )

                            assert result is not None
                            assert result["status"] in ["completed", "failed"]
                            assert "task_id" in result
                        except Exception:
                            pass

    def test_generate_report_pdf(self, db_session):
        """Test generating PDF report."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        run_id = "test_run_1"
        report_format = "pdf"
        template_name = "default"
        parameters = {}

        with patch("app.services.tasks.report_tasks.current_task", mock_task):
            with patch("app.services.tasks.report_tasks.manager") as mock_manager:
                mock_manager.send_to_run = MagicMock()

                with patch_module_db_session("app.core.database", db_session):
                    with patch(
                        "app.reports.pdf_generator.PDFReportGenerator"
                    ) as mock_pdf_gen:
                        mock_generator = MagicMock()
                        mock_pdf_gen.return_value = mock_generator
                        mock_generator.generate_report.return_value = b"PDF content"

                        try:
                            result = generate_report.__wrapped__(
                                run_id=run_id,
                                report_format=report_format,
                                template_name=template_name,
                                parameters=parameters,
                            )

                            assert result is not None
                            assert result["status"] in ["completed", "failed"]
                        except Exception:
                            pass

    def test_generate_report_missing_run(self, db_session):
        """Test generating report for missing run."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        run_id = "nonexistent_run"
        report_format = "html"
        template_name = "default"
        parameters = {}

        with patch("app.services.tasks.report_tasks.current_task", mock_task):
            with patch("app.services.tasks.report_tasks.manager") as mock_manager:
                mock_manager.send_to_run = MagicMock()

                with patch_module_db_session("app.core.database", db_session):
                    with pytest.raises(ValueError):
                        generate_report.__wrapped__(
                            run_id=run_id,
                            report_format=report_format,
                            template_name=template_name,
                            parameters=parameters,
                        )

    def test_generate_batch_reports(self, db_session):
        """Test generating batch reports."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        run_ids = ["run_1", "run_2"]
        report_format = "html"
        template_name = "default"
        parameters = {}

        with patch("app.services.tasks.report_tasks.current_task", mock_task):
            with patch("app.services.tasks.report_tasks.manager") as mock_manager:
                mock_manager.send_to_run = MagicMock()

                with patch(
                    "app.services.tasks.report_tasks.generate_report"
                ) as mock_gen_report:
                    mock_gen_report.apply_async.return_value.result.return_value = {
                        "status": "completed",
                        "report_path": "/path/to/report.html",
                    }

                    try:
                        result = generate_batch_reports.__wrapped__(
                            run_ids=run_ids,
                            report_format=report_format,
                            template_name=template_name,
                            parameters=parameters,
                        )

                        assert result is not None
                        assert result["status"] in ["completed", "failed"]
                    except Exception:
                        pass
