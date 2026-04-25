"""
Integration tests for authentication API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


class TestAuthAPI:
    """Test cases for authentication API endpoints."""

    def test_register_user_success(self, client: TestClient):
        """Test successful user registration."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "testpassword123",
            "institution": "Test Institution",
            "role": "researcher",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == user_data["email"]
        assert data["name"] == user_data["name"]
        assert data["institution"] == user_data["institution"]
        assert data["role"] == user_data["role"]
        assert data["is_active"] is True
        assert data["is_verified"] is False
        assert "id" in data
        assert "created_at" in data

    def test_register_user_duplicate_email(self, client: TestClient, test_user):
        """Test user registration with duplicate email."""
        user_data = {
            "name": "Another User",
            "email": test_user.email,  # Same email as existing user
            "password": "testpassword123",
            "institution": "Another Institution",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_register_user_invalid_email(self, client: TestClient):
        """Test user registration with invalid email."""
        user_data = {
            "name": "Test User",
            "email": "invalid-email",
            "password": "testpassword123",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_missing_fields(self, client: TestClient):
        """Test user registration with missing required fields."""
        user_data = {
            "name": "Test User"
            # Missing email and password
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_login_success(self, client: TestClient, test_user):
        """Test successful user login."""
        login_data = {"email": test_user.email, "password": "testpassword"}

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "user" in data

        user_data = data["user"]
        assert user_data["email"] == test_user.email
        assert user_data["name"] == test_user.name
        assert user_data["id"] == str(test_user.id)

    def test_login_invalid_credentials(self, client: TestClient, test_user):
        """Test login with invalid credentials."""
        login_data = {"email": test_user.email, "password": "wrongpassword"}

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user."""
        login_data = {"email": "nonexistent@example.com", "password": "testpassword"}

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_get_current_user_success(self, client: TestClient, auth_headers):
        """Test getting current user information."""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert "email" in data
        assert "name" in data
        assert "role" in data
        assert "is_active" in data
        assert "created_at" in data

    def test_get_current_user_unauthorized(self, client: TestClient):
        """Test getting current user without authentication."""
        response = client.get("/api/auth/me")

        assert response.status_code == 403  # No authorization header

    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

    def test_update_current_user_success(self, client: TestClient, auth_headers):
        """Test updating current user information."""
        update_data = {"name": "Updated Name", "institution": "Updated Institution"}

        response = client.put("/api/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == update_data["name"]
        assert data["institution"] == update_data["institution"]

    def test_update_current_user_unauthorized(self, client: TestClient):
        """Test updating current user without authentication."""
        update_data = {"name": "Updated Name"}

        response = client.put("/api/auth/me", json=update_data)

        assert response.status_code == 403

    def test_change_password_success(self, client: TestClient, auth_headers):
        """Test successful password change."""
        password_data = {
            "old_password": "testpassword",
            "new_password": "newpassword123",
        }

        response = client.post(
            "/api/auth/change-password", json=password_data, headers=auth_headers
        )

        assert response.status_code == 200
        assert "Password changed successfully" in response.json()["message"]

    def test_change_password_wrong_old_password(self, client: TestClient, auth_headers):
        """Test password change with wrong old password."""
        password_data = {
            "old_password": "wrongpassword",
            "new_password": "newpassword123",
        }

        response = client.post(
            "/api/auth/change-password", json=password_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid old password" in response.json()["detail"]

    def test_change_password_unauthorized(self, client: TestClient):
        """Test password change without authentication."""
        password_data = {
            "old_password": "testpassword",
            "new_password": "newpassword123",
        }

        response = client.post("/api/auth/change-password", json=password_data)

        assert response.status_code == 403

    def test_logout_success(self, client: TestClient, auth_headers):
        """Test successful user logout."""
        response = client.post("/api/auth/logout", headers=auth_headers)

        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]

    def test_logout_unauthorized(self, client: TestClient):
        """Test logout without authentication."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 403

    def test_verify_token_success(self, client: TestClient, auth_headers):
        """Test token verification."""
        # Extract token from headers
        token = auth_headers["Authorization"].split(" ")[1]

        response = client.post(
            "/api/auth/verify-token", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert "payload" in data
        assert "sub" in data["payload"]
        assert "exp" in data["payload"]

    def test_verify_token_invalid(self, client: TestClient):
        """Test token verification with invalid token."""
        response = client.post(
            "/api/auth/verify-token", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_get_user_activities(self, client: TestClient, auth_headers):
        """Test getting user activities."""
        response = client.get("/api/auth/activities", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "activities" in data
        assert "total" in data
        assert isinstance(data["activities"], list)
        assert isinstance(data["total"], int)

    def test_get_user_activities_unauthorized(self, client: TestClient):
        """Test getting user activities without authentication."""
        response = client.get("/api/auth/activities")

        assert response.status_code == 403

    def test_get_all_users_admin(self, client: TestClient, admin_headers):
        """Test getting all users as admin."""
        response = client.get("/api/auth/users", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        if len(data) > 0:
            user = data[0]
            assert "id" in user
            assert "email" in user
            assert "name" in user
            assert "role" in user

    def test_get_all_users_non_admin(self, client: TestClient, auth_headers):
        """Test getting all users as non-admin."""
        response = client.get("/api/auth/users", headers=auth_headers)

        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]

    def test_update_user_admin(self, client: TestClient, admin_headers, test_user):
        """Test updating user as admin."""
        update_data = {"name": "Admin Updated Name", "role": "admin"}

        response = client.put(
            f"/api/auth/users/{test_user.id}", json=update_data, headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == update_data["name"]
        assert data["role"] == update_data["role"]

    def test_update_user_non_admin(self, client: TestClient, auth_headers, test_user):
        """Test updating user as non-admin."""
        update_data = {"name": "Updated Name"}

        response = client.put(
            f"/api/auth/users/{test_user.id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]

    def test_update_nonexistent_user(self, client: TestClient, admin_headers):
        """Test updating non-existent user."""
        update_data = {"name": "Updated Name"}

        response = client.put(
            "/api/auth/users/nonexistent-id", json=update_data, headers=admin_headers
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
