"""
REST API for federated learning coordination (single-node demo server).
"""

import base64
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import federated_auth_context, log_audit
from app.core.database import get_db
from app.middleware.rate_limit import limiter
from app.services.federated_capabilities import get_federated_privacy_capabilities
from app.services.federated_learning_service import (
    FederatedConfig,
    federated_learning_service,
)

router = APIRouter()


class FederatedInitBody(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_type: str = Field(
        ...,
        description="neural_network | random_forest | logistic_regression",
    )
    participants: List[str] = Field(..., min_length=1)
    num_rounds: int = 10
    min_participants: int = 2
    learning_rate: float = 0.01
    batch_size: int = 32
    aggregation_method: str = "fedavg"
    fedprox_mu: float = 0.01
    differential_privacy: bool = False
    secure_aggregation: bool = True
    idempotency_key: Optional[str] = Field(
        None, description="If set, duplicate requests return the same round_id."
    )


class ModelUpdateBody(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    participant_id: str
    model_weights: Dict[str, Any]
    num_samples: int = Field(..., gt=0)
    loss: float = 0.0
    accuracy: float = 0.0
    meta_data: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional. use_ring_masked (with FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED); "
            "use_bonawitz_mask (with FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED), alongside Fernet."
        ),
    )


@router.get("/health")
@limiter.limit("200/minute")
async def federated_health(request: Request):
    del request
    return {"status": "ok", "service": "federated_learning"}


@router.get("/capabilities")
@limiter.limit("120/minute")
async def federated_capabilities(request: Request):
    """Privacy and aggregation capabilities (honest about crypto secure agg status)."""
    del request
    return get_federated_privacy_capabilities()


@router.get("/status")
@limiter.limit("120/minute")
async def federated_status(
    request: Request,
    _auth: Dict[str, Any] = Depends(federated_auth_context),
):
    del request
    try:
        return await federated_learning_service.get_federated_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
@limiter.limit("30/minute")
async def federated_initialize(
    request: Request,
    body: FederatedInitBody,
    auth: Dict[str, Any] = Depends(federated_auth_context),
    db: Session = Depends(get_db),
):
    cfg = FederatedConfig(
        num_rounds=body.num_rounds,
        num_participants=len(body.participants),
        min_participants=body.min_participants,
        learning_rate=body.learning_rate,
        batch_size=body.batch_size,
        aggregation_method=body.aggregation_method,
        fedprox_mu=body.fedprox_mu,
        differential_privacy=body.differential_privacy,
        secure_aggregation=body.secure_aggregation,
    )
    try:
        out = await federated_learning_service.initialize_federated_training(
            model_type=body.model_type,
            config=cfg,
            participants=body.participants,
            idempotency_key=body.idempotency_key,
        )
        uid = auth.get("user").id if auth.get("user") else None
        log_audit(
            db,
            user_id=uid,
            action="federated_initialize",
            resource=out.get("round_id"),
            detail={"idempotent": out.get("idempotent")},
            request=request,
        )
        try:
            from app.observability.metrics import FEDERATED_ROUNDS

            FEDERATED_ROUNDS.labels(phase="init").inc()
        except Exception:
            pass
        return jsonable_encoder(out)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rounds/{round_id}/updates")
@limiter.limit("120/minute")
async def federated_submit_update(
    request: Request,
    round_id: str,
    body: ModelUpdateBody,
    auth: Dict[str, Any] = Depends(federated_auth_context),
    db: Session = Depends(get_db),
):
    try:
        out = await federated_learning_service.submit_model_update(
            participant_id=body.participant_id,
            model_weights=body.model_weights,
            num_samples=body.num_samples,
            loss=body.loss,
            accuracy=body.accuracy,
            round_id=round_id,
            meta_data=body.meta_data,
        )
        uid = auth.get("user").id if auth.get("user") else None
        log_audit(
            db,
            user_id=uid,
            action="federated_submit_update",
            resource=round_id,
            detail={"participant": body.participant_id},
            request=request,
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rounds/{round_id}/aggregate")
@limiter.limit("60/minute")
async def federated_aggregate(
    request: Request,
    round_id: str,
    auth: Dict[str, Any] = Depends(federated_auth_context),
    db: Session = Depends(get_db),
):
    try:
        result = await federated_learning_service.aggregate_models(round_id)
        uid = auth.get("user").id if auth.get("user") else None
        log_audit(
            db,
            user_id=uid,
            action="federated_aggregate",
            resource=round_id,
            detail={},
            request=request,
        )
        return jsonable_encoder(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rounds/{round_id}/global-model")
@limiter.limit("90/minute")
async def federated_get_global_model(
    request: Request,
    round_id: str,
    participant_id: str,
    _auth: Dict[str, Any] = Depends(federated_auth_context),
):
    del request
    del round_id
    try:
        payload = await federated_learning_service.get_global_model(participant_id)
        enc = payload.get("model_weights")
        if isinstance(enc, bytes):
            payload["model_weights_b64"] = base64.b64encode(enc).decode("ascii")
            del payload["model_weights"]
        return payload
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
