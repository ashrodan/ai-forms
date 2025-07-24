"""
Streamlit validation app for AI Forms testing
"""
import streamlit as st
import asyncio
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project to the path
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ai_forms import AIForm, FieldPriority, ConversationMode, ValidationStrategy
from ai_forms.generators.base import PYDANTIC_AI_AVAILABLE

if PYDANTIC_AI_AVAILABLE:
    from ai_forms.generators.base import PydanticAIQuestionGenerator
    from ai_forms.parsers.ai_parser import AIResponseParser
    from ai_forms.validators.ai_tools import AIValidationTools, PYDANTIC_AI_AVAILABLE as AI_TOOLS_AVAILABLE
else:
    AI_TOOLS_AVAILABLE = False

# Sample form models for testing
class UserRegistration(BaseModel):
    """Simple user registration form"""
    full_name: str = Field(
        description="Your full legal name",
        json_schema_extra={
            "priority": FieldPriority.CRITICAL,
            "validation_hint": "min_length=2 max_length=50 pattern=^[a-zA-Z\\s\\-']+$"
        }
    )
    email: str = Field(
        description="Email address",
        json_schema_extra={
            "priority": FieldPriority.CRITICAL,
            "examples": ["user@example.com", "name@company.org"],
            "validation_hint": "email validation"
        }
    )
    age: int = Field(
        description="Age in years",
        ge=13, le=120,
        json_schema_extra={
            "examples": ["25", "30", "35"],
            "validation_hint": "min=13 max=120"
        }
    )
    newsletter: bool = Field(
        description="Subscribe to newsletter?",
        json_schema_extra={"priority": FieldPriority.LOW}
    )
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        from ai_forms.validators.base import FunctionValidator
        
        def name_validation(value):
            if not isinstance(value, str):
                return False
            value = value.strip()
            if len(value) < 2 or len(value) > 50:
                return False
            # Allow letters, spaces, hyphens, and apostrophes
            import re
            return bool(re.match(r"^[a-zA-Z\s\-']+$", value))
        
        validator = FunctionValidator(
            name_validation,
            "Name must be 2-50 characters and contain only letters, spaces, hyphens, and apostrophes"
        )
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v.strip()
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        from ai_forms.validators.base import EmailValidator
        validator = EmailValidator()
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v
    
    @field_validator('age')
    @classmethod
    def validate_age(cls, v):
        from ai_forms.validators.base import RangeValidator
        validator = RangeValidator(min_val=13, max_val=120)
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v

class JobApplication(BaseModel):
    """Job application with dependencies and conditional logic"""
    name: str = Field(
        description="Full name",
        json_schema_extra={
            "priority": FieldPriority.CRITICAL,
            "validation_hint": "min_length=2 max_length=50 pattern=^[a-zA-Z\\s\\-']+$"
        }
    )
    position: str = Field(
        description="Position applying for",
        json_schema_extra={
            "priority": FieldPriority.HIGH,
            "examples": ["Software Engineer", "Product Manager", "Designer"]
        }
    )
    experience_years: int = Field(
        description="Years of experience",
        json_schema_extra={
            "priority": FieldPriority.HIGH,
            "dependencies": ["position"],
            "validation_hint": "min=0 max=50"
        }
    )
    salary_expectation: Optional[int] = Field(
        None,
        description="Salary expectation (USD)",
        json_schema_extra={
            "priority": FieldPriority.LOW,
            "skip_if": lambda data: data.get("experience_years", 0) < 2,
            "validation_hint": "min=30000 max=500000"
        }
    )
    skills: List[str] = Field(
        description="Your key skills",
        json_schema_extra={
            "examples": ["Python, JavaScript", "Design, UX Research", "Project Management"]
        }
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        from ai_forms.validators.base import FunctionValidator
        
        def name_validation(value):
            if not isinstance(value, str):
                return False
            value = value.strip()
            if len(value) < 2 or len(value) > 50:
                return False
            # Allow letters, spaces, hyphens, and apostrophes
            import re
            return bool(re.match(r"^[a-zA-Z\s\-']+$", value))
        
        validator = FunctionValidator(
            name_validation,
            "Name must be 2-50 characters and contain only letters, spaces, hyphens, and apostrophes"
        )
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v.strip()
    
    @field_validator('experience_years')
    @classmethod
    def validate_experience(cls, v):
        from ai_forms.validators.base import RangeValidator
        validator = RangeValidator(min_val=0, max_val=50)
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v
    
    @field_validator('salary_expectation')
    @classmethod
    def validate_salary(cls, v):
        if v is None:
            return v
        from ai_forms.validators.base import RangeValidator
        validator = RangeValidator(min_val=30000, max_val=500000)
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v

class SurveyForm(BaseModel):
    """Customer satisfaction survey"""
    satisfaction: int = Field(
        description="Satisfaction rating (1-10)",
        ge=1, le=10,
        json_schema_extra={
            "examples": ["8", "9", "10"],
            "validation_hint": "min=1 max=10"
        }
    )
    would_recommend: bool = Field(description="Would you recommend us?")
    improvement_areas: str = Field(
        description="What could we improve?",
        json_schema_extra={
            "priority": FieldPriority.MEDIUM,
            "validation_hint": "min_length=10 max_length=500"
        }
    )
    additional_comments: Optional[str] = Field(
        None,
        description="Any additional comments?",
        json_schema_extra={
            "priority": FieldPriority.LOW,
            "validation_hint": "max_length=1000"
        }
    )
    
    @field_validator('satisfaction')
    @classmethod
    def validate_satisfaction(cls, v):
        from ai_forms.validators.base import RangeValidator
        validator = RangeValidator(min_val=1, max_val=10)
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v
    
    @field_validator('improvement_areas')
    @classmethod
    def validate_improvement_areas(cls, v):
        from ai_forms.validators.base import FunctionValidator
        
        def text_length_validation(value):
            if not isinstance(value, str):
                return False
            value = value.strip()
            return 10 <= len(value) <= 500
        
        validator = FunctionValidator(
            text_length_validation,
            "Improvement areas must be between 10 and 500 characters"
        )
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v.strip()
    
    @field_validator('additional_comments')
    @classmethod
    def validate_additional_comments(cls, v):
        if v is None:
            return v
        from ai_forms.validators.base import FunctionValidator
        
        def comment_length_validation(value):
            if not isinstance(value, str):
                return False
            return len(value.strip()) <= 1000
        
        validator = FunctionValidator(
            comment_length_validation,
            "Additional comments must be 1000 characters or less"
        )
        if not validator.validate(v, {}):
            raise ValueError(validator.get_error_message(v))
        return v.strip() if v else None

# Available models
MODELS = {
    "User Registration": UserRegistration,
    "Job Application": JobApplication,
    "Customer Survey": SurveyForm
}

def main():
    st.set_page_config(
        page_title="AI Forms Validator",
        page_icon="📝",
        layout="wide"
    )
    
    st.title("🤖 AI Forms Interactive Validator")
    st.markdown("Test your AI Forms configurations and workflows in real-time")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Form Configuration")
        
        # Model selection
        selected_model_name = st.selectbox(
            "Select Form Model",
            options=list(MODELS.keys()),
            help="Choose a pre-built form model to test"
        )
        
        # Form settings
        st.subheader("Form Settings")
        
        conversation_mode = st.selectbox(
            "Conversation Mode",
            options=[ConversationMode.SEQUENTIAL, ConversationMode.CLUSTERED, ConversationMode.ONE_SHOT],
            format_func=lambda x: x.value.title(),
            help="How fields are presented to users"
        )
        
        validation_strategy = st.selectbox(
            "Validation Strategy", 
            options=[ValidationStrategy.IMMEDIATE, ValidationStrategy.FINAL, ValidationStrategy.END_OF_CLUSTER],
            format_func=lambda x: x.value.title(),
            help="When validation occurs"
        )
        
        # AI configuration
        st.subheader("AI Configuration")
        
        use_ai = st.checkbox(
            "Enable AI Features",
            value=PYDANTIC_AI_AVAILABLE,
            disabled=not PYDANTIC_AI_AVAILABLE,
            help="Use AI for intelligent question generation and response parsing"
        )
        
        if not PYDANTIC_AI_AVAILABLE:
            st.warning("⚠️ Pydantic AI not available. Using default generators.")
        
        if use_ai and PYDANTIC_AI_AVAILABLE:
            test_mode = st.checkbox(
                "Test Mode",
                value=True,
                help="Use test mode for predictable responses (no API keys needed)"
            )
            
            # AI Validation Tools toggle
            use_ai_validation = st.checkbox(
                "Enable AI Validation Tools",
                value=AI_TOOLS_AVAILABLE,
                disabled=not AI_TOOLS_AVAILABLE,
                help="Use AI chat tools for validation (new feature)"
            )
        else:
            test_mode = True
            use_ai_validation = False
            
        if not AI_TOOLS_AVAILABLE and use_ai:
            st.info("ℹ️ AI Validation Tools available but not enabled for this session")
            
        # Reset button
        if st.button("🔄 Reset Form", type="secondary"):
            for key in list(st.session_state.keys()):
                if key.startswith('form_'):
                    del st.session_state[key]
            st.rerun()
    
    # Main content area - single column layout
    st.header("📋 Form Configuration")
    display_model_info(MODELS[selected_model_name])
    
    # Create form button
    if st.button("🚀 Initialize Form", type="primary"):
        create_form(
            MODELS[selected_model_name],
            conversation_mode,
            validation_strategy,
            use_ai and PYDANTIC_AI_AVAILABLE,
            test_mode,
            use_ai_validation if 'use_ai_validation' in locals() else False
        )
    
    # Form summary and progress section
    display_form_summary()
    
    # AI Validation Tools Testing section (only if enabled)
    if AI_TOOLS_AVAILABLE:
        st.header("🔧 AI Validation Tools Testing")
        test_ai_validation_tools()
    
    # Interactive chat section
    st.header("💬 Interactive Form Chat")
    handle_form_interaction()

def display_model_info(model_class):
    """Display information about the selected model"""
    st.subheader(f"📊 {model_class.__name__} Structure")
    
    # Model docstring
    if model_class.__doc__:
        st.markdown(f"*{model_class.__doc__}*")
    
    # Field information
    st.markdown("**Fields:**")
    
    fields_data = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = str(field_info.annotation).replace("typing.", "")
        description = field_info.description or "No description"
        
        # Get extra metadata
        extra = field_info.json_schema_extra or {}
        priority = extra.get("priority", FieldPriority.MEDIUM).value
        examples = extra.get("examples", [])
        dependencies = extra.get("dependencies", [])
        
        # Get validation hint
        validation_hint = extra.get("validation_hint", "-")
        
        fields_data.append({
            "Field": field_name,
            "Type": field_type,
            "Priority": priority,
            "Description": description,
            "Validation": validation_hint,
            "Examples": ", ".join(examples[:2]) if examples else "-",
            "Dependencies": ", ".join(dependencies) if dependencies else "-"
        })
    
    st.dataframe(fields_data, use_container_width=True)

def display_form_summary():
    """Display form summary with progress and accordion details"""
    if 'form_instance' not in st.session_state:
        return
    
    if not st.session_state.get('form_started', False):
        return
        
    current_response = st.session_state.get('current_response')
    if not current_response:
        return
    
    st.header("📈 Form Progress & Summary")
    
    # Progress bar and basic info
    progress = current_response.progress / 100.0
    st.progress(progress, text=f"Progress: {current_response.progress:.1f}%")
    
    # Summary metrics in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current Field", current_response.current_field or "Complete")
    with col2:
        st.metric("Fields Completed", len(current_response.collected_fields))
    with col3:
        error_count = len(current_response.errors) if current_response.errors else 0
        st.metric("Validation Errors", error_count, delta=f"-{error_count}" if error_count > 0 else None)
    
    # Accordion with detailed progress
    with st.expander("📋 Detailed Progress", expanded=False):
        if current_response.collected_fields:
            st.markdown("**✅ Completed Fields:**")
            for field in current_response.collected_fields:
                st.markdown(f"- `{field}`")
        
        if current_response.current_field:
            st.markdown(f"**🔄 Currently Processing:** `{current_response.current_field}`")
        
        if current_response.errors:
            st.markdown("**❌ Current Errors:**")
            for error in current_response.errors:
                st.markdown(f"- {error}")
        
        # Show field order from form
        form = st.session_state.form_instance
        st.markdown("**📑 Field Processing Order:**")
        for i, field_name in enumerate(form._field_order, 1):
            status = "✅" if field_name in current_response.collected_fields else ("🔄" if field_name == current_response.current_field else "⏳")
            st.markdown(f"{status} {i}. `{field_name}`")

def create_form(model_class, mode, validation, use_ai, test_mode, use_ai_validation=False):
    """Create and initialize a form"""
    try:
        # Create form with AI validation tools if enabled
        form = AIForm(
            model_class,
            mode=mode,
            validation=validation,
            use_ai=use_ai,
            test_mode=test_mode
        )
        
        # Set AI components if enabled
        if use_ai and PYDANTIC_AI_AVAILABLE:
            form.question_generator = PydanticAIQuestionGenerator(test_mode=test_mode)
            form.response_parser = AIResponseParser(test_mode=test_mode)
            
            # AI validation tools are automatically created by the form constructor when use_ai=True
        
        # Store in session state
        st.session_state.form_instance = form
        st.session_state.form_started = False
        st.session_state.form_responses = []
        st.session_state.current_response = None
        
        # Success message with AI validation tools status
        success_msg = "✅ Form initialized successfully!"
        if form.validation_tools and use_ai:
            success_msg += "\n🤖 AI Validation Tools: ACTIVE"
            if test_mode:
                success_msg += " (Test Mode)"
            else:
                success_msg += " (Live AI Mode)"
        elif use_ai and PYDANTIC_AI_AVAILABLE:
            success_msg += "\n🤖 AI Components: Active (Question Generation & Response Parsing only)"
        else:
            success_msg += "\n📝 Standard Form Mode (No AI)"
        
        # Debug info about form fields
        if st.checkbox("Show Debug Info", value=False, help="Show form field debugging information"):
            st.info(f"📊 Model fields: {list(form._field_configs.keys())}")
            st.info(f"📋 Field order: {form._field_order}")
            if hasattr(form, 'validation_tools') and form.validation_tools:
                st.info(f"🔧 Validation tools active: {form.validation_tools is not None}")
                st.info(f"🧪 Test mode: {form.validation_tools.test_mode if form.validation_tools else 'N/A'}")
        
        st.success(success_msg)
        
        # Display field order
        st.subheader("📑 Field Processing Order")
        field_order_data = []
        for i, field_name in enumerate(form._field_order, 1):
            config = form._field_configs[field_name]
            field_order_data.append({
                "Order": i,
                "Field": field_name,
                "Priority": config.priority.value,
                "Dependencies": ", ".join(config.dependencies) if config.dependencies else "-"
            })
        
        st.dataframe(field_order_data, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Error creating form: {e}")

def handle_form_interaction():
    """Handle the interactive form conversation"""
    if 'form_instance' not in st.session_state:
        st.info("👆 Initialize a form to start the interactive chat")
        return
    
    form = st.session_state.form_instance
    
    # Start form button
    if not st.session_state.get('form_started', False):
        if st.button("▶️ Start Conversation", type="primary"):
            try:
                response = asyncio.run(form.start())
                st.session_state.form_started = True
                st.session_state.current_response = response
                st.session_state.form_responses = [("START", response)]
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error starting form: {e}")
        return
    
    current_response = st.session_state.get('current_response')
    if not current_response:
        return
        
    # If form is complete, show results
    if current_response.is_complete:
        display_completion_results(current_response)
        return
    
    # Display current question prominently
    if current_response.question:
        st.markdown("### 🤔 Current Question")
        st.markdown(f"**{current_response.question}**")
    
    # Show validation errors if any
    if current_response.errors:
        st.error("❌ Please fix the following:")
        for error in current_response.errors:
            st.markdown(f"- {error}")
        
        if current_response.retry_prompt:
            st.info(f"💡 {current_response.retry_prompt}")
    
    # Show examples if available
    current_field = current_response.current_field
    if current_field and current_field in form._field_configs:
        config = form._field_configs[current_field]
        if config.examples:
            st.markdown(f"**💡 Examples:** {', '.join(config.examples[:3])}")
    
    # Input area
    user_input = st.text_input(
        "Your response:",
        key=f"input_{len(st.session_state.form_responses)}",
        placeholder="Type your answer here...",
        help="Enter your response to the current question"
    )
    
    # Action buttons
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("📤 Submit Response", type="primary", use_container_width=True):
            if user_input.strip():
                submit_response(form, user_input)
            else:
                st.warning("⚠️ Please enter a response")
    
    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            reset_form()
    
    with col3:
        if st.button("📜 History", use_container_width=True):
            display_conversation_history()
    
    # Conversation history (collapsed by default)
    if st.session_state.get('show_history', False):
        with st.expander("💬 Conversation History", expanded=True):
            display_conversation_history_content()

def display_conversation_history():
    """Toggle conversation history display"""
    st.session_state.show_history = not st.session_state.get('show_history', False)
    st.rerun()

def display_conversation_history_content():
    """Display the conversation history content"""
    if 'form_responses' not in st.session_state:
        st.info("No conversation history yet")
        return
    
    for i, (user_input, form_response) in enumerate(st.session_state.form_responses):
        if user_input == "START":
            st.markdown(f"**🤖 System:** {form_response.question}")
        else:
            st.markdown(f"**👤 You:** {user_input}")
            if form_response.question and not form_response.is_complete:
                st.markdown(f"**🤖 System:** {form_response.question}")
            elif form_response.errors:
                st.markdown(f"**❌ Error:** {'; '.join(form_response.errors)}")
        
        if i < len(st.session_state.form_responses) - 1:
            st.markdown("---")

def submit_response(form, user_input):
    """Submit user response and update state"""
    try:
        response = asyncio.run(form.respond(user_input))
        st.session_state.current_response = response
        st.session_state.form_responses.append((user_input, response))
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error processing response: {e}")

def display_completion_results(response):
    """Display form completion results"""
    st.success("🎉 Form Complete!")
    
    # Final data
    if response.data:
        # Convert to dict for display
        data_dict = response.data.model_dump()
        
        # Display summary metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Fields", len(data_dict))
        with col2:
            st.metric("Conversation Steps", len(st.session_state.form_responses))
        
        # Display as formatted JSON in expandable section
        with st.expander("📊 Raw Data (JSON)", expanded=False):
            st.json(data_dict)
        
        # Display as clean summary table
        st.subheader("📋 Final Results")
        summary_data = []
        for field, value in data_dict.items():
            summary_data.append({
                "Field": field,
                "Value": str(value),
                "Type": type(value).__name__
            })
        
        st.dataframe(summary_data, use_container_width=True)
        
        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Start New Form", type="primary", use_container_width=True):
                reset_form()
        with col2:
            if st.button("📜 View History", use_container_width=True):
                st.session_state.show_history = True
                st.rerun()

    # Show conversation history if requested
    if st.session_state.get('show_history', False):
        with st.expander("💬 Full Conversation History", expanded=True):
            display_conversation_history_content()

def test_ai_validation_tools():
    """Test AI validation tools directly"""
    if not AI_TOOLS_AVAILABLE:
        st.info("AI Validation Tools not available")
        return
    
    with st.expander("🤖 Test AI Validation Tools", expanded=False):
        st.markdown("Test the AI validation tools directly without running a full form.")
        
        # Create validation tools instance
        if 'validation_tools' not in st.session_state:
            st.session_state.validation_tools = AIValidationTools(test_mode=True)
        
        tools = st.session_state.validation_tools
        
        # Test field validation
        st.subheader("🔍 Field Validation Test")
        
        col1, col2 = st.columns(2)
        with col1:
            field_name = st.selectbox(
                "Field Name",
                options=["email", "age", "name", "tags", "consent"],
                help="Select a field type to test"
            )
            
            field_type = st.selectbox(
                "Field Type",
                options=["str", "int", "bool", "List[str]", "float"],
                help="Select the expected data type"
            )
        
        with col2:
            field_value = st.text_input(
                "Test Value",
                placeholder="Enter a value to validate",
                help="Enter the value you want to validate"
            )
            
            validation_hint = st.text_input(
                "Validation Hint (optional)",
                placeholder="e.g., email validation, min=1 max=10",
                help="Optional validation hints"
            )
        
        if st.button("🔍 Test Field Validation", type="primary"):
            if field_value:
                result = tools.validate_field(
                    field_name=field_name,
                    field_value=field_value,
                    field_type=field_type,
                    field_description=f"Test {field_name} field",
                    validation_hint=validation_hint if validation_hint else None
                )
                
                # Display results
                if result.is_valid:
                    st.success("✅ Validation Passed!")
                    st.json({
                        "input": field_value,
                        "parsed_value": result.parsed_value,
                        "type": str(type(result.parsed_value).__name__)
                    })
                else:
                    st.error(f"❌ Validation Failed: {result.error_message}")
                    st.json({
                        "input": field_value,
                        "error": result.error_message,
                        "raw_value": result.parsed_value
                    })
        
        # Test form validation
        st.subheader("📋 Form Validation Test")
        
        # Predefined test data
        test_forms = {
            "Valid User Data": {
                "name": "John Doe",
                "email": "john@example.com", 
                "age": 25
            },
            "Invalid Email": {
                "name": "Jane Smith",
                "email": "invalid-email",
                "age": 30
            },
            "Missing Required Field": {
                "email": "test@example.com",
                "age": 25
            }
        }
        
        selected_test = st.selectbox(
            "Select Test Form Data",
            options=list(test_forms.keys()),
            help="Choose predefined test data or create custom"
        )
        
        # Show and allow editing of test data
        test_data = test_forms[selected_test].copy()
        st.json(test_data)
        
        if st.button("🔍 Test Form Validation", type="primary"):
            field_configs = {
                "name": {"required": True, "field_type": "str"},
                "email": {"required": True, "field_type": "str"},
                "age": {"required": True, "field_type": "int"}
            }
            
            result = tools.validate_form(
                form_data=test_data,
                model_class_name="TestModel",
                field_configs=field_configs
            )
            
            if result.is_valid:
                st.success("✅ Form Validation Passed!")
                st.json(result.parsed_value)
            else:
                st.error(f"❌ Form Validation Failed: {result.error_message}")
        
        # Quick examples section
        st.subheader("💡 Quick Examples")
        
        examples = [
            ("Email Validation", "test@example.com", "str", "email validation"),
            ("Age Range", "25", "int", "min=18 max=120"),
            ("Boolean Parse - Yes", "yes", "bool", ""),
            ("Boolean Parse - Sure", "sure", "bool", ""),
            ("Boolean Parse - OK", "ok", "bool", ""),
            ("Boolean Parse - Nope", "nope", "bool", ""),
            ("List Parse", "python, web, backend", "List[str]", ""),
            ("Written Number", "twenty", "int", ""),
            ("Invalid Email", "not-an-email", "str", "email validation")
        ]
        
        for desc, value, ftype, hint in examples:
            if st.button(f"🚀 Test: {desc}", key=f"example_{desc}"):
                result = tools.validate_field(
                    field_name="test_field",
                    field_value=value,
                    field_type=ftype,
                    field_description=desc,
                    validation_hint=hint if hint else None
                )
                
                with st.container():
                    if result.is_valid:
                        st.success(f"✅ {desc}: `{value}` → `{result.parsed_value}` ({type(result.parsed_value).__name__})")
                    else:
                        st.error(f"❌ {desc}: {result.error_message}")

def reset_form():
    """Reset the form to initial state"""
    for key in ['form_started', 'form_responses', 'current_response', 'show_history']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

if __name__ == "__main__":
    main()
