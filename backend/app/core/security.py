"""CivicSight Security & Cryptographic Utilities (Week 3)

Handles password hashing/verification using direct bcrypt and JWT token generation/decoding.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
import bcrypt
import jwt
from app.core.config import settings


def get_password_hash(password: str) -> str:
    """Generates a secure bcrypt hash for a plaintext password."""
    # Truncate to 72 bytes if needed to satisfy bcrypt maximum input size
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any],
    claims: Optional[dict] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a signed JWT access token encoding the subject (user_id/email) and extra claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        to_encode.update(claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a signed JWT access token. Returns None if invalid or expired."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None
