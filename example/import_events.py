import csv
import json
import uuid
from datetime import datetime

from sqlalchemy import create_engine

from shared.config import settings
from shared.models import Event, Base
from shared.database import SessionLocal

def import_csv(csv_path: str) -> None:
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)

    session = SessionLocal()

    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            event = Event(
                event_id=uuid.UUID(row["event_id"]) if row.get("event_id") else None,
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                user_id=int(row["user_id"]),
                event_type=row["event_type"],
                properties=json.loads(row.get("properties") or row.get("properties_json") or "{}")
            )
            session.add(event)

    session.commit()
    session.close()

if __name__ == "__main__":
    import sys
    import_csv(sys.argv[1])