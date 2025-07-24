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
        
        # Check that validation tools are created
        print(f"Form has validation tools: {form.validation_tools is not None}")
        if form.validation_tools:
            print(f"Validation tools test mode: {form.validation_tools.test_mode}")
        
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
        """Test the simple parsing fallback that might be interfering"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        field_config = form._field_configs['newsletter']
        
        # Test the simple parsing method
        try:
            parsed_value = form._simple_parse_field_value(field_config, "sure")
            print(f"Simple parsing result: {parsed_value}")
            # This SHOULD fail since simple parsing doesn't understand 'sure'
            assert False, "Simple parsing should have failed with 'sure'"
        except Exception as e:
            print(f"Simple parsing correctly failed with: {e}")
            # This is expected - simple parsing should fail
    
    @pytest.mark.asyncio
    async def test_ai_validation_tools_integration(self):
        """Test the AI validation tools integration in form"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        field_config = form._field_configs['newsletter']
        
        # Test validate_field_with_ai method
        if form.validation_tools:
            result = await form.validation_tools.validate_field_with_ai(
                field_config, 
                "sure",
                {}
            )
            print(f"AI tools integration result: valid={result.is_valid}, value={result.parsed_value}")
            assert result.is_valid is True
            assert result.parsed_value is True
        else:
            assert False, "Validation tools not created"
    
    @pytest.mark.asyncio 
    async def test_parsing_order_issue(self):
        """Test if parsing order is the issue"""
        form = AIForm(SimpleTestModel, use_ai=True, test_mode=True)
        field_config = form._field_configs['newsletter']
        
        print("Testing parsing methods in order:")
        
        # 1. Test AI validation tools first (should work)
        if form.validation_tools:
            try:
                result = await form.validation_tools.validate_field_with_ai(field_config, "sure", {})
                print(f"1. AI validation tools: valid={result.is_valid}, value={result.parsed_value}")
            except Exception as e:
                print(f"1. AI validation tools failed: {e}")
        
        # 2. Test response parser (if available)
        if form.response_parser:
            try:
                parsed = await form.response_parser.parse_response("sure", field_config, {})
                print(f"2. Response parser result: {parsed}")
            except Exception as e:
                print(f"2. Response parser failed: {e}")
        else:
            print("2. No response parser available")
        
        # 3. Test simple parsing (should fail)
        try:
            simple_result = form._simple_parse_field_value(field_config, "sure")
            print(f"3. Simple parsing result: {simple_result}")
        except Exception as e:
            print(f"3. Simple parsing failed (expected): {e}")
        
        # Now test the actual _parse_field_value method
        try:
            final_result = await form._parse_field_value(field_config, "sure")
            print(f"Final _parse_field_value result: {final_result}")
        except Exception as e:
            print(f"Final _parse_field_value failed: {e}")
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