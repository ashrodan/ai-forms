"""Test form vs direct validation to identify the discrepancy"""
import pytest
import asyncio
from pydantic import BaseModel, Field

from ai_forms import AIForm
from ai_forms.validators.ai_tools import AIValidationTools


class SimpleTestModel(BaseModel):
    """Simple test model with boolean field"""
    newsletter: bool = Field(description="Subscribe to newsletter?")


class TestFormVsDirectValidation:
    """Test to identify why form validation differs from direct validation"""
    
    def test_direct_validation_boolean_sure(self):
        """Test direct validation with 'sure' - should work"""
        tools = AIValidationTools(test_mode=True)
        
        result = tools.validate_field(
            field_name="newsletter",
            field_value="sure",
            field_type="bool",
            field_description="Subscribe to newsletter?"
        )
        
        print(f"Direct validation result: valid={result.is_valid}, value={result.parsed_value}, error={result.error_message}")
        
        assert result.is_valid is True
        assert result.parsed_value is True
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_form_validation_boolean_sure(self):
        """Test form validation with 'sure' - currently failing"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        
        # Check that AI validator is created
        print(f"Form has AI validator: {form.ai_validator is not None}")
        if form.ai_validator:
            print(f"AI validator test mode: {form.ai_validator.test_mode}")
            print(f"AI validator status: {form.ai_validator.status}")
        
        # Start form
        response = await form.start()
        print(f"Initial question: {response.question}")
        
        # Try to respond with 'sure'
        response = await form.respond("sure")
        
        print(f"Form response after 'sure': valid={not response.errors}, errors={response.errors}")
        print(f"Current field: {response.current_field}")
        print(f"Is complete: {response.is_complete}")
        
        if response.errors:
            print(f"Error message: {response.errors[0]}")
            # This should NOT happen if AI validation tools are working properly
            assert False, f"Form validation failed with: {response.errors[0]}"
        else:
            assert response.is_complete is True
            assert response.data.newsletter is True
    
    @pytest.mark.asyncio
    async def test_form_field_parsing_direct_call(self):
        """Test the form's _parse_field_value method directly"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        
        # Get field config
        field_config = form._field_configs['newsletter']
        print(f"Field config: {field_config}")
        
        # Test direct parsing
        try:
            parsed_value = await form._parse_field_value(field_config, "sure")
            print(f"Direct field parsing result: {parsed_value} (type: {type(parsed_value)})")
            assert parsed_value is True
        except Exception as e:
            print(f"Direct field parsing failed: {e}")
            raise
    
    def test_simple_field_parsing_fallback(self):
        """Test that AI validator fallback works when AI is disabled"""
        form = AIForm(SimpleTestModel, use_ai=False, test_mode=True)
        field_config = form._field_configs['newsletter']
        
        # Test the AI validator in non-AI mode (should use simple parsing)
        async def test_fallback():
            try:
                parsed_value = await form.ai_validator.validate_field(field_config, "sure", {})
                print(f"Non-AI validation result: {parsed_value}")
                # This SHOULD fail since simple parsing doesn't understand 'sure'
                assert False, "Non-AI validation should have failed with 'sure'"
            except Exception as e:
                print(f"Non-AI validation correctly failed with: {e}")
                # This is expected - simple parsing should fail with 'sure'
        
        import asyncio
        asyncio.run(test_fallback())
    
    @pytest.mark.asyncio
    async def test_ai_validation_tools_integration(self):
        """Test the AI validator integration in form"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        field_config = form._field_configs['newsletter']
        
        # Test AI validator directly
        if form.ai_validator and form.ai_validator.is_ai_enabled:
            result = await form.ai_validator.validate_field(
                field_config, 
                "sure",
                {}
            )
            print(f"AI validator integration result: {result} (type: {type(result)})")
            assert result is True
        else:
            assert False, "AI validator not created or not enabled"
    
    @pytest.mark.asyncio 
    async def test_parsing_order_issue(self):
        """Test the new simplified parsing with AiValidator"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        field_config = form._field_configs['newsletter']
        
        print("Testing new AiValidator system:")
        
        # 1. Test AI validator directly (should work)
        try:
            ai_result = await form.ai_validator.validate_field(field_config, "sure", {})
            print(f"1. AI validator: {ai_result} (type: {type(ai_result)})")
        except Exception as e:
            print(f"1. AI validator failed: {e}")
        
        # 2. Test the form's _parse_field_value method (should work)
        try:
            form_result = await form._parse_field_value(field_config, "sure")
            print(f"2. Form _parse_field_value: {form_result} (type: {type(form_result)})")
        except Exception as e:
            print(f"2. Form _parse_field_value failed: {e}")
            raise


if __name__ == "__main__":
    # Run the tests manually for debugging
    import asyncio
    
    test_instance = TestFormVsDirectValidation()
    
    print("=== Direct Validation Test ===")
    test_instance.test_direct_validation_boolean_sure()
    
    print("\n=== Simple Field Parsing Test ===")
    test_instance.test_simple_field_parsing_fallback()
    
    print("\n=== Form Validation Test ===")
    asyncio.run(test_instance.test_form_validation_boolean_sure())