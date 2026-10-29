"""One HTTP call to a public OSM service, with every failure mapped to `ExternalServiceError`.

Standard library only: the importer needs no HTTP dependency and no `SUMO_HOME` (ADR-0010,
ADR-0045)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence

from resto.application.ports.osm import ExternalServiceError

DEFAULT_USER_AGENT = "resto-tfm/0.1 (research prototype; LLM agents for SUMO networks)"
DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_S = 5.0
"""Wait before the second attempt; it doubles for each one after."""
DEFAULT_MAX_WAIT_S = 60.0
"""Longest single wait, whatever `Retry-After` asks."""
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


def request(
    service: str,
    url: str | Sequence[str],
    *,
    user_agent: str,
    timeout_s: float,
    data: bytes | None = None,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_s: float = DEFAULT_BACKOFF_S,
    max_wait_s: float = DEFAULT_MAX_WAIT_S,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """GET `url` (POST when `data` is given) and return the body. A transient failure (HTTP 429,
    502, 503 or 504, a connection error or a timeout) is retried, up to `attempts` in all, after
    a wait that doubles from `backoff_s` or follows `Retry-After`, never beyond `max_wait_s`.
    With several urls, each attempt goes to the next one. Any other failure, or the last
    transient one, raises `ExternalServiceError` naming `service` and the attempts made."""
    urls = [url] if isinstance(url, str) else list(url)
    reason = ""
    for attempt in range(1, attempts + 1):
        retry_after: float | None = None
        try:
            return _get(urls[(attempt - 1) % len(urls)], user_agent, timeout_s, data)
        except urllib.error.HTTPError as e:
            reason = f"HTTP {e.code} {e.reason}"
            if e.code not in RETRYABLE_STATUS:
                raise ExternalServiceError(service, reason) from e
            retry_after = _retry_after(e.headers.get("Retry-After") if e.headers else None)
            error: Exception = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = f"unreachable or too slow ({e})"
            error = e
        if attempt == attempts:
            raise ExternalServiceError(service, f"{reason}, after {attempts} attempts") from error
        wait = retry_after if retry_after is not None else backoff_s * 2 ** (attempt - 1)
        sleep(min(wait, max_wait_s))
    raise AssertionError("unreachable: the last attempt returns or raises")  # pragma: no cover


def _get(url: str, user_agent: str, timeout_s: float, data: bytes | None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout_s) as response:  # noqa: S310
        body: bytes = response.read()
        return body


def _retry_after(value: str | None) -> float | None:
    """Seconds from a `Retry-After` header; a date form or garbage counts as absent."""
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None
