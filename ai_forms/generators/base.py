from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..types.config import FieldConfig


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