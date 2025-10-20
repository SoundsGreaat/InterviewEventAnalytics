# What I Learned

## Background

Coming from a Redis + Celery background, this project was my first hands-on experience with **NATS** as a messaging
system for async event processing.

## Core Concepts I Learned

### 1. NATS is Just a Message Broker

Unlike Celery which is a complete task orchestration framework, NATS is a pure message broker. It doesn't come with task
abstractions, result backends, or workflow management. This was eye-opening - I had to think in terms of raw messages
and subjects, not tasks and results.

### 2. Subjects as Routing Mechanism

```python
# Publishing to a subject
await nc.publish("events.ingest", data)

# Subscribing to a subject
sub = await nc.subscribe("events.ingest")
async for msg in sub.messages:
    await process_message(msg)
```

### 3. Manual Retry Implementation

This was the biggest learning curve. With Celery, retries were just a decorator parameter. With NATS, I built the entire
retry mechanism from scratch:

**What I learned:**

- Message headers are your state storage
- Exponential backoff: `5^1, 5^2, 5^3...` creates increasing delays
- Re-publishing is how you retry (not a built-in method)
- You control exactly when and how retries happen

## Configuration Choices

- I set max_payload to 8MB (maximum recommended value) to handle large event batches
- Fixed maximum retries prevents infinite retry loops and uncontrolled reprocessing of failing messages
- After exhausting retries, messages are moved to a Dead Letter Queue to avoid losing information while stopping
  repeated failed attempts

## Conclusion

- Learning NATS taught me what a message broker actually does vs. what a task framework provides

- For this event analytics system, NATS was perfect: simple ingestion pipeline, high throughput, no need for task
  results. The manual retry/DLQ implementation was educational and gives me precise control over failure handling
