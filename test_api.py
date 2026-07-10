```python
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app, get_db
from database import Base
from models import User, Skill, UserSkill, SkillRequest, Match
from schemas import (
    UserCreate,
    SkillCreate,
    UserSkillCreate,
    SkillRequestCreate,
    MatchCreate,
)

# Test database setup using in-memory SQLite
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the get_db dependency to use test database."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user_data():
    """Provide sample user registration data."""
    return {
        "email": "john.doe@example.com",
        "username": "johndoe",
        "full_name": "John Doe",
        "password": "SecurePass123!",
        "bio": "Full-stack developer with 5 years experience",
        "location": "San Francisco, CA",
        "availability_hours_per_week": 10,
    }


@pytest.fixture
def sample_skill_data():
    """Provide sample skill data."""
    return [
        {"name": "Python", "category": "Programming", "description": "Python programming language"},
        {"name": "React", "category": "Programming", "description": "React JavaScript library"},
        {"name": "Graphic Design", "category": "Design", "description": "Visual design and graphics"},
        {"name": "Data Analysis", "category": "Analytics", "description": "Data analysis and visualization"},
    ]


@pytest.fixture
def created_user(sample_user_data):
    """Create and return a test user."""
    response = client.post("/api/users/", json=sample_user_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def created_skills(sample_skill_data):
    """Create and return test skills."""
    skills = []
    for skill_data in sample_skill_data:
        response = client.post("/api/skills/", json=skill_data)
        assert response.status_code == 201
        skills.append(response.json())
    return skills


class TestUserEndpoints:
    """Test suite for user-related API endpoints."""

    def test_create_user_success(self, sample_user_data):
        """Test successful user registration."""
        response = client.post("/api/users/", json=sample_user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == sample_user_data["email"]
        assert data["username"] == sample_user_data["username"]
        assert "password" not in data  # Password should not be returned
        assert "id" in data
        assert "created_at" in data

    def test_create_user_duplicate_email(self, sample_user_data):
        """Test that duplicate email addresses are rejected."""
        client.post("/api/users/", json=sample_user_data)
        response = client.post("/api/users/", json=sample_user_data)
        assert response.status_code == 400
        assert "email already registered" in response.json()["detail"].lower()

    def test_create_user_invalid_email(self, sample_user_data):
        """Test that invalid email format is rejected."""
        sample_user_data["email"] = "invalid-email"
        response = client.post("/api/users/", json=sample_user_data)
        assert response.status_code == 422

    def test_get_user_by_id(self, created_user):
        """Test retrieving a user by ID."""
        user_id = created_user["id"]
        response = client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == created_user["email"]

    def test_get_user_not_found(self):
        """Test that requesting non-existent user returns 404."""
        response = client.get("/api/users/99999")
        assert response.status_code == 404

    def test_update_user(self, created_user):
        """Test updating user information."""
        user_id = created_user["id"]
        update_data = {
            "bio": "Updated bio with new information",
            "availability_hours_per_week": 15,
        }
        response = client.patch(f"/api/users/{user_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["bio"] == update_data["bio"]
        assert data["availability_hours_per_week"] == update_data["availability_hours_per_week"]

    def test_delete_user(self, created_user):
        """Test deleting a user."""
        user_id = created_user["id"]
        response = client.delete(f"/api/users/{user_id}")
        assert response.status_code == 204
        
        # Verify user is deleted
        get_response = client.get(f"/api/users/{user_id}")
        assert get_response.status_code == 404

    def test_list_users(self, sample_user_data):
        """Test listing users with pagination."""
        # Create multiple users
        for i in range(5):
            user_data = sample_user_data.copy()
            user_data["email"] = f"user{i}@example.com"
            user_data["username"] = f"user{i}"
            client.post("/api/users/", json=user_data)

        response = client.get("/api/users/?skip=0&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestSkillEndpoints:
    """Test suite for skill-related API endpoints."""

    def test_create_skill(self, sample_skill_data):
        """Test creating a new skill."""
        skill_data = sample_skill_data[0]
        response = client.post("/api/skills/", json=skill_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == skill_data["name"]
        assert data["category"] == skill_data["category"]
        assert "id" in data

    def test_create_duplicate_skill(self, sample_skill_data):
        """Test that duplicate skill names are handled appropriately."""
        skill_data = sample_skill_data[0]
        client.post("/api/skills/", json=skill_data)
        response = client.post("/api/skills/", json=skill_data)
        assert response.status_code == 400

    def test_get_skill_by_id(self, created_skills):
        """Test retrieving a skill by ID."""
        skill_id = created_skills[0]["id"]
        response = client.get(f"/api/skills/{skill_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == skill_id

    def test_list_skills(self, created_skills):
        """Test listing all skills."""
        response = client.get("/api/skills/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= len(created_skills)

    def test_search_skills_by_category(self, created_skills):
        """Test filtering skills by category."""
        response = client.get("/api/skills/?category=Programming")
        assert response.status_code == 200
        data = response.json()
        assert all(skill["category"] == "Programming" for skill in data)

    def test_search_skills_by_name(self, created_skills):
        """Test searching skills by name."""
        response = client.get("/api/skills/?search=Python")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert any("Python" in skill["name"] for skill in data)


class TestUserSkillEndpoints:
    """Test suite for user-skill relationship endpoints."""

    def test_add_user_skill_offer(self, created_user, created_skills):
        """Test adding a skill that user can offer."""
        user_id = created_user["id"]
        skill_id = created_skills[0]["id"]
        user_skill_data = {
            "user_id": user_id,
            "skill_id": skill_id,
            "proficiency_level": "intermediate",
            "is_offering": True,
            "is_seeking": False,
        }
        response = client.post("/api/user-skills/", json=user_skill_data)
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == user_id
        assert data["skill_id"] == skill_id
        assert data["proficiency_level"] == "intermediate"
        assert data["is_offering"] is True

    def test_add_user_skill_seeking(self, created_user, created_skills):
        """Test adding a skill that user wants to learn."""
        user_id = created_user["id"]
        skill_id = created_skills[1]["id"]
        user_skill_data = {
            "user_id": user_id,
            "skill_id": skill_id,
            "proficiency_level": "beginner",
            "is_offering": False,
            "is_seeking": True,
            "learning_goal": "Build production-ready React applications",
        }
        response = client.post("/api/user-skills/", json=user_skill_data)
        assert response.status_code == 201
        data = response.json()
        assert data["is_seeking"] is True
        assert data["learning_goal"] is not None

    def test_get_user_skills(self, created_user, created_skills):
        """Test retrieving all skills for a user."""
        user_id = created_user["id"]
        
        # Add multiple skills
        for skill in created_skills[:2]:
            user_skill_data = {
                "user_id": user_id,
                "skill_id": skill["id"],
                "proficiency_level": "intermediate",
                "is_offering": True,
                "is_seeking": False,
            }
            client.post("/api/user-skills/", json=user_skill_data)

        response = client.get(f"/api/users/{user_id}/skills")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_update_user_skill_proficiency(self, created_user, created_skills):
        """Test updating skill proficiency level."""
        user_id = created_user["id"]
        skill_id = created_skills[0]["id"]
        
        # Create user skill
        user_skill_data = {
            "user_id": user_id,
            "skill_id": skill_id,
            "proficiency_level": "beginner",
            "is_offering": False,
            "is_seeking": True,
        }