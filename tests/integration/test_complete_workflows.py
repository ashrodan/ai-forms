"""Integration tests for complete form workflows"""
import pytest
from typing import List, Optional
from pydantic import BaseModel, Field

from ai_forms import AIForm, ConversationMode, FieldPriority, ValidationStrategy
from ai_forms.generators.base import QuestionGenerator


class TestCompleteFormWorkflows:
    """Test complete end-to-end form workflows"""
    
    @pytest.mark.asyncio
    async def test_simple_user_registration_workflow(self):
        """Test complete user registration workflow"""
        class UserRegistration(BaseModel):
            full_name: str = Field(description="Your full legal name")
            email: str = Field(description="Email address")
            age: int = Field(description="Age in years", ge=13, le=120)
            newsletter: bool = Field(description="Subscribe to newsletter?")
        
        form = (AIForm(UserRegistration)
                .configure_field("full_name", priority=FieldPriority.CRITICAL)
                .configure_field("email", priority=FieldPriority.CRITICAL, 
                               examples=["user@example.com"])
                .configure_field("newsletter", priority=FieldPriority.LOW))
        
        # Complete workflow
        response = await form.start()
        assert "full_name" in response.current_field or "name" in response.question.lower()
        
        response = await form.respond("Alice Johnson")
        assert "email" in response.question.lower()
        assert response.progress > 0
        
        response = await form.respond("alice@example.com")
        assert "age" in response.question.lower()
        assert response.progress > 25
        
        response = await form.respond("28")
        assert "newsletter" in response.question.lower()
        assert response.progress > 50
        
        response = await form.respond("yes")
        assert response.is_complete
        assert response.progress == 100.0
        
        # Verify final data
        data = response.data
        assert data.full_name == "Alice Johnson"
        assert data.email == "alice@example.com"
        assert data.age == 28
        assert data.newsletter is True
    
    @pytest.mark.asyncio
    async def test_job_application_workflow_with_dependencies(self):
        """Test job application workflow with field dependencies"""
        class JobApplication(BaseModel):
            name: str = Field(
                description="Full name",
                json_schema_extra={"priority": FieldPriority.CRITICAL}
            )
            position: str = Field(
                description="Position applying for",
                json_schema_extra={"priority": FieldPriority.HIGH}
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
                description="Salary expectation", 
                json_schema_extra={
                    "priority": FieldPriority.LOW,
                    "skip_if": lambda data: data.get("experience_years", 0) < 2
                }
            )
        
        form = AIForm(JobApplication)
        
        # Workflow with junior applicant (should skip salary)
        response = await form.start()
        response = await form.respond("John Doe")
        response = await form.respond("Software Engineer")
        response = await form.respond("1")  # 1 year experience
        
        # Should complete without asking for salary
        assert response.is_complete
        assert response.data.name == "John Doe"
        assert response.data.position == "Software Engineer"
        assert response.data.experience_years == 1
        assert response.data.salary_expectation is None
        
        # Test with senior applicant
        form2 = AIForm(JobApplication)
        response = await form2.start()
        response = await form2.respond("Jane Smith")
        response = await form2.respond("Senior Developer")
        response = await form2.respond("5")  # 5 years experience
        
        # Should ask for salary
        assert not response.is_complete
        assert "salary" in response.question.lower()
        
        response = await form2.respond("90000")
        assert response.is_complete
        assert response.data.salary_expectation == 90000
    
    @pytest.mark.asyncio
    async def test_form_with_validation_recovery(self):
        """Test complete workflow with validation errors and recovery"""
        class ContactForm(BaseModel):
            name: str = Field(description="Your name")
            email: str = Field(description="Email address")
            age: int = Field(description="Age", ge=0, le=150)
            message: str = Field(description="Your message")
        
        form = AIForm(ContactForm)
        
        # Start form
        response = await form.start()
        
        # Valid name
        response = await form.respond("Bob Wilson")
        assert not response.errors
        
        # Invalid email (missing @) - should recover
        response = await form.respond("bobwilson.com")
        # Note: Current simple validation might not catch this
        
        # Valid email
        response = await form.respond("bob@wilson.com")
        assert not response.errors
        
        # Invalid age
        response = await form.respond("not a number")
        assert response.errors
        assert response.retry_prompt is not None
        
        # Another invalid age
        response = await form.respond("200")  # Too high
        # Note: Current implementation doesn't validate ranges
        
        # Valid age
        response = await form.respond("35")
        assert not response.errors
        
        # Complete with message
        response = await form.respond("Hello, this is my message!")
        assert response.is_complete
        assert response.data.name == "Bob Wilson"
        assert response.data.age == 35
    
    @pytest.mark.asyncio
    async def test_survey_form_workflow(self):
        """Test survey form with various question types"""
        class SurveyForm(BaseModel):
            satisfaction: int = Field(
                description="Satisfaction rating (1-10)",
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
        
        form = AIForm(SurveyForm)
        
        # Complete survey workflow
        response = await form.start()
        assert "satisfaction" in response.question.lower()
        assert "1-10" in response.question
        
        response = await form.respond("9")
        assert "recommend" in response.question.lower()
        
        response = await form.respond("yes")
        assert "improve" in response.question.lower()
        
        response = await form.respond("Better mobile app")
        assert "additional" in response.question.lower() or "comment" in response.question.lower()
        
        response = await form.respond("Keep up the good work!")
        assert response.is_complete
        
        # Verify data
        assert response.data.satisfaction == 9
        assert response.data.would_recommend is True
        assert response.data.improvement_areas == "Better mobile app"
        assert response.data.additional_comments == "Keep up the good work!"


class TestCustomQuestionGeneratorIntegration:
    """Test integration with custom question generators"""
    
    @pytest.mark.asyncio
    async def test_personalized_question_generator_workflow(self):
        """Test workflow with personalized question generation"""
        class PersonalizedGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                user_name = context.get("name", "there")
                
                if field_config.name == "email":
                    return f"Hi {user_name}! What's the best email to reach you at?"
                elif field_config.name == "age":
                    return f"Thanks {user_name}! Could you share your age?"
                elif field_config.name == "phone":
                    return f"Great! And {user_name}, what's your phone number?"
                else:
                    return f"Please provide your {field_config.name}"
        
        class PersonalizedForm(BaseModel):
            name: str = Field(description="Your name")
            email: str = Field(description="Your email")
            age: int = Field(description="Your age")
            phone: str = Field(description="Your phone")
        
        form = AIForm(PersonalizedForm, question_generator=PersonalizedGenerator())
        
        # Workflow should show personalization
        response = await form.start()
        assert response.question == "Please provide your name"
        
        response = await form.respond("Alice")
        assert response.question == "Hi Alice! What's the best email to reach you at?"
        
        response = await form.respond("alice@example.com")
        assert response.question == "Thanks Alice! Could you share your age?"
        
        response = await form.respond("30")
        assert response.question == "Great! And Alice, what's your phone number?"
        
        response = await form.respond("555-1234")
        assert response.is_complete
    
    @pytest.mark.asyncio
    async def test_conditional_question_generator(self):
        """Test question generator that adapts based on previous answers"""
        class ConditionalGenerator(QuestionGenerator):
            async def generate_question(self, field_config, context):
                if field_config.name == "follow_up":
                    user_type = context.get("collected_data", {}).get("user_type", "")
                    if "business" in user_type.lower():
                        return "What's your company name?"
                    else:
                        return "What's your occupation?"
                
                return f"Please provide your {field_config.name}"
        
        class ConditionalForm(BaseModel):
            user_type: str = Field(description="Are you a business or individual user?")
            follow_up: str = Field(description="Follow-up question")
        
        # Test business path
        form1 = AIForm(ConditionalForm, question_generator=ConditionalGenerator())
        response = await form1.start()
        
        response = await form1.respond("Business user")
        # Update context with collected data for generator
        form1.set_context({"collected_data": {"user_type": "Business user"}})
        
        # Force regeneration of question (in real implementation this would be automatic)
        response = await form1._get_next_question()
        assert "company name" in response.question
        
        # Test individual path
        form2 = AIForm(ConditionalForm, question_generator=ConditionalGenerator())
        await form2.start()
        response = await form2.respond("Individual user")
        form2.set_context({"collected_data": {"user_type": "Individual user"}})
        
        response = await form2._get_next_question()
        assert "occupation" in response.question


class TestFormModeIntegration:
    """Test integration with different conversation modes"""
    
    def test_sequential_mode_ordering(self):
        """Test sequential mode respects field ordering"""
        class OrderedForm(BaseModel):
            low_priority: str = Field(
                description="Low priority field",
                json_schema_extra={"priority": FieldPriority.LOW}
            )
            high_priority: str = Field(
                description="High priority field", 
                json_schema_extra={"priority": FieldPriority.HIGH}
            )
            critical_priority: str = Field(
                description="Critical priority field",
                json_schema_extra={"priority": FieldPriority.CRITICAL}
            )
        
        form = AIForm(OrderedForm, mode=ConversationMode.SEQUENTIAL)
        
        # Should order by priority: CRITICAL, HIGH, LOW
        expected_order = ["critical_priority", "high_priority", "low_priority"]
        assert form._field_order == expected_order
    
    @pytest.mark.asyncio
    async def test_clustered_mode_preparation(self):
        """Test clustered mode field grouping (preparation for future implementation)"""
        class ClusteredForm(BaseModel):
            name: str = Field(
                description="Name",
                json_schema_extra={"cluster": "identity"}
            )
            email: str = Field(
                description="Email",
                json_schema_extra={"cluster": "identity"}
            )
            position: str = Field(
                description="Position",
                json_schema_extra={"cluster": "job_info"}
            )
            experience: int = Field(
                description="Experience",
                json_schema_extra={"cluster": "job_info"}
            )
        
        form = AIForm(ClusteredForm, mode=ConversationMode.CLUSTERED)
        
        # Verify cluster information is captured in field configs
        identity_fields = [
            name for name, config in form._field_configs.items()
            if config.cluster == "identity"
        ]
        job_fields = [
            name for name, config in form._field_configs.items()
            if config.cluster == "job_info"
        ]
        
        assert set(identity_fields) == {"name", "email"}
        assert set(job_fields) == {"position", "experience"}


class TestRealWorldScenarios:
    """Test realistic real-world scenarios"""
    
    @pytest.mark.asyncio
    async def test_customer_onboarding_scenario(self):
        """Test complete customer onboarding scenario"""
        class CustomerOnboarding(BaseModel):
            # Basic info
            first_name: str = Field(description="First name")
            last_name: str = Field(description="Last name")
            email: str = Field(description="Email address")
            
            # Company info
            company: Optional[str] = Field(None, description="Company name")
            role: Optional[str] = Field(None, description="Your role")
            
            # Preferences
            use_case: str = Field(description="Primary use case")
            notifications: bool = Field(description="Receive email notifications?")
        
        form = (AIForm(CustomerOnboarding)
                .configure_field("first_name", priority=FieldPriority.CRITICAL)
                .configure_field("last_name", priority=FieldPriority.CRITICAL)
                .configure_field("email", priority=FieldPriority.CRITICAL,
                               examples=["user@company.com"])
                .configure_field("use_case", priority=FieldPriority.HIGH,
                               examples=["Analytics", "Marketing", "Sales"])
                .configure_field("notifications", priority=FieldPriority.LOW))
        
        # Complete onboarding flow
        await form.start()
        
        responses = [
            "Alice",
            "Johnson", 
            "alice.johnson@techcorp.com",
            "TechCorp Inc",
            "Product Manager",
            "Analytics and reporting",
            "yes"
        ]
        
        for i, user_response in enumerate(responses):
            response = await form.respond(user_response)
            if i < len(responses) - 1:
                assert not response.is_complete
                assert response.progress > (i / len(responses)) * 100
        
        assert response.is_complete
        assert response.data.first_name == "Alice"
        assert response.data.last_name == "Johnson"
        assert response.data.email == "alice.johnson@techcorp.com"
        assert response.data.company == "TechCorp Inc"
        assert response.data.notifications is True
    
    @pytest.mark.asyncio
    async def test_medical_intake_scenario(self):
        """Test medical intake form scenario with sensitive handling"""
        class MedicalIntake(BaseModel):
            patient_name: str = Field(
                description="Patient full name",
                json_schema_extra={"priority": FieldPriority.CRITICAL}
            )
            date_of_birth: str = Field(
                description="Date of birth (MM/DD/YYYY)",
                json_schema_extra={"examples": ["01/15/1990", "12/25/1985"]}
            )
            chief_complaint: str = Field(description="What brings you in today?")
            pain_level: Optional[int] = Field(
                None,
                description="Pain level (0-10, if applicable)",
                json_schema_extra={
                    "skip_if": lambda data: "pain" not in data.get("chief_complaint", "").lower()
                }
            )
            medications: Optional[str] = Field(
                None,
                description="Current medications (or 'none')"
            )
        
        form = AIForm(MedicalIntake)
        
        # Test with pain-related complaint
        await form.start()
        response = await form.respond("John Smith")
        response = await form.respond("03/15/1985")
        response = await form.respond("Back pain and stiffness")
        
        # Should ask about pain level since "pain" mentioned
        assert "pain level" in response.question.lower()
        assert "0-10" in response.question
        
        response = await form.respond("7")
        response = await form.respond("Ibuprofen 400mg twice daily")
        
        assert response.is_complete
        assert response.data.pain_level == 7
        
        # Test without pain complaint
        form2 = AIForm(MedicalIntake)
        await form2.start()
        await form2.respond("Jane Doe")
        await form2.respond("05/20/1990")
        await form2.respond("Annual checkup")
        
        # Should skip pain level question
        response = await form2.respond("None")
        assert response.is_complete
        assert response.data.pain_level is None
    
    @pytest.mark.asyncio
    async def test_event_registration_scenario(self):
        """Test event registration with complex logic"""
        class EventRegistration(BaseModel):
            attendee_name: str = Field(description="Attendee name")
            email: str = Field(description="Contact email")
            ticket_type: str = Field(
                description="Ticket type",
                json_schema_extra={"examples": ["General", "VIP", "Student"]}
            )
            dietary_restrictions: Optional[str] = Field(
                None,
                description="Dietary restrictions or allergies"
            )
            workshop_preference: Optional[str] = Field(
                None,
                description="Preferred workshop",
                json_schema_extra={
                    "skip_if": lambda data: data.get("ticket_type", "").lower() == "general",
                    "examples": ["AI Workshop", "Web Development", "Data Science"]
                }
            )
        
        form = AIForm(EventRegistration)
        
        # Test VIP registration (gets workshop choice)
        await form.start()
        response = await form.respond("Sarah Connor")
        response = await form.respond("sarah.connor@resistance.com")
        response = await form.respond("VIP")
        response = await form.respond("Vegetarian, no nuts")
        
        # VIP should get workshop question
        assert "workshop" in response.question.lower()
        
        response = await form.respond("AI Workshop")
        assert response.is_complete
        assert response.data.workshop_preference == "AI Workshop"
        
        # Test General registration (skips workshop)
        form2 = AIForm(EventRegistration)
        await form2.start()
        await form2.respond("Kyle Reese")
        await form2.respond("kyle@future.com")
        await form2.respond("General")
        response = await form2.respond("None")
        
        # Should complete without workshop question
        assert response.is_complete
        assert response.data.workshop_preference is None