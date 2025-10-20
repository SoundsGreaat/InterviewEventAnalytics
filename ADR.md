# Architecture Decision Record

## Summary

Event Analytics API is a high-throughput system for ingesting user events and computing analytics (DAU, top events,
retention cohorts). Requirements: handle large event batches, ensure idempotency, provide fast
statistics queries.

## Decision Overview

| Area                  | Choice                    | Alternatives                   | Rationale                                                                                                       |
|-----------------------|---------------------------|--------------------------------|-----------------------------------------------------------------------------------------------------------------|
| **Web Framework**     | FastAPI                   | Flask, Django                  | Native async support, automatic OpenAPI docs, Pydantic validation, best performance for I/O-bound workloads     |
| **Database**          | PostgreSQL                | MongoDB, ClickHouse            | ACID guarantees, excellent aggregation (GROUP BY for DAU/stats), reliable UUID primary keys                     |
| **Message Queue**     | NATS                      | RabbitMQ, Kafka, Redis Streams | Lightweight (25MB Alpine image), simple pub/sub, 40k+ msg/sec, no need for persistence (events can be replayed) |
| **ORM**               | SQLAlchemy                | Raw SQL, Tortoise ORM          | Industry standard, type safety, migration support, powerful query builder for analytics                         |
| **Testing**           | pytest + in-memory SQLite | unittest, Testcontainers       | Fast isolated tests, real worker function testing, zero external dependencies                                   |
| **Auth**              | API Key Header            | JWT, OAuth2, Basic Auth        | Simple for M2M communication, no token expiry management                                                        |
| **Container Runtime** | Docker Compose            | Kubernetes, Docker Swarm       | Development simplicity                                                                                          |
| **Server**            | Uvicorn                   | Gunicorn+Uvicorn, Hypercorn    | Pure ASGI server, excellent async performance, simple configuration                                             |

## Architecture Pattern

**Event-Driven with Async Workers**

```
Client → FastAPI (validate) → NATS → Worker → PostgreSQL
                                ↓ (retry 5x)
                              DLQ (events.dlq)
```

**Why this pattern:**

- **Decoupling**: API accepts events immediately, processing happens async
- **Reliability**: 5 retries with exponential backoff (3^n seconds), DLQ for permanent failures
- **Idempotency**: UUID primary key ensures duplicate events are ignored (worker checks before INSERT)