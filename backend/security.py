"""Input validation, rate limiting, and request helpers for the API."""

from __future__ import annotations

import logging
import os
import uuid
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from time import time
from typing import Any, TypeVar

from flask import Request, jsonify

from game_logic import WORD_LENGTH

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

ALLOWED_STATIC_EXTENSIONS = frozenset({".css", ".js", ".html", ".ico", ".png", ".svg", ".woff2"})


class RateLimiter:
    """Simple in-memory sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time()
        cutoff = now - self.window_seconds
        hits = [t for t in self._hits[key] if t > cutoff]
        if len(hits) >= self.max_requests:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    def clear(self) -> None:
        self._hits.clear()


NEW_GAME_LIMITER = RateLimiter(
    max_requests=int(os.getenv("WURDLE_RATE_NEW_GAME", "30")),
    window_seconds=60.0,
)
GUESS_LIMITER = RateLimiter(
    max_requests=int(os.getenv("WURDLE_RATE_GUESS", "120")),
    window_seconds=60.0,
)


def clear_rate_limiters() -> None:
    """Reset rate limiters (for tests)."""
    NEW_GAME_LIMITER.clear()
    GUESS_LIMITER.clear()


def client_ip(request: Request) -> str:
    """Best-effort client IP, honoring X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def parse_game_id(value: object) -> str | None:
    """Return canonical UUID string or None if invalid."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return str(uuid.UUID(value.strip()))
    except ValueError:
        return None


def parse_guess(value: object) -> str | None:
    """Return a normalized 5-letter guess or None if the format is invalid."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if len(normalized) != WORD_LENGTH or not normalized.isalpha():
        return None
    return normalized


def parse_word_list(value: object, *, field_name: str = "words") -> list[str] | None:
    """Parse a list of 5-letter alpha words for test endpoints."""
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    words: list[str] = []
    for item in value:
        word = parse_guess(item) if isinstance(item, str) else None
        if word is None:
            return None
        words.append(word)
    return words


def is_safe_static_path(filename: str) -> bool:
    """True if filename is a single-segment static asset we allow serving."""
    if not filename or filename != os.path.basename(filename):
        return False
    if ".." in filename or filename.startswith(("/", "\\")):
        return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_STATIC_EXTENSIONS


def rate_limit(limiter: RateLimiter, label: str) -> Callable[[F], F]:
    """Decorator: return 429 when the client exceeds the limit (skipped in TESTING)."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            from flask import current_app, request

            if current_app.config.get("TESTING"):
                return fn(*args, **kwargs)

            ip = client_ip(request)
            if not limiter.allow(ip):
                logger.warning("Rate limit exceeded for %s from %s", label, ip)
                return jsonify({"status": "error", "error": "Too many requests"}), 429
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
