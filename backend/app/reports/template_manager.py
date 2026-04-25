"""
Template manager for report generation.
"""

import os
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, Template

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """Manages report templates and rendering."""

    def __init__(self, template_dir: str = None):
        """
        Initialize template manager.

        Args:
            template_dir: Directory containing templates
        """
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.template_dir = template_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir), autoescape=True
        )

        # Load default templates
        self.templates = {
            "standard": "standard_report.html",
            "clinical": "clinical_report.html",
            "publication": "publication_report.html",
            "summary": "summary_report.html",
        }

    def get_template(self, template_name: str) -> Template:
        """
        Get a template by name.

        Args:
            template_name: Name of the template

        Returns:
            Jinja2 template object
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template_file = self.templates[template_name]
        return self.jinja_env.get_template(template_file)

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Name of the template
            context: Template context variables

        Returns:
            Rendered HTML content
        """
        try:
            template = self.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {str(e)}")
            raise

    def get_available_templates(self) -> Dict[str, str]:
        """
        Get list of available templates.

        Returns:
            Dictionary of template names and descriptions
        """
        return {
            "standard": "Standard biomarker analysis report with comprehensive results",
            "clinical": "Clinical-focused report with therapeutic implications",
            "publication": "Publication-ready report with detailed methodology",
            "summary": "Executive summary report with key findings",
        }
