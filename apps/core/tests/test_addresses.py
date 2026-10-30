"""Which address somebody else can reach this Hera at — never 0.0.0.0 (hera_core.addresses)."""

from __future__ import annotations

import pytest

from hera_core import addresses
from hera_core.addresses import is_loopback, is_unspecified, reachable_base

LAN_PROBE = addresses.lan_address
"""The real one, kept before the fixture below replaces it for every other test."""


@pytest.fixture(autouse=True)
def _on_a_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(addresses, "lan_address", lambda: "192.168.1.20")


@pytest.mark.parametrize(
    ("base", "bind", "expected"),
    [
        # Every interface: what only this machine can open becomes its LAN address.
        ("http://0.0.0.0:8756/", "0.0.0.0", "http://192.168.1.20:8756"),
        ("http://localhost:8756", "0.0.0.0", "http://192.168.1.20:8756"),
        ("http://127.0.0.1:8756", "::", "http://192.168.1.20:8756"),
        ("http://[::1]:8756", "0.0.0.0", "http://192.168.1.20:8756"),
        # A real name or address is what the browser reached; it stays.
        ("https://hera.example.com", "0.0.0.0", "https://hera.example.com"),
        ("http://192.168.1.99:8756", "0.0.0.0", "http://192.168.1.99:8756"),
        # Bound to one address: that address.
        ("http://0.0.0.0:8756", "10.0.0.5", "http://10.0.0.5:8756"),
        # Bound to loopback, nothing else can reach it, and the link says so by staying local.
        ("http://localhost:8756", "127.0.0.1", "http://localhost:8756"),
        ("http://0.0.0.0:8756", "127.0.0.1", "http://127.0.0.1:8756"),
        # A path survives; there is no port to keep when there was none.
        ("https://0.0.0.0/hera/", "0.0.0.0", "https://192.168.1.20/hera"),
    ],
)
def test_a_link_points_where_others_can_go(base: str, bind: str, expected: str) -> None:
    assert reachable_base(base, bind_host=bind) == expected


def test_an_ipv6_lan_address_is_bracketed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(addresses, "lan_address", lambda: "fd00::20")
    assert reachable_base("http://0.0.0.0:8756", bind_host="::") == "http://[fd00::20]:8756"


def test_no_network_falls_back_to_this_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(addresses, "lan_address", lambda: None)
    assert reachable_base("http://0.0.0.0:8756", bind_host="0.0.0.0") == "http://127.0.0.1:8756"


def test_the_names_for_everywhere_and_for_here() -> None:
    assert is_unspecified("0.0.0.0") and is_unspecified("[::]") and is_unspecified("")
    assert not is_unspecified("192.168.1.20")
    assert is_loopback("localhost") and is_loopback("127.0.0.2") and is_loopback("[::1]")
    assert is_loopback("hera.localhost")
    assert not is_loopback("hera.example.com") and not is_loopback("10.0.0.1")


class FakeSocket:
    def __init__(self, local: str | None) -> None:
        self.local = local

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def connect(self, _: object) -> None:
        if self.local is None:
            raise OSError("Network is unreachable")

    def getsockname(self) -> tuple[str, int]:
        assert self.local is not None
        return (self.local, 50000)


@pytest.mark.parametrize(
    ("local", "expected"),
    [("192.168.1.20", "192.168.1.20"), ("127.0.0.1", None), ("0.0.0.0", None), (None, None)],
)
def test_the_lan_probe_names_only_a_real_network_address(
    monkeypatch: pytest.MonkeyPatch, local: str | None, expected: str | None
) -> None:
    monkeypatch.setattr("hera_core.addresses.socket.socket", lambda *_: FakeSocket(local))
    assert LAN_PROBE() == expected
