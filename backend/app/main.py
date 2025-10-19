from fastapi import FastAPI, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta
import nats
import json

from shared.database import get_db, engine, Base
from shared.models import Event
from backend.app.schemas import (
    EventsIngestRequest,
    EventsIngestResponse,
    DAUResponse,
    DAUItem,
    TopEventsResponse,
    TopEventItem,
    RetentionResponse,
    RetentionCohort,
)
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


@app.post("/events", response_model=EventsIngestResponse)
async def ingest_events(request: EventsIngestRequest):
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

    return EventsIngestResponse(
        status="accepted",
        message="Events queued for processing",
        events_count=len(request.events)
    )


@app.get("/stats/dau", response_model=DAUResponse)
def get_dau(
        from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
        to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
        db: Session = Depends(get_db)
):
    results = db.query(
        func.date(Event.occurred_at).label("date"),
        func.count(func.distinct(Event.user_id)).label("unique_users")
    ).filter(
        func.date(Event.occurred_at) >= from_date,
        func.date(Event.occurred_at) <= to_date
    ).group_by(
        func.date(Event.occurred_at)
    ).order_by(
        func.date(Event.occurred_at)
    ).all()

    data = [
        DAUItem(date=str(row.date), unique_users=row.unique_users)
        for row in results
    ]

    return DAUResponse(data=data)


@app.get("/stats/top-events", response_model=TopEventsResponse)
def get_top_events(
        from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
        to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
        limit: int = Query(10, ge=1, le=100, description="Number of top events"),
        db: Session = Depends(get_db)
):
    results = db.query(
        Event.event_type,
        func.count(Event.event_id).label("count")
    ).filter(
        func.date(Event.occurred_at) >= from_date,
        func.date(Event.occurred_at) <= to_date
    ).group_by(
        Event.event_type
    ).order_by(
        func.count(Event.event_id).desc()
    ).limit(limit).all()

    data = [
        TopEventItem(event_type=row.event_type, count=row.count)
        for row in results
    ]

    return TopEventsResponse(data=data)


@app.get("/stats/retention", response_model=RetentionResponse)
def get_retention(
        start_date: date = Query(..., description="Cohort start date (YYYY-MM-DD)"),
        windows: int = Query(3, ge=1, le=12, description="Number of retention windows"),
        window_type: str = Query("week", regex="^(day|week)$", description="Window type: day or week"),
        db: Session = Depends(get_db)
):
    window_delta = timedelta(days=1 if window_type == "day" else 7)

    cohort_start = datetime.combine(start_date, datetime.min.time())
    cohort_end = cohort_start + window_delta

    cohort_users_query = db.query(func.distinct(Event.user_id)).filter(
        Event.occurred_at >= cohort_start,
        Event.occurred_at < cohort_end
    )
    cohort_user_ids = [row[0] for row in cohort_users_query.all()]
    cohort_size = len(cohort_user_ids)

    if cohort_size == 0:
        return RetentionResponse(
            data=[],
            window_type=window_type
        )

    retention_windows = []

    for window_num in range(1, windows + 1):
        window_start = cohort_start + (window_delta * window_num)
        window_end = window_start + window_delta

        returned_users = db.query(func.count(func.distinct(Event.user_id))).filter(
            Event.user_id.in_(cohort_user_ids),
            Event.occurred_at >= window_start,
            Event.occurred_at < window_end
        ).scalar()

        retention_rate = (returned_users / cohort_size) * 100 if cohort_size > 0 else 0
        retention_windows.append(round(retention_rate, 2))

    cohort_data = RetentionCohort(
        cohort_date=str(start_date),
        users_count=cohort_size,
        retention_windows=retention_windows
    )

    return RetentionResponse(
        data=[cohort_data],
        window_type=window_type
    )


@app.get("/")
def root():
    return {
        "message": "Event Analytics API",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
