# AI Forms - Interface Specification

## Core Philosophy

**"Type-safe, conversational forms that feel natural"**

- **Typed First**: Full TypeScript-like experience with Pydantic
- **Conversational**: AI handles the conversation flow intelligently  
- **Configurable**: From simple to highly customized forms
- **Extensible**: Plugin architecture for custom behaviors

## 1. Basic Interface

### Simplest Possible Usage
```python
from ai_forms import AIForm
from pydantic import BaseModel, Field

class UserInfo(BaseModel):
    name: str = Field(description="Your full name")
    email: str = Field(description="Email address")

# Create and use
form = AIForm(UserInfo)
response = await form.start()               # Returns first question
response = await form.respond("John Doe")   # Submit answer
response = await form.respond("john@email.com")  # Form completes

# Get typed result
user: UserInfo = response.data  # Fully typed!
```

### Key Principles
1. **Pydantic Model First**: The form structure comes from your Pydantic model
2. **Async by Default**: All interactions are async for AI agent calls
3. **Typed Results**: You get back exactly the type you defined
4. **Progressive**: Each `respond()` call advances the conversation

## 2. Conversation Modes

```python
# Sequential: One question at a time (default)
form = AIForm(UserInfo, mode=ConversationMode.SEQUENTIAL)

# One-shot: All questions at once
form = AIForm(UserInfo, mode=ConversationMode.ONE_SHOT)

# Clustered: Group related questions
form = AIForm(UserInfo, mode=ConversationMode.CLUSTERED)
```

**Mode Behaviors:**
- **SEQUENTIAL**: "What's your name?" → response → "What's your email?" → response
- **ONE_SHOT**: "Please provide your name and email address"
- **CLUSTERED**: "Let's start with contact info: name and email" → "Now work info: company and role"

## 3. Field Configuration Interface

### Fluent Configuration
```python
form = (AIForm(UserInfo)
        .configure_field("name", 
                        priority=FieldPriority.CRITICAL,
                        custom_question="What should I call you?")
        .configure_field("email",
                        examples=["user@example.com"],
                        validation_hint="Use your work email if possible"))
```

### Rich Pydantic Metadata
```python
class JobApplication(BaseModel):
    name: str = Field(
        description="Full legal name",
        json_schema_extra={
            "priority": FieldPriority.CRITICAL,
            "cluster": "identity", 
            "custom_question": "What's your full legal name?",
            "examples": ["John Smith", "María García"]
        }
    )
    
    salary: Optional[int] = Field(
        None,
        description="Expected salary",
        json_schema_extra={
            "priority": FieldPriority.LOW,
            "skip_if": lambda data: data.get("experience_years", 0) < 2,
            "validation_hint": "Annual salary in USD"
        }
    )
```

## 4. Hook System Interface

### Simple Hooks
```python
# Condition + Action pattern
form.add_hook(
    name="student_check",
    condition=lambda data: data.get("age", 100) < 18,
    action="Are you currently a student? What grade/year?"
)
```

### Advanced Hooks
```python
# Async hooks for complex logic
async def career_guidance(data):
    age = data.get("age")
    education = data.get("education_level")
    
    if age and education:
        # Could call external APIs, run ML models, etc.
        guidance = await get_career_suggestions(age, education)
        return f"Based on your background, consider: {guidance}"
    return None

form.add_async_hook(
    name="career_guidance",
    condition=lambda data: "age" in data and "education_level" in data,
    action=career_guidance
)
```

### Hook Types
```python
# React to field collection
form.on_field_collected("email", validate_email_domain)

# React to validation errors  
form.on_validation_error("age", suggest_age_format)

# React to form completion
form.on_complete(send_confirmation_email)

# Custom validation hooks
form.add_validation_hook(
    field="email",
    validator=lambda email: email.endswith("@company.com"),
    message="Please use your company email"
)
```

## 5. Response Interface

```python
@dataclass
class FormResponse:
    # Status
    is_complete: bool
    success: bool
    
    # Content
    question: Optional[str]        # Next question to ask
    message: Optional[str]         # System message
    data: Optional[T]              # Completed form data (typed!)
    
    # Progress
    progress: float                # 0.0 to 100.0
    current_field: Optional[str]   # Field being collected
    collected_fields: Dict[str, Any]  # What's been collected so far
    
    # Validation
    errors: List[str]              # Current validation errors
    retry_prompt: Optional[str]    # Suggested retry message
    
    # Metadata  
    hooks_triggered: List[str]     # Which hooks fired
    cluster: Optional[str]         # Current cluster (if clustered mode)
    metadata: Dict[str, Any]       # Custom metadata
```

## 6. Validation Interface

### Built-in Validation Strategies
```python
# Validate immediately after each field
form = AIForm(UserInfo, validation=ValidationStrategy.IMMEDIATE)

# Validate after completing each cluster
form = AIForm(UserInfo, validation=ValidationStrategy.CLUSTER)

# Only validate at the very end
form = AIForm(UserInfo, validation=ValidationStrategy.FINAL)
```

### Custom Validators
```python
from ai_forms.validators import EmailValidator, PhoneValidator, AgeValidator

form.add_validator("email", EmailValidator(require_work_domain=True))
form.add_validator("phone", PhoneValidator(country_code="US"))  
form.add_validator("age", AgeValidator(min_age=13, max_age=120))

# Custom validator
def validate_username(username: str) -> ValidationResult:
    if len(username) < 3:
        return ValidationResult(valid=False, message="Username too short")
    if not username.isalnum():
        return ValidationResult(valid=False, message="Username must be alphanumeric")
    return ValidationResult(valid=True)

form.add_validator("username", validate_username)
```

## 7. Question Generation Interface

### Built-in Generators
```python
from ai_forms.generators import (
    DefaultQuestionGenerator,      # Simple field-based questions
    ContextualQuestionGenerator,   # Uses conversation context
    TemplateQuestionGenerator,     # Template-based with variables
)

form = AIForm(UserInfo, question_generator=ContextualQuestionGenerator())
```

### Custom Generator
```python
class PersonalizedGenerator(QuestionGenerator):
    async def generate_question(self, field_config: FieldConfig, context: Dict[str, Any]) -> str:
        user_name = context.get("name", "there")
        
        if field_config.name == "email":
            return f"Hi {user_name}! What's the best email to reach you?"
        
        # Fall back to default behavior
        return await super().generate_question(field_config, context)

form = AIForm(UserInfo, question_generator=PersonalizedGenerator())
```

## 8. Integration Patterns

### FastAPI WebSocket
```python
@app.websocket("/form")
async def form_endpoint(websocket: WebSocket):
    form = AIForm(UserProfile)
    response = await form.start()
    
    await websocket.send_json({
        "type": "question",
        "content": response.question,
        "progress": response.progress
    })
    
    async for message in websocket.iter_text():
        response = await form.respond(message)
        
        if response.is_complete:
            await websocket.send_json({
                "type": "complete", 
                "data": response.data.model_dump()
            })
            break
        else:
            await websocket.send_json({
                "type": "question",
                "content": response.question,
                "progress": response.progress
            })
```

### Streamlit
```python
def streamlit_form():
    form = st.session_state.get("form") or AIForm(UserProfile)
    
    if "current_response" not in st.session_state:
        st.session_state.current_response = asyncio.run(form.start())
    
    response = st.session_state.current_response
    
    if response.is_complete:
        st.success("Form completed!")
        st.json(response.data.model_dump())
    else:
        st.write(response.question)
        user_input = st.text_input("Your response:")
        
        if st.button("Submit") and user_input:
            st.session_state.current_response = asyncio.run(form.respond(user_input))
            st.rerun()
```

### CLI
```python
async def cli_form():
    form = AIForm(UserProfile)
    response = await form.start()
    
    while not response.is_complete:
        print(f"\n{response.question}")
        if response.errors:
            print(f"⚠️  {', '.join(response.errors)}")
        
        user_input = input("> ")
        response = await form.respond(user_input)
    
    print(f"✅ Complete! {response.data}")
```

## 9. Factory Functions

### Pre-built Forms
```python
from ai_forms.presets import (
    user_registration_form,
    contact_form, 
    job_application_form,
    survey_form,
    onboarding_form
)

# Quick setup with sensible defaults
registration = user_registration_form(
    mode=ConversationMode.CLUSTERED,
    require_phone=True,
    include_preferences=True
)

survey = survey_form([
    "How satisfied are you with our service?",
    "What could we improve?", 
    "Would you recommend us to others?"
], rating_scale=10)
```

### Custom Factories
```python
def create_job_application_form(position_type: str) -> AIForm[JobApplication]:
    form = AIForm(JobApplication, mode=ConversationMode.CLUSTERED)
    
    if position_type == "technical":
        form.configure_field("skills", 
                           examples=["Python", "JavaScript", "AWS"],
                           custom_question="What programming languages and technologies do you know?")
    elif position_type == "sales":
        form.configure_field("skills",
                           examples=["CRM", "Lead Generation", "Account Management"])
    
    return form
```

## 10. Advanced Features

### Context and Personalization
```python
# Set context that influences conversation
form.set_context({
    "user_type": "returning_customer",
    "previous_data": {"name": "Alice", "company": "TechCorp"},
    "source": "mobile_app",
    "time_of_day": "morning"
})

# Form adapts: "Good morning Alice! Are you still at TechCorp?"
```

### Multi-Step Forms
```python
class MultiStepJobApplication(AIForm[JobApplication]):
    async def step_1_personal_info(self):
        # Collect basic info
        pass
    
    async def step_2_experience(self):
        # Collect work history
        pass
    
    async def step_3_review(self):
        # Review and confirm
        return "Please review your application: ..."

form = MultiStepJobApplication()
```

### Analytics and Monitoring
```python
# Built-in analytics
analytics = form.get_analytics()
print(f"Completion rate: {analytics.completion_rate}")
print(f"Average time: {analytics.avg_completion_time}")
print(f"Drop-off points: {analytics.drop_off_fields}")

# Custom event tracking
form.on_field_collected(lambda field, value, time_taken: 
                       track_event("field_collected", field, time_taken))

form.on_error(lambda error, context:
              log_error("form_error", error, context))
```

## 11. Type Safety

### Full Type Safety
```python
# Input type is enforced
form: AIForm[UserProfile] = AIForm(UserProfile)

# Output type is guaranteed
response = await form.start()
if response.is_complete:
    user_data: UserProfile = response.data  # Type checker knows this is UserProfile
    print(user_data.name)  # IDE autocomplete works!
```

### Generic Form Helper
```python
async def collect_form_data[T: BaseModel](model_class: Type[T], **kwargs) -> T:
    form = AIForm(model_class, **kwargs)
    response = await form.start()
    
    while not response.is_complete:
        user_input = input(response.question + "\n> ")
        response = await form.respond(user_input)
    
    return response.data  # Return type is T

# Usage with perfect typing
user: UserProfile = await collect_form_data(UserProfile)
app: JobApplication = await collect_form_data(JobApplication, mode=ConversationMode.CLUSTERED)
```

## 12. Error Handling

### Graceful Error Recovery
```python
try:
    response = await form.respond("invalid data")
except ValidationError as e:
    # Form automatically handles validation errors
    print(response.retry_prompt)  # "Please provide a valid email address"
    
except AIFormError as e:
    # Handle form-specific errors
    print(f"Form error: {e.message}")
    
except Exception as e:
    # Unexpected errors
    print(f"Unexpected error: {e}")
    
    # Form can continue from last valid state
    response = await form.retry_last_question()
```

This interface design prioritizes:

1. **Developer Experience**: Simple for basic use, powerful for advanced cases
2. **Type Safety**: Full typing support with Pydantic integration
3. **Flexibility**: Multiple conversation modes and extensive configuration
4. **Extensibility**: Hook system and custom generators
5. **Integration**: Easy to embed in web apps, CLIs, or any Python environment
6. **AI-First**: Designed around conversational AI interaction patterns

The interface feels natural for Python developers while providing the intelligent conversational capabilities of modern AI systems.
