"""Test suite for AiValidator with fallback and mock scenarios"""
import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel, Field

from ai_forms.validation.ai_validator import AiValidator
from ai_forms.types.config import FieldConfig
from ai_forms.types.enums import FieldPriority
from ai_forms.types.exceptions import ValidationError


# Test model for validation tests
class UserTestModel(BaseModel):
    """Simple test model"""
    name: str = Field(description="Name field")
    age: int = Field(description="Age field")
    email: str = Field(description="Email field")
    newsletter: bool = Field(description="Newsletter subscription")
    tags: list = Field(description="List of tags")


class TestAiValidatorCore:
    """Test core AiValidator functionality"""
    
    def test_ai_validator_initialization(self):
        """Test AiValidator initialization"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        assert validator.use_ai is True
        assert validator.test_mode is True
        assert validator.is_ai_enabled is True
        assert validator.ai_validation_tools is not None
        
        status = validator.status
        assert status["use_ai"] is True
        assert status["test_mode"] is True
        assert status["ai_validation_available"] is True
        assert status["ai_enabled"] is True
    
    def test_ai_validator_disabled(self):
        """Test AiValidator when AI is disabled"""
        validator = AiValidator(use_ai=False, test_mode=True)
        
        assert validator.use_ai is False
        assert validator.is_ai_enabled is False
        assert validator.ai_validation_tools is None
        
        status = validator.status
        assert status["use_ai"] is False
        assert status["ai_enabled"] is False
    
    @pytest.mark.asyncio
    async def test_field_validation_with_ai(self):
        """Test field validation with AI enabled"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        config = FieldConfig(
            name="newsletter",
            field_type=bool,
            description="Subscribe to newsletter?",
            priority=FieldPriority.LOW,
            required=True
        )
        
        # Test natural language boolean parsing
        result = await validator.validate_field(config, "sure", {})
        assert result is True
        
        result = await validator.validate_field(config, "nope", {})
        assert result is False
    
    @pytest.mark.asyncio
    async def test_field_validation_fallback(self):
        """Test field validation fallback when AI is disabled"""
        validator = AiValidator(use_ai=False, test_mode=True)
        
        config = FieldConfig(
            name="newsletter",
            field_type=bool,
            description="Subscribe to newsletter?",
            priority=FieldPriority.LOW,
            required=True
        )
        
        # Test standard boolean parsing (should work)
        result = await validator.validate_field(config, "yes", {})
        assert result is True
        
        result = await validator.validate_field(config, "no", {})
        assert result is False
        
        # Test natural language (should fail without AI)
        with pytest.raises(ValidationError, match="Expected yes/no, got: sure"):
            await validator.validate_field(config, "sure", {})


class TestAiValidatorFieldTypes:
    """Test AiValidator with different field types"""
    
    @pytest.mark.asyncio
    async def test_integer_validation(self):
        """Test integer field validation"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        config = FieldConfig(
            name="age",
            field_type=int,
            description="Age in years",
            priority=FieldPriority.MEDIUM,
            required=True
        )
        
        # Standard integer
        result = await validator.validate_field(config, "25", {})
        assert result == 25
        assert isinstance(result, int)
        
        # Written number (supported in AI mode)
        result = await validator.validate_field(config, "twenty", {})
        assert result == 20
        
        # Invalid integer
        with pytest.raises(ValidationError, match="Expected a number"):
            await validator.validate_field(config, "not a number", {})
    
    @pytest.mark.asyncio
    async def test_list_validation(self):
        """Test list field validation"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        from typing import List
        config = FieldConfig(
            name="tags",
            field_type=List[str],
            description="List of tags",
            priority=FieldPriority.LOW,
            required=False
        )
        
        # Comma-separated list
        result = await validator.validate_field(config, "python, web, backend", {})
        assert result == ["python", "web", "backend"]
        
        # Single item
        result = await validator.validate_field(config, "single", {})
        assert result == ["single"]
        
        # Empty list
        result = await validator.validate_field(config, "", {})
        assert result == []
    
    @pytest.mark.asyncio
    async def test_email_validation(self):
        """Test email field validation"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        config = FieldConfig(
            name="email",
            field_type=str,
            description="Email address",
            validation_hint="email validation",
            priority=FieldPriority.HIGH,
            required=True
        )
        
        # Valid email
        result = await validator.validate_field(config, "test@example.com", {})
        assert result == "test@example.com"
        
        # Invalid email (should fail)
        with pytest.raises(ValidationError, match="not a valid email"):
            await validator.validate_field(config, "invalid-email", {})


class TestAiValidatorFormValidation:
    """Test AiValidator form-level validation"""
    
    @pytest.mark.asyncio
    async def test_form_validation_success(self):
        """Test successful form validation"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        form_data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com",
            "newsletter": True,
            "tags": ["python", "web"]
        }
        
        field_configs = {
            "name": FieldConfig(name="name", field_type=str, description="Name", priority=FieldPriority.HIGH, required=True),
            "age": FieldConfig(name="age", field_type=int, description="Age", priority=FieldPriority.MEDIUM, required=True),
            "email": FieldConfig(name="email", field_type=str, description="Email", priority=FieldPriority.HIGH, required=True),
            "newsletter": FieldConfig(name="newsletter", field_type=bool, description="Newsletter", priority=FieldPriority.LOW, required=True),
            "tags": FieldConfig(name="tags", field_type=list, description="Tags", priority=FieldPriority.LOW, required=False)
        }
        
        result = await validator.validate_form(form_data, UserTestModel, field_configs)
        assert result == form_data
    
    @pytest.mark.asyncio
    async def test_form_validation_fallback(self):
        """Test form validation fallback when AI is disabled"""
        validator = AiValidator(use_ai=False, test_mode=True)
        
        form_data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com",
            "newsletter": True,
            "tags": ["python", "web"]
        }
        
        field_configs = {}
        
        # Should use basic Pydantic validation
        result = await validator.validate_form(form_data, UserTestModel, field_configs)
        assert result == form_data


class TestAiValidatorMockScenarios:
    """Test AiValidator with mocked AI components"""
    
    @pytest.mark.asyncio
    async def test_ai_validation_tools_failure_fallback(self):
        """Test fallback when AI validation tools fail"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        # Mock the AI validation tools to raise an exception
        with patch.object(validator.ai_validation_tools, 'validate_field_with_ai') as mock_validate:
            mock_validate.side_effect = Exception("AI service unavailable")
            
            config = FieldConfig(
                name="age",
                field_type=int,
                description="Age",
                priority=FieldPriority.MEDIUM,
                required=True
            )
            
            # Should fall back to simple parsing
            result = await validator.validate_field(config, "25", {})
            assert result == 25
            assert isinstance(result, int)
    
    @pytest.mark.asyncio
    async def test_ai_validation_tools_none(self):
        """Test behavior when AI validation tools are None"""
        validator = AiValidator(use_ai=True, test_mode=True)
        validator.ai_validation_tools = None  # Simulate AI tools not available
        
        config = FieldConfig(
            name="newsletter",
            field_type=bool,
            description="Newsletter",
            priority=FieldPriority.LOW,
            required=True
        )
        
        # Should fall back to simple parsing
        result = await validator.validate_field(config, "yes", {})
        assert result is True
        
        # Natural language should fail without AI
        with pytest.raises(ValidationError, match="Expected yes/no, got: sure"):
            await validator.validate_field(config, "sure", {})
    
    @pytest.mark.asyncio
    async def test_form_validation_ai_failure(self):
        """Test form validation when AI fails"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        # Mock AI validation to fail
        with patch.object(validator.ai_validation_tools, 'validate_form_with_ai') as mock_validate:
            mock_validate.side_effect = Exception("AI service down")
            
            form_data = {"name": "John", "age": 30, "email": "john@example.com", "newsletter": True, "tags": []}
            field_configs = {}
            
            # Should fall back to Pydantic validation
            result = await validator.validate_form(form_data, UserTestModel, field_configs)
            assert result == form_data


class TestAiValidatorEdgeCases:
    """Test AiValidator edge cases and error scenarios"""
    
    @pytest.mark.asyncio
    async def test_validation_error_propagation(self):
        """Test that ValidationErrors are properly propagated"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        # Mock AI validation to return invalid result
        with patch.object(validator.ai_validation_tools, 'validate_field_with_ai') as mock_validate:
            from ai_forms.validators.ai_tools import ValidationResult
            mock_validate.return_value = ValidationResult(
                is_valid=False,
                error_message="Custom validation error",
                parsed_value="invalid"
            )
            
            config = FieldConfig(
                name="test",
                field_type=str,
                description="Test field",
                priority=FieldPriority.MEDIUM,
                required=True
            )
            
            with pytest.raises(ValidationError, match="Custom validation error"):
                await validator.validate_field(config, "test input", {})
    
    def test_status_properties(self):
        """Test status properties under different conditions"""
        # AI enabled
        validator_ai = AiValidator(use_ai=True, test_mode=True)
        assert validator_ai.is_ai_enabled is True
        
        status = validator_ai.status
        assert "use_ai" in status
        assert "ai_enabled" in status
        assert "ai_validation_available" in status
        
        # AI disabled
        validator_no_ai = AiValidator(use_ai=False, test_mode=True)
        assert validator_no_ai.is_ai_enabled is False
        
        # AI tools unavailable
        validator_no_tools = AiValidator(use_ai=True, test_mode=True)
        validator_no_tools.ai_validation_tools = None
        assert validator_no_tools.is_ai_enabled is False


class TestAiValidatorIntegration:
    """Integration tests for AiValidator with realistic scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_form_workflow_with_ai(self):
        """Test complete form workflow with AI validation"""
        validator = AiValidator(use_ai=True, test_mode=True)
        
        # Simulate form field collection with natural language inputs
        field_configs = {
            "name": FieldConfig(name="name", field_type=str, description="Full name", priority=FieldPriority.HIGH, required=True),
            "age": FieldConfig(name="age", field_type=int, description="Age", priority=FieldPriority.MEDIUM, required=True),
            "email": FieldConfig(name="email", field_type=str, description="Email", validation_hint="email validation", priority=FieldPriority.HIGH, required=True),
            "newsletter": FieldConfig(name="newsletter", field_type=bool, description="Newsletter", priority=FieldPriority.LOW, required=True)
        }
        
        collected_data = {}
        
        # Collect fields one by one
        collected_data["name"] = await validator.validate_field(field_configs["name"], "John Doe", collected_data)
        assert collected_data["name"] == "John Doe"
        
        collected_data["age"] = await validator.validate_field(field_configs["age"], "twenty", collected_data)
        assert collected_data["age"] == 20
        
        collected_data["email"] = await validator.validate_field(field_configs["email"], "john@example.com", collected_data)
        assert collected_data["email"] == "john@example.com"
        
        collected_data["newsletter"] = await validator.validate_field(field_configs["newsletter"], "sure", collected_data)
        assert collected_data["newsletter"] is True
        
        # Final form validation
        class UserForm(BaseModel):
            name: str
            age: int
            email: str
            newsletter: bool
        
        final_data = await validator.validate_form(collected_data, UserForm, field_configs)
        assert final_data == collected_data
    
    @pytest.mark.asyncio
    async def test_complete_form_workflow_without_ai(self):
        """Test complete form workflow without AI (fallback mode)"""
        validator = AiValidator(use_ai=False, test_mode=True)
        
        field_configs = {
            "name": FieldConfig(name="name", field_type=str, description="Full name", priority=FieldPriority.HIGH, required=True),
            "age": FieldConfig(name="age", field_type=int, description="Age", priority=FieldPriority.MEDIUM, required=True),
            "newsletter": FieldConfig(name="newsletter", field_type=bool, description="Newsletter", priority=FieldPriority.LOW, required=True)
        }
        
        collected_data = {}
        
        # Collect fields with simple inputs (no natural language)
        collected_data["name"] = await validator.validate_field(field_configs["name"], "John Doe", collected_data)
        assert collected_data["name"] == "John Doe"
        
        collected_data["age"] = await validator.validate_field(field_configs["age"], "30", collected_data)
        assert collected_data["age"] == 30
        
        collected_data["newsletter"] = await validator.validate_field(field_configs["newsletter"], "yes", collected_data)
        assert collected_data["newsletter"] is True
        
        # Natural language should fail
        with pytest.raises(ValidationError):
            await validator.validate_field(field_configs["newsletter"], "sure", collected_data)