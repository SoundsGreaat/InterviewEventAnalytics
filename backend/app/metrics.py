import logging
import time
from collections import deque
from typing import Deque, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api_metrics")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class APIMetrics:
    def __init__(self):
        self._requests: Deque[Tuple[float, str, str]] = deque()

    def add_request(self, method: str, path: str):
        current_time = time.perf_counter()
        self._requests.append((current_time, method, path))
        self._cleanup_old_requests()

    def _cleanup_old_requests(self):
        cutoff_time = time.perf_counter() - 3600
        while self._requests and self._requests[0][0] < cutoff_time:
            self._requests.popleft()

    def get_requests_last_hour(self) -> int:
        self._cleanup_old_requests()
        return len(self._requests)


metrics = APIMetrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        metrics.add_request(request.method, request.url.path)

        response = await call_next(request)

        process_time = time.perf_counter() - start_time

        requests_last_hour = metrics.get_requests_last_hour()

        logger.info(
            f"{request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {process_time:.4f}s | "
            f"Requests last hour: {requests_last_hour}"
        )

        return response
