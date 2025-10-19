from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import nats
import json

from shared.database import get_db, engine, Base
from backend.app import crud, schemas
from shared.config import settings

app = FastAPI(
    title="Event Analytics API",
    description="API for ingesting and analyzing user events",
    version="1.0.0",
)

nats_client = None


@app.on_event("startup")
async def startup_event():
    global nats_client
    Base.metadata.create_all(bind=engine)
    nats_client = await nats.connect(settings.NATS_URL)


@app.on_event("shutdown")
async def shutdown_event():
    if nats_client:
        await nats_client.close()


@app.post("/events", response_model=schemas.EventsIngestResponse)
async def ingest_events(request: schemas.EventsIngestRequest):
    """
    Ingest user events for processing.

    Accepts a batch of events and queues them for asynchronous processing via NATS.
    Returns immediately with acceptance status.
    """
    if not nats_client or not getattr(nats_client, "is_connected", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NATS unavailable"
        )

    events_data = [event.model_dump(mode="json") for event in request.events]
    message = {"events": events_data}

    try:
        await nats_client.publish(
            "events.ingest",
            json.dumps(message, default=str).encode()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"NATS publish failed: {exc}"
        )

    return schemas.EventsIngestResponse(
        status="accepted",
        message="Events queued for processing",
        events_count=len(request.events)
    )


@app.get("/stats/dau", response_model=schemas.DAUResponse)
def get_dau(
        params: schemas.DAUQueryParams = Depends(),
        db: Session = Depends(get_db)
):
    """
    Get Daily Active Users (DAU) statistics.

    Returns the count of unique users per day for the specified date range.
    """
    results = crud.get_daily_active_users(db, params.from_date, params.to_date)
    data = [
        schemas.DAUItem(date=str(row.date), unique_users=row.unique_users)
        for row in results
    ]
    return schemas.DAUResponse(data=data)


@app.get("/stats/top-events", response_model=schemas.TopEventsResponse)
def get_top_events(
        params: schemas.TopEventsQueryParams = Depends(),
        db: Session = Depends(get_db)
):
    """
    Get top events by occurrence count.

    Returns the most frequently occurring events within the specified date range,
    sorted by count in descending order.
    """
    results = crud.get_top_events_by_count(db, params.from_date, params.to_date, params.limit)
    data = [
        schemas.TopEventItem(event_type=row.event_type, count=row.count)
        for row in results
    ]
    return schemas.TopEventsResponse(data=data)


@app.get("/stats/retention", response_model=schemas.RetentionResponse)
def get_retention(
        params: schemas.RetentionQueryParams = Depends(),
        db: Session = Depends(get_db)
):
    """
    Calculate user retention for a cohort.

    Tracks what percentage of users from a starting cohort return in subsequent time windows.
    Supports both daily and weekly retention windows.
    """
    cohort_data_dict = crud.calculate_retention(db, params.start_date, params.windows, params.window_type)

    if cohort_data_dict["users_count"] == 0:
        return schemas.RetentionResponse(data=[], window_type=params.window_type)

    cohort_data = schemas.RetentionCohort(**cohort_data_dict)
    return schemas.RetentionResponse(data=[cohort_data], window_type=params.window_type)


@app.get("/")
def root():
    return {
        "message": "Event Analytics API",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
