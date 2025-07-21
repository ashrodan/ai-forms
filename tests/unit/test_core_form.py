"""Core AIForm class tests"""
import pytest
from typing import Optional
from pydantic import BaseModel, Field

from ai_forms import AIForm, ConversationMode, FieldPriority, ValidationStrategy
from ai_forms.types.exceptions import ConfigurationError, ValidationError


class TestAIFormInitialization:
    """Test AIForm initialization and setup"""
    
    def test_form_initialization_with_simple_model(self, simple_user_model):
        """Test basic form initialization"""
        form = AIForm(simple_user_model)
        
        assert form.model_class == simple_user_model
        assert form.mode == ConversationMode.SEQUENTIAL
        assert form.validation == ValidationStrategy.IMMEDIATE
        assert len(form._field_configs) == 3
        assert not form._started
    
    def test_form_initialization_with_modes(self, simple_user_model, all_conversation_modes):
        """Test initialization with different conversation modes"""
        for mode in all_conversation_modes:
            form = AIForm(simple_user_model, mode=mode)
            assert form.mode == mode
    
    def test_form_initialization_with_validation_strategies(self, simple_user_model, all_validation_strategies):
        """Test initialization with different validation strategies"""
        for strategy in all_validation_strategies:
            form = AIForm(simple_user_model, validation=strategy)
            assert form.validation == strategy
    
    def test_form_with_empty_model(self, empty_model):
        """Test form with model that has no fields"""
        form = AIForm(empty_model)
        assert len(form._field_configs) == 0
        assert len(form._field_order) == 0
    
    def test_form_with_circular_dependencies(self, circular_dependency_model):
        """Test that circular dependencies raise ConfigurationError"""
        with pytest.raises(ConfigurationError, match="Circular dependency"):
            AIForm(circular_dependency_model)
    
    def test_field_extraction_from_pydantic_model(self, complex_job_model):
        """Test that field configurations are properly extracted"""
        form = AIForm(complex_job_model)
        
        # Check field configs exist
        assert "applicant_name" in form._field_configs
        assert "email" in form._field_configs
        assert "position" in form._field_configs
        
        # Check metadata extraction
        name_config = form._field_configs["applicant_name"]
        assert name_config.priority == FieldPriority.CRITICAL
        assert name_config.cluster == "identity"
        assert name_config.custom_question == "What's your full legal name?"
        
        # Check dependencies
        exp_config = form._field_configs["experience_years"]
        assert "position" in exp_config.dependencies


class TestAIFormFieldOrdering:
    """Test field ordering logic"""
    
    def test_field_ordering_by_priority(self, simple_user_model):
        """Test fields are ordered by priority"""
        form = (AIForm(simple_user_model)
                .configure_field("age", priority=FieldPriority.CRITICAL)
                .configure_field("name", priority=FieldPriority.LOW)
                .configure_field("email", priority=FieldPriority.HIGH))
        
        # Critical should come first, then high, then low
        expected_order = ["age", "email", "name"]
        assert form._field_order == expected_order
    
    def test_field_ordering_with_dependencies(self, complex_job_model):
        """Test fields respect dependency ordering"""
        form = AIForm(complex_job_model)
        
        # position should come before experience_years due to dependency
        position_idx = form._field_order.index("position")
        experience_idx = form._field_order.index("experience_years")
        assert position_idx < experience_idx
    
    def test_field_ordering_priority_with_dependencies(self):
        """Test priority ordering combined with dependencies"""
        class TestModel(BaseModel):
            low_priority: str = Field(
                description="Low priority field",
                json_schema_extra={"priority": FieldPriority.LOW}
            )
            depends_on_low: str = Field(
                description="Depends on low priority",
                json_schema_extra={
                    "priority": FieldPriority.CRITICAL,
                    "dependencies": ["low_priority"]
                }
            )
        
        form = AIForm(TestModel)
        
        # low_priority must come first despite lower priority due to dependency
        assert form._field_order == ["low_priority", "depends_on_low"]


class TestAIFormConfiguration:
    """Test field configuration API"""
    
    def test_configure_field_fluent_interface(self, simple_user_model):
        """Test fluent configuration interface"""
        form = (AIForm(simple_user_model)
                .configure_field("name", priority=FieldPriority.CRITICAL)
                .configure_field("email", custom_question="What's your email?")
                .configure_field("age", examples=["25", "30", "35"]))
        
        # Verify configurations were applied
        assert form._field_configs["name"].priority == FieldPriority.CRITICAL
        assert form._field_configs["email"].custom_question == "What's your email?"
        assert form._field_configs["age"].examples == ["25", "30", "35"]
    
    def test_configure_nonexistent_field(self, simple_user_model):
        """Test configuring non-existent field raises error"""
        form = AIForm(simple_user_model)
        
        with pytest.raises(ConfigurationError, match="Field 'nonexistent' not found"):
            form.configure_field("nonexistent", priority=FieldPriority.HIGH)
    
    def test_field_reconfiguration_updates_ordering(self, simple_user_model):
        """Test that reconfiguring field priority updates ordering"""
        form = AIForm(simple_user_model)
        original_order = form._field_order.copy()
        
        # Change priority of last field to critical
        last_field = original_order[-1]
        form.configure_field(last_field, priority=FieldPriority.CRITICAL)
        
        # Should now be first
        assert form._field_order[0] == last_field
    
    def test_context_setting(self, simple_user_model):
        """Test context setting functionality"""
        form = AIForm(simple_user_model)
        context = {"user_type": "returning", "source": "mobile"}
        
        form.set_context(context)
        assert form._context["user_type"] == "returning"
        assert form._context["source"] == "mobile"
        
        # Test updating context
        form.set_context({"user_type": "new"})
        assert form._context["user_type"] == "new"
        assert form._context["source"] == "mobile"  # Should remain


class TestAIFormLifecycle:
    """Test form lifecycle and state management"""
    
    @pytest.mark.asyncio
    async def test_form_start(self, simple_form):
        """Test form start functionality"""
        response = await simple_form.start()
        
        assert simple_form._started
        assert simple_form._current_field_index == 0
        assert response.question is not None
        assert not response.is_complete
        assert response.progress == 0.0
        assert response.current_field is not None
        assert len(response.collected_fields) == 0
    
    @pytest.mark.asyncio
    async def test_form_start_empty_model(self, empty_model):
        """Test starting form with empty model"""
        form = AIForm(empty_model)
        response = await form.start()
        
        assert response.is_complete
        assert response.progress == 100.0
        assert response.data is not None
    
    @pytest.mark.asyncio
    async def test_respond_before_start(self, simple_form):
        """Test responding before starting raises error"""
        with pytest.raises(ConfigurationError, match="Form not started"):
            await simple_form.respond("test input")
    
    @pytest.mark.asyncio
    async def test_complete_form_flow(self, simple_form):
        """Test complete form flow"""
        # Start form
        response = await simple_form.start()
        assert response.progress == 0.0
        
        # First response (name)
        response = await simple_form.respond("Alice Johnson")
        assert response.progress > 0
        assert len(response.collected_fields) == 1
        assert not response.is_complete
        
        # Second response (email)
        response = await simple_form.respond("alice@email.com")
        assert response.progress > 33
        assert len(response.collected_fields) == 2
        assert not response.is_complete
        
        # Third response (age)
        response = await simple_form.respond("28")
        assert response.is_complete
        assert response.progress == 100.0
        assert response.data.name == "Alice Johnson"
        assert response.data.email == "alice@email.com"
        assert response.data.age == 28
    
    @pytest.mark.asyncio
    async def test_skip_condition_handling(self, complex_job_model):
        """Test skip condition logic"""
        form = AIForm(complex_job_model)
        await form.start()
        
        # Fill required fields up to experience_years
        await form.respond("John Doe")  # name
        await form.respond("john@email.com")  # email
        await form.respond("Software Engineer")  # position
        await form.respond("1")  # experience_years (< 2, should skip salary)
        
        # Continue until we reach skills or completion
        response = await form.respond("Python, JavaScript")  # skills
        
        # salary_expectation should have been skipped
        assert "salary_expectation" not in form._collected_data
    
    @pytest.mark.asyncio
    async def test_progress_calculation(self, simple_form):
        """Test progress calculation accuracy"""
        await simple_form.start()
        
        # After first field
        response = await simple_form.respond("Test")
        expected_progress = (1 / 3) * 100
        assert abs(response.progress - expected_progress) < 0.1
        
        # After second field
        response = await simple_form.respond("test@email.com")
        expected_progress = (2 / 3) * 100
        assert abs(response.progress - expected_progress) < 0.1
        
        # After final field
        response = await simple_form.respond("25")
        assert response.progress == 100.0


class TestAIFormErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_validation_error_handling(self, simple_form):
        """Test handling of validation errors"""
        await simple_form.start()
        await simple_form.respond("Test Name")
        await simple_form.respond("test@email.com")
        
        # Try invalid age
        response = await simple_form.respond("not a number")
        
        assert len(response.errors) > 0
        assert response.retry_prompt is not None
        assert not response.is_complete
        assert "Expected a number" in response.errors[0]
    
    @pytest.mark.asyncio
    async def test_pydantic_validation_integration(self, simple_user_model):
        """Test integration with Pydantic model validation"""
        class StrictModel(BaseModel):
            age: int = Field(ge=0, le=120, description="Age in years")
        
        form = AIForm(StrictModel)
        await form.start()
        
        # Try age outside valid range
        response = await form.respond("-5")
        
        # Should catch the validation error
        assert len(response.errors) > 0
    
    @pytest.mark.asyncio
    async def test_multiple_validation_attempts(self, simple_form):
        """Test multiple validation failure attempts"""
        await simple_form.start()
        await simple_form.respond("Test")
        await simple_form.respond("test@email.com")
        
        # Multiple invalid attempts
        response1 = await simple_form.respond("invalid age")
        response2 = await simple_form.respond("still invalid")
        response3 = await simple_form.respond("25")
        
        assert len(response1.errors) > 0
        assert len(response2.errors) > 0
        assert response3.is_complete
        assert response3.data.age == 25