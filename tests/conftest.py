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


# Loopback hosts. On Windows, socket.socketpair() has no native AF_UNIX
# implementation and falls back to a connected TCP pair over the loopback
# interface, so the block must let loopback connects through for tests that
# deliberately use socketpair(). Marked with @pytest.mark.allow_loopback.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _is_loopback(address: object) -> bool:
    if isinstance(address, tuple) and len(address) >= 1:
        return str(address[0]) in _LOOPBACK_HOSTS
    return False


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "allow_loopback: permit loopback (127.0.0.1/::1) socket connects in this test "
        "(e.g. socket.socketpair() on Windows); all other addresses stay blocked.",
    )


@pytest.fixture(autouse=True)
def network_block(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """Block the network for every test. Yields the list of attempted URLs.

    A test marked ``@pytest.mark.allow_loopback`` may connect to loopback
    addresses only; every non-loopback address, and urlopen for any URL, stays
    blocked and recorded.
    """
    attempts: list[str] = []
    allow_loopback = request.node.get_closest_marker("allow_loopback") is not None

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def blocked_urlopen(url, *args, **kwargs):
        target = getattr(url, "full_url", url)
        attempts.append(str(target))
        raise NetworkBlocked(str(target))

    def blocked_connect(self, address):
        if allow_loopback and _is_loopback(address):
            return real_connect(self, address)
        target = _describe_address(address)
        attempts.append(target)
        raise NetworkBlocked(target)

    def blocked_connect_ex(self, address):
        if allow_loopback and _is_loopback(address):
            return real_connect_ex(self, address)
        target = _describe_address(address)
        attempts.append(target)
        raise NetworkBlocked(target)

    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect_ex)

    yield attempts

    if attempts:
        pytest.fail("test attempted network access: %s" % ", ".join(attempts), pytrace=False)
