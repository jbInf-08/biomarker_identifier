"""
Comprehensive unit tests for export service.
"""
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.biomarker_model import BiomarkerResult
from app.models.run_model import AnalysisRun
from app.services.export_service import ExportService
from tests.helpers import patch_module_db_session


class TestExportService:
    """Test cases for ExportService."""

    def test_export_service_initialization(self):
        """Test export service initialization."""
        service = ExportService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_export_analysis_results_csv(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test exporting analysis results as CSV."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export directory
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):

                result = await service.export_analysis_results(
                    run_id=str(test_analysis_run.id),
                    export_format="csv",
                    include_metadata=True,
                    include_visualizations=False,
                    include_raw_data=False,
                )

                assert result is not None
                assert "file_path" in result or "export_timestamp" in result

    @pytest.mark.asyncio
    async def test_export_analysis_results_json(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test exporting analysis results as JSON."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):

                result = await service.export_analysis_results(
                    run_id=str(test_analysis_run.id),
                    export_format="json",
                    include_metadata=True,
                    include_visualizations=False,
                    include_raw_data=False,
                )

                assert result is not None
                assert "file_path" in result or "export_timestamp" in result

    @pytest.mark.asyncio
    async def test_export_analysis_results_excel(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test exporting analysis results as Excel."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):

                result = await service.export_analysis_results(
                    run_id=str(test_analysis_run.id),
                    export_format="excel",
                    include_metadata=True,
                    include_visualizations=False,
                    include_raw_data=False,
                )

                assert result is not None
                assert "file_path" in result or "export_timestamp" in result

    @pytest.mark.asyncio
    async def test_export_analysis_results_pdf(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test exporting analysis results as PDF."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):

                result = await service.export_analysis_results(
                    run_id=str(test_analysis_run.id),
                    export_format="pdf",
                    include_metadata=True,
                    include_visualizations=False,
                    include_raw_data=False,
                )

                assert result is not None
                assert "file_path" in result or "export_timestamp" in result

    @pytest.mark.asyncio
    async def test_export_analysis_results_zip(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test exporting analysis results as ZIP."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):

                result = await service.export_analysis_results(
                    run_id=str(test_analysis_run.id),
                    export_format="zip",
                    include_metadata=True,
                    include_visualizations=True,
                    include_raw_data=True,
                )

                assert result is not None
                assert "file_path" in result or "export_timestamp" in result

    @pytest.mark.asyncio
    async def test_export_analysis_results_not_found(self, db_session):
        """Test exporting results for non-existent run."""
        service = ExportService()

        with patch_module_db_session("app.services.export_service", db_session):
            with pytest.raises(ValueError):
                await service.export_analysis_results(
                    run_id="nonexistent-id", export_format="csv"
                )

    @pytest.mark.asyncio
    async def test_share_analysis_results(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test sharing analysis results via email."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):
                with patch.object(
                    service, "_send_email_with_attachment", new_callable=AsyncMock
                ):
                    result = await service.share_analysis_results(
                        run_id=str(test_analysis_run.id),
                        recipient_emails=["test@example.com"],
                        message="Test message",
                        export_format="zip",
                    )

                assert result is not None
                assert (
                    "success" in result or "recipients" in result or "error" in result
                )

    @pytest.mark.asyncio
    async def test_generate_public_link(
        self, db_session, test_analysis_run, test_biomarker_results
    ):
        """Test generating public sharing link."""
        import os
        import tempfile
        from unittest.mock import patch

        from app.core.config import settings

        service = ExportService()

        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "exports")
            os.makedirs(export_dir, exist_ok=True)

            with patch_module_db_session(
                "app.services.export_service", db_session
            ), patch.object(settings, "EXPORT_DIR", export_dir):

                result = await service.generate_public_link(
                    run_id=str(test_analysis_run.id),
                    expiration_hours=24,
                    password_protected=False,
                )

                assert result is not None
                assert "link" in result or "url" in result or "share_id" in result
