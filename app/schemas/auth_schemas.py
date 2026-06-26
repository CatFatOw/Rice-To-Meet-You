"""File contains schemas for the auth"""
from pydantic import BaseModel 
from typing import Optional

class TokenData(BaseModel):
    id:Optional[int] = None


# auth
class Token(BaseModel):
    access_token:str
    token_type:str