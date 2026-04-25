"""
Shared API dependencies: auth, roles, federated API keys, audit logging.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.platform_models import AuditLog, ServiceApiKey
from app.models.user_model import User
from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
security_required = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_required),
    db: Session = Depends(get_db),
) -> User:
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
    except HTTPException:
        raise
    except Exception:
        raise credentials_exception

    user = auth_service.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    if settings.MULTI_TENANT_ENFORCE and getattr(user, "tenant_id", None):
        header_tid = request.headers.get("X-Tenant-ID") or request.headers.get(
            "x-tenant-id"
        )
        if not header_tid or header_tid.strip() != str(user.tenant_id).strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="X-Tenant-ID must match the authenticated user's tenant",
            )
    return user


def require_roles(*allowed: str):
    """Require user.role to be one of allowed (admin always allowed)."""

    allowed_set = set(allowed)

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role == "admin" or user.role in allowed_set:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation",
        )

    return _dep


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(f"{settings.SECRET_KEY}:{raw}".encode()).hexdigest()


def hash_api_key_for_storage(raw: str) -> str:
    """Public alias for scripts/tests (same algorithm as verification)."""
    return _hash_api_key(raw)


def create_service_api_key(
    db: Session,
    *,
    name: str,
    scopes: Optional[list] = None,
) -> tuple[ServiceApiKey, str]:
    """
    Create a new API key. Returns (row, raw_secret) — raw_secret is shown once.
    """
    import secrets

    raw = "sk_" + secrets.token_urlsafe(32)
    prefix = raw[:12]
    row = ServiceApiKey(
        name=name,
        key_prefix=prefix,
        key_hash=_hash_api_key(raw),
        scopes=scopes or [],
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def _lookup_api_key(db: Session, raw: str) -> Optional[ServiceApiKey]:
    if not raw or len(raw) < 8:
        return None
    prefix = raw[:12]
    candidates = (
        db.query(ServiceApiKey)
        .filter(ServiceApiKey.key_prefix == prefix, ServiceApiKey.is_active == True)
        .all()
    )
    h = _hash_api_key(raw)
    for row in candidates:
        if row.key_hash == h:
            row.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return row
    return None


async def security_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        payload = auth_service.verify_token(credentials.credentials)
        if not payload or not payload.get("sub"):
            return None
        return auth_service.get_user_by_id(db, payload.get("sub"))
    except Exception:
        return None


async def federated_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(security_optional_user),
) -> Dict[str, Any]:
    """
    Returns {"user": User|None, "api_key": ServiceApiKey|None}.
    When FEDERATED_REQUIRE_API_KEY is True, one of JWT user or valid API key is required.
    """
    if user:
        return {"user": user, "api_key": None}

    raw = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if raw:
        row = _lookup_api_key(db, raw)
        if row:
            return {"user": None, "api_key": row}
        raise HTTPException(status_code=401, detail="Invalid API key")

    if getattr(settings, "FEDERATED_REQUIRE_API_KEY", False):
        raise HTTPException(
            status_code=401,
            detail="Federated endpoint requires Bearer token or X-API-Key",
        )
    return {"user": None, "api_key": None}


def log_audit(
    db: Session,
    *,
    user_id,
    action: str,
    resource: Optional[str] = None,
    detail=None,
    request: Optional[Request] = None,
):
    try:
        ip = None
        if request and request.client:
            ip = request.client.host
        row = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            detail=detail,
            ip_address=ip,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        logger.warning("audit log failed: %s", e)
        db.rollback()
