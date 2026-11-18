"""CivicSight Authentication & Authorization Endpoints (Week 3)

Provides user registration, login credential verification, JWT token issuance,
authenticated profile lookup, and role-gated authorization proof-of-concept.
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserRegister, UserLogin, UserResponse, Token
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.dependencies import get_current_user, require_roles
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Pre-computed dummy bcrypt hash used to equalize login response time for nonexistent users
_DUMMY_BCRYPT_HASH = get_password_hash("civicsight-timing-equalizer-placeholder")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen account",
)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Registers a new public Citizen user account.

    - Strictly enforces Citizen role on public registration (prevents privilege escalation).
    - Validates email and password requirements independently of frontend.
    - Ensures email uniqueness.
    - Hashes password securely via bcrypt.
    """
    # Block privilege escalation attempts via public registration
    if user_in.role is not None and user_in.role != UserRole.CITIZEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is restricted to Citizen accounts. Privileged roles must be provisioned by an Administrator.",
        )

    # Normalize email
    email_clean = user_in.email.strip().lower()

    # Duplicate check
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{email_clean}' already exists.",
        )

    # Hash the password
    hashed_pwd = get_password_hash(user_in.password)

    # Always force Citizen role for public registration
    new_user = User(
        name=user_in.name.strip(),
        email=email_clean,
        phone=user_in.phone.strip() if user_in.phone else None,
        hashed_password=hashed_pwd,
        role=UserRole.CITIZEN,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT token",
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticates user credentials and returns a signed JWT access token.

    Handles invalid credentials uniformly with timing equalization so nonexistent emails
    and wrong passwords return identical errors in similar time. Rejects inactive accounts.
    """
    email_clean = credentials.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    # Always execute bcrypt comparison to equalize response timing
    target_hash = user.hashed_password if (user and user.hashed_password) else _DUMMY_BCRYPT_HASH
    password_valid = verify_password(credentials.password, target_hash)

    if not user or not user.hashed_password or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deactivated.",
        )

    # Generate access token
    role_val = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    token_claims = {
        "email": user.email,
        "role": role_val,
        "name": user.name,
    }
    access_token = create_access_token(
        subject=user.id,
        claims=token_claims,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns profile information for the currently authenticated bearer token."""
    return current_user


@router.get(
    "/protected-role-example",
    summary="Example role-gated endpoint proving authorization",
)
def protected_role_example(
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.MUNICIPAL_OFFICER)
    ),
):
    """Proves the role-check mechanism works.

    Accessible strictly by 'Admin' and 'Municipal Officer' roles. Returns 403 Forbidden for 'Citizen' or 'Maintenance Staff'.
    """
    role_val = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    return {
        "status": "authorized",
        "message": f"Authorization verified for privileged role: {role_val}",
        "user_id": current_user.id,
        "name": current_user.name,
        "role": role_val,
    }
