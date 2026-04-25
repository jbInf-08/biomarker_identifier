"""
Unit tests for the authentication service.
"""
from datetime import datetime, timedelta

import pytest

from app.models.user_model import User
from app.services.auth_service import auth_service


class TestAuthService:
    """Test cases for AuthService."""

    def test_verify_password(self):
        """Test password verification."""
        password = "testpassword"
        hashed = auth_service.get_password_hash(password)

        assert auth_service.verify_password(password, hashed) is True
        assert auth_service.verify_password("wrongpassword", hashed) is False

    def test_get_password_hash(self):
        """Test password hashing."""
        password = "testpassword"
        hashed = auth_service.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        # bcrypt format can be $2b$, $2a$, or $2y$
        assert hashed.startswith(("$2b$", "$2a$", "$2y$"))

    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = auth_service.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"

    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "user123"}
        expires_delta = timedelta(minutes=5)
        token = auth_service.create_access_token(data, expires_delta)

        payload = auth_service.verify_token(token)
        assert payload is not None

        # Check expiry is approximately 5 minutes from now
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_time = datetime.utcnow() + timedelta(minutes=5)
        time_diff = abs((exp_time - expected_time).total_seconds())
        assert time_diff < 120  # Within 2 minutes (more lenient for test timing)

    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        invalid_token = "invalid.token.here"
        payload = auth_service.verify_token(invalid_token)

        assert payload is None

    def test_verify_token_expired(self):
        """Test token verification with expired token."""
        data = {"sub": "user123"}
        expires_delta = timedelta(seconds=-1)  # Expired
        token = auth_service.create_access_token(data, expires_delta)

        payload = auth_service.verify_token(token)
        assert payload is None

    def test_get_user_by_email(self, db_session):
        """Test getting user by email."""
        # Create a real user in the database
        user = User(
            email="testemail@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test getting the user
        result = auth_service.get_user_by_email(db_session, "testemail@example.com")

        assert result is not None
        assert result.email == "testemail@example.com"
        assert result.name == "Test User"

    def test_get_user_by_email_not_found(self, db_session):
        """Test getting user by email when not found."""
        result = auth_service.get_user_by_email(db_session, "nonexistent@example.com")

        assert result is None

    def test_get_user_by_id(self, db_session):
        """Test getting user by ID."""
        # Create a real user in the database
        user = User(
            email="testid@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test getting the user by ID
        result = auth_service.get_user_by_id(db_session, str(user.id))

        assert result is not None
        assert result.id == user.id
        assert result.email == "testid@example.com"

    def test_authenticate_user_success(self, db_session):
        """Test successful user authentication."""
        # Create a real user in the database
        user = User(
            email="authsuccess@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test authentication
        result = auth_service.authenticate_user(
            db_session, "authsuccess@example.com", "testpassword"
        )

        assert result is not None
        assert result.email == "authsuccess@example.com"

    def test_authenticate_user_wrong_password(self, db_session):
        """Test user authentication with wrong password."""
        # Create a real user in the database
        user = User(
            email="wrongpass@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test authentication with wrong password
        result = auth_service.authenticate_user(
            db_session, "wrongpass@example.com", "wrongpassword"
        )

        assert result is None

    def test_authenticate_user_inactive(self, db_session):
        """Test user authentication with inactive user."""
        # Create an inactive user in the database
        user = User(
            email="inactive@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
            is_active=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test authentication
        result = auth_service.authenticate_user(
            db_session, "inactive@example.com", "testpassword"
        )

        assert result is None

    def test_authenticate_user_not_found(self, db_session):
        """Test user authentication with non-existent user."""
        result = auth_service.authenticate_user(
            db_session, "nonexistent@example.com", "testpassword"
        )

        assert result is None

    def test_create_user_success(self, db_session):
        """Test successful user creation."""
        user = auth_service.create_user(
            db_session,
            "newuser@example.com",
            "testpassword",
            "New User",
            "Test Institution",
            "researcher",
        )

        assert isinstance(user, User)
        assert user.email == "newuser@example.com"
        assert user.name == "New User"
        assert user.institution == "Test Institution"
        assert user.role == "researcher"
        assert user.is_active is True
        assert user.is_verified is False

        # Verify user was saved to database
        db_user = (
            db_session.query(User).filter(User.email == "newuser@example.com").first()
        )
        assert db_user is not None
        assert db_user.email == "newuser@example.com"

    def test_create_user_already_exists(self, db_session):
        """Test user creation when user already exists."""
        # Create a user first
        user = User(
            email="existing@example.com",
            name="Existing User",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
        )
        db_session.add(user)
        db_session.commit()

        # Try to create the same user again
        with pytest.raises(ValueError, match="User with this email already exists"):
            auth_service.create_user(
                db_session, "existing@example.com", "testpassword", "Test User"
            )

    def test_update_user_success(self, db_session):
        """Test successful user update."""
        # Create a real user in the database
        user = User(
            email="update@example.com",
            name="Original Name",
            hashed_password=auth_service.get_password_hash("testpassword"),
            role="researcher",
            institution="Original Institution",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Update the user
        result = auth_service.update_user(
            db_session,
            str(user.id),
            name="Updated Name",
            institution="Updated Institution",
        )

        assert result is not None
        assert result.name == "Updated Name"
        assert result.institution == "Updated Institution"

        # Verify changes were saved
        db_session.refresh(user)
        assert user.name == "Updated Name"
        assert user.institution == "Updated Institution"

    def test_update_user_not_found(self, db_session):
        """Test user update when user not found."""
        import uuid

        fake_id = str(uuid.uuid4())

        result = auth_service.update_user(db_session, fake_id, name="New Name")

        assert result is None

    def test_change_password_success(self, db_session):
        """Test successful password change."""
        # Create a real user in the database
        user = User(
            email="changepass@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("oldpassword"),
            role="researcher",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        old_hash = user.hashed_password

        # Change password
        result = auth_service.change_password(
            db_session, str(user.id), "oldpassword", "newpassword"
        )

        assert result is True

        # Verify password was changed
        db_session.refresh(user)
        assert user.hashed_password != old_hash
        assert auth_service.verify_password("newpassword", user.hashed_password)

    def test_change_password_wrong_old_password(self, db_session):
        """Test password change with wrong old password."""
        # Create a real user in the database
        user = User(
            email="wrongoldpass@example.com",
            name="Test User",
            hashed_password=auth_service.get_password_hash("oldpassword"),
            role="researcher",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        old_hash = user.hashed_password

        # Try to change password with wrong old password
        result = auth_service.change_password(
            db_session, str(user.id), "wrongpassword", "newpassword"
        )

        assert result is False

        # Verify password was NOT changed
        db_session.refresh(user)
        assert user.hashed_password == old_hash

    def test_change_password_user_not_found(self, db_session):
        """Test password change when user not found."""
        import uuid

        fake_id = str(uuid.uuid4())

        result = auth_service.change_password(
            db_session, fake_id, "oldpassword", "newpassword"
        )

        assert result is False
