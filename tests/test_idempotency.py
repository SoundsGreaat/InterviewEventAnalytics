import json
import uuid
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, schemas
from shared.database import Base
from shared.models import Event
from worker.app.worker import process_events_message


@pytest.fixture
def mock_nats_client():
    mock_client = AsyncMock()
    mock_client.is_connected = True
    mock_client.publish = AsyncMock()
    return mock_client


class TestIdempotency:

    @pytest.mark.asyncio
    async def test_duplicate_events_idempotent_statistics(self, mock_nats_client):
        test_date = datetime(2025, 10, 20, 12, 0, 0)
        event_ids = [uuid.uuid4() for _ in range(3)]

        events = [
            schemas.EventCreate(
                event_id=event_ids[0],
                occurred_at=test_date,
                user_id=1,
                event_type="login",
                properties={"country": "UA"}
            ),
            schemas.EventCreate(
                event_id=event_ids[1],
                occurred_at=test_date,
                user_id=2,
                event_type="view_item",
                properties={"country": "FR"}
            ),
            schemas.EventCreate(
                event_id=event_ids[2],
                occurred_at=test_date,
                user_id=1,
                event_type="login",
                properties={"country": "RO"}
            ),
            schemas.EventCreate(
                event_id=event_ids[2],
                occurred_at=test_date,
                user_id=1,
                event_type="login",
                properties={"country": "RO"}
            ),
        ]

        request = schemas.EventsIngestRequest(events=events)

        events_data = [event.model_dump(mode="json") for event in events]
        message_payload = {"events": events_data}
        message_bytes = json.dumps(message_payload, default=str).encode()

        mock_msg = MagicMock()
        mock_msg.data = message_bytes
        mock_msg.header = None
        mock_msg.subject = "events.ingest"

        response1 = await crud.ingest_events(request, mock_nats_client)

        with patch('worker.app.worker.SessionLocal') as mock_session_local:
            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(bind=engine)
            TestSessionLocal = sessionmaker(bind=engine)
            mock_session_local.return_value = TestSessionLocal()

            await process_events_message(mock_msg, mock_nats_client)

            db_session = TestSessionLocal()
            stats1_dau = crud.get_daily_active_users(
                db_session,
                date(2025, 10, 20),
                date(2025, 10, 20)
            )
            stats1_top = crud.get_top_events_by_count(
                db_session,
                date(2025, 10, 20),
                date(2025, 10, 20),
                limit=10
            )

            response2 = await crud.ingest_events(request, mock_nats_client)

            mock_session_local.return_value = TestSessionLocal()
            await process_events_message(mock_msg, mock_nats_client)

            stats2_dau = crud.get_daily_active_users(
                db_session,
                date(2025, 10, 20),
                date(2025, 10, 20)
            )
            stats2_top = crud.get_top_events_by_count(
                db_session,
                date(2025, 10, 20),
                date(2025, 10, 20),
                limit=10
            )

            assert response1.status == "accepted"
            assert response1.events_count == 4
            assert response2.status == "accepted"
            assert response2.events_count == 4

            assert mock_nats_client.publish.call_count == 2

            assert len(stats1_dau) == len(stats2_dau)
            assert len(stats1_top) == len(stats2_top)

            assert len(stats1_dau) == 1
            assert stats1_dau[0].unique_users == 2
            assert stats2_dau[0].unique_users == 2

            top_events_map = {row.event_type: row.count for row in stats1_top}
            assert top_events_map["login"] == 2
            assert top_events_map["view_item"] == 1

            top_events_map2 = {row.event_type: row.count for row in stats2_top}
            assert top_events_map == top_events_map2

            total_events = db_session.query(Event).count()
            assert total_events == 3

            db_session.close()
