"""CivicSight User CRUD Endpoints (Week 2)"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserCreate, UserUpdate, UserResponse

from app.core.security import get_password_hash

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user/contact",
)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """Creates a new citizen or municipal user profile."""
    if user_in.email:
        existing = db.query(User).filter(User.email == user_in.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email '{user_in.email}' already exists.",
            )

    hashed_pwd = get_password_hash(user_in.password) if user_in.password else None

    user = User(
        name=user_in.name,
        email=user_in.email,
        phone=user_in.phone,
        role=user_in.role or "Citizen",
        hashed_password=hashed_pwd,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users",
)
def list_users(
    role: Optional[str] = Query(None, description="Filter by user role (e.g. 'Maintenance Staff', 'Citizen')"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(1000, ge=1, le=1000, description="Max results per page"),
    db: Session = Depends(get_db),
):
    """Retrieves a paginated list of registered users."""
    query = db.query(User)
    if role:
        # Match enum or case-insensitive name
        normalized_role = role.strip().replace("_", " ").title()
        query = query.filter(User.role == normalized_role)
    users = query.offset(skip).limit(limit).all()
    return users


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Retrieves a single user profile by its primary key ID."""
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
    summary="Update user details",
)
def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)):
    """Updates contact information or name for an existing user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    # Check unique email conflict if changing email
    if user_in.email and user_in.email != user.email:
        existing = db.query(User).filter(User.email == user_in.email).first()
        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email '{user_in.email}' already exists.",
            )

    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a user",
)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Deletes a user record from the database."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    db.delete(user)
    db.commit()
    return {"message": f"User {user_id} successfully deleted", "id": user_id}
