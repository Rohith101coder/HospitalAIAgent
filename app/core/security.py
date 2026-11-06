import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt, JWTError
import bcrypt
from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a JWT token for authentication."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_secure_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    digits = [str(secrets.randbelow(10)) for _ in range(length)]
    return "".join(digits)


def hash_otp(otp: str) -> str:
    """Hash an OTP using SHA-256 for secure DB storage."""
    # Salt using the JWT secret to prevent rainbow table attacks on 6-digit space
    salted = f"{settings.JWT_SECRET}:{otp}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def verify_otp_hash(plain_otp: str, stored_hash: str) -> bool:
    """Verify submitted OTP against stored hash using constant-time comparison."""
    calculated_hash = hash_otp(plain_otp)
    return secrets.compare_digest(calculated_hash, stored_hash)

