import json
from datetime import datetime, date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from shared.models import Event
from backend.app import schemas


def get_daily_active_users(db: Session, from_date: date, to_date: date):
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

    return results


def get_top_events_by_count(db: Session, from_date: date, to_date: date, limit: int):
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

    return results


def calculate_retention(
    db: Session,
    start_date: date,
    windows: int,
    window_type: str
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
        return {
            "cohort_date": str(start_date),
            "users_count": 0,
            "retention_windows": []
        }

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

    return {
        "cohort_date": str(start_date),
        "users_count": cohort_size,
        "retention_windows": retention_windows
    }


async def ingest_events(
    request: schemas.EventsIngestRequest,
    nats_client
) -> schemas.EventsIngestResponse:
    if len(request.events) > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many events: {len(request.events)}. Maximum allowed is 5000 events per request."
        )

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
