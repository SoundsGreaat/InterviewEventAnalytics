FROM python:3.13-slim

WORKDIR /app

COPY shared /app/shared

COPY worker /app/worker

RUN pip install --no-cache-dir -r worker/requirements.txt

ENV PYTHONPATH=/app

CMD ["python", "worker/app/worker.py"]
