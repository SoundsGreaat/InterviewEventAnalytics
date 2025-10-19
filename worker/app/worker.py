import asyncio
import json
import logging
from datetime import datetime
from uuid import UUID

import nats

from shared.database import SessionLocal
from shared.models import Event
from shared.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def process_events_message(msg):
    try:
        data = json.loads(msg.data.decode())
        events_data = data.get("events", [])

        logger.info(f"Processing {len(events_data)} events")

        db = SessionLocal()
        try:
            for event_data in events_data:
                event = Event(
                    event_id=UUID(event_data["event_id"]) if isinstance(event_data["event_id"], str) else event_data["event_id"],
                    occurred_at=datetime.fromisoformat(event_data["occurred_at"]) if isinstance(event_data["occurred_at"], str) else event_data["occurred_at"],
                    user_id=event_data["user_id"],
                    event_type=event_data["event_type"],
                    properties=event_data.get("properties", {})
                )
                db.add(event)

            db.commit()
            logger.info(f"Successfully saved {len(events_data)} events to database")

        except Exception as e:
            db.rollback()
            logger.error(f"Error saving events to database: {e}")
            raise
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error processing message: {e}")


async def main():
    logger.info("Starting NATS worker...")

    nc = await nats.connect(settings.NATS_URL)
    logger.info("Connected to NATS")

    sub = await nc.subscribe("events.ingest")
    logger.info("Subscribed to events.ingest")

    try:
        async for msg in sub.messages:
            await process_events_message(msg)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
