"""AI-powered validation tools using pydantic-ai chat functions"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..types.config import FieldConfig
from ..types.exceptions import ValidationError

from pydantic_ai import Agent


class ValidationResult(BaseModel):
    """Result of validation operation"""
    is_valid: bool = Field(description="Whether the validation passed")
    error_message: Optional[str] = Field(None, description="Error message if validation failed")
    parsed_value: Any = Field(description="The parsed/cleaned value")


class AIValidationTools:
    """Core AI validation tools for form fields and final validation"""
    
    def __init__(self, model_name: str = "openai:gpt-4o-mini", test_mode: bool = False):
        
        self.model_name = model_name
        self.test_mode = test_mode
        
        # Only create agent if not in test mode to avoid API key requirements
        if not test_mode:
            # Create agent with validation tools
            self.agent = Agent(
                model_name,
                system_prompt="""You are an intelligent form validation assistant with natural language understanding. You have access to validation tools that you MUST use for all validation requests.

CRITICAL: Always use the validate_field or validate_form tools for processing - never just return text responses.

When validating fields, be smart about user intent:
- Boolean fields: Understand natural language like 'sure'='yes', 'ok'='yes', 'definitely'='yes', 'nope'='no', 'nah'='no'
- Numeric fields: Parse flexible formats, handle ranges intelligently  
- Email fields: Validate format and provide helpful error messages
- List fields: Parse various delimited formats (commas, semicolons, spaces)
- Text fields: Apply smart validation rules and understand common patterns

Your validation should be contextual and intelligent:
- Understand user intent even with informal language
- Convert responses to proper data types
- Provide clear, helpful error messages when validation fails
- Consider field constraints and business logic
- Be consistent with data formatting

Always return properly parsed/converted values through the validation tools.
""",
                tools=[self.validate_field, self.validate_form]
            )
        else:
            self.agent = None
    
    def validate_field(
        self, 
        field_name: str, 
        field_value: str, 
        field_type: str,
        field_description: str,
        validation_hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Intelligently validate and convert user input to the expected field type.
        
        This tool uses smart parsing and natural language understanding to convert
        user responses into the correct data types with validation.
        
        For boolean fields: Converts natural language like 'sure', 'ok', 'definitely' to True/False
        For numeric fields: Parses various number formats and validates ranges  
        For email fields: Validates format and suggests corrections
        For list fields: Parses various delimited formats
        For text fields: Applies smart validation rules
        
        Args:
            field_name: Name of the field being validated
            field_value: User input value to validate (raw string from user)
            field_type: Expected Python type (e.g., 'int', 'str', 'bool', 'List[str]')
            field_description: Description of what this field represents
            validation_hint: Additional validation requirements or business rules
            context: Other collected form data for context-aware validation
            
        Returns:
            ValidationResult with validation status, error message, and properly converted value
        """
        if self.test_mode:
            return self._test_validate_field(field_name, field_value, field_type)
        
        try:
            # Use the field type dispatcher for intelligent parsing
            parsed_value = self._parse_field_by_type(field_value, field_type, validation_hint, context)
            
            # Apply additional validation rules based on hints
            validation_error = self._apply_validation_rules(parsed_value, field_type, validation_hint, context)
            if validation_error:
                return ValidationResult(
                    is_valid=False,
                    error_message=validation_error,
                    parsed_value=field_value
                )
            
            return ValidationResult(
                is_valid=True,
                error_message=None,
                parsed_value=parsed_value
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=str(e),
                parsed_value=field_value
            )
    
    def validate_form(
        self,
        form_data: Dict[str, Any],
        model_class_name: str,
        field_configs: Dict[str, Dict[str, Any]]
    ) -> ValidationResult:
        """Validate the complete form data
        
        Args:
            form_data: Dictionary of all collected form data
            model_class_name: Name of the Pydantic model class
            field_configs: Field configuration dictionary
            
        Returns:
            ValidationResult with overall validation status and any errors
        """
        if self.test_mode:
            return self._test_validate_form(form_data, model_class_name)
        
        try:
            # Cross-field validation logic
            errors = []
            
            # Check required fields
            for field_name, config in field_configs.items():
                if config.get('required', True) and field_name not in form_data:
                    errors.append(f"Required field '{field_name}' is missing")
            
            # Business logic validation
            if 'age' in form_data and 'experience_years' in form_data:
                age = form_data.get('age', 0)
                experience = form_data.get('experience_years', 0)
                if isinstance(age, int) and isinstance(experience, int):
                    if experience > age - 16:
                        errors.append("Years of experience cannot exceed age minus 16")
            
            # Data consistency checks
            if 'email' in form_data and 'name' in form_data:
                email = form_data.get('email', '')
                name = form_data.get('name', '')
                if isinstance(email, str) and isinstance(name, str):
                    if '@' in email and len(name.strip()) < 2:
                        errors.append("Name is required when email is provided")
            
            if errors:
                return ValidationResult(
                    is_valid=False,
                    error_message="; ".join(errors),
                    parsed_value=form_data
                )
            
            return ValidationResult(
                is_valid=True,
                error_message=None,
                parsed_value=form_data
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Form validation error: {str(e)}",
                parsed_value=form_data
            )
    
    def _parse_field_by_type(self, value: str, field_type: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Any:
        """Dispatch parsing based on field type with smart natural language understanding"""
        value = value.strip()
        
        # Type dispatch mapping
        type_parsers = {
            'bool': self._parse_boolean,
            'int': self._parse_integer,
            'float': self._parse_float,
            'str': self._parse_string,
        }
        
        # Handle list types
        if 'List[' in field_type:
            return self._parse_list(value, field_type, validation_hint, context)
        
        # Handle union types (simplified)
        if 'Union[' in field_type or '|' in field_type:
            return self._parse_union(value, field_type, validation_hint, context)
        
        # Use specific parser if available
        parser = type_parsers.get(field_type, self._parse_string)
        return parser(value, validation_hint, context)
    
    def _parse_boolean(self, value: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        """Parse boolean with extensive natural language understanding"""
        lower_val = value.lower().strip()
        
        # Expanded positive responses
        positive_responses = {
            "yes", "y", "true", "1", "on", "enable", "enabled",
            "sure", "ok", "okay", "yep", "yeah", "yup", "absolutely", 
            "definitely", "certainly", "of course", "indeed", "correct",
            "right", "agree", "accept", "confirm", "affirmative"
        }
        
        # Expanded negative responses  
        negative_responses = {
            "no", "n", "false", "0", "off", "disable", "disabled",
            "nope", "nah", "never", "not", "negative", "deny", "refuse",
            "disagree", "decline", "reject", "cancel", "wrong", "incorrect"
        }
        
        if lower_val in positive_responses:
            return True
        elif lower_val in negative_responses:
            return False
        else:
            # Try partial matching for longer phrases
            if any(pos in lower_val for pos in ["yes", "sure", "ok", "definitely", "absolutely"]):
                return True
            elif any(neg in lower_val for neg in ["no", "nope", "never", "not"]):
                return False
            else:
                raise ValueError(f"Could not interpret '{value}' as yes/no. Try: yes, no, sure, nope, ok, etc.")
    
    def _parse_integer(self, value: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> int:
        """Parse integer with flexible formatting"""
        # Remove common formatting
        clean_value = value.replace(',', '').replace('_', '').strip()
        
        # Handle written numbers (basic)
        word_to_num = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
            'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20
        }
        
        if clean_value.lower() in word_to_num:
            return word_to_num[clean_value.lower()]
        
        try:
            return int(clean_value)
        except ValueError:
            raise ValueError(f"Expected a number, got: {value}")
    
    def _parse_float(self, value: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> float:
        """Parse float with flexible formatting"""
        # Remove common formatting but preserve decimal point
        clean_value = value.replace(',', '').replace('_', '').strip()
        
        try:
            return float(clean_value)
        except ValueError:
            raise ValueError(f"Expected a decimal number, got: {value}")
    
    def _parse_string(self, value: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> str:
        """Parse string with smart validation"""
        # Apply email validation if hinted
        if validation_hint and 'email' in validation_hint.lower():
            if not self._validate_email(value):
                raise ValueError(f"{value} is not a valid email address")
        
        return value.strip()
    
    def _parse_list(self, value: str, field_type: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> list:
        """Parse list with multiple delimiter support"""
        if not value.strip():
            return []
        
        # Try different delimiters
        delimiters = [',', ';', '|', '\n']
        
        for delimiter in delimiters:
            if delimiter in value:
                items = [item.strip() for item in value.split(delimiter) if item.strip()]
                
                # Convert items to correct type if specified
                if 'List[int]' in field_type:
                    return [self._parse_integer(item) for item in items]
                elif 'List[float]' in field_type:
                    return [self._parse_float(item) for item in items]
                
                return items
        
        # Single item
        return [value.strip()]
    
    def _parse_union(self, value: str, field_type: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Any:
        """Parse union types by trying each type in order"""
        # This is a simplified approach - try common types first
        try:
            return self._parse_integer(value, validation_hint, context)
        except ValueError:
            pass
        
        try:
            return self._parse_float(value, validation_hint, context)
        except ValueError:
            pass
        
        try:
            return self._parse_boolean(value, validation_hint, context)
        except ValueError:
            pass
        
        # Default to string
        return self._parse_string(value, validation_hint, context)
    
    def _apply_validation_rules(self, parsed_value: Any, field_type: str, validation_hint: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Apply additional validation rules based on hints and return error message if invalid"""
        if not validation_hint:
            return None
        
        hint_lower = validation_hint.lower()
        
        # Range validation for numeric types
        if field_type in ['int', 'float'] and isinstance(parsed_value, (int, float)):
            range_error = self._validate_range(parsed_value, validation_hint)
            if range_error:
                return range_error
        
        # Length validation for strings and lists
        if 'min_length' in hint_lower or 'max_length' in hint_lower:
            length = len(str(parsed_value)) if isinstance(parsed_value, str) else len(parsed_value) if isinstance(parsed_value, list) else 0
            
            import re
            min_match = re.search(r'min_length[=:]\s*(\d+)', hint_lower)
            max_match = re.search(r'max_length[=:]\s*(\d+)', hint_lower)
            
            if min_match and length < int(min_match.group(1)):
                return f"Must be at least {min_match.group(1)} characters/items long"
            if max_match and length > int(max_match.group(1)):
                return f"Must be at most {max_match.group(1)} characters/items long"
        
        # Pattern validation
        if 'pattern' in hint_lower or 'regex' in hint_lower:
            import re
            pattern_match = re.search(r'pattern[=:]\s*([^\s,]+)', validation_hint)
            if pattern_match:
                pattern = pattern_match.group(1)
                if not re.match(pattern, str(parsed_value)):
                    return f"Value does not match required pattern"
        
        return None
    
    def _parse_basic_type(self, value: str, field_type: str) -> Any:
        """Legacy method - redirects to new parsing system"""
        return self._parse_field_by_type(value, field_type)
    
    def _validate_email(self, value: str) -> bool:
        """Basic email validation"""
        if not isinstance(value, str):
            return False
        return '@' in value and '.' in value.split('@')[-1]
    
    def _validate_range(self, value: Any, hint: str) -> Optional[str]:
        """Validate numeric range based on hint"""
        try:
            num_value = float(value)
            
            # Extract min/max from hint
            import re
            min_match = re.search(r'min[=:]\s*(\d+)', hint)
            max_match = re.search(r'max[=:]\s*(\d+)', hint)
            
            if min_match:
                min_val = float(min_match.group(1))
                if num_value < min_val:
                    return f"Value must be at least {min_val}"
            
            if max_match:
                max_val = float(max_match.group(1))
                if num_value > max_val:
                    return f"Value must be at most {max_val}"
            
            return None
        except ValueError:
            return "Expected a numeric value"
    
    def _test_validate_field(self, field_name: str, field_value: str, field_type: str) -> ValidationResult:
        """Test mode field validation with deterministic responses using new parsing system"""
        try:
            # Use the new parsing system for consistent behavior
            parsed_value = self._parse_field_by_type(field_value, field_type)
            
            # Email validation for test mode (basic check)
            if field_name == 'email' and '@' not in field_value:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{field_value} is not a valid email address",
                    parsed_value=field_value
                )
            
            return ValidationResult(
                is_valid=True,
                parsed_value=parsed_value,
                error_message=None
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=str(e),
                parsed_value=field_value
            )
    
    def _test_validate_form(self, form_data: Dict[str, Any], model_class_name: str) -> ValidationResult:
        """Test mode form validation with deterministic responses"""
        # Simple test validation
        if 'email' in form_data and '@' not in str(form_data['email']):
            return ValidationResult(
                is_valid=False,
                error_message="Invalid email in form data",
                parsed_value=form_data
            )
        
        return ValidationResult(is_valid=True, parsed_value=form_data)
    
    async def validate_field_with_ai(self, field_config: FieldConfig, field_value: str, context: Dict[str, Any] = None) -> ValidationResult:
        """Use AI agent to validate a field"""
        if context is None:
            context = {}
        
        # In test mode, use direct tool calls
        if self.test_mode or self.agent is None:
            field_type_str = str(field_config.field_type).replace('typing.', '').replace('<class \'', '').replace('\'>', '')
            return self.validate_field(
                field_name=field_config.name,
                field_value=field_value,
                field_type=field_type_str,
                field_description=field_config.description or "",
                validation_hint=field_config.validation_hint,
                context=context
            )
        
        # Convert field config to dictionary for the tool
        field_type_str = str(field_config.field_type).replace('typing.', '').replace('<class \'', '').replace('\'>', '')
        
        prompt = f"""Please validate the field '{field_config.name}' with the value '{field_value}'.

Field details:
- Type: {field_type_str}
- Description: {field_config.description}
- Validation hint: {field_config.validation_hint or 'None'}
- Required: {field_config.required}

Context from other fields: {context}

Use the validate_field tool to perform the validation."""
        
        result = await self.agent.run(prompt)
        
        # Extract ValidationResult from agent response
        if hasattr(result, 'data') and isinstance(result.data, ValidationResult):
            return result.data
        else:
            # Fallback if AI doesn't use tools properly
            return ValidationResult(
                is_valid=True,
                parsed_value=field_value,
                error_message=None
            )
    
    async def validate_form_with_ai(self, form_data: Dict[str, Any], model_class: type, field_configs: Dict[str, FieldConfig]) -> ValidationResult:
        """Use AI agent to validate complete form"""
        
        # Convert field configs to serializable format
        configs_dict = {}
        for name, config in field_configs.items():
            configs_dict[name] = {
                'name': config.name,
                'field_type': str(config.field_type),
                'description': config.description,
                'required': config.required,
                'validation_hint': config.validation_hint
            }
        
        # In test mode, use direct tool calls
        if self.test_mode or self.agent is None:
            return self.validate_form(
                form_data=form_data,
                model_class_name=model_class.__name__,
                field_configs=configs_dict
            )
        
        prompt = f"""Please validate the complete form data for model '{model_class.__name__}'.

Form data: {form_data}
Field configurations: {configs_dict}

Use the validate_form tool to perform comprehensive validation including:
- Cross-field consistency
- Business logic rules  
- Data integrity checks"""
        
        result = await self.agent.run(prompt)
        
        # Extract ValidationResult from agent response
        if hasattr(result, 'data') and isinstance(result.data, ValidationResult):
            return result.data
        else:
            # Fallback if AI doesn't use tools properly
            return ValidationResult(
                is_valid=True,
                parsed_value=form_data,
                error_message=None
            )