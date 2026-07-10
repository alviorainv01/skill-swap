```python
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from database import get_db
from models import User, Skill, UserSkill, SwapRequest, Review
from schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    SkillCreate,
    SkillResponse,
    UserSkillCreate,
    UserSkillResponse,
    SwapRequestCreate,
    SwapRequestResponse,
    SwapRequestUpdate,
    ReviewCreate,
    ReviewResponse,
    MatchResponse,
)
from auth import get_current_user, get_password_hash
from matching import calculate_match_score, find_matches

router = APIRouter()


# User endpoints
@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user on the platform.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        bio=user.bio,
        location=user.location,
        timezone=user.timezone,
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@router.get("/users/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieve the authenticated user's profile.
    """
    return current_user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a user's public profile by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/users/me", response_model=UserResponse)
def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the authenticated user's profile information.
    """
    update_data = user_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


# Skill endpoints
@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(
    skill: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new skill category. Admin function or could be open to all users.
    """
    # Check if skill already exists
    existing_skill = db.query(Skill).filter(
        func.lower(Skill.name) == skill.name.lower()
    ).first()
    
    if existing_skill:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill already exists"
        )
    
    db_skill = Skill(
        name=skill.name,
        category=skill.category,
        description=skill.description
    )
    
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)
    
    return db_skill


@router.get("/skills", response_model=List[SkillResponse])
def list_skills(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all available skills with optional filtering.
    """
    query = db.query(Skill)
    
    if category:
        query = query.filter(Skill.category == category)
    
    if search:
        query = query.filter(Skill.name.ilike(f"%{search}%"))
    
    skills = query.offset(skip).limit(limit).all()
    return skills


# User Skills endpoints
@router.post("/users/me/skills", response_model=UserSkillResponse, status_code=status.HTTP_201_CREATED)
def add_user_skill(
    user_skill: UserSkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a skill to the current user's profile with proficiency level and type (offer/want).
    """
    # Verify skill exists
    skill = db.query(Skill).filter(Skill.id == user_skill.skill_id).first()
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )
    
    # Check if user already has this skill with same type
    existing = db.query(UserSkill).filter(
        and_(
            UserSkill.user_id == current_user.id,
            UserSkill.skill_id == user_skill.skill_id,
            UserSkill.skill_type == user_skill.skill_type
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have this skill marked as '{user_skill.skill_type}'"
        )
    
    db_user_skill = UserSkill(
        user_id=current_user.id,
        skill_id=user_skill.skill_id,
        skill_type=user_skill.skill_type,
        proficiency_level=user_skill.proficiency_level,
        years_of_experience=user_skill.years_of_experience,
        description=user_skill.description
    )
    
    db.add(db_user_skill)
    db.commit()
    db.refresh(db_user_skill)
    
    return db_user_skill


@router.get("/users/me/skills", response_model=List[UserSkillResponse])
def get_my_skills(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve all skills associated with the current user.
    """
    skills = db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()
    return skills


@router.get("/users/{user_id}/skills", response_model=List[UserSkillResponse])
def get_user_skills(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieve all skills for a specific user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    skills = db.query(UserSkill).filter(UserSkill.user_id == user_id).all()
    return skills


@router.delete("/users/me/skills/{user_skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_skill(
    user_skill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a skill from the current user's profile.
    """
    user_skill = db.query(UserSkill).filter(
        and_(
            UserSkill.id == user_skill_id,
            UserSkill.user_id == current_user.id
        )
    ).first()
    
    if not user_skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User skill not found"
        )
    
    db.delete(user_skill)
    db.commit()
    
    return None


# Matching endpoints
@router.get("/matches", response_model=List[MatchResponse])
def find_skill_matches(
    skill_id: Optional[int] = None,
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Find potential skill swap matches for the current user.
    Uses intelligent matching algorithm based on:
    - Complementary skills (what I offer matches what they want)
    - Proficiency level compatibility
    - Availability overlap
    - Location/timezone considerations
    """
    # Get user's offered skills and wanted skills
    offered_skills = db.query(UserSkill).filter(
        and_(
            UserSkill.user_id == current_user.id,
            UserSkill.skill_type == "offer"
        )
    ).all()
    
    wanted_skills = db.query(UserSkill).filter(
        and_(
            UserSkill.user_id == current_user.id,
            UserSkill.skill_type == "want"
        )
    ).all()
    
    if not offered_skills or not wanted_skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must have both skills to offer and skills you want to learn"
        )
    
    # Find potential matches
    matches = find_matches(
        user=current_user,
        offered_skills=offered_skills,
        wanted_skills=wanted_skills,
        db=db,
        min_score=min_score,
        limit=limit,
        specific_skill_id=skill_id
    )
    
    return matches


# Swap Request endpoints
@router.post("/swap-requests", response_model=SwapRequestResponse, status_code=status.HTTP_201_CREATED)
def create_swap_request(
    swap_request: SwapRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new skill swap request to another user.
    """
    # Validate recipient exists
    recipient = db.query(User).filter(User.id == swap_request.recipient_id).first()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient user not found"
        )
    
    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create swap request with yourself"
        )
    
    # Validate skills exist and belong to correct users
    offered_skill = db.query(UserSkill).filter(
        and_(
            UserSkill.id == swap_request.offered