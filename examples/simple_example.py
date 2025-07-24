#!/usr/bin/env python3
"""
Simple AI Forms Example - 2 Field Form with AI-Powered Bool and Number Validation

This example demonstrates a minimal AI-powered form with just 2 fields:
- Age (AI can parse "twenty-five", "25", etc.)
- Newsletter subscription (AI can understand "yes", "sure", "nope", "definitely", etc.)

The AI runs in test mode, so no API keys are needed.

Run with: uv run python simple_example.py
"""

import asyncio
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ai_forms import AIForm


class SimpleForm(BaseModel):
    """Simple 2-field form for testing basic validation"""
    age: int = Field(
        description="Your age in years",
        ge=13, le=120,
        json_schema_extra={
            "examples": ["25", "30", "35"],
            "validation_hint": "min=13 max=120"
        }
    )
    newsletter: bool = Field(
        description="Would you like to receive our newsletter?",
        json_schema_extra={
            "examples": ["yes", "no", "sure", "nope"]
        }
    )


async def main():
    print("🤖 AI Forms - Simple Example")
    print("=" * 40)
    print("This AI-powered form has just 2 fields:")
    print("1. Age (try: '25', 'twenty-five', 'I'm 30')")
    print("2. Newsletter (try: 'yes', 'sure', 'nope', 'definitely not')")
    print("✨ The AI understands natural language!")
    print()
    
    # Create conversational AI form (AI enabled by default, uses real AI model)
    form = AIForm(SimpleForm)
    
    # Show form setup
    print(f"🤖 AI Agent enabled: {form.agent is not None}")
    print(f"📊 Fields to collect: {list(form._field_configs.keys())}")
    print()
    
    # Start the conversation
    response = await form.start()
    print(f"Bot: {response.question}")
    
    # Conversation loop
    while not response.is_complete:
        # Get user input
        user_input = input("You: ").strip()
        
        if not user_input:
            print("Please enter a response.")
            continue
            
        # Process response
        response = await form.respond(user_input)
        
        # Show errors if any
        if response.errors:
            print("❌ Error:", "; ".join(response.errors))
            if response.retry_prompt:
                print("💡", response.retry_prompt)
        
        # Show next question or completion
        if response.question and not response.is_complete:
            print(f"Bot: {response.question}")
        elif response.is_complete:
            print("\n🎉 Form completed!")
            print(f"Final data: {response.data}")
            break


if __name__ == "__main__":
    asyncio.run(main())
