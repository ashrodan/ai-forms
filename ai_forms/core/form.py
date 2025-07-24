from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, get_type_hints
from pydantic import BaseModel, ValidationError as PydanticValidationError
from pydantic_core import PydanticUndefined
import inspect

from ..types.enums import ConversationMode, FieldPriority, ValidationStrategy
from ..types.responses import FormResponse
from ..types.config import FieldConfig
from ..types.exceptions import ConfigurationError, ValidationError
from ..generators.base import QuestionGenerator, DefaultQuestionGenerator, PydanticAIQuestionGenerator, PYDANTIC_AI_AVAILABLE
from ..validation.ai_validator import AiValidator

T = TypeVar('T', bound=BaseModel)


class AIForm(Generic[T]):
    """AI-powered conversational form for collecting structured data"""
    
    def __init__(
        self,
        model_class: Type[T],
        mode: ConversationMode = ConversationMode.SEQUENTIAL,
        validation: ValidationStrategy = ValidationStrategy.IMMEDIATE,
        question_generator: Optional[QuestionGenerator] = None,
        use_ai: bool = False,
        ai_model: str = "openai:gpt-4o-mini",
        test_mode: bool = False
    ):
        self.model_class = model_class
        self.mode = mode
        self.validation = validation
        self.use_ai = use_ai
        self.ai_model = ai_model
        self.test_mode = test_mode
        
        # Initialize question generator
        if question_generator:
            self.question_generator = question_generator
        elif self.use_ai:
            # Don't auto-create AI components in constructor to avoid API key issues
            # Let user explicitly set test mode components if needed
            self.question_generator = DefaultQuestionGenerator()
        else:
            self.question_generator = DefaultQuestionGenerator()
        
        # Initialize AI validator (core validation mechanism)
        self.ai_validator = AiValidator(
            use_ai=self.use_ai,
            test_mode=test_mode,
            ai_model=ai_model
        )
        
        self._field_configs: Dict[str, FieldConfig] = {}
        self._collected_data: Dict[str, Any] = {}
        self._current_field_index = 0
        self._field_order: List[str] = []
        self._hooks: List[Dict[str, Any]] = []
        self._context: Dict[str, Any] = {}
        self._started = False
        
        self._initialize_fields()
    
    def _initialize_fields(self):
        """Extract field configurations from Pydantic model"""
        model_fields = self.model_class.model_fields
        type_hints = get_type_hints(self.model_class)
        
        for field_name, field_info in model_fields.items():
            field_type = type_hints.get(field_name, str)
            description = field_info.description or ""
            
            # Extract metadata from json_schema_extra
            extra = field_info.json_schema_extra or {}
            
            config = FieldConfig(
                name=field_name,
                field_type=field_type,
                description=description,
                priority=extra.get("priority", FieldPriority.MEDIUM),
                cluster=extra.get("cluster"),
                custom_question=extra.get("custom_question"),
                examples=extra.get("examples", []),
                validation_hint=extra.get("validation_hint"),
                dependencies=extra.get("dependencies", []),
                skip_if=extra.get("skip_if"),
                required=field_info.is_required(),
                default=field_info.default if field_info.default is not PydanticUndefined else None
            )
            
            self._field_configs[field_name] = config
        
        self._calculate_field_order()
    
    def _calculate_field_order(self):
        """Calculate field order based on priorities and dependencies"""
        # Simple topological sort for dependencies
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(field_name: str):
            if field_name in temp_visited:
                raise ConfigurationError(f"Circular dependency detected involving {field_name}")
            if field_name in visited:
                return
                
            temp_visited.add(field_name)
            
            config = self._field_configs[field_name]
            for dep in config.dependencies:
                if dep in self._field_configs:
                    visit(dep)
            
            temp_visited.remove(field_name)
            visited.add(field_name)
            result.append(field_name)
        
        # Sort by priority first, then apply dependency ordering
        priority_order = {
            FieldPriority.CRITICAL: 0,
            FieldPriority.HIGH: 1,
            FieldPriority.MEDIUM: 2,
            FieldPriority.LOW: 3
        }
        
        sorted_fields = sorted(
            self._field_configs.keys(),
            key=lambda x: priority_order[self._field_configs[x].priority]
        )
        
        for field_name in sorted_fields:
            visit(field_name)
        
        self._field_order = result
    
    def configure_field(
        self,
        field_name: str,
        priority: Optional[FieldPriority] = None,
        custom_question: Optional[str] = None,
        validation_hint: Optional[str] = None,
        examples: Optional[List[str]] = None,
        cluster: Optional[str] = None
    ) -> 'AIForm[T]':
        """Configure a specific field (fluent interface)"""
        if field_name not in self._field_configs:
            raise ConfigurationError(f"Field '{field_name}' not found in model")
        
        # Validate priority is a valid FieldPriority enum value
        if priority is not None:
            from ..types.enums import FieldPriority
            if not isinstance(priority, FieldPriority):
                raise ValueError(f"Priority must be a FieldPriority enum value, got: {priority}")
        
        config = self._field_configs[field_name]
        if priority is not None:
            config.priority = priority
        if custom_question is not None:
            config.custom_question = custom_question
        if validation_hint is not None:
            config.validation_hint = validation_hint
        if examples is not None:
            config.examples = examples
        if cluster is not None:
            config.cluster = cluster
            
        self._calculate_field_order()
        return self
    
    def set_context(self, context: Dict[str, Any]) -> None:
        """Set context for question generation"""
        self._context.update(context)
    
    async def start(self) -> FormResponse[T]:
        """Start the form conversation"""
        self._started = True
        self._current_field_index = 0
        
        if not self._field_order:
            return FormResponse(
                is_complete=True,
                data=await self._create_model_instance() if self._field_order else self.model_class(),
                progress=100.0
            )
        
        return await self._get_next_question()
    
    async def respond(self, user_input: str) -> FormResponse[T]:
        """Process user response and return next question or completion"""
        if not self._started:
            raise ConfigurationError("Form not started. Call start() first.")
        
        if self._current_field_index >= len(self._field_order):
            return FormResponse(
                is_complete=True,
                data=await self._create_model_instance(),
                progress=100.0
            )
        
        current_field_name = self._field_order[self._current_field_index]
        current_config = self._field_configs[current_field_name]
        
        # Validate and store the input
        try:
            parsed_value = await self._parse_field_value(current_config, user_input)
            self._collected_data[current_field_name] = parsed_value
            self._current_field_index += 1
            
            # Check if we've now collected all fields (this handles the case where
            # we're fixing a field after final validation error)
            if len(self._collected_data) == len(self._field_order):
                # All fields collected, try final validation
                try:
                    model_instance = await self._create_model_instance()
                    return FormResponse(
                        is_complete=True,
                        data=model_instance,
                        progress=100.0,
                        collected_fields=list(self._collected_data.keys())
                    )
                except ValidationError as e:
                    # Handle final model validation errors
                    return self._handle_final_validation_error(e)
            
        except ValidationError as e:
            return FormResponse(
                question=await self.question_generator.generate_question(current_config, self._context),
                errors=[str(e)],
                retry_prompt=f"Please provide a valid {current_field_name}. {e}",
                progress=self._calculate_progress(),
                current_field=current_field_name,
                collected_fields=list(self._collected_data.keys())
            )
        
        # Check if form is complete
        if self._current_field_index >= len(self._field_order):
            try:
                model_instance = await self._create_model_instance()
                return FormResponse(
                    is_complete=True,
                    data=model_instance,
                    progress=100.0,
                    collected_fields=list(self._collected_data.keys())
                )
            except ValidationError as e:
                # Handle final model validation errors by directing user to specific field
                return self._handle_final_validation_error(e)
        
        # Get next question
        return await self._get_next_question()
    
    async def _get_next_question(self) -> FormResponse[T]:
        """Get the next question in the sequence"""
        if self._current_field_index >= len(self._field_order):
            return FormResponse(
                is_complete=True,
                data=await self._create_model_instance(),
                progress=100.0
            )
        
        current_field_name = self._field_order[self._current_field_index]
        current_config = self._field_configs[current_field_name]
        
        # Check skip condition
        if current_config.skip_if and current_config.skip_if(self._collected_data):
            self._current_field_index += 1
            return await self._get_next_question()
        
        # Merge context with collected data for question generation
        combined_context = {**self._context, **self._collected_data}
        question = await self.question_generator.generate_question(current_config, combined_context)
        
        return FormResponse(
            question=question,
            progress=self._calculate_progress(),
            current_field=current_field_name,
            collected_fields=list(self._collected_data.keys())
        )
    
    async def _parse_field_value(self, config: FieldConfig, user_input: str) -> Any:
        """Parse and validate user input using AI-first validation"""
        return await self.ai_validator.validate_field(
            config,
            user_input,
            self._collected_data
        )
    
    
    def _handle_final_validation_error(self, e: ValidationError) -> FormResponse[T]:
        """Handle final model validation errors by directing to specific fields"""
        error_message = str(e)
        
        # Try to extract field-specific errors from Pydantic validation error
        if "Model validation failed:" in error_message:
            error_message = error_message.replace("Model validation failed: ", "")
        
        # Parse the error to find which field failed
        failed_field = None
        clean_error = error_message
        
        try:
            # Parse Pydantic error format to extract field name
            if "validation error" in error_message.lower():
                lines = error_message.split('\n')
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith(' ') and not 'validation error' in line.lower():
                        # This might be the field name
                        potential_field = line.strip()
                        if potential_field in self._field_configs:
                            failed_field = potential_field
                            # Get the actual error message
                            if i + 1 < len(lines):
                                clean_error_line = lines[i + 1].strip()
                                if 'Value error,' in clean_error_line:
                                    clean_error = clean_error_line.replace('Value error, ', '')
                                elif 'type=' in clean_error_line:
                                    # Extract message before type= part
                                    clean_error = clean_error_line.split('[type=')[0].strip()
                            break
        except Exception:
            # If parsing fails, use original error
            pass
        
        # Set current field to the failed field for retry
        if failed_field and failed_field in self._field_order:
            self._current_field_index = self._field_order.index(failed_field)
            current_field = failed_field
            # Remove the failed field's data so it gets re-collected
            if failed_field in self._collected_data:
                del self._collected_data[failed_field]
        else:
            # Default to last field
            self._current_field_index = max(0, len(self._field_order) - 1)
            current_field = self._field_order[self._current_field_index] if self._field_order else None
        
        return FormResponse(
            question=f"Please provide a valid {current_field}" if current_field else "Please check your input",
            errors=[clean_error],
            progress=self._calculate_progress(),
            current_field=current_field,
            collected_fields=list(self._collected_data.keys())
        )
    
    async def _create_model_instance(self) -> T:
        """Create and validate Pydantic model instance using AI validator"""
        try:
            # Use AI validator for form validation
            validated_data = await self.ai_validator.validate_form(
                self._collected_data,
                self.model_class,
                self._field_configs
            )
            
            # Create the model instance
            return self.model_class(**validated_data)
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Model creation failed: {e}")
    
    def _calculate_progress(self) -> float:
        """Calculate form completion progress"""
        if not self._field_order:
            return 100.0
        return (self._current_field_index / len(self._field_order)) * 100.0