import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.auth import USERS_DB, create_access_token

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_users_db():
    """Cleans in-memory user db before each test."""
    USERS_DB.clear()
    yield
    USERS_DB.clear()

def test_health_endpoint():
    """Verify health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_user_registration_success():
    """Verify successful user registration and JWT token issuance."""
    payload = {
        "username": "alex_dev",
        "email": "alex@example.com",
        "password": "SuperSecretPassword123!"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alex_dev"

def test_user_registration_duplicate_username_fails():
    """Verify duplicate username registration returns 400."""
    payload = {
        "username": "alex_dev",
        "email": "alex@example.com",
        "password": "Password123"
    }
    client.post("/api/auth/register", json=payload)
    dup_res = client.post("/api/auth/register", json=payload)
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json()["detail"]

def test_login_success():
    """Verify valid login returns 200 and access token."""
    client.post("/api/auth/register", json={
        "username": "johndoe",
        "email": "john@test.com",
        "password": "CorrectPassword456"
    })

    login_res = client.post("/api/auth/login", json={
        "username": "johndoe",
        "password": "CorrectPassword456"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert login_res.json()["user"]["username"] == "johndoe"

def test_login_invalid_password_returns_401():
    """Verify invalid password returns 401 Unauthorized."""
    client.post("/api/auth/register", json={
        "username": "johndoe",
        "email": "john@test.com",
        "password": "CorrectPassword456"
    })

    login_res = client.post("/api/auth/login", json={
        "username": "johndoe",
        "password": "WrongPassword789"
    })
    assert login_res.status_code == 401
    assert "Invalid username or password" in login_res.json()["detail"]

def test_protected_route_access_with_valid_jwt():
    """Verify GET /api/auth/me returns user profile when Authorization Bearer token is passed."""
    reg_res = client.post("/api/auth/register", json={
        "username": "protected_user",
        "email": "protected@test.com",
        "password": "ValidPassword999"
    })
    token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "protected_user"
    assert me_res.json()["email"] == "protected@test.com"

def test_protected_route_fails_without_token():
    """Verify GET /api/auth/me returns 401/403 when Authorization header is missing."""
    response = client.get("/api/auth/me")
    assert response.status_code in (401, 403)

def test_expired_jwt_token_fails():
    """Verify expired token returns 401."""
    expired_token = create_access_token(
        data={"sub": "expired_user", "email": "expired@test.com"},
        expires_delta=timedelta(seconds=-10)
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
