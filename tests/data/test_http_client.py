"""Example tests for HTTP_Client (Req 9.1-9.5, 9.7, 14.3).

All tests inject `opener`, `sleep` and `clock`, so nothing reaches the network.
"""
import io
import socket
import urllib.error

import pytest

from pipeline.data.http_client import HttpClient, HttpStatusError
from pipeline.errors import PipelineError

URL = "https://clinicaltrials.gov/api/v2/studies?pageSize=1000"


class FakeResponse:
    def __init__(self, body: bytes = b"{}", status: int = 200, on_read=None):
        self.status = status
        self._buf = io.BytesIO(body)
        self._on_read = on_read

    def read(self, n=-1):
        if self._on_read:
            self._on_read()
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, status, "err", {}, io.BytesIO(b"secret body"))


class ScriptedOpener:
    """Returns or raises the scripted outcomes in order, recording each call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_client(outcomes):
    opener = ScriptedOpener(outcomes)
    sleeps = []
    client = HttpClient(sleep=sleeps.append, opener=opener, clock=FakeClock())
    return client, opener, sleeps


def test_retry_sequence_and_waits_req_9_1():
    # Req 9.1: connection error, timeout, 429 and 5xx are retried with 1, 2, 4 s waits.
    client, opener, sleeps = make_client([
        urllib.error.URLError(ConnectionRefusedError()),
        socket.timeout(),
        http_error(429),
        FakeResponse(b'{"ok":1}'),
    ])
    assert client.get(URL) == b'{"ok":1}'
    assert sleeps == [1, 2, 4]
    assert len(opener.requests) == 4


def test_fourth_failure_stops_with_url_status_and_attempts_req_9_3():
    # Req 9.3: after the 4th failure, no further request; message has URL, status, 4 attempts.
    client, opener, sleeps = make_client([http_error(503)] * 4 + [FakeResponse()])
    with pytest.raises(PipelineError) as info:
        client.get(URL)
    message = str(info.value)
    assert URL in message
    assert "HTTP 503" in message
    assert "4 attempts" in message
    assert "secret body" not in message  # Req 3.3: no body content
    assert len(opener.requests) == 4
    assert sleeps == [1, 2, 4]


def test_no_retry_on_404_req_9_4():
    # Req 9.4: 4xx other than 429 is not retried.
    client, opener, sleeps = make_client([http_error(404), FakeResponse()])
    with pytest.raises(HttpStatusError) as info:
        client.get(URL)
    assert info.value.status == 404
    assert URL in str(info.value) and "404" in str(info.value)
    assert len(opener.requests) == 1
    assert sleeps == []


def test_2xx_after_two_failures_returns_body_req_9_7():
    # Req 9.7: a 2xx ends retrying and returns the body to the fetcher.
    client, opener, sleeps = make_client([
        http_error(500),
        ConnectionResetError(),
        FakeResponse(b"[1,2,3]"),
    ])
    assert client.get(URL) == b"[1,2,3]"
    assert sleeps == [1, 2]
    assert len(opener.requests) == 3


def test_retry_counter_is_per_request_req_9_2():
    # Req 9.2: each get call has its own limit of 4 attempts.
    client, opener, _ = make_client(
        [http_error(502)] * 3 + [FakeResponse(b"a")] + [http_error(502)] * 3 + [FakeResponse(b"b")]
    )
    assert client.get(URL) == b"a"
    assert client.get(URL) == b"b"
    assert len(opener.requests) == 8


def test_deadline_exceeded_is_retryable_timeout_req_9_5():
    # Req 9.5: the 60 s deadline covers the whole body, not each socket read.
    clock = FakeClock()

    def slow_read():
        clock.now += 25  # each 64 KiB chunk takes 25 s; total > 60 s

    def slow_response():
        return FakeResponse(b"x" * (64 * 1024 * 4), on_read=slow_read)

    opener = ScriptedOpener([slow_response() for _ in range(4)])
    sleeps = []
    client = HttpClient(sleep=sleeps.append, opener=opener, clock=clock)
    with pytest.raises(PipelineError) as info:
        client.get(URL)
    assert "timeout" in str(info.value)
    assert "4 attempts" in str(info.value)
    assert len(opener.requests) == 4
    assert all(timeout == 60.0 for _, timeout in opener.requests)


def test_host_outside_allowlist_sends_nothing_req_14_3():
    # Req 14.3: only clinicaltrials.gov and data.cdc.gov, checked before sending.
    for url in [
        "https://example.com/api",
        "https://clinicaltrials.gov.evil.com/api",
        "http://clinicaltrials.gov/api/v2/studies",
    ]:
        client, opener, _ = make_client([FakeResponse()])
        with pytest.raises(PipelineError) as info:
            client.get(url)
        assert url in str(info.value)
        assert opener.requests == []


def test_headers_and_allowed_places_host():
    client, opener, _ = make_client([FakeResponse(b"[]")])
    assert client.get("https://data.cdc.gov/resource/swc5-untb.json?$limit=1") == b"[]"
    request, _ = opener.requests[0]
    assert request.get_header("User-agent") == "research-gap-index-pipeline"
    assert request.get_header("Accept") == "application/json"
