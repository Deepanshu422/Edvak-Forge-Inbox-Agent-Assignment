from pydantic import BaseModel, Field

class Caregiver(BaseModel):
    name: str
    relationship: str
    phone: str


class Patient(BaseModel):
    id: str
    name: str
    dob: str
    phone: str
    email: str
    primary_provider: str
    last_visit: str
    allergies: list[str]
    preferred_language: str
    authorised_caregiver: Caregiver | None = None

class Medication(BaseModel):
    patient_id: str
    medication: str
    controlled_schedule: str | None = None
    days_supply: int
    last_filled: str
    refills_remaining: int
    prescriber: str

class Appointment(BaseModel):
    id: str
    patient_id: str
    provider: str
    date: str
    start: str
    end: str
    visit_type: str
    status: str

class AgentOutput(BaseModel):
    id: str = Field(..., description="The message ID, e.g., 'M001'")
    patient_id: str | None = Field(None, description="The verified patient ID, or null if unverified/new patient")
    intents: list[str] = Field(..., description="List of intents, e.g., ['refill', 'clinical']")
    urgency: str = Field(..., description="Must be exactly one of: 'routine', 'urgent', or 'emergency'")
    actions: list[str] = Field(default_factory=list, description="List of actions taken from the allowed vocabulary")
    routed_to: list[str] = Field(default_factory=list, description="List of queues this message was routed to")
    tool_calls: list[str] = Field(default_factory=list, description="List of MCP tools invoked")
    reply_draft: str = Field(..., description="The final reply drafted for the patient")
