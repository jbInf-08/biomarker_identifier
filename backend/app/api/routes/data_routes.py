"""
Data API routes for data upload, validation, processing, and management.
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.data_model import (
    ClinicalData,
    DataQualityMetrics,
    DataType,
    ExpressionData,
)
from app.models.user_model import User
from app.services.auth_service import auth_service
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

UPLOAD_REGISTRY_FILENAME = "upload_registry.json"


def _upload_registry_path() -> str:
    return os.path.join(settings.UPLOAD_DIR, UPLOAD_REGISTRY_FILENAME)


def _read_upload_registry() -> Dict[str, Any]:
    p = _upload_registry_path()
    if not os.path.isfile(p):
        return {"files": {}}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"files": {}}


def _write_upload_registry(data: Dict[str, Any]) -> None:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(_upload_registry_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _record_upload_metadata(
    *,
    file_id: str,
    filename: str,
    data_type: str,
    organism: str,
    rows: int,
    columns: int,
) -> None:
    reg = _read_upload_registry()
    reg.setdefault("files", {})[file_id] = {
        "filename": filename,
        "data_type": data_type,
        "organism": organism,
        "rows": rows,
        "columns": columns,
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    _write_upload_registry(reg)

# =============================================================================
# Data Upload Endpoints
# =============================================================================


@router.post("/upload/expression", response_model=Dict[str, Any])
async def upload_expression_data(
    file: UploadFile = File(...),
    data_type: str = Form(
        "rna_seq", description="Data type (rna_seq, microarray, proteomics)"
    ),
    organism: str = Form("human", description="Organism"),
    normalization_method: Optional[str] = Form(
        None, description="Normalization method"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload gene expression data.

    Args:
        file: Expression data file (CSV, TSV, or Excel)
        data_type: Type of expression data
        organism: Organism
        normalization_method: Normalization method
        db: Database session

    Returns:
        Upload confirmation and data summary
    """
    try:
        # Validate file type
        allowed_extensions = [".csv", ".tsv", ".xlsx", ".xls"]
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
            )

        # Create unique filename
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)

        # Save file
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Load and validate data
        if file_extension == ".csv":
            df = pd.read_csv(filepath)
        elif file_extension == ".tsv":
            df = pd.read_csv(filepath, sep="\t")
        else:
            df = pd.read_excel(filepath)

        # Basic validation
        if df.empty:
            raise HTTPException(status_code=400, detail="File is empty")

        if len(df.columns) < 2:
            raise HTTPException(
                status_code=400, detail="File must have at least 2 columns"
            )

        # Calculate basic statistics
        data_summary = {
            "file_id": file_id,
            "filename": file.filename,
            "data_type": data_type,
            "organism": organism,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "file_size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2),
            "missing_values": int(df.isnull().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()),
            "upload_time": datetime.utcnow().isoformat(),
        }

        _record_upload_metadata(
            file_id=file_id,
            filename=file.filename,
            data_type=data_type,
            organism=organism,
            rows=int(len(df)),
            columns=int(len(df.columns)),
        )

        logger.info(
            f"Uploaded expression data",
            extra={
                "file_id": file_id,
                "filename": file.filename,
                "data_type": data_type,
                "rows": len(df),
                "columns": len(df.columns),
            },
        )

        return {
            "status": "success",
            "message": "Expression data uploaded successfully",
            "file_id": file_id,
            "data_summary": data_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to upload expression data",
            extra={"error": str(e), "filename": file.filename},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to upload expression data: {str(e)}"
        )


@router.post("/upload/clinical", response_model=Dict[str, Any])
async def upload_clinical_data(
    file: UploadFile = File(...),
    data_type: str = Form("clinical", description="Data type"),
    study_id: Optional[str] = Form(None, description="Study ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload clinical data.

    Args:
        file: Clinical data file
        data_type: Type of clinical data
        study_id: Study ID
        db: Database session

    Returns:
        Upload confirmation and data summary
    """
    try:
        # Validate file type
        allowed_extensions = [".csv", ".tsv", ".xlsx", ".xls"]
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
            )

        # Create unique filename
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)

        # Save file
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Load and validate data
        if file_extension == ".csv":
            df = pd.read_csv(filepath)
        elif file_extension == ".tsv":
            df = pd.read_csv(filepath, sep="\t")
        else:
            df = pd.read_excel(filepath)

        # Basic validation
        if df.empty:
            raise HTTPException(status_code=400, detail="File is empty")

        # Check for required columns
        required_columns = ["sample_id"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}",
            )

        # Calculate basic statistics
        data_summary = {
            "file_id": file_id,
            "filename": file.filename,
            "data_type": data_type,
            "study_id": study_id,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "file_size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2),
            "missing_values": int(df.isnull().sum().sum()),
            "unique_samples": int(df["sample_id"].nunique())
            if "sample_id" in df.columns
            else 0,
            "upload_time": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Uploaded clinical data",
            extra={
                "file_id": file_id,
                "filename": file.filename,
                "data_type": data_type,
                "rows": len(df),
                "columns": len(df.columns),
            },
        )

        return {
            "status": "success",
            "message": "Clinical data uploaded successfully",
            "file_id": file_id,
            "data_summary": data_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to upload clinical data",
            extra={"error": str(e), "filename": file.filename},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to upload clinical data: {str(e)}"
        )


@router.post("/upload/multi-omics", response_model=Dict[str, Any])
async def upload_multi_omics_data(
    expression_file: UploadFile = File(...),
    clinical_file: UploadFile = File(...),
    mutation_file: Optional[UploadFile] = File(None),
    methylation_file: Optional[UploadFile] = File(None),
    proteomics_file: Optional[UploadFile] = File(None),
    study_name: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload multi-omics data package.

    Args:
        expression_file: Gene expression data
        clinical_file: Clinical data
        mutation_file: Mutation data (optional)
        methylation_file: Methylation data (optional)
        proteomics_file: Proteomics data (optional)
        study_name: Study name
        db: Database session

    Returns:
        Upload confirmation and data summary
    """
    try:
        study_id = str(uuid.uuid4())
        uploaded_files = {}

        # Upload expression data
        expression_result = await upload_expression_data(
            file=expression_file, data_type="rna_seq", organism="human"
        )
        uploaded_files["expression"] = expression_result

        # Upload clinical data
        clinical_result = await upload_clinical_data(
            file=clinical_file, data_type="clinical", study_id=study_id
        )
        uploaded_files["clinical"] = clinical_result

        # Upload optional files
        if mutation_file:
            mutation_result = await upload_expression_data(
                file=mutation_file, data_type="mutations", organism="human"
            )
            uploaded_files["mutations"] = mutation_result

        if methylation_file:
            methylation_result = await upload_expression_data(
                file=methylation_file, data_type="methylation", organism="human"
            )
            uploaded_files["methylation"] = methylation_result

        if proteomics_file:
            proteomics_result = await upload_expression_data(
                file=proteomics_file, data_type="proteomics", organism="human"
            )
            uploaded_files["proteomics"] = proteomics_result

        logger.info(
            f"Uploaded multi-omics data package",
            extra={
                "study_id": study_id,
                "study_name": study_name,
                "files_uploaded": len(uploaded_files),
            },
        )

        return {
            "status": "success",
            "message": "Multi-omics data package uploaded successfully",
            "study_id": study_id,
            "study_name": study_name,
            "uploaded_files": uploaded_files,
        }

    except Exception as e:
        logger.error(
            f"Failed to upload multi-omics data",
            extra={"error": str(e), "study_name": study_name},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to upload multi-omics data: {str(e)}"
        )


# =============================================================================
# Data Validation Endpoints
# =============================================================================


@router.post("/validate/expression", response_model=Dict[str, Any])
async def validate_expression_data(
    file_id: str = Query(..., description="File ID to validate"),
    db: Session = Depends(get_db),
):
    """
    Validate uploaded expression data.

    Args:
        file_id: File ID to validate
        db: Database session

    Returns:
        Validation results
    """
    try:
        # Find file
        filepath = None
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                break

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        # Load data
        file_extension = os.path.splitext(filepath)[1].lower()
        if file_extension == ".csv":
            df = pd.read_csv(filepath)
        elif file_extension == ".tsv":
            df = pd.read_csv(filepath, sep="\t")
        else:
            df = pd.read_excel(filepath)

        # Perform validation checks
        validation_results = {
            "file_id": file_id,
            "validation_time": datetime.utcnow().isoformat(),
            "checks": {},
        }

        # Basic structure checks
        validation_results["checks"]["file_structure"] = {
            "has_data": not df.empty,
            "row_count": len(df),
            "column_count": len(df.columns),
            "has_gene_column": any(
                col.lower() in ["gene", "gene_id", "gene_symbol"] for col in df.columns
            ),
        }

        # Data quality checks
        validation_results["checks"]["data_quality"] = {
            "missing_values": df.isnull().sum().sum(),
            "missing_percentage": round(
                (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100, 2
            ),
            "duplicate_rows": df.duplicated().sum(),
            "duplicate_columns": df.columns.duplicated().sum(),
        }

        # Expression-specific checks
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        validation_results["checks"]["expression_quality"] = {
            "numeric_columns": len(numeric_columns),
            "negative_values": (df[numeric_columns] < 0).sum().sum()
            if len(numeric_columns) > 0
            else 0,
            "zero_values": (df[numeric_columns] == 0).sum().sum()
            if len(numeric_columns) > 0
            else 0,
            "expression_range": {
                "min": float(df[numeric_columns].min().min())
                if len(numeric_columns) > 0
                else None,
                "max": float(df[numeric_columns].max().max())
                if len(numeric_columns) > 0
                else None,
            },
        }

        # Overall validation status
        validation_results["overall_status"] = "valid"
        validation_results["issues"] = []

        # Check for issues
        if validation_results["checks"]["data_quality"]["missing_percentage"] > 20:
            validation_results["overall_status"] = "warning"
            validation_results["issues"].append("High percentage of missing values")

        if validation_results["checks"]["data_quality"]["duplicate_rows"] > 0:
            validation_results["overall_status"] = "warning"
            validation_results["issues"].append("Duplicate rows found")

        if not validation_results["checks"]["file_structure"]["has_gene_column"]:
            validation_results["overall_status"] = "error"
            validation_results["issues"].append("No gene identifier column found")

        logger.info(
            f"Validated expression data",
            extra={
                "file_id": file_id,
                "status": validation_results["overall_status"],
                "issues_count": len(validation_results["issues"]),
            },
        )

        return validation_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to validate expression data",
            extra={"error": str(e), "file_id": file_id},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to validate expression data: {str(e)}"
        )


@router.post("/validate/clinical", response_model=Dict[str, Any])
async def validate_clinical_data(
    file_id: str = Query(..., description="File ID to validate"),
    db: Session = Depends(get_db),
):
    """
    Validate uploaded clinical data.

    Args:
        file_id: File ID to validate
        db: Database session

    Returns:
        Validation results
    """
    try:
        # Find file
        filepath = None
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                break

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        # Load data
        file_extension = os.path.splitext(filepath)[1].lower()
        if file_extension == ".csv":
            df = pd.read_csv(filepath)
        elif file_extension == ".tsv":
            df = pd.read_csv(filepath, sep="\t")
        else:
            df = pd.read_excel(filepath)

        # Perform validation checks
        validation_results = {
            "file_id": file_id,
            "validation_time": datetime.utcnow().isoformat(),
            "checks": {},
        }

        # Basic structure checks
        validation_results["checks"]["file_structure"] = {
            "has_data": not df.empty,
            "row_count": len(df),
            "column_count": len(df.columns),
            "has_sample_id": "sample_id" in df.columns,
        }

        # Data quality checks
        validation_results["checks"]["data_quality"] = {
            "missing_values": df.isnull().sum().sum(),
            "missing_percentage": round(
                (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100, 2
            ),
            "duplicate_rows": df.duplicated().sum(),
            "duplicate_samples": df["sample_id"].duplicated().sum()
            if "sample_id" in df.columns
            else 0,
        }

        # Clinical-specific checks
        validation_results["checks"]["clinical_quality"] = {
            "unique_samples": df["sample_id"].nunique()
            if "sample_id" in df.columns
            else 0,
            "categorical_columns": len(df.select_dtypes(include=["object"]).columns),
            "numeric_columns": len(df.select_dtypes(include=[np.number]).columns),
        }

        # Overall validation status
        validation_results["overall_status"] = "valid"
        validation_results["issues"] = []

        # Check for issues
        if not validation_results["checks"]["file_structure"]["has_sample_id"]:
            validation_results["overall_status"] = "error"
            validation_results["issues"].append("Missing sample_id column")

        if validation_results["checks"]["data_quality"]["duplicate_samples"] > 0:
            validation_results["overall_status"] = "error"
            validation_results["issues"].append("Duplicate sample IDs found")

        if validation_results["checks"]["data_quality"]["missing_percentage"] > 30:
            validation_results["overall_status"] = "warning"
            validation_results["issues"].append("High percentage of missing values")

        logger.info(
            f"Validated clinical data",
            extra={
                "file_id": file_id,
                "status": validation_results["overall_status"],
                "issues_count": len(validation_results["issues"]),
            },
        )

        return validation_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to validate clinical data",
            extra={"error": str(e), "file_id": file_id},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to validate clinical data: {str(e)}"
        )


# =============================================================================
# Data Processing Endpoints
# =============================================================================


@router.post("/process/normalize", response_model=Dict[str, Any])
async def normalize_expression_data(
    file_id: str = Query(..., description="File ID to normalize"),
    method: str = Query("quantile", description="Normalization method"),
    db: Session = Depends(get_db),
):
    """
    Normalize expression data.

    Args:
        file_id: File ID to normalize
        method: Normalization method
        db: Database session

    Returns:
        Normalization results
    """
    try:
        # Find file
        filepath = None
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                break

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        # Load data
        file_extension = os.path.splitext(filepath)[1].lower()
        if file_extension == ".csv":
            df = pd.read_csv(filepath)
        elif file_extension == ".tsv":
            df = pd.read_csv(filepath, sep="\t")
        else:
            df = pd.read_excel(filepath)

        # Quantile / z-score style normalization (extend with limma/combat as needed)

        # Mock normalization
        normalized_df = df.copy()
        numeric_columns = df.select_dtypes(include=[np.number]).columns

        if method == "quantile":
            # Mock quantile normalization
            for col in numeric_columns:
                normalized_df[col] = (df[col] - df[col].mean()) / df[col].std()
        elif method == "log2":
            # Mock log2 transformation
            for col in numeric_columns:
                normalized_df[col] = np.log2(df[col] + 1)

        # Save normalized data
        processed_file_id = str(uuid.uuid4())
        processed_filename = (
            f"{processed_file_id}_normalized_{os.path.basename(filepath)}"
        )
        processed_filepath = os.path.join(settings.PROCESSED_DIR, processed_filename)

        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        normalized_df.to_csv(processed_filepath, index=False)

        logger.info(
            f"Normalized expression data",
            extra={
                "original_file_id": file_id,
                "processed_file_id": processed_file_id,
                "method": method,
            },
        )

        return {
            "status": "success",
            "message": "Data normalized successfully",
            "original_file_id": file_id,
            "processed_file_id": processed_file_id,
            "method": method,
            "output_file": processed_filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to normalize data",
            extra={"error": str(e), "file_id": file_id, "method": method},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to normalize data: {str(e)}"
        )


@router.post("/process/quality-control", response_model=Dict[str, Any])
async def perform_quality_control(
    file_id: str = Query(..., description="File ID for QC"),
    min_variance: float = Query(0.1, description="Minimum variance threshold"),
    max_missing: float = Query(0.2, description="Maximum missing value percentage"),
    db: Session = Depends(get_db),
):
    """
    Perform quality control on expression data.

    Args:
        file_id: File ID for QC
        min_variance: Minimum variance threshold
        max_missing: Maximum missing value percentage
        db: Database session

    Returns:
        QC results
    """
    try:
        # Find file
        filepath = None
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                break

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        # Load data
        file_extension = os.path.splitext(filepath)[1].lower()
        if file_extension == ".csv":
            df = pd.read_csv(filepath)
        elif file_extension == ".tsv":
            df = pd.read_csv(filepath, sep="\t")
        else:
            df = pd.read_excel(filepath)

        # Variance + missing-rate filters (extend with per-platform QC modules as needed)

        # Mock QC filtering
        numeric_columns = df.select_dtypes(include=[np.number]).columns

        # Filter by variance
        variances = df[numeric_columns].var()
        high_variance_genes = variances[variances >= min_variance].index.tolist()

        # Filter by missing values
        missing_percentages = df[numeric_columns].isnull().sum() / len(df) * 100
        low_missing_genes = missing_percentages[
            missing_percentages <= max_missing * 100
        ].index.tolist()

        # Intersection of filters
        passed_qc_genes = list(set(high_variance_genes) & set(low_missing_genes))

        # Create filtered dataset
        qc_df = df[df.index.isin(passed_qc_genes)]

        # Save QC results
        qc_file_id = str(uuid.uuid4())
        qc_filename = f"{qc_file_id}_qc_filtered_{os.path.basename(filepath)}"
        qc_filepath = os.path.join(settings.PROCESSED_DIR, qc_filename)

        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        qc_df.to_csv(qc_filepath, index=False)

        logger.info(
            f"Performed quality control",
            extra={
                "original_file_id": file_id,
                "qc_file_id": qc_file_id,
                "original_genes": len(df),
                "passed_qc_genes": len(passed_qc_genes),
            },
        )

        return {
            "status": "success",
            "message": "Quality control completed successfully",
            "original_file_id": file_id,
            "qc_file_id": qc_file_id,
            "qc_parameters": {"min_variance": min_variance, "max_missing": max_missing},
            "qc_results": {
                "original_genes": len(df),
                "passed_qc_genes": len(passed_qc_genes),
                "filtered_genes": len(df) - len(passed_qc_genes),
                "pass_rate": round(len(passed_qc_genes) / len(df) * 100, 2),
            },
            "output_file": qc_filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to perform quality control",
            extra={"error": str(e), "file_id": file_id},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to perform quality control: {str(e)}"
        )


# =============================================================================
# Data Management Endpoints
# =============================================================================


@router.get("/files", response_model=List[Dict[str, Any]])
async def list_uploaded_files(
    data_type: Optional[str] = Query(None, description="Filter by data type"),
    limit: int = Query(50, description="Maximum number of files"),
    offset: int = Query(0, description="Number of files to skip"),
    db: Session = Depends(get_db),
):
    """
    List uploaded files.

    Args:
        data_type: Filter by data type
        limit: Maximum number of files
        offset: Number of files to skip
        db: Database session

    Returns:
        List of uploaded files
    """
    try:
        files = []
        registry = _read_upload_registry().get("files", {})

        # Scan upload directory
        if os.path.exists(settings.UPLOAD_DIR):
            for filename in os.listdir(settings.UPLOAD_DIR):
                if filename == UPLOAD_REGISTRY_FILENAME:
                    continue
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                if os.path.isfile(filepath):
                    file_id = filename.split("_")[0]
                    meta = registry.get(file_id, {})
                    file_info = {
                        "filename": filename,
                        "file_id": file_id,
                        "file_size_mb": round(
                            os.path.getsize(filepath) / (1024 * 1024), 2
                        ),
                        "upload_time": datetime.fromtimestamp(
                            os.path.getctime(filepath)
                        ).isoformat(),
                        "data_type": meta.get("data_type", "unknown"),
                    }
                    files.append(file_info)

        # Apply filters
        if data_type:
            files = [f for f in files if f["data_type"] == data_type]

        # Apply pagination
        files = files[offset : offset + limit]

        return files

    except Exception as e:
        logger.error(f"Failed to list files", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str = Path(..., description="File ID to delete"),
    db: Session = Depends(get_db),
):
    """
    Delete an uploaded file.

    Args:
        file_id: File ID to delete
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        # Find file
        filepath = None
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                break

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        # Delete file
        os.remove(filepath)

        logger.info(f"Deleted file", extra={"file_id": file_id})

        return {
            "status": "success",
            "message": "File deleted successfully",
            "file_id": file_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete file", extra={"error": str(e), "file_id": file_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str = Path(..., description="File ID to download"),
    db: Session = Depends(get_db),
):
    """
    Download an uploaded file.

    Args:
        file_id: File ID to download
        db: Database session

    Returns:
        File download
    """
    try:
        # Find file
        filepath = None
        filename = None
        for fname in os.listdir(settings.UPLOAD_DIR):
            if fname.startswith(file_id):
                filepath = os.path.join(settings.UPLOAD_DIR, fname)
                filename = fname
                break

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=filepath, filename=filename, media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to download file", extra={"error": str(e), "file_id": file_id}
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to download file: {str(e)}"
        )
