"""File handles the schemas for user generation"""
from pydantic import BaseModel, ConfigDict 
from datetime import datetime 
from typing import Optional


# ----------------------INPUT SCHEMA-----------------------
class UserCreate(BaseModel):
    email: str
    password: str

class PasswordChange(BaseModel):
    """Payload for a logged-in user changing their own password."""
    current_password: str
    new_password: str




# ----------------------RESPONSE SCHEMA-----------------------
class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    access_token: Optional[str] = None
    token_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
