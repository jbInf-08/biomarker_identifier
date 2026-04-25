"""
Unit tests for template manager module.
"""

import os
import tempfile
from pathlib import Path

import pytest

from app.reports.template_manager import TemplateManager


@pytest.fixture
def temp_template_dir():
    """Create temporary template directory with sample templates."""
    temp_dir = tempfile.mkdtemp()
    template_dir = Path(temp_dir) / "templates"
    template_dir.mkdir()

    # Create sample template files
    (template_dir / "standard_report.html").write_text("Standard Report: {{ title }}")
    (template_dir / "clinical_report.html").write_text("Clinical Report: {{ title }}")
    (template_dir / "publication_report.html").write_text(
        "Publication Report: {{ title }}"
    )
    (template_dir / "summary_report.html").write_text("Summary Report: {{ title }}")

    return str(template_dir)


class TestTemplateManager:
    """Test TemplateManager class."""

    def test_init_default(self):
        """Test TemplateManager initialization with default directory."""
        manager = TemplateManager()
        assert manager.template_dir is not None
        assert manager.jinja_env is not None
        assert "standard" in manager.templates

    def test_init_custom(self, temp_template_dir):
        """Test TemplateManager initialization with custom directory."""
        manager = TemplateManager(template_dir=temp_template_dir)
        assert manager.template_dir == temp_template_dir

    def test_get_template(self, temp_template_dir):
        """Test getting a template."""
        manager = TemplateManager(template_dir=temp_template_dir)
        template = manager.get_template("standard")
        assert template is not None

    def test_get_template_not_found(self, temp_template_dir):
        """Test getting a non-existent template."""
        manager = TemplateManager(template_dir=temp_template_dir)

        with pytest.raises(ValueError):
            manager.get_template("nonexistent")

    def test_render_template(self, temp_template_dir):
        """Test rendering a template."""
        manager = TemplateManager(template_dir=temp_template_dir)

        context = {"title": "Test Report"}
        rendered = manager.render_template("standard", context)

        assert "Test Report" in rendered
        assert "Standard Report" in rendered

    def test_get_available_templates(self):
        """Test getting available templates."""
        manager = TemplateManager()
        templates = manager.get_available_templates()

        assert "standard" in templates
        assert "clinical" in templates
        assert "publication" in templates
        assert "summary" in templates

        assert isinstance(templates["standard"], str)
