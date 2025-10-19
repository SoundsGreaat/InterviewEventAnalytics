from pydantic import BaseModel, Field
from datetime import datetime, date
from uuid import UUID
from typing import List, Dict, Any, Literal


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


class DAUQueryParams(BaseModel):
    from_date: date = Field(..., alias="from", description="Start date (YYYY-MM-DD)")
    to_date: date = Field(..., alias="to", description="End date (YYYY-MM-DD)")

    class Config:
        populate_by_name = True


class TopEventsQueryParams(BaseModel):
    from_date: date = Field(..., alias="from", description="Start date (YYYY-MM-DD)")
    to_date: date = Field(..., alias="to", description="End date (YYYY-MM-DD)")
    limit: int = Field(10, ge=1, le=100, description="Number of top events")

    class Config:
        populate_by_name = True


class RetentionQueryParams(BaseModel):
    start_date: date = Field(..., description="Cohort start date (YYYY-MM-DD)")
    windows: int = Field(3, ge=1, le=12, description="Number of retention windows")
    window_type: Literal["day", "week"] = Field("week", description="Window type: day or week")

    class Config:
        populate_by_name = True
