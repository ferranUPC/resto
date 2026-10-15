"""One HTTP call to a public OSM service, with every failure mapped to `ExternalServiceError`.

Standard library only: the importer needs no HTTP dependency and no `SUMO_HOME` (ADR-0010,
ADR-0045)."""

from __future__ import annotations

import urllib.error
import urllib.request

from resto.application.ports.osm import ExternalServiceError

DEFAULT_USER_AGENT = "resto-tfm/0.1 (research prototype; LLM agents for SUMO networks)"


def request(
    service: str,
    url: str,
    *,
    user_agent: str,
    timeout_s: float,
    data: bytes | None = None,
) -> bytes:
    """GET `url` (POST when `data` is given) and return the body. Any failure to get a 2xx answer,
    including a timeout, raises `ExternalServiceError` naming `service`."""
    req = urllib.request.Request(url, data=data, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:  # noqa: S310
            body: bytes = response.read()
            return body
    except urllib.error.HTTPError as e:
        raise ExternalServiceError(service, f"HTTP {e.code} {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ExternalServiceError(service, f"unreachable or too slow ({e})") from e
