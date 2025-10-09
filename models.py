from pydantic import BaseModel
from typing import List, Optional

class Lead(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    lead_type: Optional[str] = None

class LeadRequest(BaseModel):
    query: str
    country: Optional[str] = None
    lead_type: Optional[str] = None

class LeadResponse(BaseModel):
    leads: List[Lead]