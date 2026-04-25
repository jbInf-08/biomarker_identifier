"""
Authentication and user management API routes.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.middleware.rate_limit import limiter
from app.models.user_model import User, UserSession
from app.services.auth_service import auth_service
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["authentication"])

# Security
security = HTTPBearer()


# Pydantic models
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    institution: Optional[str] = None
    role: str = "researcher"
    tenant_id: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    institution: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


# Dependency to get current user
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user; optional tenant header enforcement."""
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
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

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


# Authentication endpoints
@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate, request: Request, db: Session = Depends(get_db)
):
    """Register a new user."""
    try:
        # Create user
        user = auth_service.create_user(
            db=db,
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
            institution=user_data.institution,
            role=user_data.role,
            tenant_id=user_data.tenant_id,
        )

        # Log activity
        auth_service.log_user_activity(
            db=db,
            user_id=str(user.id),
            activity_type="user_registered",
            description="User registered successfully",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(f"User registered: {user.email}")
        return UserResponse(**user.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=Token)
@limiter.limit("15/minute")
async def login_user(
    user_credentials: UserLogin, request: Request, db: Session = Depends(get_db)
):
    """Authenticate user and return access token."""
    try:
        # Authenticate user
        user = auth_service.authenticate_user(
            db=db, email=user_credentials.email, password=user_credentials.password
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Persist last_login with a single UPDATE (avoids SQLite + UUID ORM stale-row issues)
        uid = user.id
        db.execute(
            update(User)
            .where(User.id == uid)
            .values(last_login=datetime.utcnow())
        )
        db.commit()
        user = db.get(User, uid)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login state error",
            )

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
        }
        if getattr(user, "tenant_id", None):
            token_data["tid"] = user.tenant_id
        access_token = auth_service.create_access_token(
            data=token_data,
            expires_delta=access_token_expires,
        )

        # Create session
        auth_service.create_session(
            db=db,
            user_id=str(user.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )

        # Log activity
        auth_service.log_user_activity(
            db=db,
            user_id=str(user.id),
            activity_type="user_login",
            description="User logged in successfully",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )

        # create_session / log_user_activity commit — reload user for response payload
        user_out = db.get(User, uid)
        if user_out is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login state error",
            )
        logger.info(f"User logged in: {user_out.email}")
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_out.to_dict(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Logout user and invalidate session."""
    try:
        # Invalidate all user sessions
        auth_service.invalidate_all_user_sessions(db=db, user_id=str(current_user.id))

        # Log activity
        auth_service.log_user_activity(
            db=db,
            user_id=str(current_user.id),
            activity_type="user_logout",
            description="User logged out successfully",
        )

        logger.info(f"User logged out: {current_user.email}")
        return {"message": "Successfully logged out"}

    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(**current_user.to_dict())


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user information."""
    try:
        # Update user
        updated_user = auth_service.update_user(
            db=db, user_id=str(current_user.id), **user_update.dict(exclude_unset=True)
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Log activity
        auth_service.log_user_activity(
            db=db,
            user_id=str(current_user.id),
            activity_type="user_updated",
            description="User profile updated",
        )

        logger.info(f"User updated: {updated_user.email}")
        return UserResponse(**updated_user.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed",
        )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change user password."""
    try:
        # Change password
        success = auth_service.change_password(
            db=db,
            user_id=str(current_user.id),
            old_password=password_data.old_password,
            new_password=password_data.new_password,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid old password"
            )

        # Log activity
        auth_service.log_user_activity(
            db=db,
            user_id=str(current_user.id),
            activity_type="password_changed",
            description="User password changed",
        )

        logger.info(f"Password changed for user: {current_user.email}")
        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed",
        )


@router.get("/activities")
async def get_user_activities(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user activity history."""
    try:
        activities = auth_service.get_user_activities(
            db=db, user_id=str(current_user.id), limit=limit
        )

        return {
            "activities": [activity.to_dict() for activity in activities],
            "total": len(activities),
        }

    except Exception as e:
        logger.error(f"Failed to get user activities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user activities",
        )


@router.post("/verify-token")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify if a token is valid."""
    try:
        payload = auth_service.verify_token(credentials.credentials)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        return {"valid": True, "payload": payload}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed",
        )


# Admin endpoints (require admin role)
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all users (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        users = db.query(User).offset(skip).limit(limit).all()
        return [UserResponse(**user.to_dict()) for user in users]

    except Exception as e:
        logger.error(f"Failed to get users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users",
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        updated_user = auth_service.update_user(
            db=db, user_id=user_id, **user_update.dict(exclude_unset=True)
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        logger.info(f"Admin updated user: {updated_user.email}")
        return UserResponse(**updated_user.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed",
        )
