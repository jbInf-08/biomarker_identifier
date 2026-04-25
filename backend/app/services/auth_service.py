"""
Authentication service for user management and JWT token handling.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user_model import User, UserActivity, UserSession

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication and user management."""

    def __init__(self):
        """Initialize authentication service."""
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            # Ensure password is bytes and within 72-byte limit
            if isinstance(plain_password, str):
                password_bytes = plain_password.encode("utf-8")
                if len(password_bytes) > 72:
                    password_bytes = password_bytes[:72]
            else:
                password_bytes = (
                    plain_password[:72] if len(plain_password) > 72 else plain_password
                )

            # Ensure hash is bytes
            if isinstance(hashed_password, str):
                hash_bytes = hashed_password.encode("utf-8")
            else:
                hash_bytes = hashed_password

            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception as e:
            logger.warning(f"Password verification failed: {str(e)}")
            return False

    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        # Bcrypt has a 72-byte limit, truncate if necessary
        if isinstance(password, str):
            password_bytes = password.encode("utf-8")
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
        else:
            password_bytes = password[:72] if len(password) > 72 else password

        # Generate salt and hash
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.access_token_expire_minutes
            )

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            return None

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email address."""
        return db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        """Get user by ID."""
        import uuid

        # Convert user_id string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                return None
        else:
            user_id_uuid = user_id

        return db.query(User).filter(User.id == user_id_uuid).first()

    def authenticate_user(
        self, db: Session, email: str, password: str
    ) -> Optional[User]:
        """Authenticate a user with email and password."""
        user = self.get_user_by_email(db, email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    def create_user(
        self,
        db: Session,
        email: str,
        password: str,
        name: str,
        institution: Optional[str] = None,
        role: str = "researcher",
        tenant_id: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        # Check if user already exists
        existing_user = self.get_user_by_email(db, email)
        if existing_user:
            raise ValueError("User with this email already exists")

        # Create new user
        hashed_password = self.get_password_hash(password)
        user = User(
            email=email,
            name=name,
            hashed_password=hashed_password,
            institution=institution,
            role=role,
            tenant_id=tenant_id,
            is_active=True,
            is_verified=False,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"Created new user: {email}")
        return user

    def update_user(self, db: Session, user_id: str, **kwargs) -> Optional[User]:
        """Update user information."""
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        # Update allowed fields
        allowed_fields = [
            "name",
            "institution",
            "role",
            "is_active",
            "is_verified",
            "preferences",
        ]
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(user, field):
                setattr(user, field, value)

        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        logger.info(f"Updated user: {user.email}")
        return user

    def change_password(
        self, db: Session, user_id: str, old_password: str, new_password: str
    ) -> bool:
        """Change user password."""
        user = self.get_user_by_id(db, user_id)
        if not user:
            return False

        # Verify old password
        if not self.verify_password(old_password, user.hashed_password):
            return False

        # Update password
        user.hashed_password = self.get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Password changed for user: {user.email}")
        return True

    def create_session(
        self,
        db: Session,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        """Create a new user session."""
        import secrets
        import uuid

        # Convert user_id string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                raise ValueError(f"Invalid user_id format: {user_id}")
        else:
            user_id_uuid = user_id

        # Generate session token
        session_token = secrets.token_urlsafe(32)

        # Create session
        session = UserSession(
            user_id=user_id_uuid,
            session_token=session_token,
            expires_at=datetime.utcnow() + timedelta(days=30),  # 30 days
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        logger.info(f"Created session for user: {user_id}")
        return session

    def get_session(self, db: Session, session_token: str) -> Optional[UserSession]:
        """Get user session by token."""
        return (
            db.query(UserSession)
            .filter(
                and_(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow(),
                )
            )
            .first()
        )

    def invalidate_session(self, db: Session, session_token: str) -> bool:
        """Invalidate a user session."""
        session = (
            db.query(UserSession)
            .filter(UserSession.session_token == session_token)
            .first()
        )
        if not session:
            return False

        session.is_active = False
        db.commit()

        logger.info(f"Invalidated session: {session_token}")
        return True

    def invalidate_all_user_sessions(self, db: Session, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        import uuid

        # Convert user_id string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                raise ValueError(f"Invalid user_id format: {user_id}")
        else:
            user_id_uuid = user_id

        sessions = (
            db.query(UserSession)
            .filter(
                and_(UserSession.user_id == user_id_uuid, UserSession.is_active == True)
            )
            .all()
        )

        count = 0
        for session in sessions:
            session.is_active = False
            count += 1

        db.commit()

        logger.info(f"Invalidated {count} sessions for user: {user_id}")
        return count

    def log_user_activity(
        self,
        db: Session,
        user_id: str,
        activity_type: str,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserActivity:
        """Log user activity."""
        import json
        import uuid

        # Convert user_id string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                raise ValueError(f"Invalid user_id format: {user_id}")
        else:
            user_id_uuid = user_id

        activity = UserActivity(
            user_id=user_id_uuid,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            meta_data=json.dumps(metadata) if metadata else None,
        )

        db.add(activity)
        db.commit()
        db.refresh(activity)

        return activity

    def get_user_activities(self, db: Session, user_id: str, limit: int = 100) -> list:
        """Get user activities."""
        import uuid

        # Convert user_id string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                raise ValueError(f"Invalid user_id format: {user_id}")
        else:
            user_id_uuid = user_id

        return (
            db.query(UserActivity)
            .filter(UserActivity.user_id == user_id_uuid)
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
            .all()
        )

    def cleanup_expired_sessions(self, db: Session) -> int:
        """Clean up expired sessions."""
        expired_sessions = (
            db.query(UserSession)
            .filter(UserSession.expires_at < datetime.utcnow())
            .all()
        )

        count = 0
        for session in expired_sessions:
            session.is_active = False
            count += 1

        db.commit()

        logger.info(f"Cleaned up {count} expired sessions")
        return count


# Global auth service instance
auth_service = AuthService()
