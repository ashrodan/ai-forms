"""AI-first validator that leverages pydantic-ai for intelligent form validation"""
from typing import Any, Dict, Optional
from ..types.config import FieldConfig
from ..types.exceptions import ValidationError


class AiValidator:
    """
    AI-first validator that leverages pydantic-ai for intelligent form validation.
    
    This is the core validation system that defaults to AI-powered validation
    and falls back to simple parsing only when AI is disabled or unavailable.
    """
    
    def __init__(
        self,
        use_ai: bool = True,
        test_mode: bool = False,
        ai_model: str = "openai:gpt-4o-mini"
    ):
        self.use_ai = use_ai
        self.test_mode = test_mode
        self.ai_model = ai_model
        
        # Initialize AI validation tools (primary validation mechanism)
        self.ai_validation_tools = None
        
        if self.use_ai:
            self._initialize_ai_validation()
    
    def _initialize_ai_validation(self):
        """Initialize AI validation tools using pydantic-ai"""
        try:
            from ..validators.ai_tools import AIValidationTools, PYDANTIC_AI_AVAILABLE
            if PYDANTIC_AI_AVAILABLE:
                self.ai_validation_tools = AIValidationTools(
                    model_name=self.ai_model,
                    test_mode=self.test_mode
                )
        except ImportError:
            pass
    
    async def validate_field(
        self,
        field_config: FieldConfig,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Validate and parse user input using AI-first approach.
        
        Args:
            field_config: Field configuration
            user_input: Raw user input
            context: Other collected form data for context
            
        Returns:
            Parsed and validated value
            
        Raises:
            ValidationError: If validation fails
        """
        if context is None:
            context = {}
        
        # AI-first validation (primary method)
        if self.ai_validation_tools:
            try:
                result = await self.ai_validation_tools.validate_field_with_ai(
                    field_config,
                    user_input,
                    context
                )
                
                if result.is_valid:
                    return result.parsed_value
                else:
                    raise ValidationError(result.error_message)
                    
            except ValidationError:
                raise
            except Exception as e:
                # If AI fails, fall back to simple parsing
                pass
        
        # Fallback to simple parsing (when AI is disabled or unavailable)
        return self._simple_parse_and_validate(field_config, user_input)
    
    async def validate_form(
        self,
        form_data: Dict[str, Any],
        model_class: type,
        field_configs: Dict[str, FieldConfig]
    ) -> Dict[str, Any]:
        """
        Validate complete form data using AI-powered cross-field validation.
        
        Args:
            form_data: All collected form data
            model_class: Pydantic model class
            field_configs: Field configurations
            
        Returns:
            Validated form data
            
        Raises:
            ValidationError: If form validation fails
        """
        # AI-first form validation
        if self.ai_validation_tools:
            try:
                result = await self.ai_validation_tools.validate_form_with_ai(
                    form_data,
                    model_class,
                    field_configs
                )
                
                if result.is_valid:
                    return result.parsed_value
                else:
                    raise ValidationError(result.error_message)
                    
            except ValidationError:
                raise
            except Exception:
                # Fall back to basic Pydantic validation
                pass
        
        # Fallback to basic Pydantic model validation
        try:
            from pydantic import ValidationError as PydanticValidationError
            model_instance = model_class(**form_data)
            return form_data
        except PydanticValidationError as e:
            raise ValidationError(f"Form validation failed: {e}")
    
    def _simple_parse_and_validate(self, config: FieldConfig, user_input: str) -> Any:
        """Simple parsing fallback with basic validation"""
        from typing import get_origin
        value = user_input.strip()
        
        # Handle List types
        origin = get_origin(config.field_type)
        if origin is list:
            if ',' in value:
                return [item.strip() for item in value.split(',')]
            elif value:
                return [value]
            else:
                return []
        
        # Basic type conversion
        if config.field_type == int:
            try:
                return int(value)
            except ValueError:
                raise ValidationError(f"Expected a number, got: {value}")
        elif config.field_type == float:
            try:
                return float(value)
            except ValueError:
                raise ValidationError(f"Expected a decimal number, got: {value}")
        elif config.field_type == bool:
            lower_val = value.lower()
            if lower_val in ("yes", "true", "1", "y"):
                return True
            elif lower_val in ("no", "false", "0", "n"):
                return False
            else:
                raise ValidationError(f"Expected yes/no, got: {value}")
        
        # String validation with hints
        if isinstance(value, str) and config.validation_hint:
            if 'email' in config.validation_hint.lower():
                from ..validators.base import EmailValidator
                validator = EmailValidator()
                if not validator.validate(value, {}):
                    raise ValidationError(validator.get_error_message(value))
        
        return value
    
    @property
    def is_ai_enabled(self) -> bool:
        """Check if AI validation is enabled and available"""
        return self.use_ai and self.ai_validation_tools is not None
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get status information about the AI validator"""
        return {
            "use_ai": self.use_ai,
            "test_mode": self.test_mode,
            "ai_validation_available": self.ai_validation_tools is not None,
            "ai_enabled": self.is_ai_enabled
        }