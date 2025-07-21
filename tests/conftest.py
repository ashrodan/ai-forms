"""Pytest configuration and shared fixtures"""
import pytest
from typing import List, Optional
from pydantic import BaseModel, Field
from ai_forms import AIForm, ConversationMode, FieldPriority, ValidationStrategy


@pytest.fixture
def simple_user_model():
    """Simple user model for basic testing"""
    class UserProfile(BaseModel):
        name: str = Field(description="Your full name")
        email: str = Field(description="Email address for contact")
        age: int = Field(description="Your age in years", ge=0, le=120)
    
    return UserProfile


@pytest.fixture
def complex_job_model():
    """Complex job application model with metadata"""
    class JobApplication(BaseModel):
        applicant_name: str = Field(
            description="Full legal name",
            json_schema_extra={
                "priority": FieldPriority.CRITICAL,
                "cluster": "identity",
                "custom_question": "What's your full legal name?"
            }
        )
        
        email: str = Field(
            description="Professional email address",
            json_schema_extra={
                "priority": FieldPriority.CRITICAL,
                "cluster": "identity", 
                "examples": ["john.doe@company.com"],
                "validation_hint": "Use your professional email"
            }
        )
        
        position: str = Field(
            description="Position applying for",
            json_schema_extra={
                "priority": FieldPriority.HIGH,
                "cluster": "job_details"
            }
        )
        
        experience_years: int = Field(
            description="Years of relevant experience",
            ge=0, le=50,
            json_schema_extra={
                "priority": FieldPriority.HIGH,
                "cluster": "job_details",
                "dependencies": ["position"]
            }
        )
        
        salary_expectation: Optional[int] = Field(
            None,
            description="Expected salary range",
            json_schema_extra={
                "priority": FieldPriority.LOW,
                "cluster": "compensation",
                "skip_if": lambda data: data.get("experience_years", 0) < 2
            }
        )
        
        skills: List[str] = Field(
            default_factory=list,
            description="Key skills and technologies",
            json_schema_extra={
                "priority": FieldPriority.MEDIUM,
                "cluster": "job_details",
                "examples": ["Python", "JavaScript", "Project Management"]
            }
        )
    
    return JobApplication


@pytest.fixture
def empty_model():
    """Model with no fields for edge case testing"""
    class EmptyModel(BaseModel):
        pass
    
    return EmptyModel


@pytest.fixture
def circular_dependency_model():
    """Model with circular dependencies for error testing"""
    class CircularModel(BaseModel):
        field_a: str = Field(
            description="Field A",
            json_schema_extra={"dependencies": ["field_b"]}
        )
        field_b: str = Field(
            description="Field B", 
            json_schema_extra={"dependencies": ["field_a"]}
        )
    
    return CircularModel


@pytest.fixture
def simple_form(simple_user_model):
    """Basic form instance for testing"""
    return AIForm(simple_user_model)


@pytest.fixture
def complex_form(complex_job_model):
    """Complex form instance for testing"""
    return AIForm(complex_job_model)


@pytest.fixture
def all_conversation_modes():
    """All conversation modes for parametrized testing"""
    return [
        ConversationMode.SEQUENTIAL,
        ConversationMode.ONE_SHOT,
        ConversationMode.CLUSTERED
    ]


@pytest.fixture
def all_validation_strategies():
    """All validation strategies for parametrized testing"""
    return [
        ValidationStrategy.IMMEDIATE,
        ValidationStrategy.END_OF_CLUSTER,
        ValidationStrategy.FINAL
    ]


@pytest.fixture
def all_field_priorities():
    """All field priorities for parametrized testing"""
    return [
        FieldPriority.CRITICAL,
        FieldPriority.HIGH,
        FieldPriority.MEDIUM,
        FieldPriority.LOW
    ]