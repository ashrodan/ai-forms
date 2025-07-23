from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..types.config import FieldConfig

try:
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel
    PYDANTIC_AI_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_AVAILABLE = False
    TestModel = None


class QuestionGenerator(ABC):
    """Base class for generating questions from field configurations"""
    
    @abstractmethod
    async def generate_question(
        self, 
        field_config: FieldConfig, 
        context: Dict[str, Any]
    ) -> str:
        """Generate a question for the given field"""
        pass


class DefaultQuestionGenerator(QuestionGenerator):
    """Default question generator using field descriptions"""
    
    async def generate_question(
        self, 
        field_config: FieldConfig, 
        context: Dict[str, Any]
    ) -> str:
        if field_config.custom_question:
            return field_config.custom_question
            
        base_question = f"Please provide your {field_config.name}"
        if field_config.description:
            base_question += f" ({field_config.description})"
            
        if field_config.examples:
            examples_str = ", ".join(field_config.examples[:3])
            base_question += f". Examples: {examples_str}"
            
        return base_question


class PydanticAIQuestionGenerator(QuestionGenerator):
    """AI-powered question generator using Pydantic AI"""
    
    def __init__(self, model_name: str = "openai:gpt-4o-mini", test_mode: bool = False):
        if not PYDANTIC_AI_AVAILABLE:
            raise ImportError("pydantic-ai is required for PydanticAIQuestionGenerator")
        
        self.test_mode = test_mode
        if test_mode:
            # Use TestModel for deterministic testing with predefined responses
            self.test_responses = [
                "What is your name?",
                "Could you provide your email address?", 
                "How old are you?",
                "What is your phone number?",
                "Please tell us about your skills",
                "What's your experience level?",
                "Are you interested in our newsletter?",
                "Please provide this information"
            ]
            self.response_index = 0
            # Don't create agent in test mode, handle manually
            self.agent = None
        else:
            self.agent = Agent(
                model_name,
                system_prompt=self._get_system_prompt()
            )
    
    def _get_system_prompt(self) -> str:
        return """You are a helpful form assistant that generates conversational questions for data collection.

Guidelines:
- Create natural, friendly questions that feel conversational
- Use the field description to understand what information is needed
- Include examples when provided to help users understand the format
- Keep questions concise but clear
- Adapt tone based on the field context (professional for business, casual for personal)
- If context about previous answers is provided, reference it naturally

Always return just the question text, no additional formatting or explanation."""
    
    async def generate_question(
        self, 
        field_config: FieldConfig, 
        context: Dict[str, Any]
    ) -> str:
        # If custom question is set, use it directly
        if field_config.custom_question:
            return field_config.custom_question
        
        # Prepare context for the AI
        prompt_context = {
            "field_name": field_config.name,
            "field_type": field_config.field_type.__name__ if hasattr(field_config.field_type, '__name__') else str(field_config.field_type),
            "description": field_config.description or "",
            "examples": field_config.examples[:3] if field_config.examples else [],
            "required": field_config.required,
            "validation_hint": field_config.validation_hint or "",
            "user_context": context
        }
        
        prompt = f"""Generate a conversational question to collect the following information:

Field: {prompt_context['field_name']} ({prompt_context['field_type']})
Description: {prompt_context['description']}
Required: {prompt_context['required']}
"""
        
        if prompt_context['examples']:
            prompt += f"Examples: {', '.join(prompt_context['examples'])}\n"
        
        if prompt_context['validation_hint']:
            prompt += f"Validation hint: {prompt_context['validation_hint']}\n"
        
        if prompt_context['user_context']:
            # Include relevant context from previous answers
            relevant_context = {k: v for k, v in prompt_context['user_context'].items() 
                              if k in ['name', 'email', 'company', 'position'] and v}
            if relevant_context:
                prompt += f"User context: {relevant_context}\n"
        
        prompt += "\nGenerate a friendly, conversational question:"
        
        if self.test_mode:
            # Return deterministic test responses
            if self.response_index < len(self.test_responses):
                response = self.test_responses[self.response_index]
                self.response_index += 1
                return response
            else:
                # Fall back to default question for additional calls
                fallback = DefaultQuestionGenerator()
                return await fallback.generate_question(field_config, context)
        
        try:
            result = await self.agent.run(prompt)
            return result.output
        except Exception as e:
            # Fallback to default generator on error
            fallback = DefaultQuestionGenerator()
            return await fallback.generate_question(field_config, context)