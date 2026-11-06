from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.schemas.auth import LoginRequest, TokenResponse, AdminResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Admin login endpoint."""
    admin = db.query(AdminUser).filter(AdminUser.email == request.email).first()
    if not admin or not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated",
        )

    access_token = create_access_token(data={"sub": admin.email, "id": admin.id})
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=AdminResponse)
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    """Return currently logged-in admin details."""
    return current_admin

