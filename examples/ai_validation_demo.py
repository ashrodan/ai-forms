"""
AI Validation Tools Demo

This example demonstrates the new AI-powered validation system that uses
pydantic-ai chat tools as the core validation mechanism.
"""
import asyncio
from pydantic import BaseModel, Field
from ai_forms import AIForm
from ai_forms.validators.ai_tools import AIValidationTools

class UserProfile(BaseModel):
    """User profile with AI-powered validation"""
    name: str = Field(
        description="Full name", 
        json_schema_extra={"validation_hint": "name validation with regex pattern"}
    )
    email: str = Field(
        description="Email address",
        json_schema_extra={"validation_hint": "email validation"}
    )
    age: int = Field(
        description="Age in years",
        json_schema_extra={"validation_hint": "range validation min=13 max=120"}
    )
    experience_years: int = Field(
        description="Years of professional experience", 
        json_schema_extra={"validation_hint": "range validation min=0 max=50"}
    )

async def demo_ai_validation():
    """Demonstrate AI validation tools"""
    print("🤖 AI Validation Tools Demo")
    print("=" * 50)
    
    # Create form with AI validation tools
    form = AIForm(
        UserProfile, 
        use_ai=True, 
        test_mode=True  # Use test mode for demo (no API keys needed)
    )
    
    print("\n✅ AI Validation Tools Status:")
    print(f"   - AI Available: {form.use_ai}")
    print(f"   - Validation Tools: {'✓' if form.validation_tools else '✗'}")
    print(f"   - Test Mode: {form.test_mode}")
    
    # Start the form
    response = await form.start()
    print(f"\n📝 First Question: {response.question}")
    
    # Demonstrate field validation during collection
    print("\n🔍 Testing Field Validation:")
    
    # Valid name
    print("\n1. Valid name input:")
    response = await form.respond("John Smith")
    print(f"   Input: 'John Smith'")
    print(f"   Status: {'✓ Valid' if not response.errors else '✗ Invalid'}")
    if response.errors:
        print(f"   Error: {response.errors[0]}")
    
    # Invalid email
    print("\n2. Invalid email input:")
    response = await form.respond("invalid-email")
    print(f"   Input: 'invalid-email'")
    print(f"   Status: {'✓ Valid' if not response.errors else '✗ Invalid'}")
    if response.errors:
        print(f"   Error: {response.errors[0]}")
    
    # Valid email
    print("\n3. Valid email input:")
    response = await form.respond("john@example.com")
    print(f"   Input: 'john@example.com'")
    print(f"   Status: {'✓ Valid' if not response.errors else '✗ Invalid'}")
    
    # Valid age
    print("\n4. Valid age input:")
    response = await form.respond("28")
    print(f"   Input: '28'")
    print(f"   Status: {'✓ Valid' if not response.errors else '✗ Invalid'}")
    
    # Complete form
    print("\n5. Experience years:")
    response = await form.respond("5")
    print(f"   Input: '5'")
    print(f"   Status: {'✓ Valid' if not response.errors else '✗ Invalid'}")
    
    if response.is_complete:
        print("\n🎉 Form completed successfully!")
        print("Final data:")
        print(f"   - Name: {response.data.name}")
        print(f"   - Email: {response.data.email}")
        print(f"   - Age: {response.data.age}")
        print(f"   - Experience: {response.data.experience_years} years")
    else:
        print(f"\n📋 Next question: {response.question}")

async def demo_validation_tools_directly():
    """Demonstrate AI validation tools directly"""
    print("\n\n🔧 Direct AI Validation Tools Demo")
    print("=" * 50)
    
    # Create validation tools directly
    tools = AIValidationTools(test_mode=True)
    
    # Test field validation
    print("\n📋 Field Validation Tests:")
    
    # Email validation
    result = tools.validate_field(
        field_name="email",
        field_value="test@example.com",
        field_type="str",
        field_description="Email address",
        validation_hint="email validation"
    )
    print(f"\n1. Email Validation:")
    print(f"   Input: 'test@example.com'")
    print(f"   Valid: {result.is_valid}")
    print(f"   Parsed: {result.parsed_value}")
    
    # Integer parsing
    result = tools.validate_field(
        field_name="age",
        field_value="25",
        field_type="int", 
        field_description="Age in years"
    )
    print(f"\n2. Integer Parsing:")
    print(f"   Input: '25'")
    print(f"   Valid: {result.is_valid}")
    print(f"   Parsed: {result.parsed_value} (type: {type(result.parsed_value)})")
    
    # List parsing
    result = tools.validate_field(
        field_name="tags",
        field_value="python, web, backend",
        field_type="List[str]",
        field_description="List of tags"
    )
    print(f"\n3. List Parsing:")
    print(f"   Input: 'python, web, backend'")
    print(f"   Valid: {result.is_valid}")
    print(f"   Parsed: {result.parsed_value}")
    
    # Boolean parsing
    result = tools.validate_field(
        field_name="consent",
        field_value="yes",
        field_type="bool",
        field_description="Consent flag"
    )
    print(f"\n4. Boolean Parsing:")
    print(f"   Input: 'yes'")
    print(f"   Valid: {result.is_valid}")
    print(f"   Parsed: {result.parsed_value} (type: {type(result.parsed_value)})")

async def main():
    """Run the demo"""
    try:
        await demo_ai_validation()
        await demo_validation_tools_directly()
        
        print("\n\n🌟 Summary:")
        print("The AI validation tools provide:")
        print("• Field-level validation during collection")
        print("• AI-powered parsing with fallbacks")
        print("• Final form validation with cross-field logic")
        print("• Test mode for development without API keys")
        print("• Integration with pydantic-ai chat tools")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())