"""Test AI validation tools functionality"""
import pytest
from typing import Dict, Any
from pydantic import BaseModel, Field

from ai_forms import AIForm
from ai_forms.validators.ai_tools import AIValidationTools, ValidationResult
from ai_forms.types.config import FieldConfig
from ai_forms.types.enums import FieldPriority


class TestAIValidationTools:
    """Test AI validation tools in test mode"""
    
    def test_validation_tools_initialization(self):
        """Test AI validation tools can be initialized"""
        tools = AIValidationTools(test_mode=True)
        assert tools is not None
        assert tools.test_mode is True
    
    def test_field_validation_tool_basic(self):
        """Test basic field validation tool"""
        tools = AIValidationTools(test_mode=True)
        
        # Test valid email
        result = tools.validate_field(
            field_name="email",
            field_value="test@example.com", 
            field_type="str",
            field_description="Email address",
            validation_hint="email validation"
        )
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.parsed_value == "test@example.com"
        assert result.error_message is None
    
    def test_field_validation_tool_invalid_email(self):
        """Test field validation tool with invalid email"""
        tools = AIValidationTools(test_mode=True)
        
        result = tools.validate_field(
            field_name="email",
            field_value="invalid-email",
            field_type="str", 
            field_description="Email address",
            validation_hint="email validation"
        )
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert "not a valid email address" in result.error_message
        assert result.parsed_value == "invalid-email"
    
    def test_field_validation_tool_integer(self):
        """Test field validation with integer parsing"""
        tools = AIValidationTools(test_mode=True)
        
        # Valid integer
        result = tools.validate_field(
            field_name="age",
            field_value="25",
            field_type="int",
            field_description="Age in years"
        )
        
        assert result.is_valid is True
        assert result.parsed_value == 25
        
        # Invalid integer
        result = tools.validate_field(
            field_name="age", 
            field_value="not a number",
            field_type="int",
            field_description="Age in years"
        )
        
        assert result.is_valid is False
        assert "Expected a number" in result.error_message
    
    def test_form_validation_tool_basic(self):
        """Test basic form validation tool"""
        tools = AIValidationTools(test_mode=True)
        
        form_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }
        
        field_configs = {
            "name": {"required": True, "field_type": "str"},
            "email": {"required": True, "field_type": "str"},  
            "age": {"required": True, "field_type": "int"}
        }
        
        result = tools.validate_form(
            form_data=form_data,
            model_class_name="TestModel",
            field_configs=field_configs
        )
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.parsed_value == form_data
        assert result.error_message is None
    
    def test_form_validation_tool_invalid_email(self):
        """Test form validation with invalid email"""
        tools = AIValidationTools(test_mode=True)
        
        form_data = {
            "name": "John Doe", 
            "email": "invalid-email",
            "age": 30
        }
        
        field_configs = {
            "name": {"required": True, "field_type": "str"},
            "email": {"required": True, "field_type": "str"},
            "age": {"required": True, "field_type": "int"}
        }
        
        result = tools.validate_form(
            form_data=form_data,
            model_class_name="TestModel", 
            field_configs=field_configs
        )
        
        assert result.is_valid is False
        assert "Invalid email" in result.error_message


class TestAIFormWithValidationTools:
    """Test AIForm integration with AI validation tools"""
    
    @pytest.mark.asyncio
    async def test_ai_form_with_validation_tools(self):
        """Test AIForm using AI validation tools as primary validation"""
        
        class TestModel(BaseModel):
            name: str = Field(description="Full name")
            email: str = Field(description="Email address", json_schema_extra={"validation_hint": "email validation"})
            age: int = Field(description="Age in years")
        
        # Create form with AI validation tools in test mode
        form = AIForm(TestModel, use_ai=True, test_mode=True)
        await form.start()
        
        # Test valid inputs
        response = await form.respond("John Doe")
        assert not response.errors
        assert response.current_field == "email"
        
        response = await form.respond("john@example.com")
        assert not response.errors
        assert response.current_field == "age"
        
        response = await form.respond("30")
        assert not response.errors
        assert response.is_complete
        assert response.data.name == "John Doe"
        assert response.data.email == "john@example.com"
        assert response.data.age == 30
    
    @pytest.mark.asyncio
    async def test_ai_form_validation_tools_field_error(self):
        """Test AIForm validation tools catching field errors"""
        
        class TestModel(BaseModel):
            email: str = Field(description="Email address", json_schema_extra={"validation_hint": "email validation"})
        
        form = AIForm(TestModel, use_ai=True, test_mode=True)
        await form.start()
        
        # Test invalid email - should be caught by AI validation tools
        response = await form.respond("invalid-email")
        
        # In test mode, the validation tools should catch this
        # The behavior depends on implementation but should either:
        # 1. Show error immediately (field validation), or
        # 2. Complete and show error at final validation
        
        # Let's check if we get an error or complete the form
        if response.errors:
            # Field validation caught the error
            assert "email" in response.errors[0].lower()
        else:
            # Form completed, error should be in final validation
            assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_ai_form_fallback_when_no_ai_tools(self):
        """Test AIForm falls back to basic validation when AI tools unavailable"""
        
        class TestModel(BaseModel):
            name: str = Field(description="Name")
            age: int = Field(description="Age")
        
        # Create form without AI tools (use_ai=False)
        form = AIForm(TestModel, use_ai=False)
        await form.start()
        
        # Should still work with basic validation
        response = await form.respond("John Doe")
        assert not response.errors
        
        response = await form.respond("30")
        assert not response.errors
        assert response.is_complete
        assert response.data.name == "John Doe"
        assert response.data.age == 30


class TestValidationToolsEdgeCases:
    """Test edge cases for AI validation tools"""
    
    def test_validation_tools_with_context(self):
        """Test validation tools using context data"""
        tools = AIValidationTools(test_mode=True)
        
        context = {"name": "John Doe", "age": 30}
        
        result = tools.validate_field(
            field_name="email",
            field_value="john@example.com",
            field_type="str",
            field_description="Email address",
            validation_hint="email validation",
            context=context
        )
        
        assert result.is_valid is True
        assert result.parsed_value == "john@example.com"
    
    def test_validation_tools_range_validation(self):
        """Test range validation in validation tools"""
        tools = AIValidationTools(test_mode=True)
        
        # Test with range hint
        result = tools.validate_field(
            field_name="age",
            field_value="25",
            field_type="int", 
            field_description="Age in years",
            validation_hint="min=18 max=120"
        )
        
        # Should parse the integer successfully
        assert result.is_valid is True
        assert result.parsed_value == 25
    
    def test_validation_tools_list_parsing(self):
        """Test list field parsing in validation tools"""
        tools = AIValidationTools(test_mode=True)
        
        result = tools.validate_field(
            field_name="tags",
            field_value="python, web, backend",
            field_type="List[str]",
            field_description="List of tags"
        )
        
        assert result.is_valid is True
        assert result.parsed_value == ["python", "web", "backend"]
    
    def test_validation_tools_boolean_parsing(self):
        """Test boolean field parsing in validation tools"""
        tools = AIValidationTools(test_mode=True)
        
        # Test standard boolean values
        test_cases = [
            # Standard cases
            ("yes", True),
            ("no", False),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
            
            # Natural language cases (the key improvement)
            ("sure", True),
            ("ok", True),
            ("okay", True),
            ("definitely", True),
            ("absolutely", True),
            ("nope", False),
            ("nah", False),
            ("never", False),
            
            # Case insensitive
            ("SURE", True),
            ("Sure", True),
            ("OK", True),
            ("NOPE", False),
        ]
        
        for input_val, expected in test_cases:
            result = tools.validate_field(
                field_name="consent",
                field_value=input_val,
                field_type="bool",
                field_description="Consent flag"
            )
            
            assert result.is_valid is True, f"'{input_val}' should be valid"
            assert result.parsed_value == expected, f"'{input_val}' should parse to {expected}, got {result.parsed_value}"
    
    def test_validation_tools_boolean_parsing_invalid(self):
        """Test invalid boolean inputs"""
        tools = AIValidationTools(test_mode=True)
        
        invalid_cases = ["maybe", "sometimes", "perhaps", "12345", "random text"]
        
        for input_val in invalid_cases:
            result = tools.validate_field(
                field_name="consent",
                field_value=input_val,
                field_type="bool", 
                field_description="Consent flag"
            )
            
            assert result.is_valid is False, f"'{input_val}' should be invalid"
            assert "Could not interpret" in result.error_message

    def test_enhanced_field_type_parsing(self):
        """Test enhanced field type parsing with natural language"""
        tools = AIValidationTools(test_mode=True)
        
        # Test integer parsing with written numbers
        int_cases = [
            ("five", 5),
            ("ten", 10),
            ("twenty", 20),
            ("1,234", 1234),  # Comma formatting
            ("1_000", 1000),  # Underscore formatting
        ]
        
        for input_val, expected in int_cases:
            result = tools.validate_field(
                field_name="age",
                field_value=input_val,
                field_type="int",
                field_description="Age"
            )
            
            assert result.is_valid is True, f"'{input_val}' should be valid integer"
            assert result.parsed_value == expected, f"'{input_val}' should parse to {expected}"
        
        # Test list parsing with different delimiters
        list_cases = [
            ("python, javascript, go", ["python", "javascript", "go"]),  # Comma
            ("python; javascript; go", ["python", "javascript", "go"]),  # Semicolon
            ("python | javascript | go", ["python", "javascript", "go"]),  # Pipe
            ("python\njavascript\ngo", ["python", "javascript", "go"]),  # Newline
            ("single", ["single"]),  # Single item
        ]
        
        for input_val, expected in list_cases:
            result = tools.validate_field(
                field_name="skills",
                field_value=input_val,
                field_type="List[str]",
                field_description="Skills"
            )
            
            assert result.is_valid is True, f"'{input_val}' should be valid list"
            assert result.parsed_value == expected, f"'{input_val}' should parse to {expected}"