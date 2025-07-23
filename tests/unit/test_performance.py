"""Performance and boundary tests"""
import pytest
import time
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from unittest.mock import patch

from ai_forms import AIForm, FieldPriority, ConversationMode
from ai_forms.generators.base import QuestionGenerator


class TestPerformanceBasics:
    """Basic performance tests for core operations"""
    
    def test_form_initialization_performance(self):
        """Test form initialization time scales reasonably"""
        class SimpleModel(BaseModel):
            field1: str = Field(description="Field 1")
            field2: str = Field(description="Field 2") 
            field3: str = Field(description="Field 3")
        
        # Time multiple initializations
        start_time = time.time()
        for _ in range(100):
            form = AIForm(SimpleModel)
        end_time = time.time()
        
        # Should initialize 100 forms in well under 1 second
        assert (end_time - start_time) < 1.0
    
    def test_large_model_initialization(self):
        """Test initialization with model containing many fields"""
        # Create model with 100 fields
        fields = {}
        annotations = {}
        
        for i in range(100):
            field_name = f'field_{i}'
            annotations[field_name] = str
            fields[field_name] = Field(
                description=f"Field number {i}",
                json_schema_extra={
                    "priority": FieldPriority.MEDIUM,
                    "examples": [f"example_{i}_{j}" for j in range(3)]
                }
            )
        
        # Dynamically create the model class
        LargeModel = type('LargeModel', (BaseModel,), {
            '__annotations__': annotations,
            **fields
        })
        
        start_time = time.time()
        form = AIForm(LargeModel)
        end_time = time.time()
        
        # Should initialize in reasonable time even with 100 fields
        assert (end_time - start_time) < 2.0
        assert len(form._field_configs) == 100
        assert len(form._field_order) == 100
    
    def test_dependency_calculation_performance(self):
        """Test performance of dependency resolution with complex dependencies"""
        # Create model with chain dependencies
        annotations = {}
        fields = {}
        
        # Create chain: field_0 -> field_1 -> field_2 -> ... -> field_19
        for i in range(20):
            field_name = f'field_{i}'
            annotations[field_name] = str
            
            extra = {"priority": FieldPriority.MEDIUM}
            if i > 0:
                extra["dependencies"] = [f'field_{i-1}']
            
            fields[field_name] = Field(
                description=f"Field {i}",
                json_schema_extra=extra
            )
        
        ChainModel = type('ChainModel', (BaseModel,), {
            '__annotations__': annotations,
            **fields
        })
        
        start_time = time.time()
        form = AIForm(ChainModel)
        end_time = time.time()
        
        # Dependency resolution should be fast
        assert (end_time - start_time) < 1.0
        
        # Verify correct ordering
        expected_order = [f'field_{i}' for i in range(20)]
        assert form._field_order == expected_order
    
    @pytest.mark.asyncio
    async def test_question_generation_performance(self):
        """Test question generation performance"""
        class TestModel(BaseModel):
            field: str = Field(
                description="Test field with long description " * 10,
                json_schema_extra={
                    "examples": [f"example_{i}" for i in range(50)]  # Many examples
                }
            )
        
        form = AIForm(TestModel)
        
        # Time question generation
        start_time = time.time()
        for _ in range(100):
            await form.start()
            form._current_field_index = 0  # Reset for next iteration
        end_time = time.time()
        
        # Should generate 100 questions quickly
        assert (end_time - start_time) < 1.0


class TestScalabilityLimits:
    """Test behavior at scale limits"""
    
    def test_maximum_reasonable_field_count(self):
        """Test with maximum reasonable number of fields"""
        # Test with 500 fields
        annotations = {}
        fields = {}
        
        for i in range(500):
            field_name = f'field_{i:03d}'  # Zero-padded for consistent naming
            annotations[field_name] = str
            fields[field_name] = Field(description=f"Field {i}")
        
        MaxFieldsModel = type('MaxFieldsModel', (BaseModel,), {
            '__annotations__': annotations,
            **fields
        })
        
        # Should handle gracefully
        form = AIForm(MaxFieldsModel)
        assert len(form._field_configs) == 500
        
        # Verify all fields have valid configurations
        for field_name in annotations:
            assert field_name in form._field_configs
            assert form._field_configs[field_name].name == field_name
    
    def test_large_metadata_handling(self):
        """Test handling of fields with large metadata"""
        class LargeMetadataModel(BaseModel):
            field_with_large_metadata: str = Field(
                description="A" * 10000,  # 10KB description
                json_schema_extra={
                    "examples": [f"example_{i}" for i in range(1000)],  # 1000 examples
                    "validation_hint": "B" * 5000,  # 5KB validation hint
                    "large_data": list(range(10000))  # Large data structure
                }
            )
        
        form = AIForm(LargeMetadataModel)
        config = form._field_configs["field_with_large_metadata"]
        
        # Should handle large metadata
        assert len(config.description) == 10000
        assert len(config.examples) == 1000
        assert len(config.validation_hint) == 5000
    
    @pytest.mark.asyncio
    async def test_long_conversation_memory(self):
        """Test memory usage over long conversation"""
        class SimpleModel(BaseModel):
            name: str = Field(description="Name")
            age: int = Field(description="Age")
        
        form = AIForm(SimpleModel)
        await form.start()
        
        # First, provide valid name to get to age field
        response = await form.respond("TestName")
        assert not response.errors
        assert response.current_field == "age"
        
        # Now simulate many validation failures on age field (memory stress test)
        for i in range(100):
            response = await form.respond("invalid age input")
            assert response.errors  # Should consistently fail on age field
            assert response.current_field == "age"  # Should stay on age field
        
        # Should still work after many failures
        response = await form.respond("25")  # Valid age
        assert not response.errors
        assert response.is_complete
        assert len(response.collected_fields) == 2  # Both name and age collected
    
    def test_deeply_nested_dependencies(self):
        """Test deeply nested field dependencies"""
        # Create model with deep dependency chain (50 levels)
        annotations = {}
        fields = {}
        
        for i in range(50):
            field_name = f'level_{i}'
            annotations[field_name] = str
            
            extra = {}
            if i > 0:
                extra["dependencies"] = [f'level_{i-1}']
            
            fields[field_name] = Field(
                description=f"Level {i}",
                json_schema_extra=extra
            )
        
        DeepDepModel = type('DeepDepModel', (BaseModel,), {
            '__annotations__': annotations,
            **fields
        })
        
        # Should resolve deep dependencies without stack overflow
        form = AIForm(DeepDepModel)
        
        # Verify correct ordering
        expected_order = [f'level_{i}' for i in range(50)]
        assert form._field_order == expected_order


class TestMemoryUsage:
    """Test memory-related performance characteristics"""
    
    def test_form_instance_memory_efficiency(self):
        """Test that form instances don't use excessive memory"""
        class SimpleModel(BaseModel):
            field1: str = Field(description="Field 1")
            field2: str = Field(description="Field 2")
        
        # Create many form instances
        forms = []
        for _ in range(1000):
            forms.append(AIForm(SimpleModel))
        
        # Should not consume excessive memory
        # This is more of a smoke test - actual memory profiling would be external
        assert len(forms) == 1000
        
        # Clean up
        del forms
    
    @pytest.mark.asyncio
    async def test_collected_data_memory_growth(self):
        """Test that collected data doesn't grow unexpectedly"""
        class TenFieldModel(BaseModel):
            f1: str = Field(description="Field 1")
            f2: str = Field(description="Field 2")
            f3: str = Field(description="Field 3")
            f4: str = Field(description="Field 4")
            f5: str = Field(description="Field 5")
            f6: str = Field(description="Field 6")
            f7: str = Field(description="Field 7")
            f8: str = Field(description="Field 8")
            f9: str = Field(description="Field 9")
            f10: str = Field(description="Field 10")
        
        form = AIForm(TenFieldModel)
        await form.start()
        
        # Fill all fields
        for i in range(10):
            response = await form.respond(f"value_{i}")
        
        # Collected data should only contain expected fields
        assert len(form._collected_data) == 10
        
        # Each field should contain only the expected value
        for i in range(10):
            field_name = f'f{i+1}'
            assert form._collected_data[field_name] == f"value_{i}"
    
    def test_configuration_memory_efficiency(self):
        """Test that field configurations are memory efficient"""
        class ConfigModel(BaseModel):
            field: str = Field(description="Test field")
        
        # Multiple forms with same model should share immutable data efficiently
        forms = [AIForm(ConfigModel) for _ in range(100)]
        
        # All forms should have equivalent but separate configurations
        for form in forms:
            assert len(form._field_configs) == 1
            assert "field" in form._field_configs


class TestAsyncPerformance:
    """Test asynchronous operation performance"""
    
    @pytest.mark.asyncio
    async def test_concurrent_form_operations(self):
        """Test multiple forms operating concurrently"""
        class SimpleModel(BaseModel):
            name: str = Field(description="Name")
            age: int = Field(description="Age")
        
        # Create multiple forms
        forms = [AIForm(SimpleModel) for _ in range(10)]
        
        # Start all forms concurrently
        start_time = time.time()
        start_tasks = [form.start() for form in forms]
        responses = await asyncio.gather(*start_tasks)
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 1.0
        assert len(responses) == 10
        assert all(not response.is_complete for response in responses)
        assert all(response.question is not None for response in responses)
    
    @pytest.mark.asyncio
    async def test_rapid_successive_responses(self):
        """Test rapid successive responses to same form"""
        class ThreeFieldModel(BaseModel):
            f1: str = Field(description="Field 1")
            f2: str = Field(description="Field 2")
            f3: str = Field(description="Field 3")
        
        form = AIForm(ThreeFieldModel)
        await form.start()
        
        # Rapid successive responses
        start_time = time.time()
        response1 = await form.respond("value1")
        response2 = await form.respond("value2")
        response3 = await form.respond("value3")
        end_time = time.time()
        
        # Should complete quickly
        assert (end_time - start_time) < 0.5
        assert response3.is_complete
        assert response3.data.f1 == "value1"
        assert response3.data.f2 == "value2"
        assert response3.data.f3 == "value3"
    
    @pytest.mark.asyncio
    async def test_question_generator_async_performance(self):
        """Test async question generator performance"""
        class SlowGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                # Simulate some async work
                await asyncio.sleep(0.01)  # 10ms delay
                return f"Slow question for {field_config.name}"
        
        class SimpleModel(BaseModel):
            field: str = Field(description="Test field")
        
        form = AIForm(SimpleModel, question_generator=SlowGenerator())
        
        # Even with slow generator, should not block excessively
        start_time = time.time()
        response = await form.start()
        end_time = time.time()
        
        assert (end_time - start_time) < 0.1  # Should be close to 10ms
        assert "Slow question" in response.question


class TestResourceCleanup:
    """Test resource cleanup and lifecycle management"""
    
    @pytest.mark.asyncio
    async def test_form_cleanup_after_completion(self):
        """Test that forms clean up properly after completion"""
        class SimpleModel(BaseModel):
            name: str = Field(description="Name")
        
        form = AIForm(SimpleModel)
        await form.start()
        response = await form.respond("Test Name")
        
        assert response.is_complete
        
        # Form should maintain state but not hold unnecessary resources
        assert form._collected_data == {"name": "Test Name"}
        assert form._started is True
    
    def test_multiple_form_lifecycle(self):
        """Test multiple forms through complete lifecycle"""
        class SimpleModel(BaseModel):
            field: str = Field(description="Field")
        
        # Create, use, and discard many forms
        for i in range(100):
            form = AIForm(SimpleModel)
            assert form.model_class == SimpleModel
        
        # Should handle lifecycle efficiently without accumulating resources
    
    @pytest.mark.asyncio
    async def test_exception_cleanup(self):
        """Test cleanup when exceptions occur"""
        class FailingModel(BaseModel):
            field: str = Field(description="Field")
        
        form = AIForm(FailingModel)
        
        # Simulate exception during processing
        try:
            await form.start()
            # Force an exception by corrupting internal state
            form._field_order = None  # type: ignore
            await form.respond("test")
        except (AttributeError, TypeError):
            pass  # Expected
        
        # Form should still be in a reasonable state
        assert form._started is True
        assert form.model_class == FailingModel