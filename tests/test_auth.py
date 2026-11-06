from app.core.config import settings


def test_login_success(client):
    response = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    response = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": "WrongPassword!"}
    )
    assert response.status_code == 401


def test_get_current_admin(client, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == settings.ADMIN_EMAIL
    assert data["is_active"] is True


def test_get_current_admin_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401

