from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import List, Dict, Any


class EventCreate(BaseModel):
    event_id: UUID
    occurred_at: datetime
    user_id: int
    event_type: str = Field(..., max_length=100)
    properties: Dict[str, Any] = Field(default_factory=dict)


class EventsIngestRequest(BaseModel):
    events: List[EventCreate]


class EventsIngestResponse(BaseModel):
    status: str
    message: str
    events_count: int


class DAUItem(BaseModel):
    date: str
    unique_users: int


class DAUResponse(BaseModel):
    data: List[DAUItem]


class TopEventItem(BaseModel):
    event_type: str
    count: int


class TopEventsResponse(BaseModel):
    data: List[TopEventItem]


class RetentionCohort(BaseModel):
    cohort_date: str
    users_count: int
    retention_windows: List[float]


class RetentionResponse(BaseModel):
    data: List[RetentionCohort]
    window_type: str
