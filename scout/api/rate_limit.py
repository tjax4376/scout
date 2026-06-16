"""In-memory rate limiting for expensive API routes.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class RateLimitPolicy:
    max_events: int
    window_seconds: float


class InMemoryRateLimiter:
    """Sliding window limiter keyed by client identity."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _key(self, request: Request) -> str:
        # Per-IP + per-token buckets so shared NAT cannot exhaust another credential.
        client = request.client.host if request.client else "unknown"
        auth = request.headers.get("Authorization", "")
        digest = hashlib.sha256(auth.encode("utf-8")).hexdigest()[:16]
        return f"{client}:{digest}"

    def check(self, request: Request, policy: RateLimitPolicy) -> int:
        """Return Retry-After seconds or 0 when allowed."""
        now = time.monotonic()
        key = self._key(request)
        window = self._events[key]
        cutoff = now - policy.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= policy.max_events:
            retry = int(max(1, policy.window_seconds - (now - window[0])))
            return retry
        window.append(now)
        return 0


_limiter = InMemoryRateLimiter()


def enforce_rate_limit(request: Request, policy: RateLimitPolicy) -> None:
    retry = _limiter.check(request, policy)
    if retry > 0:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(retry)},
        )
