"""
AI Forms - AI-powered conversational form collection

Transform Pydantic models into natural, conversational data collection workflows.
"""

from .core.form import AIForm
from .types.enums import ConversationMode, FieldPriority, ValidationStrategy
from .types.responses import FormResponse
from .generators.base import QuestionGenerator, DefaultQuestionGenerator

# Import AI components if available
try:
    from .generators.base import PydanticAIQuestionGenerator
    from .parsers.ai_parser import AIResponseParser
    _AI_AVAILABLE = True
except ImportError:
    _AI_AVAILABLE = False

__version__ = "0.1.0"

if _AI_AVAILABLE:
    __all__ = [
        "AIForm",
        "ConversationMode", 
        "FieldPriority",
        "ValidationStrategy",
        "FormResponse",
        "QuestionGenerator",
        "DefaultQuestionGenerator",
        "PydanticAIQuestionGenerator",
        "AIResponseParser",
    ]
else:
    __all__ = [
        "AIForm",
        "ConversationMode", 
        "FieldPriority",
        "ValidationStrategy",
        "FormResponse",
        "QuestionGenerator",
        "DefaultQuestionGenerator",
    ]