"""Security checks for the pinned transport used by the public URL endpoint."""

import socket

import pytest

from aeos.live.adapters.public_http import PublicHTTPTransport
from aeos.live.adapters.website_inspector import WebsiteInspectionError


def test_blocks_dns_answers_that_include_a_private_address() -> None:
    calls: list[str] = []

    def resolve(host: str, port: int, **_kwargs: object) -> list[tuple[object, ...]]:
        calls.append(host)
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", port)),
        ]

    def should_not_connect(*_args: object) -> object:
        pytest.fail("a private DNS answer must be rejected before opening a socket")

    transport = PublicHTTPTransport(
        resolver=resolve,
        connection_factory=should_not_connect,  # type: ignore[arg-type]
    )

    with pytest.raises(WebsiteInspectionError) as error:
        transport("https://example.com/", 2, 1024, "example.com")

    assert error.value.category == "blocked_destination"
    assert calls == ["example.com"]


@pytest.mark.parametrize(
    ("location", "expected_category"),
    [
        ("http://127.0.0.1/admin", "blocked_destination"),
        ("https://attacker.example/path", "cross_domain_redirect"),
    ],
)
def test_unsafe_redirect_is_rejected_before_a_second_connection(
    location: str, expected_category: str
) -> None:
    addresses: list[str] = []
    connections: list[object] = []

    def resolve(host: str, port: int, **_kwargs: object) -> list[tuple[object, ...]]:
        addresses.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    class RedirectResponse:
        status = 302

        def getheader(self, name: str) -> str | None:
            return location if name == "Location" else None

        def read(self, _limit: int) -> bytes:
            return b""

    class RedirectConnection:
        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> RedirectResponse:
            return RedirectResponse()

        def close(self) -> None:
            return None

    def connect(*_args: object) -> RedirectConnection:
        connection = RedirectConnection()
        connections.append(connection)
        return connection

    transport = PublicHTTPTransport(
        resolver=resolve,
        connection_factory=connect,  # type: ignore[arg-type]
    )

    with pytest.raises(WebsiteInspectionError) as error:
        transport("https://example.com/", 2, 1024, "example.com")

    assert error.value.category == expected_category
    assert addresses == ["example.com"]
    assert len(connections) == 1
