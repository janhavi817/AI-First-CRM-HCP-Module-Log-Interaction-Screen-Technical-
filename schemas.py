from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, time, datetime

# HCP schemas
class HCPBase(BaseModel):
    name: str
    specialty: str
    hospital: str
    email: str
    phone: Optional[str] = None

class HCPCreate(HCPBase):
    pass

class HCPResponse(HCPBase):
    id: int
    class Config:
        from_attributes = True

# Product schemas
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    brochure_url: Optional[str] = None

class ProductResponse(ProductBase):
    id: int
    class Config:
        from_attributes = True

# Follow-up schemas
class FollowUpBase(BaseModel):
    hcp_id: int
    date: date
    notes: Optional[str] = None
    status: str = "Pending"

class FollowUpCreate(FollowUpBase):
    interaction_id: Optional[int] = None

class FollowUpResponse(FollowUpBase):
    id: int
    interaction_id: Optional[int] = None
    class Config:
        from_attributes = True

# Interaction schemas
class InteractionState(BaseModel):
    hcp_name: Optional[str] = ""
    interaction_type: Optional[str] = ""
    date: Optional[str] = "" # YYYY-MM-DD
    time: Optional[str] = "" # HH:MM
    attendees: Optional[List[str]] = []
    topics_discussed: Optional[str] = ""
    sentiment: Optional[str] = ""
    materials_shared: Optional[List[str]] = []
    summary: Optional[str] = ""

class InteractionCreate(BaseModel):
    hcp_id: int
    interaction_type: str
    date: date
    time: time
    attendees: Optional[List[str]] = []
    topics_discussed: str
    sentiment: Optional[str] = None
    materials_shared: Optional[List[str]] = []
    summary: Optional[str] = None

class InteractionResponse(BaseModel):
    id: int
    hcp_id: int
    interaction_type: str
    date: date
    time: time
    attendees: Optional[List[str]] = []
    topics_discussed: str
    sentiment: Optional[str] = None
    materials_shared: Optional[List[str]] = []
    summary: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Chat schemas
class ChatRequest(BaseModel):
    message: str
    current_state: InteractionState
    history: Optional[List[Dict[str, str]]] = [] # List of {"role": "user"|"assistant", "content": "..."}

class ChatResponse(BaseModel):
    reply: str
    updated_state: InteractionState
    steps: List[str] # List of active LangGraph nodes, e.g. ["agent", "tools", "agent"]
    tools_called: List[Dict[str, Any]] # Info about tools triggered during this turn
