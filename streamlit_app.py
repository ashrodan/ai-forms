"""
Streamlit validation app for AI Forms testing
"""
import streamlit as st
import asyncio
from typing import Optional, List
from pydantic import BaseModel, Field

# Add the project to the path
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ai_forms import AIForm, FieldPriority, ConversationMode, ValidationStrategy
from ai_forms.generators.base import PYDANTIC_AI_AVAILABLE

if PYDANTIC_AI_AVAILABLE:
    from ai_forms.generators.base import PydanticAIQuestionGenerator
    from ai_forms.parsers.ai_parser import AIResponseParser

# Sample form models for testing
class UserRegistration(BaseModel):
    """Simple user registration form"""
    full_name: str = Field(
        description="Your full legal name",
        json_schema_extra={"priority": FieldPriority.CRITICAL}
    )
    email: str = Field(
        description="Email address",
        json_schema_extra={
            "priority": FieldPriority.CRITICAL,
            "examples": ["user@example.com", "name@company.org"]
        }
    )
    age: int = Field(
        description="Age in years",
        ge=13, le=120,
        json_schema_extra={"examples": ["25", "30", "35"]}
    )
    newsletter: bool = Field(
        description="Subscribe to newsletter?",
        json_schema_extra={"priority": FieldPriority.LOW}
    )

class JobApplication(BaseModel):
    """Job application with dependencies and conditional logic"""
    name: str = Field(
        description="Full name",
        json_schema_extra={"priority": FieldPriority.CRITICAL}
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
            "dependencies": ["position"]
        }
    )
    salary_expectation: Optional[int] = Field(
        None,
        description="Salary expectation (USD)",
        json_schema_extra={
            "priority": FieldPriority.LOW,
            "skip_if": lambda data: data.get("experience_years", 0) < 2
        }
    )
    skills: List[str] = Field(
        description="Your key skills",
        json_schema_extra={
            "examples": ["Python, JavaScript", "Design, UX Research", "Project Management"]
        }
    )

class SurveyForm(BaseModel):
    """Customer satisfaction survey"""
    satisfaction: int = Field(
        description="Satisfaction rating (1-10)",
        ge=1, le=10,
        json_schema_extra={"examples": ["8", "9", "10"]}
    )
    would_recommend: bool = Field(description="Would you recommend us?")
    improvement_areas: str = Field(
        description="What could we improve?",
        json_schema_extra={"priority": FieldPriority.MEDIUM}
    )
    additional_comments: Optional[str] = Field(
        None,
        description="Any additional comments?",
        json_schema_extra={"priority": FieldPriority.LOW}
    )

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
        else:
            test_mode = True
            
        # Reset button
        if st.button("🔄 Reset Form", type="secondary"):
            for key in list(st.session_state.keys()):
                if key.startswith('form_'):
                    del st.session_state[key]
            st.rerun()
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📋 Form Configuration")
        display_model_info(MODELS[selected_model_name])
        
        # Create form button
        if st.button("🚀 Initialize Form", type="primary"):
            create_form(
                MODELS[selected_model_name],
                conversation_mode,
                validation_strategy,
                use_ai and PYDANTIC_AI_AVAILABLE,
                test_mode
            )
    
    with col2:
        st.header("💬 Interactive Form")
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
        
        fields_data.append({
            "Field": field_name,
            "Type": field_type,
            "Priority": priority,
            "Description": description,
            "Examples": ", ".join(examples[:2]) if examples else "-",
            "Dependencies": ", ".join(dependencies) if dependencies else "-"
        })
    
    st.dataframe(fields_data, use_container_width=True)

def create_form(model_class, mode, validation, use_ai, test_mode):
    """Create and initialize a form"""
    try:
        # Create form
        form = AIForm(
            model_class,
            mode=mode,
            validation=validation,
            use_ai=use_ai
        )
        
        # Set AI components if enabled
        if use_ai and PYDANTIC_AI_AVAILABLE:
            form.question_generator = PydanticAIQuestionGenerator(test_mode=test_mode)
            form.response_parser = AIResponseParser(test_mode=test_mode)
        
        # Store in session state
        st.session_state.form_instance = form
        st.session_state.form_started = False
        st.session_state.form_responses = []
        st.session_state.current_response = None
        
        st.success("✅ Form initialized successfully!")
        
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
        st.info("👈 Initialize a form to start testing")
        return
    
    form = st.session_state.form_instance
    
    # Start form button
    if not st.session_state.get('form_started', False):
        if st.button("▶️ Start Form", type="primary"):
            try:
                response = asyncio.run(form.start())
                st.session_state.form_started = True
                st.session_state.current_response = response
                st.session_state.form_responses = [("START", response)]
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error starting form: {e}")
        return
    
    # Display current state
    current_response = st.session_state.get('current_response')
    if current_response:
        display_form_state(current_response)
        
        # If form is complete, show results
        if current_response.is_complete:
            display_completion_results(current_response)
            return
        
        # Input for next response
        st.subheader("💭 Your Response")
        
        # Show examples if available
        current_field = current_response.current_field
        if current_field and current_field in form._field_configs:
            config = form._field_configs[current_field]
            if config.examples:
                st.markdown(f"**Examples:** {', '.join(config.examples[:3])}")
        
        user_input = st.text_input(
            "Enter your response:",
            key=f"input_{len(st.session_state.form_responses)}",
            help="Type your answer to the current question"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Submit Response", type="primary"):
                if user_input.strip():
                    submit_response(form, user_input)
                else:
                    st.warning("⚠️ Please enter a response")
        
        with col2:
            if st.button("🔄 Reset Form"):
                reset_form()

def display_form_state(response):
    """Display current form state"""
    st.subheader("📈 Current State")
    
    # Progress bar
    progress = response.progress / 100.0
    st.progress(progress, text=f"Progress: {response.progress:.1f}%")
    
    # Current question
    if response.question:
        st.markdown("### 🤔 Current Question")
        st.markdown(f"**{response.question}**")
    
    # Current field info
    if response.current_field:
        st.markdown(f"**Current Field:** `{response.current_field}`")
    
    # Collected fields
    if response.collected_fields:
        st.markdown(f"**Completed Fields:** {', '.join(response.collected_fields)}")
    
    # Errors
    if response.errors:
        st.error("❌ Validation Errors:")
        for error in response.errors:
            st.markdown(f"- {error}")
        
        if response.retry_prompt:
            st.info(f"💡 {response.retry_prompt}")

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
        st.subheader("📊 Collected Data")
        
        # Convert to dict for display
        data_dict = response.data.model_dump()
        
        # Display as formatted JSON
        st.json(data_dict)
        
        # Display as table
        st.subheader("📋 Summary Table")
        summary_data = []
        for field, value in data_dict.items():
            summary_data.append({
                "Field": field,
                "Value": str(value),
                "Type": type(value).__name__
            })
        
        st.dataframe(summary_data, use_container_width=True)
    
    # Conversation history
    st.subheader("💬 Conversation History")
    
    for i, (user_input, form_response) in enumerate(st.session_state.form_responses):
        if user_input == "START":
            st.markdown(f"**🤖 System:** {form_response.question}")
        else:
            st.markdown(f"**👤 You:** {user_input}")
            if form_response.question and not form_response.is_complete:
                st.markdown(f"**🤖 System:** {form_response.question}")
            elif form_response.errors:
                st.markdown(f"**❌ Error:** {'; '.join(form_response.errors)}")

def reset_form():
    """Reset the form to initial state"""
    for key in ['form_started', 'form_responses', 'current_response']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

if __name__ == "__main__":
    main()
