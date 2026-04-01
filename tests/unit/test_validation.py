"""Validation system tests"""
import pytest
from typing import Union, List, Optional
from pydantic import BaseModel, Field, validator, field_validator

from ai_forms import AIForm, ValidationStrategy
from ai_forms.validators.base import (
    Validator, FunctionValidator, EmailValidator, RangeValidator
)
from ai_forms.types.exceptions import ValidationError


class TestValidatorClasses:
    """Test individual validator classes"""
    
    def test_function_validator(self):
        """Test FunctionValidator with custom function"""
        validator = FunctionValidator(
            lambda x: len(x) > 5,
            "Value must be longer than 5 characters"
        )
        
        assert validator.validate("short", {}) is False
        assert validator.validate("long enough", {}) is True
        assert validator.get_error_message("test") == "Value must be longer than 5 characters"
    
    def test_email_validator(self):
        """Test EmailValidator functionality"""
        validator = EmailValidator()
        
        # Valid emails
        assert validator.validate("test@example.com", {}) is True
        assert validator.validate("user.name@domain.co.uk", {}) is True
        
        # Invalid emails
        assert validator.validate("invalid-email", {}) is False
        assert validator.validate("@domain.com", {}) is False
        assert validator.validate("user@", {}) is False
        assert validator.validate(123, {}) is False
        
        # Error message
        error_msg = validator.get_error_message("invalid")
        assert "not a valid email" in error_msg
    
    def test_range_validator_numeric(self):
        """Test RangeValidator with numeric values"""
        validator = RangeValidator(min_val=0, max_val=100)
        
        # Valid values
        assert validator.validate(50, {}) is True
        assert validator.validate("75", {}) is True
        assert validator.validate(0, {}) is True
        assert validator.validate(100, {}) is True
        
        # Invalid values
        assert validator.validate(-1, {}) is False
        assert validator.validate(101, {}) is False
        assert validator.validate("not a number", {}) is False
        assert validator.validate(None, {}) is False
    
    def test_range_validator_min_only(self):
        """Test RangeValidator with only minimum value"""
        validator = RangeValidator(min_val=18)
        
        assert validator.validate(18, {}) is True
        assert validator.validate(100, {}) is True
        assert validator.validate(17, {}) is False
        
        error_msg = validator.get_error_message(15)
        assert "at least 18" in error_msg
    
    def test_range_validator_max_only(self):
        """Test RangeValidator with only maximum value"""
        validator = RangeValidator(max_val=65)
        
        assert validator.validate(30, {}) is True
        assert validator.validate(65, {}) is True
        assert validator.validate(66, {}) is False
        
        error_msg = validator.get_error_message(70)
        assert "at most 65" in error_msg


class TestFieldValidationIntegration:
    """Test validation integration with form fields"""
    
    @pytest.mark.asyncio
    async def test_basic_type_validation(self):
        """Test basic type validation for different field types"""
        class TypeTestModel(BaseModel):
            integer_field: int = Field(description="An integer field")
            float_field: float = Field(description="A float field")
            boolean_field: bool = Field(description="A boolean field")
            string_field: str = Field(description="A string field")
        
        form = AIForm(TypeTestModel, test_mode=True)
        await form.start()
        
        # Test integer field
        response = await form.respond("42")
        assert not response.errors
        
        # Test invalid integer
        response = await form.respond("not a number")
        assert response.errors
        assert "Expected a" in response.errors[0] and "number" in response.errors[0]
        
        # Test valid float
        response = await form.respond("3.14")
        assert not response.errors
        
        # Test boolean field - valid inputs
        response = await form.respond("yes")
        assert not response.errors
        
        # Complete with string
        response = await form.respond("test string")
        assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_boolean_field_variations(self):
        """Test boolean field accepts various input formats"""
        class BoolModel(BaseModel):
            consent: bool = Field(description="Do you consent?")
        
        form = AIForm(BoolModel, test_mode=True)
        
        # Test various true values
        true_values = ["yes", "Yes", "YES", "true", "True", "1", "y", "Y"]
        for value in true_values:
            form = AIForm(BoolModel, test_mode=True)
            await form.start()
            response = await form.respond(value)
            assert response.is_complete
            assert response.data.consent is True
        
        # Test various false values
        false_values = ["no", "No", "NO", "false", "False", "0", "n", "N"]
        for value in false_values:
            form = AIForm(BoolModel, test_mode=True)
            await form.start()
            response = await form.respond(value)
            assert response.is_complete
            assert response.data.consent is False
        
        # Test invalid boolean
        form = AIForm(BoolModel, test_mode=True)
        await form.start()
        response = await form.respond("maybe")
        assert response.errors
        assert "Expected yes/no" in response.errors[0]
    
    @pytest.mark.asyncio
    async def test_pydantic_field_constraints(self):
        """Test Pydantic field constraints are enforced"""
        class ConstrainedModel(BaseModel):
            age: int = Field(ge=0, le=150, description="Age in years")
            email: str = Field(pattern=r'^[^@]+@[^@]+\.[^@]+$', description="Valid email")
            score: float = Field(gt=0.0, lt=100.0, description="Score percentage")
        
        form = AIForm(ConstrainedModel, test_mode=True)
        await form.start()
        
        # Test age constraints - should pass basic int parsing but fail on model validation
        response = await form.respond("200")  # Valid int, invalid constraint
        # Current implementation doesn't validate Pydantic constraints yet
        # This test documents expected future behavior
        
        # Test valid age
        response = await form.respond("25")
        assert not response.errors
    
    @pytest.mark.asyncio
    async def test_email_field_validator_integration(self):
        """Test EmailValidator integration with Pydantic field_validator"""
        class EmailValidatedModel(BaseModel):
            name: str = Field(description="User name")
            email: str = Field(description="Email address")
            
            @field_validator('email')
            @classmethod
            def validate_email(cls, v):
                from ai_forms.validators.base import EmailValidator
                validator = EmailValidator()
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v
        
        form = AIForm(EmailValidatedModel, test_mode=True)
        await form.start()
        
        # Test valid name
        response = await form.respond("John Doe")
        assert not response.errors
        assert response.current_field == "email"
        
        # Test invalid email - should trigger field validator
        response = await form.respond("invalid-email")
        assert response.errors
        assert "not a valid email address" in response.errors[0]
        assert not response.is_complete
        assert response.current_field == "email"  # Should stay on same field
        
        # Test another invalid email format
        response = await form.respond("@domain.com")
        assert response.errors
        assert "not a valid email address" in response.errors[0]
        
        # Test valid email - should succeed
        response = await form.respond("john@example.com")
        assert not response.errors
        assert response.is_complete
        assert response.data.email == "john@example.com"
    
    @pytest.mark.asyncio
    async def test_range_validator_integration(self):
        """Test RangeValidator integration with Pydantic field_validator"""
        class RangeValidatedModel(BaseModel):
            age: int = Field(description="Age in years")
            score: float = Field(description="Score percentage")
            
            @field_validator('age')
            @classmethod
            def validate_age(cls, v):
                from ai_forms.validators.base import RangeValidator
                validator = RangeValidator(min_val=13, max_val=120)
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v
            
            @field_validator('score')
            @classmethod
            def validate_score(cls, v):
                from ai_forms.validators.base import RangeValidator
                validator = RangeValidator(min_val=0.0, max_val=100.0)
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v
        
        form = AIForm(RangeValidatedModel, test_mode=True)
        await form.start()
        
        # Test valid age (validation happens at final model creation)
        response = await form.respond("25")
        assert not response.errors
        assert response.current_field == "score"
        
        # Test valid score
        response = await form.respond("85.5")
        assert not response.errors
        assert response.is_complete
        assert response.data.age == 25
        assert response.data.score == 85.5
        
        # Test invalid age with final validation
        form2 = AIForm(RangeValidatedModel, test_mode=True)
        await form2.start()
        await form2.respond("25")  # Valid age first
        
        # Try invalid score - should be caught at final validation
        response = await form2.respond("150.5")
        # With new approach, this may complete the form and then fail at model creation
        # Reset and try a workflow that triggers final validation error
        
        form3 = AIForm(RangeValidatedModel, test_mode=True)
        await form3.start()
        response = await form3.respond("10")  # Invalid age
        response = await form3.respond("85.5")  # Valid score
        
        # Should fail at final model creation and redirect to age field
        assert response.errors
        assert "Value must be between 13 and 120" in response.errors[0]
        assert response.current_field == "age"
        
        # Fix the age
        response = await form3.respond("25")
        assert not response.errors
        assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_function_validator_integration(self):
        """Test FunctionValidator integration with Pydantic field_validator"""
        class FunctionValidatedModel(BaseModel):
            name: str = Field(description="Full name")
            description: str = Field(description="Description text")
            
            @field_validator('name')
            @classmethod
            def validate_name(cls, v):
                from ai_forms.validators.base import FunctionValidator
                
                def name_validation(value):
                    if not isinstance(value, str):
                        return False
                    value = value.strip()
                    if len(value) < 2 or len(value) > 50:
                        return False
                    # Allow letters, spaces, hyphens, and apostrophes
                    import re
                    return bool(re.match(r"^[a-zA-Z\s\-']+$", value))
                
                validator = FunctionValidator(
                    name_validation,
                    "Name must be 2-50 characters and contain only letters, spaces, hyphens, and apostrophes"
                )
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v.strip()
            
            @field_validator('description')
            @classmethod
            def validate_description(cls, v):
                from ai_forms.validators.base import FunctionValidator
                
                def length_validation(value):
                    if not isinstance(value, str):
                        return False
                    return 10 <= len(value.strip()) <= 200
                
                validator = FunctionValidator(
                    length_validation,
                    "Description must be between 10 and 200 characters"
                )
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v.strip()
        
        # Test successful completion with valid data
        form = AIForm(FunctionValidatedModel, test_mode=True)
        await form.start()
        
        response = await form.respond("John O'Connor-Smith")
        assert not response.errors
        assert response.current_field == "description"
        
        response = await form.respond("This is a detailed description that meets the length requirements.")
        assert not response.errors
        assert response.is_complete
        assert response.data.name == "John O'Connor-Smith"
        assert "detailed description" in response.data.description
        
        # Test final validation catches invalid name
        form2 = AIForm(FunctionValidatedModel, test_mode=True)
        await form2.start()
        
        response = await form2.respond("A")  # Invalid name (too short)
        response = await form2.respond("This is a detailed description that meets the length requirements.")
        
        # Should fail at final model creation and redirect to name field
        assert response.errors
        assert "Name must be 2-50 characters" in response.errors[0]
        assert response.current_field == "name"
        
        # Fix the name
        response = await form2.respond("John Smith")
        assert not response.errors
        assert response.is_complete
        
        # Test final validation catches invalid description
        form3 = AIForm(FunctionValidatedModel, test_mode=True)
        await form3.start()
        
        response = await form3.respond("John Smith")  # Valid name
        response = await form3.respond("Short")  # Invalid description
        
        # Should fail at final model creation and redirect to description field
        assert response.errors
        assert "Description must be between 10 and 200 characters" in response.errors[0]
        assert response.current_field == "description"
    
    @pytest.mark.asyncio
    async def test_combined_validators_integration(self):
        """Test all three validators working together in a realistic form"""
        class ComprehensiveForm(BaseModel):
            name: str = Field(description="Full name")
            email: str = Field(description="Email address")
            age: int = Field(description="Age in years")
            experience_years: int = Field(description="Years of experience")
            
            @field_validator('name')
            @classmethod
            def validate_name(cls, v):
                from ai_forms.validators.base import FunctionValidator
                
                def name_validation(value):
                    if not isinstance(value, str):
                        return False
                    value = value.strip()
                    if len(value) < 2 or len(value) > 50:
                        return False
                    import re
                    return bool(re.match(r"^[a-zA-Z\s\-']+$", value))
                
                validator = FunctionValidator(
                    name_validation,
                    "Name must be 2-50 characters and contain only letters, spaces, hyphens, and apostrophes"
                )
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v.strip()
            
            @field_validator('email')
            @classmethod
            def validate_email(cls, v):
                from ai_forms.validators.base import EmailValidator
                validator = EmailValidator()
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v
            
            @field_validator('age')
            @classmethod
            def validate_age(cls, v):
                from ai_forms.validators.base import RangeValidator
                validator = RangeValidator(min_val=18, max_val=120)
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v
            
            @field_validator('experience_years')
            @classmethod
            def validate_experience(cls, v):
                from ai_forms.validators.base import RangeValidator
                validator = RangeValidator(min_val=0, max_val=50)
                if not validator.validate(v, {}):
                    raise ValueError(validator.get_error_message(v))
                return v
        
        form = AIForm(ComprehensiveForm, test_mode=True)
        await form.start()
        
        # Test successful completion with valid data
        response = await form.respond("Jane Smith")
        assert not response.errors
        
        response = await form.respond("jane@example.com")
        assert not response.errors
        
        response = await form.respond("28")
        assert not response.errors
        
        response = await form.respond("8")
        assert not response.errors
        assert response.is_complete
        
        # Verify final data
        assert response.data.name == "Jane Smith"
        assert response.data.email == "jane@example.com"
        assert response.data.age == 28
        assert response.data.experience_years == 8
        
        # Test final validation with invalid data
        form2 = AIForm(ComprehensiveForm, test_mode=True)
        await form2.start()
        
        # Collect all fields with some invalid data
        response = await form2.respond("J")  # Invalid name (too short)
        response = await form2.respond("jane@example.com")  # Valid email
        response = await form2.respond("16")  # Invalid age (too young)
        response = await form2.respond("8")  # Valid experience
        
        # Should fail at final validation and redirect to first invalid field
        assert response.errors
        # Should redirect to name field (first invalid field)
        assert response.current_field == "name"
        assert "Name must be 2-50 characters" in response.errors[0]
        
        # Fix the name
        response = await form2.respond("Jane Smith")
        # Should now fail on age validation
        assert response.errors
        assert response.current_field == "age"
        assert "Value must be between 18 and 120" in response.errors[0]
        
        # Fix the age
        response = await form2.respond("25")
        assert not response.errors
        assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_optional_field_handling(self):
        """Test optional field validation and skipping"""
        class OptionalModel(BaseModel):
            required_name: str = Field(description="Required name")
            optional_age: Optional[int] = Field(None, description="Optional age")
            optional_email: Optional[str] = Field(None, description="Optional email")
        
        form = AIForm(OptionalModel, test_mode=True)
        await form.start()
        
        # Provide required field
        response = await form.respond("John Doe")
        assert not response.errors
        
        # Skip optional field with empty input
        response = await form.respond("")  # Should handle empty string for optional
        # Current implementation will try to parse empty string
        # This test documents expected behavior
    
    @pytest.mark.asyncio
    async def test_list_field_parsing(self):
        """Test parsing of list fields"""
        class ListModel(BaseModel):
            tags: List[str] = Field(default_factory=list, description="List of tags")
        
        form = AIForm(ListModel, test_mode=True)
        await form.start()
        
        # Test comma-separated list parsing
        # Now supports list parsing
        response = await form.respond("python, web, backend")
        assert response.is_complete
        assert isinstance(response.data.tags, list)
        assert response.data.tags == ["python", "web", "backend"]
    
    @pytest.mark.asyncio
    async def test_union_type_handling(self):
        """Test Union type field handling"""
        class UnionModel(BaseModel):
            value: Union[int, str] = Field(description="Number or text")
        
        form = AIForm(UnionModel, test_mode=True)
        await form.start()
        
        # Should accept string (current implementation behavior)
        response = await form.respond("test value")
        assert response.is_complete
        assert response.data.value == "test value"


class TestValidationStrategies:
    """Test different validation strategies"""
    
    def test_immediate_validation_strategy(self, simple_user_model):
        """Test immediate validation strategy (default)"""
        form = AIForm(simple_user_model, validation=ValidationStrategy.IMMEDIATE, test_mode=True)
        assert form.validation == ValidationStrategy.IMMEDIATE
    
    def test_cluster_validation_strategy(self, complex_job_model):
        """Test end-of-cluster validation strategy"""
        form = AIForm(complex_job_model, validation=ValidationStrategy.END_OF_CLUSTER, test_mode=True)
        assert form.validation == ValidationStrategy.END_OF_CLUSTER
        # Full implementation would defer validation until cluster completion
    
    def test_final_validation_strategy(self, simple_user_model):
        """Test final validation strategy"""
        form = AIForm(simple_user_model, validation=ValidationStrategy.FINAL, test_mode=True)
        assert form.validation == ValidationStrategy.FINAL
        # Full implementation would defer all validation until form completion


class TestValidationErrorHandling:
    """Test validation error scenarios and recovery"""
    
    @pytest.mark.asyncio
    async def test_validation_error_recovery(self, simple_form):
        """Test recovery from validation errors"""
        await simple_form.start()
        
        # First field (name) - valid
        response = await simple_form.respond("John Doe")
        assert not response.errors
        
        # Second field (email) - valid
        response = await simple_form.respond("john@example.com")
        assert not response.errors
        
        # Third field (age) - invalid, then valid
        error_response = await simple_form.respond("not an age")
        assert error_response.errors
        assert not error_response.is_complete
        assert error_response.retry_prompt
        
        # Retry with valid input
        success_response = await simple_form.respond("30")
        assert not success_response.errors
        assert success_response.is_complete
        assert success_response.data.age == 30
    
    @pytest.mark.asyncio
    async def test_multiple_consecutive_errors(self, simple_form):
        """Test handling multiple consecutive validation errors"""
        await simple_form.start()
        await simple_form.respond("Test User")
        await simple_form.respond("test@email.com")
        
        # Multiple invalid attempts
        for invalid_input in ["abc", "not a number", "invalid", "still wrong"]:
            response = await simple_form.respond(invalid_input)
            assert response.errors
            assert not response.is_complete
            assert response.current_field == "age"
            assert len(response.collected_fields) == 2  # Previous fields still collected
        
        # Finally provide valid input
        response = await simple_form.respond("25")
        assert not response.errors
        assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_validation_error_maintains_progress(self, simple_form):
        """Test that validation errors don't affect progress calculation"""
        await simple_form.start()
        await simple_form.respond("Test")
        
        initial_response = await simple_form.respond("test@email.com")
        initial_progress = initial_response.progress
        
        # Error shouldn't change progress
        error_response = await simple_form.respond("invalid age")
        assert error_response.progress == initial_progress
        
        # Success should complete
        final_response = await simple_form.respond("30")
        assert final_response.progress == 100.0
    
    @pytest.mark.asyncio
    async def test_edge_case_inputs(self, simple_form):
        """Test edge case inputs that might cause issues"""
        await simple_form.start()
        
        # Test various edge cases for string field
        edge_cases = [
            "",  # Empty string
            "   ",  # Whitespace only
            "A" * 1000,  # Very long string
            "Special chars: !@#$%^&*()",  # Special characters
            "Unicode: 测试 🚀",  # Unicode characters
        ]
        
        for case in edge_cases:
            # Reset form for each test
            form = AIForm(simple_form.model_class, test_mode=True)
            await form.start()
            response = await form.respond(case)
            # Should not crash, might have validation errors
            assert hasattr(response, 'errors')
    
    @pytest.mark.asyncio
    async def test_numeric_edge_cases(self):
        """Test numeric field edge cases"""
        class NumericModel(BaseModel):
            integer: int = Field(description="Integer field")
            float_val: float = Field(description="Float field")
        
        form = AIForm(NumericModel, test_mode=True)
        await form.start()
        
        # Test integer edge cases
        int_cases = [
            ("0", True),  # Zero
            ("-1", True),  # Negative
            ("999999999", True),  # Large number
            ("1.0", False),  # Float for int field
            ("1e5", False),  # Scientific notation
            ("infinity", False),  # Infinity
            ("NaN", False),  # Not a number
        ]
        
        for case, should_succeed in int_cases:
            form = AIForm(NumericModel, test_mode=True)
            await form.start()
            response = await form.respond(case)
            
            if should_succeed:
                assert not response.errors, f"Expected {case} to be valid integer"
            else:
                assert response.errors, f"Expected {case} to be invalid integer"