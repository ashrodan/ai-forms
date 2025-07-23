"""AI Integration tests using TestModel for deterministic LLM emulation"""
import pytest
from typing import List, Optional
from pydantic import BaseModel, Field

from ai_forms import AIForm, ConversationMode, FieldPriority
from ai_forms.generators.base import PydanticAIQuestionGenerator, PYDANTIC_AI_AVAILABLE
from ai_forms.parsers.ai_parser import AIResponseParser

# Skip all tests if pydantic-ai not available
pytestmark = pytest.mark.skipif(not PYDANTIC_AI_AVAILABLE, reason="pydantic-ai not available")


class TestPydanticAIQuestionGenerator:
    """Test AI-powered question generation using TestModel"""
    
    @pytest.mark.asyncio
    async def test_ai_question_generator_test_mode(self):
        """Test AI question generator in test mode"""
        generator = PydanticAIQuestionGenerator(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(
            name="email",
            field_type=str,
            description="Your email address",
            examples=["user@example.com", "alice@company.co"]
        )
        
        # TestModel returns predictable responses
        question = await generator.generate_question(config, {})
        
        # Should return a string question (TestModel gives consistent output)
        assert isinstance(question, str)
        assert len(question) > 0
        
    @pytest.mark.asyncio
    async def test_ai_generator_with_context(self):
        """Test AI question generator with context"""
        generator = PydanticAIQuestionGenerator(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(
            name="age",
            field_type=int,
            description="Your age in years"
        )
        
        context = {"name": "Alice", "email": "alice@example.com"}
        question = await generator.generate_question(config, context)
        
        assert isinstance(question, str)
        assert len(question) > 0
    
    @pytest.mark.asyncio
    async def test_ai_generator_custom_question_override(self):
        """Test that custom questions are used directly"""
        generator = PydanticAIQuestionGenerator(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(
            name="email",
            field_type=str,
            description="Your email address",
            custom_question="What's your email?"
        )
        
        # Custom question should be used directly without AI call
        question = await generator.generate_question(config, {})
        assert question == "What's your email?"
    
    @pytest.mark.asyncio
    async def test_ai_generator_fallback_on_error(self):
        """Test fallback to DefaultQuestionGenerator on error"""
        # Create generator that will fail by running out of responses
        generator = PydanticAIQuestionGenerator(test_mode=True)
        
        # Exhaust all test responses to trigger fallback
        generator.response_index = len(generator.test_responses) + 1
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(
            name="name",
            field_type=str,
            description="Your name"
        )
        
        # Should fall back to default generator
        question = await generator.generate_question(config, {})
        assert question == "Please provide your name (Your name)"


class TestAIResponseParser:
    """Test AI-powered response parsing using TestModel"""
    
    @pytest.mark.asyncio
    async def test_ai_parser_simple_types(self):
        """Test AI parser with simple types"""
        parser = AIResponseParser(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(name="age", field_type=int, description="Age in years")
        
        # TestModel should return something parseable
        result = await parser.parse_response("twenty-five", config)
        # The exact result depends on TestModel behavior, just check it works
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_ai_parser_list_type(self):
        """Test AI parser with list types"""
        parser = AIResponseParser(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(
            name="skills", 
            field_type=List[str], 
            description="List of skills",
            examples=["Python", "JavaScript", "SQL"]
        )
        
        # Test various list formats
        result = await parser.parse_response("Python, JavaScript, SQL", config)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_ai_parser_simple_fallback(self):
        """Test simple parsing fallback for basic types"""
        parser = AIResponseParser(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(name="name", field_type=str, description="Your name")
        
        # Simple string should work with simple parsing
        result = await parser.parse_response("Alice Johnson", config)
        assert result == "Alice Johnson"
    
    @pytest.mark.asyncio
    async def test_ai_parser_boolean_variations(self):
        """Test boolean parsing with various inputs"""
        parser = AIResponseParser(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(name="subscribe", field_type=bool, description="Subscribe to newsletter")
        
        # Test various boolean inputs
        test_cases = [
            ("yes", True),
            ("no", False),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False)
        ]
        
        for input_val, expected in test_cases:
            result = await parser.parse_response(input_val, config)
            assert result == expected


class TestAIFormIntegration:
    """Test AIForm with AI components using TestModel"""
    
    @pytest.mark.asyncio
    async def test_ai_form_basic_workflow(self):
        """Test basic AI form workflow with TestModel"""
        class SimpleModel(BaseModel):
            name: str = Field(description="Your full name")
            email: str = Field(description="Email address")
            age: int = Field(description="Age in years")
        
        # Create AI form in test mode
        form = AIForm(SimpleModel, use_ai=True)
        # Override with test mode generators
        form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        form.response_parser = AIResponseParser(test_mode=True)
        
        # Start form
        response = await form.start()
        assert response.question is not None
        assert not response.is_complete
        
        # Provide responses
        response = await form.respond("Alice Johnson")
        assert not response.is_complete or response.current_field != "name"
    
    @pytest.mark.asyncio
    async def test_ai_form_vs_default_form(self, simple_user_model):
        """Compare AI form with default form behavior"""
        # Default form
        default_form = AIForm(simple_user_model)
        default_response = await default_form.start()
        
        # AI form in test mode
        ai_form = AIForm(simple_user_model, use_ai=True)
        ai_form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        ai_form.response_parser = AIResponseParser(test_mode=True)
        
        ai_response = await ai_form.start()
        
        # Both should work and provide questions
        assert default_response.question is not None
        assert ai_response.question is not None
        
        # Questions might be different due to AI generation
        # (but both should be valid)
        assert len(default_response.question) > 0
        assert len(ai_response.question) > 0
    
    @pytest.mark.asyncio
    async def test_ai_form_fallback_behavior(self, simple_user_model):
        """Test AI form fallback to simple parsing"""
        form = AIForm(simple_user_model, use_ai=True)
        form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        form.response_parser = AIResponseParser(test_mode=True)
        
        # Start and respond
        await form.start()
        
        # Simple responses should work with fallback parsing
        response = await form.respond("Alice")  # Simple string
        assert not response.errors or len(response.errors) == 0
        
    def test_ai_form_without_pydantic_ai(self):
        """Test that AI form degrades gracefully without pydantic-ai"""
        # Simulate pydantic-ai unavailable
        import ai_forms.core.form
        original_available = ai_forms.core.form.PYDANTIC_AI_AVAILABLE
        
        try:
            ai_forms.core.form.PYDANTIC_AI_AVAILABLE = False
            
            class TestModel(BaseModel):
                name: str = Field(description="Name")
            
            # Should fall back to default generator
            form = AIForm(TestModel, use_ai=True)  # use_ai=True but unavailable
            assert not form.use_ai  # Should be False due to unavailability
            assert isinstance(form.question_generator, ai_forms.generators.base.DefaultQuestionGenerator)
            
        finally:
            ai_forms.core.form.PYDANTIC_AI_AVAILABLE = original_available


class TestAIFormComplexTypes:
    """Test AI form with complex field types"""
    
    @pytest.mark.asyncio
    async def test_list_field_parsing(self):
        """Test AI parsing of list fields"""
        class ModelWithList(BaseModel):
            skills: List[str] = Field(description="List of your skills")
            ratings: List[int] = Field(description="Ratings from 1-10")
        
        form = AIForm(ModelWithList, use_ai=True)
        form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        form.response_parser = AIResponseParser(test_mode=True)
        
        await form.start()
        
        # Test comma-separated list
        response = await form.respond("Python, JavaScript, SQL")
        assert not response.errors or len(response.errors) == 0
    
    @pytest.mark.asyncio
    async def test_optional_field_handling(self):
        """Test handling of optional fields"""
        class ModelWithOptional(BaseModel):
            name: str = Field(description="Your name")
            company: Optional[str] = Field(None, description="Company name")
            phone: Optional[str] = Field(None, description="Phone number")
        
        form = AIForm(ModelWithOptional, use_ai=True)
        form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        form.response_parser = AIResponseParser(test_mode=True)
        
        await form.start()
        
        # Provide responses including optional fields
        await form.respond("Alice Johnson")
        response = await form.respond("")  # Empty response for optional field
        
        # Should handle optional fields gracefully
        assert response is not None


class TestAIMockResponses:
    """Test AI with predefined mock responses for specific scenarios"""
    
    @pytest.mark.asyncio
    async def test_contextual_question_generation(self):
        """Test that context influences question generation"""
        generator = PydanticAIQuestionGenerator(test_mode=True)
        
        from ai_forms.types.config import FieldConfig
        
        # Test question without context
        config = FieldConfig(name="phone", field_type=str, description="Phone number")
        question1 = await generator.generate_question(config, {})
        
        # Test question with context (user name known)
        context_with_name = {"name": "Alice"}
        question2 = await generator.generate_question(config, context_with_name)
        
        # Both should be valid questions
        assert isinstance(question1, str) and len(question1) > 0
        assert isinstance(question2, str) and len(question2) > 0
    
    @pytest.mark.asyncio
    async def test_ai_error_recovery(self):
        """Test AI error recovery and fallback"""
        class ErrorProneParser(AIResponseParser):
            def __init__(self, *args, **kwargs):
                super().__init__(test_mode=True)
                self.error_count = 0
            
            async def _ai_parse(self, user_input, field_config, context):
                self.error_count += 1
                if self.error_count == 1:
                    raise Exception("Simulated AI error")
                return await super()._ai_parse(user_input, field_config, context)
        
        parser = ErrorProneParser()
        
        from ai_forms.types.config import FieldConfig
        config = FieldConfig(name="name", field_type=str, description="Your name")
        
        # Should handle error and potentially retry or fallback
        result = await parser.parse_response("Alice", config)
        assert result == "Alice"  # Should fallback to simple parsing