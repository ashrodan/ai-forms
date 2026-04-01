# AI Forms

**AI-powered conversational form builder** that transforms Pydantic models into natural, intelligent conversations.

## ✨ Key Features

- **🤖 Natural AI Conversations** - Turn rigid forms into friendly chat experiences
- **🧠 Smart Field Extraction** - AI extracts multiple fields from single responses ("I'm 25 and yes to newsletter")
- **🔧 Zero Setup** - Just add your Pydantic model and go
- **📊 Real-time Progress** - Track completion and validation in real-time

## 🚀 Quick Start

```bash
pip install ai-forms
```

### Set up your API key
```bash
export OPENAI_API_KEY="your-openai-key"
```

### Create a conversational form
```python
import asyncio
from pydantic import BaseModel, Field
from ai_forms import AIForm

class SimpleForm(BaseModel):
    age: int = Field(description="Your age in years", ge=13, le=120)
    newsletter: bool = Field(description="Subscribe to newsletter?")

async def main():
    # Create AI-powered form
    form = AIForm(SimpleForm)
    
    # Start conversation
    response = await form.start()
    print(f"Bot: {response.question}")
    # → "Hi! I'm here to help you fill out a quick form. What's your age in years?"
    
    while not response.is_complete:
        user_input = input("You: ")
        response = await form.respond(user_input)
        print(f"Bot: {response.question}")
    
    print(f"✅ Complete! Data: {response.data}")

asyncio.run(main())
```

**Example conversation:**
```
Bot: Hi! I'm here to help you fill out a quick form. What's your age in years?
You: I'm 25 years old and yes to newsletter
Bot: Perfect! Thanks for completing the form!
✅ Complete! Data: SimpleForm(age=25, newsletter=True)
```

## AI-Powered Features

### AI Question Generation

Transform static field descriptions into dynamic, contextual questions:

```python
from ai_forms import AIForm
from ai_forms.generators.base import PydanticAIQuestionGenerator

# Enable AI question generation
form = AIForm(UserProfile, use_ai=True)
form.question_generator = PydanticAIQuestionGenerator("openai:gpt-4o-mini")

# AI generates context-aware questions:
# Instead of: "Please provide your age (Age in years)"  
# AI generates: "How old are you? This helps us customize your experience."
```

### AI Response Parsing

Parse natural language responses intelligently:

```python
from ai_forms.parsers.ai_parser import AIResponseParser

# Enable AI response parsing
form.response_parser = AIResponseParser("openai:gpt-4o-mini")

# Now handles natural language:
await form.respond("I'm twenty-eight years old")     # → 28
await form.respond("Python, JavaScript, and Go")     # → ["Python", "JavaScript", "Go"]
await form.respond("yes, definitely!")               # → True
await form.respond("alice at example dot com")       # → "alice@example.com"
```

### Test Mode

For development and CI/CD, use deterministic test mode:

```python
# Test mode - no API keys required
form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
form.response_parser = AIResponseParser(test_mode=True)

# Returns predictable responses for testing
```

## Advanced Configuration

### Field Priorities & Customization

```python
form = (AIForm(UserProfile)
        .configure_field("name", priority="critical", 
                        custom_question="What should we call you?")
        .configure_field("email", priority="critical",
                        examples=["user@example.com"])
        .configure_field("newsletter", priority="low")
        .configure_field("age", validation_hint="Must be 13 or older"))
```

### Conversation Modes

```python
from ai_forms import ConversationMode

# Sequential (default) - one field at a time
form = AIForm(UserProfile, mode=ConversationMode.SEQUENTIAL)

# One-shot - all fields in one prompt (future)
form = AIForm(UserProfile, mode=ConversationMode.ONE_SHOT)

# Clustered - group related fields (future)  
form = AIForm(UserProfile, mode=ConversationMode.CLUSTERED)
```

### Field Dependencies & Skip Logic

```python
class JobApplication(BaseModel):
    name: str = Field(description="Full name")
    experience_years: int = Field(description="Years of experience")
    salary_expectation: Optional[int] = Field(
        None,
        description="Expected salary",
        json_schema_extra={
            "skip_if": lambda data: data.get("experience_years", 0) < 2,
            "dependencies": ["experience_years"]
        }
    )

# Automatically skips salary question for junior candidates
```

## Framework Integration

### FastAPI Integration

```python
from fastapi import FastAPI
from ai_forms import AIForm

app = FastAPI()

@app.post("/forms/{form_id}/respond")
async def respond_to_form(form_id: str, user_input: str):
    form = get_form(form_id)  # Your form storage logic
    response = await form.respond(user_input)
    
    return {
        "question": response.question,
        "is_complete": response.is_complete,
        "progress": response.progress,
        "errors": response.errors
    }
```

### Streamlit Integration

```python
import streamlit as st
from ai_forms import AIForm

if 'form' not in st.session_state:
    st.session_state.form = AIForm(UserProfile)
    response = await st.session_state.form.start()
    st.session_state.current_question = response.question

st.write(st.session_state.current_question)
user_input = st.text_input("Your response:")

if st.button("Submit") and user_input:
    response = await st.session_state.form.respond(user_input)
    if response.is_complete:
        st.success("Form completed!")
        st.json(response.data.model_dump())
    else:
        st.session_state.current_question = response.question
        st.rerun()
```

## Configuration

### Environment Variables

```bash
# For AI features (optional)
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"

# AI Forms will automatically detect and use available providers
```

### Model Configuration

```python
# OpenAI models
form.question_generator = PydanticAIQuestionGenerator("openai:gpt-4o-mini")
form.response_parser = AIResponseParser("openai:gpt-4")

# Anthropic models  
form.question_generator = PydanticAIQuestionGenerator("anthropic:claude-3-haiku")
form.response_parser = AIResponseParser("anthropic:claude-3-sonnet")

# Custom configuration
form.question_generator = PydanticAIQuestionGenerator(
    model_name="openai:gpt-4o-mini",
    custom_system_prompt="You are a friendly form assistant..."
)
```

## Testing

### Unit Testing

```python
import pytest
from ai_forms import AIForm
from ai_forms.generators.base import PydanticAIQuestionGenerator
from ai_forms.parsers.ai_parser import AIResponseParser

@pytest.mark.asyncio
async def test_form_completion():
    form = AIForm(UserProfile)
    # Use test mode for deterministic responses
    form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
    form.response_parser = AIResponseParser(test_mode=True)
    
    response = await form.start()
    assert response.question is not None
    
    # Test complete workflow
    response = await form.respond("Alice Johnson")
    response = await form.respond("28")
    response = await form.respond("alice@example.com") 
    response = await form.respond("yes")
    
    assert response.is_complete
    assert response.data.name == "Alice Johnson"
```

### Running Tests

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ai_forms
```

## Examples

See the [`examples/`](examples/) directory for complete examples:

- [`basic_ai_form.py`](examples/basic_ai_form.py) - Basic AI-powered form
- [`comparison_example.py`](examples/comparison_example.py) - AI vs default comparison

Run examples:

```bash
cd examples
python basic_ai_form.py
```

## Architecture

AI Forms is built on a modular architecture:

```
AIForm[T]          ← Main form controller
    ↓
QuestionGenerator  ← Pluggable question generation
ResponseParser     ← Pluggable response parsing  
ValidationStrategy ← Configurable validation
    ↓
Pydantic Models    ← Data models & validation
```

### Core Components

- **AIForm[T]** - Generic form controller with type safety
- **QuestionGenerator** - Abstract base for question generation strategies
- **ResponseParser** - Abstract base for response parsing strategies  
- **FieldConfig** - Rich field metadata and configuration
- **FormResponse** - Structured response with progress and validation

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/ai-forms.git
cd ai-forms

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black .
mypy .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Pydantic AI](https://ai.pydantic.dev/) for LLM integration
- Inspired by modern conversational interfaces
- Thanks to the Pydantic team for excellent data validation

---

**Ready to build intelligent forms?**

```bash
pip install ai-forms
```

[Get Started](examples/basic_ai_form.py) | [Documentation](docs/) | [Examples](examples/) | [Contributing](CONTRIBUTING.md)