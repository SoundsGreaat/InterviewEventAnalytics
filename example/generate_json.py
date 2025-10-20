import json
import random
import uuid
from datetime import datetime, timedelta


def generate_events(num_events: int):
    base_time = datetime.utcnow()
    event_types = [
        "app_open", "view_item", "message_sent", "add_to_cart", "login", "logout", "purchase"
    ]

    events = []
    for _ in range(num_events):
        event = {
            "event_id": str(uuid.uuid4()),
            "occurred_at": (base_time - timedelta(seconds=random.randint(0, 3600 * 24 * 30))).isoformat() + "Z",
            "user_id": random.randint(0, 1000),
            "event_type": random.choice(event_types),
            "properties": {"additionalProp": {}}
        }
        events.append(event)
    return {"events": events}


def main():
    data = generate_events(5000)
    with open("events.json", "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()
