import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.config import settings
from app.errors import AppError


class RateLimiter:
    """Sliding window: remembers when each key last made a request."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: int = 60) -> int | None:
        """Return None if allowed, or the number of seconds to wait."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(window_s - (now - hits[0])) + 1)
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def _enforce(key: str, limit: int) -> None:
    wait = limiter.check(key, limit)
    if wait is not None:
        raise AppError(
            429,
            "rate_limited",
            "Too many requests. Please try again later.",
            headers={"Retry-After": str(wait)},
        )


def login_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _enforce(f"login:{ip}", settings.rate_limit_login_per_min)


def enforce_upload_limit(user_id: int) -> None:
    _enforce(f"upload:{user_id}", settings.rate_limit_upload_per_min)


def enforce_user_limit(user_id: int) -> None:
    _enforce(f"user:{user_id}", settings.rate_limit_default_per_min)