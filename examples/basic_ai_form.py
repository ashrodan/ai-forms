"""
Basic AI-powered form example

This example demonstrates how to use AI-powered question generation 
and response parsing with the ai-forms library.
"""

import asyncio
import os
from pydantic import BaseModel, Field
from typing import List, Optional

from ai_forms import AIForm, FieldPriority
from ai_forms.generators.base import PydanticAIQuestionGenerator
from ai_forms.parsers.ai_parser import AIResponseParser


class UserProfile(BaseModel):
    """User profile data model"""
    full_name: str = Field(description="Your full legal name")
    email: str = Field(description="Email address")
    age: int = Field(description="Age in years", ge=13, le=120)
    skills: List[str] = Field(description="Programming skills you have", default_factory=list)
    experience_years: int = Field(description="Years of professional experience")
    newsletter: bool = Field(description="Subscribe to our newsletter?")
    bio: Optional[str] = Field(None, description="Brief bio (optional)")


async def run_ai_form():
    """Run the AI-powered form"""
    print("🤖 AI-Powered Form Example")
    print("=" * 40)
    
    # Check if we have API keys for real AI usage
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    
    # For this demo, use test mode to show reliable parsing
    # Set USE_REAL_AI=1 environment variable to use real AI
    use_real_ai = os.getenv("USE_REAL_AI") == "1" and (has_openai or has_anthropic)
    
    if use_real_ai:
        print("✅ Using real AI models")
        # Use real AI models
        ai_model = "openai:gpt-4o-mini" if has_openai else "anthropic:claude-3-haiku"
        form = AIForm(UserProfile, use_ai=True)
        form.question_generator = PydanticAIQuestionGenerator(ai_model)
        form.response_parser = AIResponseParser(ai_model)
    else:
        print("🧪 Using test mode for predictable demo")
        # Use test mode for demonstration
        form = AIForm(UserProfile, use_ai=True)
        form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
        form.response_parser = AIResponseParser(test_mode=True)
    
    # Configure field priorities for better conversation flow
    form = (form
            .configure_field("full_name", priority=FieldPriority.CRITICAL)
            .configure_field("email", priority=FieldPriority.CRITICAL)
            .configure_field("age", priority=FieldPriority.HIGH)
            .configure_field("skills", priority=FieldPriority.HIGH, 
                           examples=["Python", "JavaScript", "React"])
            .configure_field("newsletter", priority=FieldPriority.LOW)
            .configure_field("bio", priority=FieldPriority.LOW))
    
    # Start the conversation
    response = await form.start()
    
    print(f"\n🤖: {response.question}")
    print(f"📊 Progress: {response.progress:.0f}%")
    
    # Simulate user responses (in real app, get from user input)
    user_responses = [
        "Alice Johnson",
        "alice.johnson@techcorp.com", 
        "I'm 28 years old",  # AI can parse natural language
        "Python, TypeScript, React, and some Go",  # AI can parse lists
        "5",
        "yes please",  # AI can parse casual boolean responses
        "I'm a full-stack developer who loves building user-friendly applications"
    ]
    
    for i, user_input in enumerate(user_responses):
        print(f"\n👤: {user_input}")
        
        try:
            response = await form.respond(user_input)
            
            if response.errors:
                print(f"❌ Error: {response.errors[0]}")
                if response.retry_prompt:
                    print(f"💡 Hint: {response.retry_prompt}")
                continue
            
            if response.is_complete:
                print("✅ Form completed!")
                break
            
            print(f"🤖: {response.question}")
            print(f"📊 Progress: {response.progress:.0f}%")
            
        except Exception as e:
            print(f"❌ Error processing response: {e}")
            break
    
    # Display final results
    if response.is_complete and response.data:
        print("\n" + "=" * 40)
        print("📋 Final Profile Data:")
        print("=" * 40)
        
        data = response.data
        print(f"Name: {data.full_name}")
        print(f"Email: {data.email}")
        print(f"Age: {data.age}")
        print(f"Skills: {', '.join(data.skills)}")
        print(f"Experience: {data.experience_years} years")
        print(f"Newsletter: {'Yes' if data.newsletter else 'No'}")
        if data.bio:
            print(f"Bio: {data.bio}")


async def run_comparison_example():
    """Compare AI vs default form behavior"""
    print("\n🔄 AI vs Default Comparison")
    print("=" * 40)
    
    class SimpleForm(BaseModel):
        name: str = Field(description="Your name")
        age: int = Field(description="Your age")
        active: bool = Field(description="Are you active?")
    
    # Default form
    print("\n📝 Default Form:")
    default_form = AIForm(SimpleForm)
    response = await default_form.start()
    print(f"Question: {response.question}")
    
    # AI form in test mode
    print("\n🤖 AI Form (test mode):")
    ai_form = AIForm(SimpleForm, use_ai=True)
    ai_form.question_generator = PydanticAIQuestionGenerator(test_mode=True)
    ai_form.response_parser = AIResponseParser(test_mode=True)
    
    response = await ai_form.start()
    print(f"Question: {response.question}")
    
    # Show parsing differences
    print("\n🔍 Parsing Comparison:")
    
    # Test natural language parsing
    test_input = "twenty-five"
    
    # Default form parsing
    try:
        parsed_default = default_form._simple_parse_field_value(
            default_form._field_configs['age'], test_input
        )
        print(f"Default parser: '{test_input}' → Error (can't parse)")
    except Exception as e:
        print(f"Default parser: '{test_input}' → Error: {str(e)}")
    
    # AI form parsing
    age_config = ai_form._field_configs['age']
    parsed_ai = await ai_form.response_parser.parse_response(test_input, age_config)
    print(f"AI parser: '{test_input}' → {parsed_ai} ({type(parsed_ai).__name__})")


if __name__ == "__main__":
    print("🚀 Starting AI Forms Examples\n")
    
    # Run the main AI form example
    asyncio.run(run_ai_form())
    
    # Run the comparison example
    asyncio.run(run_comparison_example())
    
    print("\n✨ Examples completed!")