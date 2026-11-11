"""DNS-pinned HTTP transport for the public, untrusted-URL beta boundary."""

from __future__ import annotations

from collections.abc import Callable
from http.client import HTTPConnection, HTTPException, HTTPSConnection
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

from aeos.live.adapters.website_inspector import (
    FetchResponse,
    WebsiteInspectionError,
    _validate_url,
)

Resolver = Callable[..., list[tuple[object, ...]]]
ConnectionFactory = Callable[[str, str, str, int, float], HTTPConnection]
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5
_DEFAULT_TOTAL_TIMEOUT_SECONDS = 25


class PublicHTTPTransport:
    """Fetch public pages while pinning each validated DNS result to its socket."""

    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        connection_factory: ConnectionFactory | None = None,
        total_timeout_seconds: float = _DEFAULT_TOTAL_TIMEOUT_SECONDS,
    ) -> None:
        if total_timeout_seconds <= 0:
            raise ValueError("total_timeout_seconds must be positive")
        self._resolver = resolver or socket.getaddrinfo
        self._connection_factory = connection_factory or _pinned_connection
        self._deadline = time.monotonic() + total_timeout_seconds

    def __call__(
        self, url: str, timeout: int, byte_limit: int, root_host: str
    ) -> FetchResponse:
        current_url = _validate_url(url, root_host=root_host, resolve_host=False)
        for redirect_count in range(_MAX_REDIRECTS + 1):
            parts = urlsplit(current_url)
            host = parts.hostname
            if host is None:
                raise WebsiteInspectionError(
                    "Only absolute HTTP and HTTPS website URLs are supported.",
                    category="invalid_url",
                )
            port = parts.port or (443 if parts.scheme.casefold() == "https" else 80)
            address = self._resolve_public_address(host, port)
            remaining_seconds = self._deadline - time.monotonic()
            if remaining_seconds <= 0:
                raise WebsiteInspectionError(
                    "The public website request budget was exhausted.",
                    category="time_budget_exhausted",
                    stage="request_budget",
                )
            target = parts.path or "/"
            if parts.query:
                target += "?" + parts.query
            connection = self._connection_factory(
                parts.scheme.casefold(),
                host,
                address,
                port,
                min(float(timeout), remaining_seconds),
            )
            try:
                connection.request(
                    "GET",
                    target,
                    headers={
                        "User-Agent": "AEOSPublicBeta/1.0",
                        "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,*/*;q=0.5",
                        "Accept-Encoding": "identity",
                        "Connection": "close",
                    },
                )
                response = connection.getresponse()
                if response.status in _REDIRECT_CODES:
                    location = response.getheader("Location")
                    response.read(byte_limit + 1)
                    if not location:
                        return FetchResponse(
                            b"",
                            response.status,
                            current_url,
                            response.getheader("Content-Type"),
                        )
                    if redirect_count >= _MAX_REDIRECTS:
                        raise WebsiteInspectionError(
                            "The website exceeded the redirect limit.",
                            category="redirect_limit",
                        )
                    current_url = _validate_url(
                        urljoin(current_url, location),
                        root_host=root_host,
                        resolve_host=False,
                    )
                    continue
                body = response.read(byte_limit + 1)
                if len(body) > byte_limit:
                    raise WebsiteInspectionError(
                        "A website response exceeded the configured response limit.",
                        category="oversized_response",
                    )
                return FetchResponse(
                    body,
                    response.status,
                    current_url,
                    response.getheader("Content-Type"),
                )
            except WebsiteInspectionError:
                raise
            except (TimeoutError, socket.timeout) as error:
                raise WebsiteInspectionError(
                    "Website request timed out.",
                    category="timeout",
                    stage="http_request",
                ) from error
            except (OSError, HTTPException, ssl.SSLError) as error:
                raise WebsiteInspectionError(
                    "Website request failed.",
                    category="network_error",
                    stage="http_request",
                ) from error
            finally:
                connection.close()
        raise WebsiteInspectionError(
            "The website exceeded the redirect limit.", category="redirect_limit"
        )

    def _resolve_public_address(self, host: str, port: int) -> str:
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None:
            if not literal.is_global:
                raise WebsiteInspectionError(
                    "Local and private network destinations are not allowed.",
                    category="blocked_destination",
                    stage="dns_resolution",
                )
            return str(literal)
        try:
            results = self._resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as error:
            raise WebsiteInspectionError(
                "The website host could not be resolved.",
                category="dns_error",
                stage="dns_resolution",
            ) from error
        addresses: set[str] = set()
        for item in results:
            sockaddr = item[4] if len(item) > 4 else None
            if (
                isinstance(sockaddr, tuple)
                and sockaddr
                and isinstance(sockaddr[0], str)
            ):
                addresses.add(sockaddr[0].split("%", 1)[0])
        try:
            parsed = {ipaddress.ip_address(item) for item in addresses}
        except ValueError as error:
            raise WebsiteInspectionError(
                "The website returned an invalid network address.",
                category="dns_error",
                stage="dns_resolution",
            ) from error
        if not parsed:
            raise WebsiteInspectionError(
                "The website host could not be resolved.",
                category="dns_error",
                stage="dns_resolution",
            )
        if any(not address.is_global for address in parsed):
            raise WebsiteInspectionError(
                "The website resolves to a local or private network destination.",
                category="blocked_destination",
                stage="dns_resolution",
            )
        return sorted((str(address) for address in parsed))[0]


def _pinned_connection(
    scheme: str, host: str, address: str, port: int, timeout: float
) -> HTTPConnection:
    if scheme == "https":

        class PinnedHTTPSConnection(HTTPSConnection):
            def connect(self) -> None:
                raw_socket = socket.create_connection((address, port), self.timeout)
                context = ssl.create_default_context()
                self.sock = context.wrap_socket(raw_socket, server_hostname=host)

        return PinnedHTTPSConnection(host, port, timeout=timeout)

    class PinnedHTTPConnection(HTTPConnection):
        def connect(self) -> None:
            self.sock = socket.create_connection((address, port), self.timeout)

    return PinnedHTTPConnection(host, port, timeout=timeout)
