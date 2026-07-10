```python
"""
Pydantic schemas for request/response validation.

This module defines all data validation models used across the API,
including user profiles, skills, skill exchanges, and matching logic.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator, root_validator


# Enums for controlled vocabularies
class ProficiencyLevel(str, Enum):
    """Skill proficiency levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillCategory(str, Enum):
    """Predefined skill categories for better matching."""
    DESIGN = "design"
    DEVELOPMENT = "development"
    MARKETING = "marketing"
    DATA_SCIENCE = "data_science"
    BUSINESS = "business"
    WRITING = "writing"
    OTHER = "other"


class ExchangeStatus(str, Enum):
    """Skill exchange request status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AvailabilityDay(str, Enum):
    """Days of the week for availability."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# Base schemas
class SkillBase(BaseModel):
    """Base skill schema with common attributes."""
    name: str = Field(..., min_length=2, max_length=100)
    category: SkillCategory
    proficiency_level: ProficiencyLevel
    description: Optional[str] = Field(None, max_length=500)

    @validator('name')
    def normalize_skill_name(cls, v):
        """Normalize skill names for consistency."""
        return v.strip().lower()


class SkillCreate(SkillBase):
    """Schema for creating a new skill."""
    pass


class SkillUpdate(BaseModel):
    """Schema for updating an existing skill."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    category: Optional[SkillCategory] = None
    proficiency_level: Optional[ProficiencyLevel] = None
    description: Optional[str] = Field(None, max_length=500)


class Skill(SkillBase):
    """Complete skill schema with database fields."""
    id: int
    user_id: int
    is_offering: bool
    is_seeking: bool
    created_at: datetime

    class Config:
        from_attributes = True


# User schemas
class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    bio: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=50)


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)

    @validator('password')
    def validate_password_strength(cls, v):
        """Ensure password meets security requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    bio: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=50)


class UserProfile(UserBase):
    """Public user profile schema."""
    id: int
    created_at: datetime
    is_active: bool
    skills_offered: List[Skill] = []
    skills_seeking: List[Skill] = []
    exchanges_completed: int = 0
    rating_average: Optional[float] = None

    class Config:
        from_attributes = True


class User(UserProfile):
    """Complete user schema including private fields."""
    email_verified: bool = False
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


# Availability schemas
class AvailabilitySlot(BaseModel):
    """User availability time slot."""
    day: AvailabilityDay
    start_time: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

    @root_validator
    def validate_time_range(cls, values):
        """Ensure end time is after start time."""
        start = values.get('start_time')
        end = values.get('end_time')
        if start and end:
            start_minutes = int(start.split(':')[0]) * 60 + int(start.split(':')[1])
            end_minutes = int(end.split(':')[0]) * 60 + int(end.split(':')[1])
            if end_minutes <= start_minutes:
                raise ValueError('End time must be after start time')
        return values


class AvailabilityCreate(BaseModel):
    """Schema for creating availability slots."""
    slots: List[AvailabilitySlot] = Field(..., min_items=1)


class Availability(BaseModel):
    """Complete availability schema."""
    id: int
    user_id: int
    day: AvailabilityDay
    start_time: str
    end_time: str
    created_at: datetime

    class Config:
        from_attributes = True


# Exchange schemas
class ExchangeBase(BaseModel):
    """Base exchange schema."""
    offered_skill_id: int
    requested_skill_id: int
    message: Optional[str] = Field(None, max_length=1000)
    proposed_duration_hours: int = Field(..., ge=1, le=100)


class ExchangeCreate(ExchangeBase):
    """Schema for creating a skill exchange request."""
    pass


class ExchangeUpdate(BaseModel):
    """Schema for updating an exchange."""
    status: Optional[ExchangeStatus] = None
    actual_duration_hours: Optional[int] = Field(None, ge=1, le=100)
    notes: Optional[str] = Field(None, max_length=1000)


class ExchangeResponse(BaseModel):
    """Schema for responding to an exchange request."""
    status: ExchangeStatus
    response_message: Optional[str] = Field(None, max_length=1000)


class Exchange(ExchangeBase):
    """Complete exchange schema with all fields."""
    id: int
    requester_id: int
    provider_id: int
    status: ExchangeStatus
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_duration_hours: Optional[int] = None
    notes: Optional[str] = None
    
    # Nested relationships
    offered_skill: Optional[Skill] = None
    requested_skill: Optional[Skill] = None

    class Config:
        from_attributes = True


# Rating schemas
class RatingBase(BaseModel):
    """Base rating schema."""
    score: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=500)


class RatingCreate(RatingBase):
    """Schema for creating a rating."""
    exchange_id: int


class Rating(RatingBase):
    """Complete rating schema."""
    id: int
    exchange_id: int
    rater_id: int
    rated_user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Matching schemas
class MatchPreferences(BaseModel):
    """User preferences for matching algorithm."""
    min_proficiency_level: Optional[ProficiencyLevel] = None
    max_proficiency_level: Optional[ProficiencyLevel] = None
    preferred_categories: Optional[List[SkillCategory]] = None
    location_radius_km: Optional[int] = Field(None, ge=0, le=500)
    min_rating: Optional[float] = Field(None, ge=1.0, le=5.0)


class MatchScore(BaseModel):
    """Schema representing a match score between users."""
    user: UserProfile
    score: float = Field(..., ge=0.0, le=100.0)
    matching_skills: List[Skill]
    compatibility_factors: dict = Field(
        default_factory=dict,
        description="Breakdown of compatibility scoring factors"
    )

    class Config:
        from_attributes = True


class MatchRequest(BaseModel):
    """Schema for requesting matches."""
    skill_seeking_id: int
    preferences: Optional[MatchPreferences] = None
    limit: int = Field(10, ge=1, le=50)


class MatchResult(BaseModel):
    """Schema for match results."""
    matches: List[MatchScore]
    total_candidates: int
    search_params: dict


# Authentication schemas
class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    email: Optional[str] = None


class LoginRequest(BaseModel):
    """Login credentials."""
    email: EmailStr
    password: str


# Statistics schemas
class UserStats(BaseModel):
    """User statistics schema."""
    total_exchanges: int
    completed_exchanges: int
    pending_exchanges: int
    skills_offered_count: int
    skills_seeking_count: int
    average_rating: Optional[float] = None
    total_hours_exchanged: int
    member_since: datetime


class PlatformStats(BaseModel):
    """Platform-wide statistics."""
    total_users: int
    active_users: int
    total_exchanges: int
    completed_exchanges: int
    total_skills: int
    most_popular_skills: List[dict]
    average_match_score: float


# Notification schemas
class NotificationBase(BaseModel):
    """Base notification schema."""
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=1000)
    notification_type: str


class Notification(NotificationBase):
    """Complete notification schema."""
    id: int
    user_id: int
    is_read: bool = False
    created_at: datetime
    related_exchange_id: Optional[int] = None

    class Config:
        from_attributes = True


# Pagination schemas
class PaginationParams(BaseModel):
    """Common pagination parameters."""
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: List[dict]
    total: int
    skip: int
    limit: int
    has_more: bool

    @property
    def page(self) -> int:
        """Calculate current page number."""
        return (self.skip // self.limit) + 1 if self.limit > 0 else 1
```