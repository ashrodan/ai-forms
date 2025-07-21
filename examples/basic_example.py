"""
Basic example demonstrating AI Forms functionality
"""
import asyncio
from pydantic import BaseModel, Field
from ai_forms import AIForm, ConversationMode, FieldPriority


class UserProfile(BaseModel):
    name: str = Field(description="Your full name")
    email: str = Field(description="Email address for contact") 
    age: int = Field(description="Your age in years", ge=0, le=120)


async def main():
    print("=== AI Forms Basic Example ===\n")
    
    # Create form with field configuration
    form = (AIForm(UserProfile)
            .configure_field("name", 
                           priority=FieldPriority.CRITICAL,
                           custom_question="What should I call you?")
            .configure_field("email",
                           validation_hint="Must be a valid email format",
                           examples=["user@example.com", "alice@company.co"])
            .configure_field("age",
                           priority=FieldPriority.MEDIUM))
    
    # Start the conversation
    response = await form.start()
    
    # Simulate the conversation flow
    print(f"Bot: {response.question}")
    print(f"Progress: {response.progress:.1f}%\n")
    
    # User responds to name
    print("User: Alice Johnson")
    response = await form.respond("Alice Johnson")
    print(f"Bot: {response.question}")
    print(f"Progress: {response.progress:.1f}%\n")
    
    # User responds to email
    print("User: alice@email.com")
    response = await form.respond("alice@email.com")
    print(f"Bot: {response.question}")
    print(f"Progress: {response.progress:.1f}%\n")
    
    # User responds to age
    print("User: 28")
    response = await form.respond("28")
    
    if response.is_complete:
        print("✅ Form completed successfully!")
        print(f"Progress: {response.progress:.1f}%")
        print(f"Final data: {response.data}")
    
    print("\n=== Validation Error Example ===\n")
    
    # Demonstrate validation error
    form2 = AIForm(UserProfile)
    await form2.start()
    await form2.respond("Test User")
    await form2.respond("test@email.com")
    
    print("User: not a number")
    error_response = await form2.respond("not a number")
    print(f"Bot: {error_response.retry_prompt}")
    print(f"Errors: {error_response.errors}")


if __name__ == "__main__":
    asyncio.run(main())