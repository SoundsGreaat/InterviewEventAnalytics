# Event Analytics API

High-throughput event ingestion and analytics system with idempotent processing. Built with FastAPI, PostgreSQL, and
NATS.

## Features

- **Async Event Ingestion**
- **Idempotent Processing**
- **Analytics Endpoints**: DAU, Top Events, Retention Cohorts
- **Retry & DLQ**: 5 automatic retries with exponential backoff, dead letter queue for failures
- **API Key Authentication**: Simple and secure M2M authentication
- **Logging & Metrics**: Request duration, status codes, events processed

## Project Tree

```
├── backend                     FastAPI REST API service
│   ├── app
│   │   ├── auth.py             API key authentication
│   │   ├── crud.py             Business logic for API endpoints
│   │   ├── main.py             FastAPI entrypoint
│   │   ├── metrics.py          Request logging middleware
│   │   └── schemas.py          Pydantic models for request/response
│   ├── Dockerfile
│   └── requirements.txt
├── example                     Sample event generation and import scripts
│   ├── events_sample.csv       Sample CSV with event data
│   ├── generate_json.py        Script to generate sample JSON events
│   └── import_events.py        Script to import events directly to DB
├── shared
│   ├── config.py               Configuration management (env vars)
│   ├── database.py             Database session management
│   └── models.py               SQLAlchemy models
├── tests                       Test suite for backend and worker
│   ├── requirements.txt
│   └── test_idempotency.py
├── worker                      NATS consumer worker service
│   ├── app
│   │   └── worker.py           Event processing logic with retry/DLQ
│   ├── Dockerfile
│   ├── nats-server.conf        NATS server configuration
│   └── requirements.txt
├── docker-compose.yml
├── ADR.md                      Architecture Decision Record
├── LEARNED.md                  Technologies learned (NATS vs Celery)
└── README.md
```

**Key Components:**

- **Backend** (FastAPI): REST API with Pydantic validation
- **Worker** (NATS consumer): Async event processor with idempotency check
- **PostgreSQL**: Analytics queries with indexed columns
- **NATS**: Lightweight message broker (8MB max payload)

## Performance Benchmark

### Test Setup

- **Load**: 100,000 events in a single request
- **Configuration**: Default docker-compose setup + 64MB NATS max payload

### Results

| Stage                    | Duration | Description                                        |
|--------------------------|----------|----------------------------------------------------|
| **1. API Ingestion**     | 1.48s    | FastAPI validation + NATS publish                  |
| **2. Worker Processing** | 7.52s    | NATS → Database insertion (with idempotency check) |
| **3. DAU Query**         | 0.076s   | PostgreSQL aggregation query                       |
| **Total**                | ~9s      | End-to-end (API → Worker → Query)                  |

**Raw Logs:**

```
backend   | 2025-10-20 02:13:15,818 - INFO - POST /events | Status: 200 | Duration: 1.4798s
worker    | 2025-10-20 02:13:23,275 - INFO - Successfully saved 100000 events to database in 7.523s
backend   | 2025-10-20 02:15:31,977 - INFO - GET /stats/dau | Status: 200 | Duration: 0.0758s
```

### Bottleneck Analysis

**Identified Bottleneck: Database Insertion (7.52s)**

The worker spends most time on individual INSERT operations with idempotency checks:

```python
for event_data in events_data:
    existing_event = db.query(Event).filter(Event.event_id == event_id).first()
    if not existing_event:
        db.add(event)
db.commit()
```

**Why it's slow:**

- 100.000 SELECT queries to check for duplicates (1 per event)
- Single-threaded processing (one worker instance)

### Performance Optimization Strategies

#### 1. **Batch Upsert with PostgreSQL `ON CONFLICT`**

- Replace individual inserts with bulk upsert
- Single database round-trip instead of 100k
- PostgreSQL handles duplicate detection natively
- No application-level SELECT queries needed

#### 2. **Horizontal Scaling with NATS Queue Groups**

Run multiple worker instances:

```python
sub = await nc.subscribe("events.ingest", queue="workers")
```

```bash
docker-compose up --scale worker=4
```

- Distributes load across workers automatically
- NATS handles message distribution
- Requires no code changes (just queue parameter)

#### 3. **PostgreSQL COPY for Bulk Insert**

For extremely large batches (1M+ events) we can use `COPY` command with CSV files

#### 4. **Connection Pooling Tuning**

Increase PostgreSQL connection pool:

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

# Quick Start

## Prerequisites

- Docker & Docker Compose

## Configuration

### Configure API Key

```bash
cp .env.example .env
```

### Change .env file location in `docker-compose.yml` if needed.

From:

```yaml
env_file:
  - .env.example
```

To:

```yaml
env_file:
  - .env
```

## Start Services

```bash
docker-compose up --build
```

Services will be available at:

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **NATS Monitoring**: http://localhost:8222
- **PostgreSQL**: localhost:5432

## Send Events

**Generate sample events:**

```bash
python example/generate_json.py
```

**Send events to API:**

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: secret-key" \
  -d @events.json
```

**Response:**

```json
{
  "status": "accepted",
  "message": "Events queued for processing",
  "events_count": 5000
}
```

## Query Analytics

**Daily Active Users (DAU):**

```bash
curl "http://localhost:8000/stats/dau?from_date=2025-10-01&to=2025-10-31" \
  -H "X-API-Key: secret-key"
```

**Top Events:**

```bash
curl "http://localhost:8000/stats/top-events?from_date=2025-10-01&to=2025-10-31&limit=10" \
  -H "X-API-Key: secret-key"
```

**Retention Cohorts:**

```bash
curl "http://localhost:8000/stats/retention?start_date=2025-10-01&windows=4&window_type=week" \
  -H "X-API-Key: secret-key"
```

**See API docs for more details: http://localhost:8000/docs**

## Running Tests

**Install test dependencies:**

```bash
pip install -r tests/requirements.txt
```

**Run tests:**

```bash
pytest tests/
```

**Or if you see issues with imports on Linux/MacOS:**

```bash
PYTHONPATH=$(pwd) pytest tests/
```

## Related Documentation

- [ADR.md](ADR.md) - Architecture Decision Record
- [LEARNED.md](LEARNED.md) - Lessons learned (NATS vs Celery)
