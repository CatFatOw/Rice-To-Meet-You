import uuid

from database import Base
from sqlalchemy import Column, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID


class ChatbotContext(Base):
    __tablename__ = "chatbot_context"

    context_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    context = Column(JSONB, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )