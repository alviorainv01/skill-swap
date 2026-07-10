```python
"""
Matching Engine for SkillSwap Platform

Implements intelligent matching algorithms to pair professionals based on:
- Complementary skill needs and offerings
- Proficiency level compatibility
- Availability overlap
- Learning goals alignment
- Historical interaction patterns
"""

from datetime import datetime, time
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from models import User, Skill, UserSkill, SkillLevel, MatchRequest, Match, MatchStatus
from schemas import MatchScore, MatchResult


logger = logging.getLogger(__name__)


class MatchingStrategy(str, Enum):
    """Available matching strategies for skill pairing"""
    BALANCED = "balanced"  # Equal weight to all factors
    SKILL_FOCUSED = "skill_focused"  # Prioritize skill compatibility
    AVAILABILITY_FOCUSED = "availability_focused"  # Prioritize schedule overlap
    GOAL_FOCUSED = "goal_focused"  # Prioritize learning objectives


@dataclass
class MatchWeights:
    """Configurable weights for match scoring components"""
    skill_compatibility: float = 0.35
    proficiency_match: float = 0.25
    availability_overlap: float = 0.20
    goal_alignment: float = 0.15
    proximity_bonus: float = 0.05
    
    def normalize(self) -> None:
        """Ensure weights sum to 1.0"""
        total = (
            self.skill_compatibility + 
            self.proficiency_match + 
            self.availability_overlap + 
            self.goal_alignment + 
            self.proximity_bonus
        )
        if total > 0:
            self.skill_compatibility /= total
            self.proficiency_match /= total
            self.availability_overlap /= total
            self.goal_alignment /= total
            self.proximity_bonus /= total


class MatchingEngine:
    """
    Core matching engine for pairing users based on complementary skills
    and mutual learning goals
    """
    
    def __init__(
        self, 
        db: Session,
        strategy: MatchingStrategy = MatchingStrategy.BALANCED,
        min_score_threshold: float = 0.5
    ):
        self.db = db
        self.strategy = strategy
        self.min_score_threshold = min_score_threshold
        self.weights = self._get_strategy_weights(strategy)
    
    def _get_strategy_weights(self, strategy: MatchingStrategy) -> MatchWeights:
        """Return weight configuration based on selected strategy"""
        if strategy == MatchingStrategy.SKILL_FOCUSED:
            return MatchWeights(
                skill_compatibility=0.45,
                proficiency_match=0.30,
                availability_overlap=0.10,
                goal_alignment=0.10,
                proximity_bonus=0.05
            )
        elif strategy == MatchingStrategy.AVAILABILITY_FOCUSED:
            return MatchWeights(
                skill_compatibility=0.25,
                proficiency_match=0.15,
                availability_overlap=0.45,
                goal_alignment=0.10,
                proximity_bonus=0.05
            )
        elif strategy == MatchingStrategy.GOAL_FOCUSED:
            return MatchWeights(
                skill_compatibility=0.25,
                proficiency_match=0.20,
                availability_overlap=0.15,
                goal_alignment=0.35,
                proximity_bonus=0.05
            )
        else:  # BALANCED
            weights = MatchWeights()
            weights.normalize()
            return weights
    
    def find_matches(
        self, 
        user_id: int, 
        limit: int = 10,
        exclude_previous: bool = True
    ) -> List[MatchResult]:
        """
        Find top matching candidates for a given user
        
        Args:
            user_id: ID of user seeking matches
            limit: Maximum number of matches to return
            exclude_previous: Skip users who have been previously matched
            
        Returns:
            List of MatchResult objects sorted by score (descending)
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get user's skills they want to learn
        desired_skills = self._get_desired_skills(user)
        if not desired_skills:
            logger.info(f"User {user_id} has no desired skills specified")
            return []
        
        # Get user's skills they can teach
        teaching_skills = self._get_teaching_skills(user)
        if not teaching_skills:
            logger.info(f"User {user_id} has no teaching skills specified")
            return []
        
        # Find candidate users who have complementary skills
        candidates = self._get_candidate_users(
            user_id=user_id,
            desired_skills=desired_skills,
            teaching_skills=teaching_skills,
            exclude_previous=exclude_previous
        )
        
        # Score each candidate
        match_results = []
        for candidate in candidates:
            score = self._calculate_match_score(user, candidate, desired_skills, teaching_skills)
            
            if score.total_score >= self.min_score_threshold:
                match_results.append(MatchResult(
                    user_id=candidate.id,
                    username=candidate.username,
                    email=candidate.email,
                    score=score,
                    matched_skills=score.matched_skills,
                    availability_overlap=score.availability_score
                ))
        
        # Sort by score and return top matches
        match_results.sort(key=lambda x: x.score.total_score, reverse=True)
        return match_results[:limit]
    
    def _get_desired_skills(self, user: User) -> List[UserSkill]:
        """Get skills the user wants to learn"""
        return [
            us for us in user.user_skills 
            if us.is_learning and not us.is_teaching
        ]
    
    def _get_teaching_skills(self, user: User) -> List[UserSkill]:
        """Get skills the user can teach (intermediate to expert level)"""
        return [
            us for us in user.user_skills 
            if us.is_teaching and us.proficiency_level in [
                SkillLevel.INTERMEDIATE,
                SkillLevel.ADVANCED,
                SkillLevel.EXPERT
            ]
        ]
    
    def _get_candidate_users(
        self,
        user_id: int,
        desired_skills: List[UserSkill],
        teaching_skills: List[UserSkill],
        exclude_previous: bool
    ) -> List[User]:
        """
        Query database for candidate users with complementary skills
        
        A good candidate should:
        1. Have at least one skill the user wants to learn (at teaching level)
        2. Want to learn at least one skill the user can teach
        3. Be active and available
        """
        desired_skill_ids = [us.skill_id for us in desired_skills]
        teaching_skill_ids = [us.skill_id for us in teaching_skills]
        
        # Build query for candidates who can teach what user wants to learn
        query = self.db.query(User).join(UserSkill).filter(
            and_(
                User.id != user_id,
                User.is_active == True,
                UserSkill.skill_id.in_(desired_skill_ids),
                UserSkill.is_teaching == True,
                UserSkill.proficiency_level.in_([
                    SkillLevel.INTERMEDIATE,
                    SkillLevel.ADVANCED,
                    SkillLevel.EXPERT
                ])
            )
        )
        
        # Exclude users who have been previously matched
        if exclude_previous:
            previous_match_ids = self.db.query(Match.user2_id).filter(
                Match.user1_id == user_id
            ).union(
                self.db.query(Match.user1_id).filter(Match.user2_id == user_id)
            ).all()
            
            if previous_match_ids:
                excluded_ids = [match_id[0] for match_id in previous_match_ids]
                query = query.filter(User.id.notin_(excluded_ids))
        
        candidates = query.distinct().all()
        
        # Filter candidates who also want to learn what user can teach
        filtered_candidates = []
        for candidate in candidates:
            candidate_learning_skill_ids = [
                us.skill_id for us in candidate.user_skills 
                if us.is_learning
            ]
            
            # Check for mutual skill exchange potential
            if any(skill_id in teaching_skill_ids for skill_id in candidate_learning_skill_ids):
                filtered_candidates.append(candidate)
        
        return filtered_candidates
    
    def _calculate_match_score(
        self,
        user: User,
        candidate: User,
        desired_skills: List[UserSkill],
        teaching_skills: List[UserSkill]
    ) -> MatchScore:
        """
        Calculate comprehensive match score between two users
        
        Scoring components:
        1. Skill compatibility - how well skills align
        2. Proficiency match - appropriate skill level differences
        3. Availability overlap - schedule compatibility
        4. Goal alignment - learning objectives similarity
        5. Proximity bonus - location-based bonus (if applicable)
        """
        skill_score, matched_skills = self._calculate_skill_compatibility(
            user, candidate, desired_skills, teaching_skills
        )
        
        proficiency_score = self._calculate_proficiency_match(
            user, candidate, desired_skills, teaching_skills
        )
        
        availability_score = self._calculate_availability_overlap(user, candidate)
        
        goal_score = self._calculate_goal_alignment(user, candidate)
        
        proximity_score = self._calculate_proximity_bonus(user, candidate)
        
        # Calculate weighted total score
        total_score = (
            skill_score * self.weights.skill_compatibility +
            proficiency_score * self.weights.proficiency_match +
            availability_score * self.weights.availability_overlap +
            goal_score * self.weights.goal_alignment +
            proximity_score * self.weights.proximity_bonus
        )
        
        return MatchScore(
            total_score=total_score,
            skill_compatibility_score=skill_score,
            proficiency_match_score=proficiency_score,
            availability_score=availability_score,
            goal_alignment_score=goal_score,
            proximity_score=proximity_score,
            matched_skills=matched_skills
        )
    
    def _calculate_skill_compatibility(
        self,
        user: User,
        candidate: User,
        desired_skills: List[UserSkill],
        teaching_skills: List[UserSkill]
    ) -> Tuple[float, Dict[str, str]]:
        """
        Calculate how well the skill sets complement each other
        
        Returns:
            Tuple of (score, matched_skills_dict)
        """
        desired_skill_ids = {us.skill_id for us in desired_skills}
        teaching_skill_ids = {us.skill_id for us in teaching_skills}
        
        candidate_teaching_skills = {
            us.skill_id: us for us in candidate.user_skills 
            if us.is_teaching
        }
        candidate_learning_skills = {
            us.skill_id for us in candidate.user_skills 
            if us.is_learning
        }
        
        # Count mutual skill exchanges
        user_gets_count = len(desired_skill_ids & candidate_teaching_skills.keys())
        candidate_gets_count = len(teaching_skill_ids & candidate_learning_skills)
        
        # Track matched skills for display
        matched_skills = {}
        for skill_id in desired_skill_ids & candidate_