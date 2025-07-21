from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, get_type_hints
from pydantic import BaseModel, ValidationError as PydanticValidationError
import inspect

from ..types.enums import ConversationMode, FieldPriority, ValidationStrategy
from ..types.responses import FormResponse
from ..types.config import FieldConfig
from ..types.exceptions import ConfigurationError, ValidationError
from ..generators.base import QuestionGenerator, DefaultQuestionGenerator

T = TypeVar('T', bound=BaseModel)


class AIForm(Generic[T]):
    """AI-powered conversational form for collecting structured data"""
    
    def __init__(
        self,
        model_class: Type[T],
        mode: ConversationMode = ConversationMode.SEQUENTIAL,
        validation: ValidationStrategy = ValidationStrategy.IMMEDIATE,
        question_generator: Optional[QuestionGenerator] = None
    ):
        self.model_class = model_class
        self.mode = mode
        self.validation = validation
        self.question_generator = question_generator or DefaultQuestionGenerator()
        
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
                default=getattr(field_info, 'default', None)
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
                data=self.model_class(),
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
                data=self._create_model_instance(),
                progress=100.0
            )
        
        current_field_name = self._field_order[self._current_field_index]
        current_config = self._field_configs[current_field_name]
        
        # Validate and store the input
        try:
            parsed_value = await self._parse_field_value(current_config, user_input)
            self._collected_data[current_field_name] = parsed_value
            self._current_field_index += 1
            
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
            return FormResponse(
                is_complete=True,
                data=self._create_model_instance(),
                progress=100.0,
                collected_fields=list(self._collected_data.keys())
            )
        
        # Get next question
        return await self._get_next_question()
    
    async def _get_next_question(self) -> FormResponse[T]:
        """Get the next question in the sequence"""
        if self._current_field_index >= len(self._field_order):
            return FormResponse(
                is_complete=True,
                data=self._create_model_instance(),
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
        """Parse and validate user input for a specific field"""
        # Basic parsing - this would be enhanced with AI in a real implementation
        value = user_input.strip()
        
        # Simple type conversion
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
        
        return value
    
    def _create_model_instance(self) -> T:
        """Create and validate Pydantic model instance"""
        try:
            return self.model_class(**self._collected_data)
        except PydanticValidationError as e:
            raise ValidationError(f"Model validation failed: {e}")
    
    def _calculate_progress(self) -> float:
        """Calculate form completion progress"""
        if not self._field_order:
            return 100.0
        return (self._current_field_index / len(self._field_order)) * 100.0