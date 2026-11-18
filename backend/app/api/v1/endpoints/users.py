"""CivicSight User CRUD Endpoints (Week 2)"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserCreate, UserUpdate, UserResponse

from app.core.security import get_password_hash
from app.core.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user/contact (Admin only)",
)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Creates a new citizen or municipal user profile (Admin only)."""
    if user_in.email:
        email_clean = user_in.email.strip().lower()
        existing = db.query(User).filter(User.email == email_clean).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email '{email_clean}' already exists.",
            )
    else:
        email_clean = None

    hashed_pwd = get_password_hash(user_in.password) if user_in.password else None

    user = User(
        name=user_in.name,
        email=email_clean,
        phone=user_in.phone,
        role=user_in.role or UserRole.CITIZEN,
        hashed_password=hashed_pwd,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users (Officer/Admin only)",
)
def list_users(
    role: Optional[str] = Query(None, description="Filter by user role (e.g. 'Maintenance Staff', 'Citizen')"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(100, ge=1, le=200, description="Max results per page"),
    current_user: User = Depends(require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves a paginated list of registered users (Officer/Admin only)."""
    query = db.query(User)
    if role:
        normalized_role = role.strip().replace("_", " ").title()
        valid_roles = {r.value for r in UserRole}
        if normalized_role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid role filter '{role}'. Allowed roles: {sorted(valid_roles)}.",
            )
        query = query.filter(User.role == normalized_role)
    users = query.offset(skip).limit(limit).all()
    return users


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (Self or Officer/Admin only)",
)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves a single user profile by its primary key ID (self or Officer/Admin only)."""
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    is_privileged = user_role in (UserRole.MUNICIPAL_OFFICER.value, UserRole.ADMIN.value)
    if not is_privileged and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You can only view your own user profile.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user details (Admin only)",
)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Updates contact information, role, or name for an existing user (Admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if user_in.email and user_in.email.strip().lower() != (user.email or "").lower():
        email_clean = user_in.email.strip().lower()
        existing = db.query(User).filter(User.email == email_clean).first()
        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email '{email_clean}' already exists.",
            )

    update_data = user_in.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].strip().lower()
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a user (Admin only)",
)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Deletes a user record from the database (Admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    db.delete(user)
    db.commit()
    return {"message": f"User {user_id} successfully deleted", "id": user_id}
