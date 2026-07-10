# models.py
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Table, 
    Float, Boolean, Enum as SQLEnum, Text, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
import enum


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class ProficiencyLevel(str, enum.Enum):
    """Skill proficiency levels for standardized matching."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ExchangeStatus(str, enum.Enum):
    """Exchange lifecycle states."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class AvailabilityStatus(str, enum.Enum):
    """User availability for skill exchange."""
    AVAILABLE = "available"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"


# Association table for user skills they want to offer
user_offered_skills = Table(
    'user_offered_skills',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('skill_id', Integer, ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
    Column('proficiency_level', SQLEnum(ProficiencyLevel), nullable=False),
    Column('years_experience', Float, default=0.0),
    Column('verified', Boolean, default=False),
    Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    UniqueConstraint('user_id', 'skill_id', name='uq_user_offered_skill')
)

# Association table for skills users want to learn
user_desired_skills = Table(
    'user_desired_skills',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('skill_id', Integer, ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
    Column('target_proficiency', SQLEnum(ProficiencyLevel), nullable=False),
    Column('priority', Integer, default=5),  # 1-10 scale
    Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    UniqueConstraint('user_id', 'skill_id', name='uq_user_desired_skill')
)


class User(Base):
    """Core user model representing platform professionals."""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Profile information
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        SQLEnum(AvailabilityStatus), 
        default=AvailabilityStatus.AVAILABLE
    )
    
    # Reputation and engagement metrics
    reputation_score: Mapped[float] = mapped_column(Float, default=0.0)
    completed_exchanges: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    offered_skills: Mapped[List["Skill"]] = relationship(
        "Skill",
        secondary=user_offered_skills,
        back_populates="offering_users",
        lazy="selectin"
    )
    
    desired_skills: Mapped[List["Skill"]] = relationship(
        "Skill",
        secondary=user_desired_skills,
        back_populates="seeking_users",
        lazy="selectin"
    )
    
    # Exchanges where user is the initiator (teaching)
    initiated_exchanges: Mapped[List["SkillExchange"]] = relationship(
        "SkillExchange",
        foreign_keys="SkillExchange.initiator_id",
        back_populates="initiator",
        cascade="all, delete-orphan"
    )
    
    # Exchanges where user is the recipient (learning)
    received_exchanges: Mapped[List["SkillExchange"]] = relationship(
        "SkillExchange",
        foreign_keys="SkillExchange.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan"
    )
    
    # Reviews written by this user
    reviews_given: Mapped[List["Review"]] = relationship(
        "Review",
        foreign_keys="Review.reviewer_id",
        back_populates="reviewer",
        cascade="all, delete-orphan"
    )
    
    # Reviews received by this user
    reviews_received: Mapped[List["Review"]] = relationship(
        "Review",
        foreign_keys="Review.reviewee_id",
        back_populates="reviewee",
        cascade="all, delete-orphan"
    )
    
    availability_slots: Mapped[List["AvailabilitySlot"]] = relationship(
        "AvailabilitySlot",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    @hybrid_property
    def total_exchanges(self) -> int:
        """Total number of exchanges (both initiated and received)."""
        return len(self.initiated_exchanges) + len(self.received_exchanges)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class Skill(Base):
    """Skill taxonomy for matching and categorization."""
    __tablename__ = 'skills'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    # Metadata for matching algorithm
    popularity_score: Mapped[float] = mapped_column(Float, default=0.0)  # Based on user interest
    demand_score: Mapped[float] = mapped_column(Float, default=0.0)  # How many want to learn
    supply_score: Mapped[float] = mapped_column(Float, default=0.0)  # How many can teach
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    offering_users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_offered_skills,
        back_populates="offered_skills"
    )
    
    seeking_users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_desired_skills,
        back_populates="desired_skills"
    )
    
    exchanges_teaching: Mapped[List["SkillExchange"]] = relationship(
        "SkillExchange",
        foreign_keys="SkillExchange.offered_skill_id",
        back_populates="offered_skill"
    )
    
    exchanges_learning: Mapped[List["SkillExchange"]] = relationship(
        "SkillExchange",
        foreign_keys="SkillExchange.requested_skill_id",
        back_populates="requested_skill"
    )
    
    @hybrid_property
    def supply_demand_ratio(self) -> float:
        """Calculate supply/demand ratio for matching optimization."""
        if self.demand_score == 0:
            return float('inf') if self.supply_score > 0 else 0.0
        return self.supply_score / self.demand_score

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}', category='{self.category}')>"


class SkillExchange(Base):
    """Represents a bilateral skill exchange agreement between two users."""
    __tablename__ = 'skill_exchanges'
    
    __table_args__ = (
        CheckConstraint('initiator_id != recipient_id', name='check_different_users'),
        CheckConstraint('estimated_hours > 0', name='check_positive_hours'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Participants
    initiator_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('users.id', ondelete='CASCADE'), 
        nullable=False,
        index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('users.id', ondelete='CASCADE'), 
        nullable=False,
        index=True
    )
    
    # Skills being exchanged
    offered_skill_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('skills.id', ondelete='CASCADE'), 
        nullable=False
    )  # Skill initiator teaches
    requested_skill_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('skills.id', ondelete='CASCADE'), 
        nullable=False
    )  # Skill initiator wants to learn
    
    # Exchange details
    status: Mapped[ExchangeStatus