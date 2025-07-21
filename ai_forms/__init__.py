"""
AI Forms - AI-powered conversational form collection

Transform Pydantic models into natural, conversational data collection workflows.
"""

from .core.form import AIForm
from .types.enums import ConversationMode, FieldPriority, ValidationStrategy
from .types.responses import FormResponse
from .generators.base import QuestionGenerator

__version__ = "0.1.0"
__all__ = [
    "AIForm",
    "ConversationMode", 
    "FieldPriority",
    "ValidationStrategy",
    "FormResponse",
    "QuestionGenerator",
]