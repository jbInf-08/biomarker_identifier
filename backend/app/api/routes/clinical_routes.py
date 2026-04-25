"""
Clinical database integration API routes for COSMIC, ClinVar, and OncoKB.
Uses real public APIs only. No mock or fake data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.biomarker_model import BiomarkerResult
from app.models.run_model import AnalysisRun
from app.models.user_model import User
from app.services.auth_service import auth_service
from app.services.run_access import get_analysis_run_for_user
from app.services.clinical_decision_support import (
    clinical_recommendation_to_dict,
    clinical_decision_support_service,
    ensure_cds_ready,
)
from app.services.clinical_api_client import (
    fetch_clinvar_variants,
    fetch_cosmic_mutations,
    fetch_oncokb_cancer_genes,
    fetch_oncokb_drugs,
    fetch_oncokb_genes,
)
from app.utils.logging_config import get_logger

# Authentication dependency
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    from fastapi import HTTPException, status

    from app.models.user_model import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = auth_service.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except Exception:
        raise credentials_exception

    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise credentials_exception

    return user


logger = get_logger(__name__)
router = APIRouter()

# =============================================================================
# Real API helpers (delegate to clinical_api_client - no mock data)
# =============================================================================


def _get_cosmic_mutations_data(
    gene_symbol: Optional[str] = None,
    cancer_type: Optional[str] = None,
    mutation_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Get COSMIC mutations from real NIH Clinical Tables API."""
    return fetch_cosmic_mutations(
        gene_symbol=gene_symbol,
        cancer_type=cancer_type,
        mutation_type=mutation_type,
        limit=limit,
    )


def _get_clinvar_variants_data(
    gene_symbol: Optional[str] = None,
    clinical_significance: Optional[str] = None,
    variant_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Get ClinVar variants from real NCBI E-utilities API."""
    return fetch_clinvar_variants(
        gene_symbol=gene_symbol,
        clinical_significance=clinical_significance,
        variant_type=variant_type,
        limit=limit,
    )


def _get_oncokb_genes_data(
    cancer_type: Optional[str] = None,
    oncogenic: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Get OncoKB genes from real public API."""
    result = fetch_oncokb_genes(
        cancer_type=cancer_type,
        oncogenic=oncogenic,
        limit=limit,
    )
    if "genes" not in result:
        result["genes"] = result.get("cancer_genes", [])
    return result


# =============================================================================
# COSMIC Integration
# =============================================================================


@router.get("/cosmic/mutations", response_model=Dict[str, Any])
async def get_cosmic_mutations(
    gene_symbol: Optional[str] = Query(None, description="Gene symbol"),
    cancer_type: Optional[str] = Query(None, description="Cancer type"),
    mutation_type: Optional[str] = Query(None, description="Mutation type"),
    limit: int = Query(100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Get COSMIC mutation data.
    """
    try:
        result = _get_cosmic_mutations_data(
            gene_symbol, cancer_type, mutation_type, limit
        )

        logger.info(
            f"Retrieved COSMIC mutations",
            extra={
                "gene_symbol": gene_symbol,
                "cancer_type": cancer_type,
                "count": result["total_count"],
            },
        )

        return result

    except Exception as e:
        logger.error(f"Failed to get COSMIC mutations", extra={"error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to get COSMIC mutations: {str(e)}"
        )


@router.get("/cosmic/cancer-genes", response_model=Dict[str, Any])
async def get_cosmic_cancer_genes(
    cancer_type: Optional[str] = Query(None, description="Cancer type"),
    tier: Optional[int] = Query(None, description="Gene tier (1-3)"),
    limit: int = Query(100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Get COSMIC cancer gene census data from OncoKB (real cancer gene list).
    COSMIC Cancer Gene Census requires licensed access; OncoKB provides curated cancer genes.
    """
    try:
        result = fetch_oncokb_cancer_genes(
            cancer_type=cancer_type, tier=tier, limit=limit
        )
        logger.info(
            f"Retrieved cancer genes",
            extra={
                "cancer_type": cancer_type,
                "tier": tier,
                "count": result.get("total_count", 0),
            },
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get cancer genes", extra={"error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to get cancer genes: {str(e)}"
        )


# =============================================================================
# ClinVar Integration
# =============================================================================


@router.get("/clinvar/variants", response_model=Dict[str, Any])
async def get_clinvar_variants(
    gene_symbol: Optional[str] = Query(None, description="Gene symbol"),
    clinical_significance: Optional[str] = Query(
        None, description="Clinical significance"
    ),
    variant_type: Optional[str] = Query(None, description="Variant type"),
    limit: int = Query(100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Get ClinVar variant data.
    """
    try:
        result = _get_clinvar_variants_data(
            gene_symbol, clinical_significance, variant_type, limit
        )

        logger.info(
            f"Retrieved ClinVar variants",
            extra={
                "gene_symbol": gene_symbol,
                "clinical_significance": clinical_significance,
                "count": result.get("total_count", 0),
            },
        )

        return result

    except Exception as e:
        logger.error(f"Failed to get ClinVar variants", extra={"error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to get ClinVar variants: {str(e)}"
        )


# =============================================================================
# OncoKB Integration
# =============================================================================


@router.get("/oncokb/genes", response_model=Dict[str, Any])
async def get_oncokb_genes(
    cancer_type: Optional[str] = Query(None, description="Cancer type"),
    oncogenic: Optional[str] = Query(None, description="Oncogenic classification"),
    limit: int = Query(100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Get OncoKB gene data.
    """
    try:
        result = _get_oncokb_genes_data(cancer_type, oncogenic, limit)

        logger.info(
            f"Retrieved OncoKB genes",
            extra={
                "cancer_type": cancer_type,
                "oncogenic": oncogenic,
                "count": result["total_count"],
            },
        )

        return result

    except Exception as e:
        logger.error(f"Failed to get OncoKB genes", extra={"error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to get OncoKB genes: {str(e)}"
        )


@router.get("/oncokb/drugs", response_model=Dict[str, Any])
async def get_oncokb_drugs(
    gene_symbol: Optional[str] = Query(None, description="Gene symbol"),
    cancer_type: Optional[str] = Query(None, description="Cancer type"),
    evidence_level: Optional[str] = Query(None, description="Evidence level"),
    limit: int = Query(100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Get OncoKB drug data from real public API.
    """
    try:
        result = fetch_oncokb_drugs(
            gene_symbol=gene_symbol,
            cancer_type=cancer_type,
            evidence_level=evidence_level,
            limit=limit,
        )
        logger.info(
            f"Retrieved OncoKB drugs",
            extra={
                "gene_symbol": gene_symbol,
                "cancer_type": cancer_type,
                "evidence_level": evidence_level,
                "count": result.get("total_count", 0),
            },
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get OncoKB drugs", extra={"error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to get OncoKB drugs: {str(e)}"
        )


# =============================================================================
# Biomarker Annotation
# =============================================================================


@router.post("/annotate-biomarkers", response_model=Dict[str, Any])
async def annotate_biomarkers(
    biomarkers: List[str],
    databases: List[str] = ["COSMIC", "ClinVar", "OncoKB"],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Annotate a list of biomarkers with clinical database information.
    """
    try:
        annotated_biomarkers = []

        for gene_symbol in biomarkers:
            annotation = {
                "gene_symbol": gene_symbol,
                "cosmic_annotations": [],
                "clinvar_annotations": [],
                "oncokb_annotations": [],
                "clinical_summary": {
                    "is_cancer_gene": False,
                    "has_pathogenic_variants": False,
                    "has_therapeutic_implications": False,
                    "evidence_level": "Unknown",
                },
            }

            # Get COSMIC annotations
            if "COSMIC" in databases:
                try:
                    cosmic_data = _get_cosmic_mutations_data(
                        gene_symbol=gene_symbol, limit=5
                    )
                    annotation["cosmic_annotations"] = cosmic_data["mutations"]
                    if cosmic_data["mutations"]:
                        annotation["clinical_summary"]["is_cancer_gene"] = True
                except Exception as e:
                    logger.warning(
                        f"Failed to get COSMIC data for {gene_symbol}: {str(e)}"
                    )

            # Get ClinVar annotations
            if "ClinVar" in databases:
                try:
                    clinvar_data = _get_clinvar_variants_data(
                        gene_symbol=gene_symbol, limit=5
                    )
                    annotation["clinvar_annotations"] = clinvar_data["variants"]
                    pathogenic_variants = [
                        v
                        for v in clinvar_data["variants"]
                        if "Pathogenic" in v.get("clinical_significance", "")
                    ]
                    if pathogenic_variants:
                        annotation["clinical_summary"]["has_pathogenic_variants"] = True
                except Exception as e:
                    logger.warning(
                        f"Failed to get ClinVar data for {gene_symbol}: {str(e)}"
                    )

            # Get OncoKB annotations
            if "OncoKB" in databases:
                try:
                    oncokb_data = _get_oncokb_genes_data(cancer_type=None, limit=100)
                    oncokb_genes = [
                        g
                        for g in oncokb_data["genes"]
                        if g.get("gene_symbol") == gene_symbol
                    ]
                    if oncokb_genes:
                        annotation["oncokb_annotations"] = oncokb_genes
                        annotation["clinical_summary"][
                            "has_therapeutic_implications"
                        ] = True
                        annotation["clinical_summary"]["evidence_level"] = "1"
                except Exception as e:
                    logger.warning(
                        f"Failed to get OncoKB data for {gene_symbol}: {str(e)}"
                    )

            annotated_biomarkers.append(annotation)

        logger.info(
            f"Annotated biomarkers",
            extra={"biomarker_count": len(biomarkers), "databases": databases},
        )

        return {
            "annotation_summary": {
                "total_biomarkers": len(biomarkers),
                "databases_used": databases,
                "annotated_at": datetime.utcnow().isoformat(),
            },
            "annotated_biomarkers": annotated_biomarkers,
        }

    except Exception as e:
        logger.error(f"Failed to annotate biomarkers", extra={"error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to annotate biomarkers: {str(e)}"
        )


@router.post("/annotate-run/{run_id}", response_model=Dict[str, Any])
async def annotate_run_biomarkers(
    run_id: str = Path(..., description="Run ID"),
    databases: List[str] = ["COSMIC", "ClinVar", "OncoKB"],
    top_n: int = Query(50, description="Number of top biomarkers to annotate"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Annotate biomarkers from a specific run with clinical database information.
    """
    try:
        run = get_analysis_run_for_user(db, run_id, current_user)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        # Get top biomarkers from the run
        from app.models.biomarker_model import BiomarkerResult

        biomarkers_results = (
            db.query(BiomarkerResult)
            .filter(BiomarkerResult.run_id == run_id)
            .order_by(BiomarkerResult.p_value.asc())
            .limit(top_n)
            .all()
        )

        if not biomarkers_results:
            raise HTTPException(
                status_code=404, detail="No biomarkers found for this run"
            )

        # Extract gene symbols
        gene_symbols = [result.gene_symbol for result in biomarkers_results]

        # Annotate biomarkers
        annotated_biomarkers = []

        for result in biomarkers_results:
            # Convert log2_fold_change to fold_change
            fold_change = (
                2**result.log2_fold_change
                if result.log2_fold_change is not None
                else None
            )

            annotation = {
                "gene_symbol": result.gene_symbol,
                "p_value": result.p_value,
                "fold_change": fold_change,
                "cosmic_annotations": [],
                "clinvar_annotations": [],
                "oncokb_annotations": [],
                "clinical_summary": {
                    "is_cancer_gene": False,
                    "has_pathogenic_variants": False,
                    "has_therapeutic_implications": False,
                    "evidence_level": "Unknown",
                    "clinical_relevance_score": 0.0,
                },
            }

            # Get COSMIC annotations
            if "COSMIC" in databases:
                try:
                    cosmic_data = _get_cosmic_mutations_data(
                        gene_symbol=result.gene_symbol, limit=5
                    )
                    annotation["cosmic_annotations"] = cosmic_data["mutations"]
                    if cosmic_data["mutations"]:
                        annotation["clinical_summary"]["is_cancer_gene"] = True
                        annotation["clinical_summary"][
                            "clinical_relevance_score"
                        ] += 0.3
                except Exception as e:
                    logger.warning(
                        f"Failed to get COSMIC data for {result.gene_symbol}: {str(e)}"
                    )

            # Get ClinVar annotations
            if "ClinVar" in databases:
                try:
                    clinvar_data = _get_clinvar_variants_data(
                        gene_symbol=result.gene_symbol, limit=5
                    )
                    annotation["clinvar_annotations"] = clinvar_data["variants"]
                    pathogenic_variants = [
                        v
                        for v in clinvar_data["variants"]
                        if "Pathogenic" in v.get("clinical_significance", "")
                    ]
                    if pathogenic_variants:
                        annotation["clinical_summary"]["has_pathogenic_variants"] = True
                        annotation["clinical_summary"][
                            "clinical_relevance_score"
                        ] += 0.4
                except Exception as e:
                    logger.warning(
                        f"Failed to get ClinVar data for {result.gene_symbol}: {str(e)}"
                    )

            # Get OncoKB annotations
            if "OncoKB" in databases:
                try:
                    oncokb_data = _get_oncokb_genes_data(cancer_type=None, limit=100)
                    oncokb_genes = [
                        g
                        for g in oncokb_data["genes"]
                        if g.get("gene_symbol") == result.gene_symbol
                    ]
                    if oncokb_genes:
                        annotation["oncokb_annotations"] = oncokb_genes
                        annotation["clinical_summary"][
                            "has_therapeutic_implications"
                        ] = True
                        annotation["clinical_summary"]["evidence_level"] = "1"
                        annotation["clinical_summary"][
                            "clinical_relevance_score"
                        ] += 0.3
                except Exception as e:
                    logger.warning(
                        f"Failed to get OncoKB data for {result.gene_symbol}: {str(e)}"
                    )

            annotated_biomarkers.append(annotation)

        # Sort by clinical relevance score
        annotated_biomarkers.sort(
            key=lambda x: x["clinical_summary"]["clinical_relevance_score"],
            reverse=True,
        )

        logger.info(
            f"Annotated run biomarkers",
            extra={
                "run_id": run_id,
                "biomarker_count": len(annotated_biomarkers),
                "databases": databases,
            },
        )

        return {
            "run_id": run_id,
            "annotation_summary": {
                "total_biomarkers": len(annotated_biomarkers),
                "databases_used": databases,
                "annotated_at": datetime.utcnow().isoformat(),
                "high_relevance_count": len(
                    [
                        b
                        for b in annotated_biomarkers
                        if b["clinical_summary"]["clinical_relevance_score"] > 0.5
                    ]
                ),
            },
            "annotated_biomarkers": annotated_biomarkers,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to annotate run biomarkers",
            extra={"run_id": run_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to annotate run biomarkers: {str(e)}"
        )


# =============================================================================
# Clinical Decision Support (authenticated)
# =============================================================================


class CDSRecommendationsBody(BaseModel):
    run_id: Optional[str] = None
    biomarker_results: Optional[List[Dict[str, Any]]] = None
    patient_context: Dict[str, Any] = Field(default_factory=dict)


class CDSEvidenceBody(BaseModel):
    genes: List[str]
    patient_context: Dict[str, Any] = Field(default_factory=dict)


class CDSValidateBody(BaseModel):
    biomarker: str
    clinical_decision: str
    patient_context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/decision-support/recommendations")
async def cds_recommendations(
    body: CDSRecommendationsBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate clinical recommendations from biomarker rows and patient context.
    Optionally pass run_id to load top biomarkers from the database.
    """
    await ensure_cds_ready()
    rows = body.biomarker_results or []
    if body.run_id and not rows:
        run = get_analysis_run_for_user(db, body.run_id, current_user)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        results = (
            db.query(BiomarkerResult)
            .filter(BiomarkerResult.run_id == body.run_id)
            .order_by(BiomarkerResult.p_value.asc())
            .limit(50)
            .all()
        )
        rows = [{"gene_symbol": r.gene_symbol, "p_value": r.p_value} for r in results]

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="Provide biomarker_results or a valid run_id with stored biomarkers.",
        )

    recs = await clinical_decision_support_service.generate_clinical_recommendations(
        rows, body.patient_context
    )
    return {
        "disclaimer": "Research and educational use only. Not a substitute for clinical judgment or licensed medical advice.",
        "recommendations": [clinical_recommendation_to_dict(r) for r in recs],
        "count": len(recs),
    }


@router.post("/decision-support/evidence-quality")
async def cds_evidence_quality(
    body: CDSEvidenceBody,
    current_user: User = Depends(get_current_user),
):
    await ensure_cds_ready()
    if not body.genes:
        raise HTTPException(status_code=400, detail="genes required")
    assessed = await clinical_decision_support_service.assess_evidence_quality(
        body.genes[:100], body.patient_context
    )
    return {
        "disclaimer": "Evidence tiers reflect internal CDS scoring, not regulatory labels.",
        "genes": assessed,
    }


@router.post("/decision-support/validate")
async def cds_validate_decision(
    body: CDSValidateBody,
    current_user: User = Depends(get_current_user),
):
    await ensure_cds_ready()
    result = await clinical_decision_support_service.validate_clinical_decision(
        body.biomarker, body.clinical_decision, body.patient_context
    )
    result["disclaimer"] = "Validation is heuristic; confirm against primary literature and guidelines."
    return result
