"""
API routes package for Cancer Biomarker Identifier.
"""

from . import admin_routes, analysis_routes, auth_routes
from . import biomarker_routes as biomarkers
from . import clinical_routes, data_routes, federated_routes, system_routes, tenant_routes

__all__ = [
    "admin_routes",
    "biomarkers",
    "analysis_routes",
    "data_routes",
    "clinical_routes",
    "auth_routes",
    "federated_routes",
    "system_routes",
    "tenant_routes",
]
