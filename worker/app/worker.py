import asyncio
import json
import logging
from datetime import datetime
from uuid import UUID

import nats
from nats.aio.msg import Msg

from shared.config import settings
from shared.database import SessionLocal
from shared.models import Event

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY_BASE = 3
DLQ_SUBJECT = "events.dlq"


def get_retry_count(msg: Msg) -> int:
    if msg.header is None:
        return 0
    retry_count = msg.header.get("X-Retry-Count", "0")
    try:
        return int(retry_count)
    except (ValueError, TypeError):
        return 0


async def send_to_dlq(nc: nats.NATS, original_msg: Msg, error_msg: str):
    try:
        headers = {
            "X-Original-Subject": original_msg.subject,
            "X-Error-Message": error_msg,
            "X-Failed-At": datetime.utcnow().isoformat(),
        }

        if original_msg.header:
            retry_count = get_retry_count(original_msg)
            headers["X-Retry-Count"] = str(retry_count)

        await nc.publish(
            DLQ_SUBJECT,
            original_msg.data,
            headers=headers
        )
        logger.warning(f"Message sent to DLQ after {get_retry_count(original_msg)} retries: {error_msg}")
    except Exception as e:
        logger.error(f"Failed to send message to DLQ: {e}")


async def process_events_message(msg: Msg, nc: nats.NATS):
    retry_count = get_retry_count(msg)

    try:
        data = json.loads(msg.data.decode())
        events_data = data.get("events", [])

        logger.info(f"Processing {len(events_data)} events (attempt {retry_count + 1}/{MAX_RETRIES + 1})")

        db = SessionLocal()
        try:
            for event_data in events_data:
                event = Event(
                    event_id=UUID(event_data["event_id"]) if isinstance(event_data["event_id"], str) else event_data[
                        "event_id"],
                    occurred_at=datetime.fromisoformat(event_data["occurred_at"]) if isinstance(
                        event_data["occurred_at"], str) else event_data["occurred_at"],
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
        error_msg = str(e)
        logger.error(f"Error processing message (attempt {retry_count + 1}/{MAX_RETRIES + 1}): {error_msg}")

        if retry_count < MAX_RETRIES:
            retry_delay = RETRY_DELAY_BASE ** (retry_count + 1)
            logger.info(f"Scheduling retry in {retry_delay} seconds...")

            await asyncio.sleep(retry_delay)

            headers = msg.header.copy() if msg.header else {}
            headers["X-Retry-Count"] = str(retry_count + 1)

            await nc.publish(
                msg.subject,
                msg.data,
                headers=headers
            )
            logger.info(f"Message requeued for retry {retry_count + 1}")
        else:
            await send_to_dlq(nc, msg, error_msg)


async def main():
    logger.info("Starting NATS worker...")

    nc = await nats.connect(settings.NATS_URL)
    logger.info("Connected to NATS")

    sub = await nc.subscribe("events.ingest")
    logger.info("Subscribed to events.ingest")

    dlq_sub = await nc.subscribe(DLQ_SUBJECT)
    logger.info(f"Subscribed to {DLQ_SUBJECT} for monitoring")

    async def dlq_handler():
        async for msg in dlq_sub.messages:
            logger.error(f"DLQ message received: {msg.header}")

    dlq_task = asyncio.create_task(dlq_handler())

    try:
        async for msg in sub.messages:
            await process_events_message(msg, nc)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        dlq_task.cancel()
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
