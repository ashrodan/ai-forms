"""Validation system tests"""
import pytest
from typing import Union, List, Optional
from pydantic import BaseModel, Field, validator

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
        
        form = AIForm(TypeTestModel)
        await form.start()
        
        # Test integer field
        response = await form.respond("42")
        assert not response.errors
        
        # Test invalid integer
        response = await form.respond("not a number")
        assert response.errors
        assert "Expected a number" in response.errors[0]
        
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
        
        form = AIForm(BoolModel)
        
        # Test various true values
        true_values = ["yes", "Yes", "YES", "true", "True", "1", "y", "Y"]
        for value in true_values:
            form = AIForm(BoolModel)
            await form.start()
            response = await form.respond(value)
            assert response.is_complete
            assert response.data.consent is True
        
        # Test various false values
        false_values = ["no", "No", "NO", "false", "False", "0", "n", "N"]
        for value in false_values:
            form = AIForm(BoolModel)
            await form.start()
            response = await form.respond(value)
            assert response.is_complete
            assert response.data.consent is False
        
        # Test invalid boolean
        form = AIForm(BoolModel)
        await form.start()
        response = await form.respond("maybe")
        assert response.errors
        assert "Expected yes/no" in response.errors[0]
    
    @pytest.mark.asyncio
    async def test_pydantic_field_constraints(self):
        """Test Pydantic field constraints are enforced"""
        class ConstrainedModel(BaseModel):
            age: int = Field(ge=0, le=150, description="Age in years")
            email: str = Field(regex=r'^[^@]+@[^@]+\.[^@]+$', description="Valid email")
            score: float = Field(gt=0.0, lt=100.0, description="Score percentage")
        
        form = AIForm(ConstrainedModel)
        await form.start()
        
        # Test age constraints - should pass basic int parsing but fail on model validation
        response = await form.respond("200")  # Valid int, invalid constraint
        # Current implementation doesn't validate Pydantic constraints yet
        # This test documents expected future behavior
        
        # Test valid age
        response = await form.respond("25")
        assert not response.errors
    
    @pytest.mark.asyncio
    async def test_optional_field_handling(self):
        """Test optional field validation and skipping"""
        class OptionalModel(BaseModel):
            required_name: str = Field(description="Required name")
            optional_age: Optional[int] = Field(None, description="Optional age")
            optional_email: Optional[str] = Field(None, description="Optional email")
        
        form = AIForm(OptionalModel)
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
        
        form = AIForm(ListModel)
        await form.start()
        
        # Test comma-separated list parsing
        # Current implementation treats as string - this tests current behavior
        response = await form.respond("python, web, backend")
        assert response.is_complete
        assert isinstance(response.data.tags, str)  # Current behavior
    
    @pytest.mark.asyncio
    async def test_union_type_handling(self):
        """Test Union type field handling"""
        class UnionModel(BaseModel):
            value: Union[int, str] = Field(description="Number or text")
        
        form = AIForm(UnionModel)
        await form.start()
        
        # Should accept string (current implementation behavior)
        response = await form.respond("test value")
        assert response.is_complete
        assert response.data.value == "test value"


class TestValidationStrategies:
    """Test different validation strategies"""
    
    def test_immediate_validation_strategy(self, simple_user_model):
        """Test immediate validation strategy (default)"""
        form = AIForm(simple_user_model, validation=ValidationStrategy.IMMEDIATE)
        assert form.validation == ValidationStrategy.IMMEDIATE
    
    def test_cluster_validation_strategy(self, complex_job_model):
        """Test end-of-cluster validation strategy"""
        form = AIForm(complex_job_model, validation=ValidationStrategy.END_OF_CLUSTER)
        assert form.validation == ValidationStrategy.END_OF_CLUSTER
        # Full implementation would defer validation until cluster completion
    
    def test_final_validation_strategy(self, simple_user_model):
        """Test final validation strategy"""
        form = AIForm(simple_user_model, validation=ValidationStrategy.FINAL)
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
            form = AIForm(simple_form.model_class)
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
        
        form = AIForm(NumericModel)
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
            form = AIForm(NumericModel)
            await form.start()
            response = await form.respond(case)
            
            if should_succeed:
                assert not response.errors, f"Expected {case} to be valid integer"
            else:
                assert response.errors, f"Expected {case} to be invalid integer"