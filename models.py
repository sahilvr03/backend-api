from pydantic import BaseModel
from typing import List, Optional

class Lead(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class LeadRequest(BaseModel):
    query: str

class LeadResponse(BaseModel):
    leads: List[Lead]
