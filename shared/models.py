import uuid
from sqlalchemy import Column, String, UUID, JSON, DateTime, Integer
from shared.database import Base


class Event(Base):
    __tablename__ = "events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    properties = Column(JSON, nullable=False, default=dict)