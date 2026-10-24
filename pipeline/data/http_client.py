"""HTTP_Client (design § HTTP_Client; Req 9.1-9.5, 9.7, 14.3).

Performs GET requests for both fetchers and applies the retry policy:

- Host allowlist: only https URLs on clinicaltrials.gov and data.cdc.gov are
  sent. Anything else raises PipelineError before any request (Req 14.3).
  Redirects to a host outside the allowlist are refused too.
- 1 initial attempt plus up to 3 retries, waiting 1, 2, then 4 s (Req 9.1).
  The counter is local to each `get` call (Req 9.2).
- Retried: connection errors, timeouts, HTTP 429 and HTTP 5xx. Retry-After is
  ignored because the requirements fix the waits.
- Other 4xx: HttpStatusError, no retry (Req 9.4).
- 60 s per attempt over the whole response (Req 9.5). The body is read in
  64 KiB chunks; before each read the socket timeout is reset to the time left,
  and passing the deadline counts as a timeout failure.

Error messages hold only the URL, the status or error type, and the attempt
count. Response bodies are never logged or put in messages (Req 3.3).
"""
from __future__ import annotations

import http.client
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from pipeline.errors import PipelineError

ALLOWED_HOSTS = frozenset({"clinicaltrials.gov", "data.cdc.gov"})
MAX_ATTEMPTS = 4
RETRY_WAITS = (1, 2, 4)  # seconds before retry 1, 2, 3 (Req 9.1)
ATTEMPT_TIMEOUT = 60.0  # seconds per attempt, whole response (Req 9.5)
CHUNK_SIZE = 64 * 1024
HEADERS = {
    "User-Agent": "research-gap-index-pipeline",
    "Accept": "application/json",
}


class HttpStatusError(PipelineError):
    """A non-retryable HTTP status (4xx other than 429). Req 9.4."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__("request failed: %s returned HTTP %d (no retry)" % (url, status))
        self.url = url
        self.status = status


class _RetryableFailure(Exception):
    """Internal: one failed attempt that may be retried. `kind` is a status or error type."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def check_allowed_url(url: str) -> None:
    """Raise PipelineError unless `url` is https on an allowlisted host (Req 14.3)."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_HOSTS:
        raise PipelineError(
            "refusing request to %s: only https on %s is allowed"
            % (url, ", ".join(sorted(ALLOWED_HOSTS)))
        )


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects that would leave the host allowlist (Req 14.3)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_opener(request: urllib.request.Request, timeout: float):
    # Built per call (not bound at import) so test-time patches of the
    # urllib/socket layer always apply.
    opener = urllib.request.build_opener(_AllowlistRedirectHandler)
    return opener.open(request, timeout=timeout)


def _find_socket(response) -> socket.socket | None:
    """Best-effort lookup of the socket under an http.client response."""
    fp = getattr(response, "fp", None)
    raw = getattr(fp, "raw", None)
    sock = getattr(raw, "_sock", None)
    return sock if isinstance(sock, socket.socket) else None


class HttpClient:
    def __init__(
        self,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sleep = sleep
        self._opener = opener if opener is not None else _default_opener
        self._clock = clock

    def get(self, url: str) -> bytes:
        """Return the body of a 2xx response, retrying per Req 9.1 (Req 9.7)."""
        check_allowed_url(url)
        last_kind = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                self._sleep(RETRY_WAITS[attempt - 2])
            try:
                return self._attempt(url)
            except _RetryableFailure as failure:
                last_kind = failure.kind
        raise PipelineError(
            "request failed: %s, final error %s after %d attempts"
            % (url, last_kind, MAX_ATTEMPTS)
        )

    def _attempt(self, url: str) -> bytes:
        deadline = self._clock() + ATTEMPT_TIMEOUT
        request = urllib.request.Request(url, headers=HEADERS, method="GET")
        try:
            response = self._opener(request, timeout=ATTEMPT_TIMEOUT)
            with response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if not 200 <= status < 300:
                    self._raise_for_status(url, status)
                return self._read_body(response, deadline)
        except urllib.error.HTTPError as exc:
            self._raise_for_status(url, exc.code)
        except (socket.timeout, TimeoutError):
            raise _RetryableFailure("timeout") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise _RetryableFailure("timeout") from None
            raise _RetryableFailure("connection error (%s)" % type(exc.reason).__name__) from None
        except (OSError, http.client.HTTPException) as exc:
            raise _RetryableFailure("connection error (%s)" % type(exc).__name__) from None
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _raise_for_status(url: str, status: int) -> None:
        if status == 429 or 500 <= status < 600:
            raise _RetryableFailure("HTTP %d" % status)
        raise HttpStatusError(url, status)

    def _read_body(self, response, deadline: float) -> bytes:
        sock = _find_socket(response)
        chunks: list[bytes] = []
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise _RetryableFailure("timeout")
            if sock is not None:
                sock.settimeout(remaining)
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
        if self._clock() > deadline:
            raise _RetryableFailure("timeout")
        return b"".join(chunks)
