# AI Forms

**AI-powered conversational form builder** that transforms Pydantic models into natural, intelligent data collection workflows.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Pydantic v2](https://img.shields.io/badge/pydantic-v2-green.svg)](https://pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Natural Conversations** - AI generates contextual, friendly questions from field descriptions
- **Intelligent Parsing** - Understands natural language responses ("twenty-eight" → 28)
- **Zero Configuration** - Works with existing Pydantic models
- **Progress Tracking** - Real-time completion progress and field validation
- **Flexible Modes** - Sequential, clustered, or one-shot data collection
- **Error Recovery** - Smart validation with helpful retry prompts
- **Test-Friendly** - Deterministic test mode for CI/CD pipelines
- **Multi-Provider** - Support for OpenAI, Anthropic, and more via Pydantic AI

## Quick Start

### Installation

```bash
pip install ai-forms
```

### Basic Usage

```python
import asyncio
from pydantic import BaseModel, Field
from ai_forms import AIForm

class UserProfile(BaseModel):
    name: str = Field(description="Your full name")
    age: int = Field(description="Age in years", ge=13, le=120) 
    email: str = Field(description="Email address")
    newsletter: bool = Field(description="Subscribe to newsletter?")

async def main():
    # Create form
    form = AIForm(UserProfile)
    
    # Start conversation
    response = await form.start()
    print(f"Bot: {response.question}")
    
    # Simulate user responses
    response = await form.respond("Alice Johnson")
    print(f"Bot: {response.question}")
    
    response = await form.respond("28")
    print(f"Bot: {response.question}")
    
    response = await form.respond("alice@example.com")
    print(f"Bot: {response.question}")
    
    response = await form.respond("yes")
    
    # Get final data
    if response.is_complete:
        user_data = response.data
        print(f"Collected: {user_data}")

asyncio.run(main())
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