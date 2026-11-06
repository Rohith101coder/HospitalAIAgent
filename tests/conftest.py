import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.admin import AdminUser
from app.core.security import hash_password, create_access_token


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def admin_token():
    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.email == settings.ADMIN_EMAIL).first()
        if not admin:
            admin = AdminUser(
                name="Test Super Admin",
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return create_access_token(data={"sub": admin.email, "id": admin.id})
    finally:
        db.close()


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
