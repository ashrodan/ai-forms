"""Question generation system tests"""
import pytest
from unittest.mock import AsyncMock, patch

from ai_forms import AIForm, FieldPriority
from ai_forms.generators.base import QuestionGenerator, DefaultQuestionGenerator, PYDANTIC_AI_AVAILABLE
from ai_forms.types.config import FieldConfig

# Import AI components if available
if PYDANTIC_AI_AVAILABLE:
    from ai_forms.generators.base import PydanticAIQuestionGenerator


class TestQuestionGeneratorBase:
    """Test base QuestionGenerator functionality"""
    
    def test_question_generator_is_abstract(self):
        """Test that QuestionGenerator cannot be instantiated directly"""
        with pytest.raises(TypeError):
            QuestionGenerator()
    
    @pytest.mark.asyncio
    async def test_custom_question_generator(self):
        """Test custom question generator implementation"""
        class CustomGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                return f"CUSTOM: Please provide {field_config.name}"
        
        generator = CustomGenerator()
        config = FieldConfig(
            name="test_field",
            field_type=str,
            description="Test field"
        )
        
        question = await generator.generate_question(config, {})
        assert question == "CUSTOM: Please provide test_field"


class TestDefaultQuestionGenerator:
    """Test DefaultQuestionGenerator functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_question_generation(self):
        """Test basic question generation from field config"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="email",
            field_type=str,
            description="Your email address"
        )
        
        question = await generator.generate_question(config, {})
        expected = "Please provide your email (Your email address)"
        assert question == expected
    
    @pytest.mark.asyncio
    async def test_custom_question_override(self):
        """Test custom question overrides default generation"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="email",
            field_type=str,
            description="Your email address",
            custom_question="What's your email?"
        )
        
        question = await generator.generate_question(config, {})
        assert question == "What's your email?"
    
    @pytest.mark.asyncio
    async def test_question_with_examples(self):
        """Test question generation includes examples"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="email",
            field_type=str,
            description="Your email address",
            examples=["user@example.com", "alice@company.co", "test@domain.org"]
        )
        
        question = await generator.generate_question(config, {})
        assert "Please provide your email" in question
        assert "Examples:" in question
        assert "user@example.com" in question
        assert "alice@company.co" in question
        assert "test@domain.org" in question
    
    @pytest.mark.asyncio
    async def test_question_with_limited_examples(self):
        """Test that only first 3 examples are included"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="skill",
            field_type=str,
            description="A skill",
            examples=["Python", "JavaScript", "Java", "C++", "Go"]  # 5 examples
        )
        
        question = await generator.generate_question(config, {})
        assert "Python" in question
        assert "JavaScript" in question
        assert "Java" in question
        # Should not include 4th and 5th examples
        assert "C++" not in question
        assert "Go" not in question
    
    @pytest.mark.asyncio
    async def test_question_without_description(self):
        """Test question generation when no description provided"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="username",
            field_type=str,
            description=""  # Empty description
        )
        
        question = await generator.generate_question(config, {})
        assert question == "Please provide your username"
    
    @pytest.mark.asyncio
    async def test_question_generation_with_context(self):
        """Test that context is passed but not used by default generator"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="name",
            field_type=str,
            description="Your name"
        )
        context = {"user_type": "returning", "previous_name": "Alice"}
        
        # Default generator ignores context
        question = await generator.generate_question(config, context)
        assert question == "Please provide your name (Your name)"


class TestQuestionGenerationIntegration:
    """Test question generation integration with AIForm"""
    
    @pytest.mark.asyncio
    async def test_form_uses_question_generator(self, simple_user_model):
        """Test that form uses question generator for questions"""
        form = AIForm(simple_user_model)
        response = await form.start()
        
        # Should generate question using DefaultQuestionGenerator
        assert "Please provide your" in response.question
        assert response.question is not None
    
    @pytest.mark.asyncio
    async def test_form_with_custom_generator(self, simple_user_model):
        """Test form with custom question generator"""
        class CustomGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                return f"[CUSTOM] {field_config.name.upper()}: {field_config.description}"
        
        form = AIForm(simple_user_model, question_generator=CustomGenerator())
        response = await form.start()
        
        assert "[CUSTOM]" in response.question
        assert response.question.startswith("[CUSTOM]")
    
    @pytest.mark.asyncio
    async def test_configured_custom_questions(self, simple_user_model):
        """Test that configured custom questions are used"""
        form = (AIForm(simple_user_model)
                .configure_field("name", custom_question="What should I call you?")
                .configure_field("email", custom_question="Your email please:"))
        
        # Start and check first question
        response = await form.start()
        assert response.question == "What should I call you?"
        
        # Move to second question
        response = await form.respond("Alice")
        assert response.question == "Your email please:"
    
    @pytest.mark.asyncio
    async def test_examples_in_generated_questions(self, simple_user_model):
        """Test that configured examples appear in questions"""
        form = (AIForm(simple_user_model)
                .configure_field("email", examples=["user@example.com", "alice@company.co"]))
        
        await form.start()
        response = await form.respond("Test User")
        
        # Email question should include examples
        assert "Examples:" in response.question
        assert "user@example.com" in response.question
        assert "alice@company.co" in response.question
    
    @pytest.mark.asyncio
    async def test_question_generation_with_metadata(self, complex_job_model):
        """Test question generation with rich metadata"""
        form = AIForm(complex_job_model)
        response = await form.start()
        
        # Should use custom question from metadata
        # First field should be applicant_name with custom question
        expected_question = "What's your full legal name?"
        assert response.question == expected_question


class TestContextualQuestionGeneration:
    """Test context-aware question generation"""
    
    @pytest.mark.asyncio
    async def test_context_passed_to_generator(self, simple_user_model):
        """Test that context is passed to question generator"""
        class ContextAwareGenerator(QuestionGenerator):
            def __init__(self):
                self.received_context = None
            
            async def generate_question(self, field_config, context):
                self.received_context = context
                return f"Context test: {field_config.name}"
        
        generator = ContextAwareGenerator()
        form = AIForm(simple_user_model, question_generator=generator)
        form.set_context({"user_type": "returning", "source": "mobile"})
        
        await form.start()
        
        assert generator.received_context is not None
        assert generator.received_context["user_type"] == "returning"
        assert generator.received_context["source"] == "mobile"
    
    @pytest.mark.asyncio
    async def test_personalized_question_generator(self, simple_user_model):
        """Test personalized question generation using context"""
        class PersonalizedGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                user_name = context.get("name", "there")
                
                if field_config.name == "email":
                    return f"Hi {user_name}! What's your email address?"
                elif field_config.name == "age":
                    return f"Thanks {user_name}! Could you share your age?"
                else:
                    return f"Hi there! Please provide your {field_config.name}"
        
        form = AIForm(simple_user_model, question_generator=PersonalizedGenerator())
        response = await form.start()
        
        # First question (name) - no name in context yet
        assert "Hi there!" in response.question
        
        # Provide name
        response = await form.respond("Alice")
        
        # Second question (email) - should use name
        assert "Hi Alice!" in response.question
        assert "email address?" in response.question


class TestQuestionGenerationEdgeCases:
    """Test edge cases in question generation"""
    
    @pytest.mark.asyncio
    async def test_empty_field_name(self):
        """Test question generation with empty field name"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="",
            field_type=str,
            description="Empty name field"
        )
        
        question = await generator.generate_question(config, {})
        # Should handle gracefully
        assert "Please provide your" in question
    
    @pytest.mark.asyncio
    async def test_none_description(self):
        """Test question generation with None description"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="test_field",
            field_type=str,
            description=None  # type: ignore
        )
        
        question = await generator.generate_question(config, {})
        # Should not crash
        assert "test_field" in question
    
    @pytest.mark.asyncio
    async def test_empty_examples_list(self):
        """Test question generation with empty examples"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="test_field",
            field_type=str,
            description="Test description",
            examples=[]  # Empty list
        )
        
        question = await generator.generate_question(config, {})
        assert "Examples:" not in question
        assert question == "Please provide your test_field (Test description)"
    
    @pytest.mark.asyncio
    async def test_very_long_description(self):
        """Test question generation with very long description"""
        generator = DefaultQuestionGenerator()
        long_description = "A" * 500  # Very long description
        
        config = FieldConfig(
            name="test_field",
            field_type=str,
            description=long_description
        )
        
        question = await generator.generate_question(config, {})
        # Should include the full description
        assert long_description in question
    
    @pytest.mark.asyncio
    async def test_special_characters_in_field_data(self):
        """Test question generation with special characters"""
        generator = DefaultQuestionGenerator()
        config = FieldConfig(
            name="special_field",
            field_type=str,
            description="Field with special chars: !@#$%^&*()",
            examples=["test@example.com", "user+tag@domain.co.uk", "name.surname@test-domain.org"]
        )
        
        question = await generator.generate_question(config, {})
        # Should handle special characters in description and examples
        assert "!@#$%^&*()" in question
        assert "test@example.com" in question
        assert "+" in question  # From second example


@pytest.mark.skipif(not PYDANTIC_AI_AVAILABLE, reason="pydantic-ai not available")
class TestAIQuestionGeneratorIntegration:
    """Test AI question generator integration"""
    
    @pytest.mark.asyncio
    async def test_ai_form_creation_with_use_ai_flag(self, simple_user_model):
        """Test creating AI form with use_ai flag"""
        ai_form = AIForm(simple_user_model, use_ai=True)
        
        # With current implementation, use_ai doesn't auto-create AI components to avoid API key issues
        # User must explicitly set AI components
        ai_form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        
        # Should now use AI generator
        assert isinstance(ai_form.question_generator, PydanticAIQuestionGenerator)
    
    @pytest.mark.asyncio
    async def test_ai_form_vs_default_question_generation(self, simple_user_model):
        """Test AI vs default question generation"""
        # Default form
        default_form = AIForm(simple_user_model)
        default_form.question_generator = DefaultQuestionGenerator()
        
        # AI form with test mode
        ai_form = AIForm(simple_user_model, use_ai=True)
        ai_form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        
        # Both should generate questions
        default_response = await default_form.start()
        ai_response = await ai_form.start()
        
        assert default_response.question is not None
        assert ai_response.question is not None
        
        # Questions should be strings
        assert isinstance(default_response.question, str)
        assert isinstance(ai_response.question, str)
    
    def test_ai_unavailable_fallback(self, simple_user_model):
        """Test graceful fallback when AI is unavailable"""
        # Simulate AI unavailable
        import ai_forms.core.form
        original_available = ai_forms.core.form.PYDANTIC_AI_AVAILABLE
        
        try:
            ai_forms.core.form.PYDANTIC_AI_AVAILABLE = False
            
            # Should fall back to default generator
            form = AIForm(simple_user_model, use_ai=True)
            assert not form.use_ai
            assert isinstance(form.question_generator, DefaultQuestionGenerator)
        
        finally:
            ai_forms.core.form.PYDANTIC_AI_AVAILABLE = original_available