"""
API module for the Cancer Biomarker Identifier application.
"""

from .routes import (
    analysis_routes,
    auth_routes,
    biomarker_routes,
    clinical_routes,
    data_routes,
)

__all__ = [
    "biomarker_routes",
    "analysis_routes",
    "data_routes",
    "clinical_routes",
    "auth_routes",
]
