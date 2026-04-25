"""
Clinical annotation service used by Celery tasks.

Wraps the async ``ClinicalAnnotationService`` from advanced models with a
small sync API (``asyncio.run``) so task code can call it without ``await``.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

from app.ml_models.advanced_models import ClinicalAnnotationService as _AsyncClinicalService


def _normalize_source(name: str) -> str:
    """Map UI/database names to annotation_sources keys."""
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    aliases = {
        "cosmic": "cosmic",
        "clinvar": "clinvar",
        "oncokb": "oncokb",
        "pubmed": "pubmed",
    }
    return aliases.get(key, key)


class ClinicalAnnotationService(_AsyncClinicalService):
    """Sync adapter for background tasks."""

    def annotate_biomarker(
        self,
        biomarker_id: str,
        databases: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        parameters = parameters or {}
        sources = (
            [_normalize_source(d) for d in databases]
            if databases
            else None
        )
        return asyncio.run(
            super().annotate_biomarker(biomarker=biomarker_id, sources=sources)
        )

    def update_database(self, database: str) -> Dict[str, Any]:
        """Placeholder for scheduled DB refresh (not yet implemented)."""
        return {"status": "updated", "database": database}
