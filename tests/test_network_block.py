"""The test harness blocks the network and reports the attempted URL (Req 13.5, 13.6)."""

import socket
import urllib.request

import pytest

from tests.conftest import NetworkBlocked


def test_urlopen_is_blocked_and_reports_url(network_block):
    url = "https://clinicaltrials.gov/api/v2/studies?pageSize=1"
    with pytest.raises(NetworkBlocked) as excinfo:
        urllib.request.urlopen(url, timeout=1)
    assert url in str(excinfo.value)
    assert network_block == [url]
    network_block.clear()  # the attempt was deliberate; don't fail at teardown


def test_request_object_reports_full_url(network_block):
    url = "https://data.cdc.gov/resource/swc5-untb.json?$limit=1"
    with pytest.raises(NetworkBlocked) as excinfo:
        urllib.request.urlopen(urllib.request.Request(url))
    assert url in str(excinfo.value)
    network_block.clear()


def test_raw_socket_connect_is_blocked(network_block):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlocked) as excinfo:
            sock.connect(("192.0.2.1", 443))
    finally:
        sock.close()
    assert "192.0.2.1:443" in str(excinfo.value)
    assert not isinstance(excinfo.value, OSError)  # retry logic must not swallow it
    network_block.clear()
