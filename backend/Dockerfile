FROM python:3.13-slim

WORKDIR /app

COPY shared /app/shared

COPY backend /app/backend

RUN pip install --no-cache-dir -r backend/requirements.txt

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
