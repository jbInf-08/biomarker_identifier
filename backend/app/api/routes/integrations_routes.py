"""
Third-party integrations: webhooks and future connectors.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, HttpUrl
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.middleware.rate_limit import limiter
from app.models.platform_models import WebhookSubscription
from app.models.user_model import User

router = APIRouter()


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: List[str] = ["run.completed", "run.failed"]
    secret: Optional[str] = None


class WebhookRead(BaseModel):
    id: str
    url: str
    events: Optional[List[str]]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/webhooks", response_model=List[WebhookRead])
@limiter.limit("60/minute")
async def list_webhooks(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del request
    rows = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.user_id == user.id)
        .order_by(WebhookSubscription.created_at.desc())
        .all()
    )
    return rows


@router.post("/webhooks", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_webhook(
    request: Request,
    body: WebhookCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del request
    row = WebhookSubscription(
        user_id=user.id,
        url=str(body.url),
        secret=body.secret,
        events=body.events,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_webhook(
    request: Request,
    webhook_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del request
    row = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.user_id == user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(row)
    db.commit()
    return None


@router.post("/webhooks/{webhook_id}/test", response_model=Dict[str, Any])
@limiter.limit("10/minute")
async def test_webhook(
    request: Request,
    webhook_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Queue a no-op test ping (delivery wiring can extend Celery)."""
    del request
    row = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.user_id == user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {
        "status": "accepted",
        "webhook_id": row.id,
        "url": row.url,
        "message": "Test dispatch accepted; connect Celery to POST payloads for production.",
    }
