from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, get_type_hints
from pydantic import BaseModel, ValidationError as PydanticValidationError
from pydantic_core import PydanticUndefined
import inspect

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel

from ..types.enums import ConversationMode, FieldPriority, ValidationStrategy
from ..types.responses import FormResponse
from ..types.config import FieldConfig
from ..types.exceptions import ConfigurationError, ValidationError
from ..generators.base import QuestionGenerator, DefaultQuestionGenerator, PydanticAIQuestionGenerator  
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
        use_ai: bool = True,
        ai_model: str = "openai:gpt-4o-mini",
        test_mode: bool = False
    ):
        self.model_class = model_class
        self.mode = mode
        self.validation = validation
        self.use_ai = use_ai
        self.ai_model = ai_model
        self.test_mode = test_mode
        
        # Initialize AI validator (handles validation logic)
        from ..validation.ai_validator import AiValidator
        self.ai_validator = AiValidator(
            use_ai=self.use_ai,
            test_mode=test_mode,
            ai_model=ai_model
        )
        
        # Core conversational AI agent (handles conversation flow)
        if self.use_ai:
            model = TestModel() if test_mode else ai_model
            self.agent = Agent(
                model=model,
                system_prompt=self._build_system_prompt()
            )
            
            # Add tools to agent for field storage during conversation
            @self.agent.tool
            def store_field_value(ctx: RunContext['AIForm'], field_name: str, value: str) -> str:
                """Store a field value when extracted from user input"""
                return ctx.deps._store_field_value_impl(field_name, value)
            
            @self.agent.tool  
            def get_missing_fields(ctx: RunContext['AIForm']) -> str:
                """Check what fields are still needed"""
                return ctx.deps._get_missing_fields_impl()
            
            @self.agent.tool
            def validate_complete_form(ctx: RunContext['AIForm']) -> str:
                """Check if form is complete and ready for submission"""
                return ctx.deps._validate_complete_form_impl()
        else:
            self.agent = None
        
        self._field_configs: Dict[str, FieldConfig] = {}
        self._collected_data: Dict[str, Any] = {}
        self._conversation_history = []  # Will store pydantic-ai conversation history
        self._form_complete = False
        self._started = False
        self._field_order: List[str] = []
        self._context: Dict[str, Any] = {}
        
        self._initialize_fields()
        self._calculate_field_order()
    
    def _build_system_prompt(self) -> str:
        """Build conversational system prompt from model definition"""
        form_name = self.model_class.__name__
        form_doc = self.model_class.__doc__ or f"{form_name} form"
        
        # Extract field information for prompt
        model_fields = self.model_class.model_fields
        type_hints = get_type_hints(self.model_class)
        
        field_descriptions = []
        for field_name, field_info in model_fields.items():
            field_type = type_hints.get(field_name, str)
            description = field_info.description or f"{field_name} field"
            
            # Get validation constraints
            constraints = []
            if hasattr(field_info, 'ge') and field_info.ge is not None:
                constraints.append(f"minimum: {field_info.ge}")
            if hasattr(field_info, 'le') and field_info.le is not None:
                constraints.append(f"maximum: {field_info.le}")
            
            # Get examples from json_schema_extra
            extra = field_info.json_schema_extra or {}
            examples = extra.get("examples", [])
            
            field_desc = f"- {field_name} ({field_type.__name__}): {description}"
            if constraints:
                field_desc += f" [{', '.join(constraints)}]"
            if examples:
                field_desc += f" (examples: {', '.join(examples[:3])})"
            
            field_descriptions.append(field_desc)
        
        return f"""You are helping a user fill out a {form_name} form through natural conversation.

{form_doc}

REQUIRED FIELDS:
{chr(10).join(field_descriptions)}

CRITICAL INSTRUCTIONS:
- When you extract ANY field values from user input, IMMEDIATELY call store_field_value(field_name, value)
- For boolean fields (like newsletter), responses like "yes", "sure", "no", "nope" are valid values - store them!
- ALWAYS call get_missing_fields() at the start of each response to check current status
- The tools tell you exactly what's stored and what's still needed - trust them completely
- When all fields are collected, call validate_complete_form() to finish
- If a field is successfully stored, don't ask for it again
- ASK ONLY ONE QUESTION AT A TIME - don't overwhelm the user with multiple questions
- Focus on the first missing field, then move to the next after it's collected

WORKFLOW:
1. Call get_missing_fields() to see what's needed
2. If user provides data, immediately call store_field_value() 
3. Ask for the FIRST missing field only (one question at a time)
4. When no fields missing, call validate_complete_form()

IMPORTANT: Use the tools by calling them directly - do NOT mention the tool calls in your response text. The tools work behind the scenes.

Examples:
1. Age field:
User: "I am 25 years old"
You internally: store_field_value("age", "25"), get_missing_fields()
Response: "Perfect! I've got your age as 25. Now, would you like to receive our newsletter?"

2. Boolean field:
User: "sure" or "yes" 
You internally: store_field_value("newsletter", "sure"), get_missing_fields()
Response: "Great! Thanks for completing the form!"

Start by greeting the user, then immediately check what fields are needed and ask for the first one."""

    def _store_field_value_impl(self, field_name: str, value: str) -> str:
        """Store a field value during conversation"""
        if field_name not in self._field_configs:
            available_fields = list(self._field_configs.keys())
            return f"Error: Unknown field '{field_name}'. Available fields: {available_fields}"
        
        try:
            config = self._field_configs[field_name]
            
            # Parse the value based on field type
            if config.field_type == int:
                parsed_value = int(value)
            elif config.field_type == bool:
                parsed_value = value.lower() in ('yes', 'true', 'y', '1', 'sure', 'ok', 'definitely', 'of course')
            else:
                parsed_value = value
            
            # Store the value
            self._collected_data[field_name] = parsed_value
            
            # Check if form is now complete
            missing = self._get_missing_required_fields()
            if not missing:
                self._form_complete = True
            
            return f"✅ Successfully stored {field_name}: {parsed_value}. Current data: {dict(self._collected_data)}"
            
        except (ValueError, TypeError) as e:
            return f"❌ Error parsing {field_name} with value '{value}': {e}"
    
    def _get_missing_fields_impl(self) -> str:
        """Get current form status - what's collected and what's still needed"""
        required_fields = [name for name, config in self._field_configs.items() if config.required]
        collected = {k: v for k, v in self._collected_data.items() if k in required_fields}
        missing = [field for field in required_fields if field not in self._collected_data]
        
        status = f"FORM STATUS: Collected: {collected}. "
        if missing:
            status += f"Still need: {', '.join(missing)}"
        else:
            status += "✅ ALL FIELDS COLLECTED!"
        
        return status
    
    def _validate_complete_form_impl(self) -> str:
        """Check if form is complete and ready for submission"""
        required_fields = [name for name, config in self._field_configs.items() if config.required]
        missing = [field for field in required_fields if field not in self._collected_data]
        
        if missing:
            return f"Form incomplete. Still need: {', '.join(missing)}"
        
        try:
            # Create the model instance to validate
            model_instance = self.model_class(**self._collected_data)
            self._form_complete = True
            return "Form validation successful! Ready to submit."
        except Exception as e:
            return f"Form validation failed: {e}"

    async def _extract_and_validate_fields(self, user_input: str):
        """Extract and validate field values from user input using ai_validator"""
        # Try to extract values for each missing field
        for field_name, config in self._field_configs.items():
            if field_name not in self._collected_data:  # Only process missing fields
                try:
                    # Use ai_validator to validate and parse the field from user input
                    validated_value = await self.ai_validator.validate_field(
                        config, 
                        user_input, 
                        self._collected_data
                    )
                    self._collected_data[field_name] = validated_value
                except Exception:
                    # If validation fails, field remains missing
                    continue
    
    def _get_missing_required_fields(self) -> List[str]:
        """Get list of required fields that are still missing"""
        required_fields = [name for name, config in self._field_configs.items() if config.required]
        return [field for field in required_fields if field not in self._collected_data]
    
    def _calculate_progress(self) -> float:
        """Calculate form completion progress"""
        total_fields = len(self._field_configs)
        if total_fields == 0:
            return 100.0
        collected_count = len(self._collected_data)
        return (collected_count / total_fields) * 100.0
    
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
    
    def _calculate_field_order(self):
        """Calculate field order based on priority and dependencies"""
        # Simple implementation - just use the order from field configs
        # In the future this could implement proper dependency resolution
        self._field_order = list(self._field_configs.keys())
        
    
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
        """Start the conversational form"""
        self._started = True
        
        if not self.use_ai or not self.agent:
            # Fallback to simple mode
            return FormResponse(
                question="Please provide the required information.",
                progress=0.0
            )
        
        # Start conversation with AI agent and store conversation history
        result = await self.agent.run("Hello", deps=self)
        self._conversation_history = result.all_messages()
        
        return FormResponse(
            question=result.output,
            progress=0.0,
            collected_fields=list(self._collected_data.keys())
        )
    
    async def respond(self, user_input: str) -> FormResponse[T]:
        """Process user response through conversational AI with tool usage"""
        if not self.use_ai or not self.agent:
            # Fallback to simple mode
            return FormResponse(
                question="AI not available. Please provide information.",
                progress=0.0
            )
        
        # Continue conversation with history context
        result = await self.agent.run(
            user_input, 
            deps=self, 
            message_history=self._conversation_history
        )
        self._conversation_history = result.all_messages()
        ai_response = result.output
        
        # Check if form is complete (agent would have called validate_complete_form)
        if self._form_complete:
            try:
                model_instance = self.model_class(**self._collected_data)
                return FormResponse(
                    is_complete=True,
                    data=model_instance,
                    progress=100.0,
                    collected_fields=list(self._collected_data.keys())
                )
            except Exception as e:
                return FormResponse(
                    question=f"Let me verify your information. {ai_response}",
                    progress=self._calculate_progress(),
                    errors=[str(e)],
                    collected_fields=list(self._collected_data.keys())
                )
        
        # Continue conversation
        return FormResponse(
            question=ai_response,
            progress=self._calculate_progress(),
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
    
