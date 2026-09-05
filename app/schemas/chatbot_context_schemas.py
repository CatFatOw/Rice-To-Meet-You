from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatbotContextCreate(BaseModel):
    context: Dict[str, Any]


class ChatbotContextResponse(ChatbotContextCreate):
    model_config = ConfigDict(from_attributes=True)

    context_id: UUID
  