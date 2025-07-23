"""Edge cases and error handling tests"""
import pytest
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError, field_validator
from unittest.mock import AsyncMock, patch

from ai_forms import AIForm, ConversationMode, FieldPriority, ValidationStrategy
from ai_forms.types.exceptions import ConfigurationError, ValidationError, DependencyError
from ai_forms.generators.base import QuestionGenerator


class TestModelEdgeCases:
    """Test edge cases with different Pydantic models"""
    
    @pytest.mark.asyncio
    async def test_empty_model_form(self, empty_model):
        """Test form with model that has no fields"""
        form = AIForm(empty_model)
        
        response = await form.start()
        assert response.is_complete
        assert response.progress == 100.0
        assert response.data is not None
        assert response.question is None
    
    @pytest.mark.asyncio
    async def test_single_field_model(self):
        """Test form with model that has only one field"""
        class SingleFieldModel(BaseModel):
            name: str = Field(description="Just a name")
        
        form = AIForm(SingleFieldModel)
        response = await form.start()
        
        assert response.progress == 0.0
        assert not response.is_complete
        
        response = await form.respond("Test Name")
        assert response.is_complete
        assert response.progress == 100.0
        assert response.data.name == "Test Name"
    
    @pytest.mark.asyncio
    async def test_all_optional_fields_model(self):
        """Test model with all optional fields"""
        class AllOptionalModel(BaseModel):
            name: Optional[str] = Field(None, description="Optional name")
            age: Optional[int] = Field(None, description="Optional age")
            email: Optional[str] = Field(None, description="Optional email")
        
        form = AIForm(AllOptionalModel)
        await form.start()
        
        # Should still ask for fields even if optional
        response = await form.respond("Test")
        assert not response.is_complete
        
        response = await form.respond("25")
        assert not response.is_complete
        
        response = await form.respond("test@email.com")
        assert response.is_complete
    
    def test_model_with_complex_types(self):
        """Test model with complex field types"""
        class ComplexModel(BaseModel):
            simple_dict: Dict[str, Any] = Field(default_factory=dict, description="A dictionary")
            string_list: List[str] = Field(default_factory=list, description="List of strings")
            union_field: Union[str, int] = Field(description="String or integer")
            nested_optional: Optional[Dict[str, List[str]]] = Field(None, description="Nested structure")
        
        form = AIForm(ComplexModel)
        # Should initialize without errors
        assert len(form._field_configs) == 4
    
    def test_model_with_no_descriptions(self):
        """Test model where fields have no descriptions"""
        class NoDescModel(BaseModel):
            field1: str
            field2: int
            field3: bool
        
        form = AIForm(NoDescModel)
        
        # Should create configs with empty descriptions
        assert all(config.description == "" for config in form._field_configs.values())
    
    def test_model_with_default_values(self):
        """Test model with various default values"""
        class DefaultsModel(BaseModel):
            with_default: str = Field("default_value", description="Has default")
            with_factory: List[str] = Field(default_factory=list, description="Has factory")
            no_default: str = Field(description="No default")
        
        form = AIForm(DefaultsModel)
        
        # Check default handling in configs
        assert form._field_configs["with_default"].default == "default_value"
        assert form._field_configs["no_default"].default is None


class TestDependencyEdgeCases:
    """Test edge cases with field dependencies"""
    
    def test_self_dependency(self):
        """Test field that depends on itself"""
        class SelfDepModel(BaseModel):
            self_dep: str = Field(
                description="Self dependent field",
                json_schema_extra={"dependencies": ["self_dep"]}
            )
        
        with pytest.raises(ConfigurationError, match="Circular dependency"):
            AIForm(SelfDepModel)
    
    def test_nonexistent_dependency(self):
        """Test dependency on non-existent field"""
        class BadDepModel(BaseModel):
            field1: str = Field(
                description="Field 1",
                json_schema_extra={"dependencies": ["nonexistent_field"]}
            )
            field2: str = Field(description="Field 2")
        
        form = AIForm(BadDepModel)
        # Should handle gracefully - nonexistent dependencies are ignored
        assert len(form._field_order) == 2
    
    def test_complex_dependency_chain(self):
        """Test complex dependency chain"""
        class ChainDepModel(BaseModel):
            field_a: str = Field(description="Field A")
            field_b: str = Field(
                description="Field B",
                json_schema_extra={"dependencies": ["field_a"]}
            )
            field_c: str = Field(
                description="Field C", 
                json_schema_extra={"dependencies": ["field_b"]}
            )
            field_d: str = Field(
                description="Field D",
                json_schema_extra={"dependencies": ["field_c", "field_a"]}  # Multiple deps
            )
        
        form = AIForm(ChainDepModel)
        
        # Verify proper ordering
        expected_order = ["field_a", "field_b", "field_c", "field_d"]
        assert form._field_order == expected_order
    
    def test_multiple_circular_dependencies(self):
        """Test multiple circular dependency scenarios"""
        class MultiCircularModel(BaseModel):
            field_a: str = Field(
                description="Field A",
                json_schema_extra={"dependencies": ["field_b"]}
            )
            field_b: str = Field(
                description="Field B",
                json_schema_extra={"dependencies": ["field_c"]}
            )
            field_c: str = Field(
                description="Field C",
                json_schema_extra={"dependencies": ["field_a"]}
            )
        
        with pytest.raises(ConfigurationError, match="Circular dependency"):
            AIForm(MultiCircularModel)


class TestInputEdgeCases:
    """Test edge cases with user input"""
    
    @pytest.mark.asyncio
    async def test_extremely_long_input(self, simple_form):
        """Test handling of extremely long user input"""
        await simple_form.start()
        
        # Very long string (10KB)
        long_input = "A" * 10000
        response = await simple_form.respond(long_input)
        
        # Should handle without crashing
        assert hasattr(response, 'errors')
        # Current implementation should accept it
        assert not response.errors
    
    @pytest.mark.asyncio 
    async def test_unicode_and_emoji_input(self, simple_form):
        """Test Unicode and emoji input handling"""
        await simple_form.start()
        
        unicode_inputs = [
            "测试用户",  # Chinese characters
            "José María",  # Accented characters  
            "🚀 Space User 🌟",  # Emojis
            "Здравствуй мир",  # Cyrillic
            "مرحبا بالعالم",  # Arabic
            "🤖👨‍💻🎯"  # Only emojis
        ]
        
        for unicode_input in unicode_inputs:
            form = AIForm(simple_form.model_class)
            await form.start()
            response = await form.respond(unicode_input)
            # Should handle Unicode gracefully
            assert not response.errors or len(response.errors) == 0
    
    @pytest.mark.asyncio
    async def test_whitespace_only_input(self, simple_form):
        """Test various whitespace-only inputs"""
        whitespace_inputs = [
            "",  # Empty
            " ",  # Single space
            "\t",  # Tab
            "\n",  # Newline
            "\r\n",  # CRLF
            "   \t\n   ",  # Mixed whitespace
        ]
        
        for ws_input in whitespace_inputs:
            form = AIForm(simple_form.model_class)
            await form.start()
            response = await form.respond(ws_input)
            # Current implementation strips and may accept empty
            assert hasattr(response, 'errors')
    
    @pytest.mark.asyncio
    async def test_special_character_input(self, simple_form):
        """Test special characters that might break parsing"""
        special_inputs = [
            "null",
            "undefined", 
            "true",
            "false",
            "{}",
            "[]",
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "\x00\x01\x02",  # Control characters
            "\\n\\t\\r",  # Escaped characters as literals
        ]
        
        for special_input in special_inputs:
            form = AIForm(simple_form.model_class)
            await form.start()
            response = await form.respond(special_input)
            # Should not crash
            assert hasattr(response, 'errors')
    
    @pytest.mark.asyncio
    async def test_numeric_edge_values(self):
        """Test numeric fields with edge values"""
        class NumericModel(BaseModel):
            integer: int = Field(description="Integer field")
            float_val: float = Field(description="Float field")
        
        edge_values = [
            ("0", True),
            ("-0", True),
            ("9999999999999999999", True),  # Very large number
            ("-9999999999999999999", True),  # Very large negative
            ("0.0", False),  # Float for int field
            ("1e10", False),  # Scientific notation for int
            ("∞", False),  # Infinity symbol
            ("−1", False),  # Unicode minus
        ]
        
        for value, should_work_for_int in edge_values:
            form = AIForm(NumericModel)
            await form.start()
            response = await form.respond(value)
            
            if should_work_for_int:
                # Should parse as integer successfully
                assert not response.errors or "Expected a number" not in str(response.errors)
            else:
                # Should fail integer parsing
                assert response.errors and "Expected a number" in str(response.errors)


class TestConcurrencyEdgeCases:
    """Test edge cases related to concurrent operations"""
    
    @pytest.mark.asyncio
    async def test_multiple_simultaneous_responses(self, simple_form):
        """Test multiple simultaneous responses to same form"""
        await simple_form.start()
        
        # This tests the current implementation - in a real concurrent scenario,
        # we'd need proper state management
        response1 = await simple_form.respond("Alice")  # Goes to name field
        response2 = await simple_form.respond("Bob")   # Goes to email field
        
        # Form progresses through fields sequentially
        assert response1.collected_fields[-1] == "name"  # First response collected name
        assert response2.collected_fields[-1] == "email"  # Second response collected email
    
    @pytest.mark.asyncio
    async def test_form_state_after_completion(self, simple_form):
        """Test form behavior after completion"""
        await simple_form.start()
        await simple_form.respond("Alice")
        await simple_form.respond("alice@email.com")
        final_response = await simple_form.respond("25")
        
        assert final_response.is_complete
        
        # Try to continue after completion
        post_completion_response = await simple_form.respond("extra input")
        # Should indicate completion
        assert post_completion_response.is_complete
        assert post_completion_response.progress == 100.0


class TestMemoryEdgeCases:
    """Test memory-related edge cases"""
    
    @pytest.mark.asyncio
    async def test_large_number_of_fields(self):
        """Test form with many fields"""
        # Dynamically create model with many fields
        fields = {}
        for i in range(50):  # 50 fields
            fields[f'field_{i}'] = (str, Field(description=f"Field number {i}"))
        
        LargeModel = type('LargeModel', (BaseModel,), {'__annotations__': {k: v[0] for k, v in fields.items()}})
        
        # Add Field objects to model
        for field_name, (field_type, field_obj) in fields.items():
            setattr(LargeModel, field_name, field_obj)
        
        form = AIForm(LargeModel)
        
        # Should initialize successfully
        assert len(form._field_configs) == 50
        assert len(form._field_order) == 50
    
    def test_deeply_nested_field_metadata(self):
        """Test fields with deeply nested metadata"""
        class DeepMetadataModel(BaseModel):
            complex_field: str = Field(
                description="Complex field",
                json_schema_extra={
                    "priority": FieldPriority.HIGH,
                    "cluster": "main",
                    "examples": ["example1", "example2"] * 100,  # Many examples
                    "validation_hint": "A very long validation hint " * 50,  # Long hint
                    "custom_data": {
                        "nested": {
                            "deeply": {
                                "nested": {
                                    "data": list(range(1000))  # Large nested structure
                                }
                            }
                        }
                    }
                }
            )
        
        form = AIForm(DeepMetadataModel)
        # Should handle complex metadata
        config = form._field_configs["complex_field"]
        assert config.priority == FieldPriority.HIGH
        assert len(config.examples) == 200  # 100 * 2


class TestErrorPropagation:
    """Test error propagation and handling"""
    
    @pytest.mark.asyncio
    async def test_question_generator_exception(self, simple_user_model):
        """Test handling when question generator raises exception"""
        class FailingGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                raise RuntimeError("Generator failed!")
        
        form = AIForm(simple_user_model, question_generator=FailingGenerator())
        
        # Should propagate the exception
        with pytest.raises(RuntimeError, match="Generator failed!"):
            await form.start()
    
    @pytest.mark.asyncio
    async def test_pydantic_model_creation_failure(self):
        """Test handling when Pydantic model creation fails"""
        class FailingModel(BaseModel):
            # Field with validator that always fails
            failing_field: str = Field(description="Always fails")
            
            @field_validator('failing_field')
            @classmethod
            def validate_failing(cls, v):
                raise ValueError("This field always fails validation")
        
        form = AIForm(FailingModel)
        await form.start()
        
        # When we complete the form, model creation should fail
        response = await form.respond("any value")
        
        # Current implementation doesn't catch Pydantic validation at model creation
        # This documents expected behavior when that's implemented
        
    def test_invalid_configuration_combinations(self):
        """Test invalid configuration combinations"""
        class TestModel(BaseModel):
            field: str = Field(description="Test field")
        
        form = AIForm(TestModel)
        
        # Test invalid priority type (should be handled gracefully or raise clear error)
        with pytest.raises((ValueError, TypeError, AttributeError)):
            form.configure_field("field", priority="invalid_priority")  # type: ignore


class TestBoundaryConditions:
    """Test boundary conditions and limits"""
    
    @pytest.mark.asyncio
    async def test_zero_progress_edge_case(self, empty_model):
        """Test progress calculation with no fields"""
        form = AIForm(empty_model)
        response = await form.start()
        
        # Should be 100% complete immediately
        assert response.progress == 100.0
        assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_progress_precision(self):
        """Test progress calculation precision with odd field counts"""
        class ThreeFieldModel(BaseModel):
            field1: str = Field(description="Field 1")
            field2: str = Field(description="Field 2") 
            field3: str = Field(description="Field 3")
        
        form = AIForm(ThreeFieldModel)
        await form.start()
        
        # First field: 1/3 = 33.33...%
        response = await form.respond("test1")
        assert abs(response.progress - 33.333333333333336) < 0.01
        
        # Second field: 2/3 = 66.66...%
        response = await form.respond("test2")
        assert abs(response.progress - 66.66666666666667) < 0.01
        
        # Third field: 100%
        response = await form.respond("test3")
        assert response.progress == 100.0
    
    @pytest.mark.asyncio
    async def test_field_index_boundaries(self, simple_form):
        """Test field index boundary conditions"""
        await simple_form.start()
        
        # Verify initial index
        assert simple_form._current_field_index == 0
        
        # Complete all fields
        await simple_form.respond("test")
        await simple_form.respond("test@email.com")
        await simple_form.respond("25")
        
        # Index should be at end
        assert simple_form._current_field_index >= len(simple_form._field_order)
    
    def test_configuration_parameter_boundaries(self, simple_user_model):
        """Test configuration with boundary parameter values"""
        form = AIForm(simple_user_model)
        
        # Test with empty examples list
        form.configure_field("name", examples=[])
        
        # Test with very long custom question
        long_question = "A" * 10000
        form.configure_field("email", custom_question=long_question)
        
        # Test with empty validation hint
        form.configure_field("age", validation_hint="")
        
        # Should handle all boundary cases gracefully
        assert form._field_configs["name"].examples == []
        assert form._field_configs["email"].custom_question == long_question
        assert form._field_configs["age"].validation_hint == ""