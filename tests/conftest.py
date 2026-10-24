"""Shared test harness.

- Network block (Req 13.5, 13.6): every test runs with `socket.socket.connect`,
  `socket.socket.connect_ex` and `urllib.request.urlopen` patched. Any attempt
  raises `NetworkBlocked` naming the URL or address, and is also recorded, so
  the test fails at teardown even if the code under test swallows the error.
- Hypothesis profile (Req 13.7): at least 100 examples per property, no deadline.
"""

import socket
import urllib.request

import pytest
from hypothesis import settings

settings.register_profile("pipeline", max_examples=100, deadline=None)
settings.load_profile("pipeline")


class NetworkBlocked(Exception):
    """Raised on any network attempt during tests.

    Deliberately not an OSError subclass, so retry logic that catches
    connection errors (OSError / URLError) does not swallow it.
    """

    def __init__(self, url: str) -> None:
        super().__init__("network access blocked in tests: %s" % url)
        self.url = url


def _describe_address(address: object) -> str:
    if isinstance(address, tuple) and len(address) >= 2:
        return "%s:%s" % (address[0], address[1])
    return str(address)


@pytest.fixture(autouse=True)
def network_block(monkeypatch: pytest.MonkeyPatch):
    """Block the network for every test. Yields the list of attempted URLs."""
    attempts: list[str] = []

    def blocked_urlopen(url, *args, **kwargs):
        target = getattr(url, "full_url", url)
        attempts.append(str(target))
        raise NetworkBlocked(str(target))

    def blocked_connect(self, address):
        target = _describe_address(address)
        attempts.append(target)
        raise NetworkBlocked(target)

    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect)

    yield attempts

    if attempts:
        pytest.fail("test attempted network access: %s" % ", ".join(attempts), pytrace=False)
