"""Focused offline regression tests for the integrated Playwright renderer."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import aeos.live.adapters.website_inspector as website_inspector
from aeos.live.adapters.website_inspector import PlaywrightDOMRenderer

URL = "https://sample-cleaning.example/"


class _Frame:
    parent_frame: _Frame | None = None


class _Request:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        resource_type: str = "document",
        navigation: bool = False,
        frame: _Frame | None = None,
    ) -> None:
        self.url = url
        self.method = method
        self.resource_type = resource_type
        self.navigation = navigation
        self.frame = frame
        self.headers = {
            "authorization": "Basic private",
            "cookie": "session=private",
            "referer": "https://outside.example/",
        }

    def is_navigation_request(self) -> bool:
        return self.navigation


class _Route:
    def __init__(self, request: _Request) -> None:
        self.request = request
        self.aborted = False
        self.continued_headers: dict[str, str] | None = None

    def abort(self) -> None:
        self.aborted = True

    def continue_(self, *, headers: dict[str, str]) -> None:
        self.continued_headers = headers


class _Response:
    status = 200


class _Page:
    def __init__(
        self,
        context: _Context,
        dom: dict[str, Any],
        *,
        external_image: bool = False,
        navigation_timeout: bool = False,
        hydrated_dom: dict[str, Any] | None = None,
    ) -> None:
        self.context = context
        self.dom = dom
        self.external_image = external_image
        self.navigation_timeout = navigation_timeout
        self.hydrated_dom = hydrated_dom
        self.url = "about:blank"
        self.main_frame = _Frame()
        self.goto_wait_until: str | None = None
        self.waits: list[int] = []
        self.routes: list[_Route] = []

    def set_default_timeout(self, _timeout: int) -> None:
        pass

    def set_default_navigation_timeout(self, _timeout: int) -> None:
        pass

    def goto(self, url: str, *, wait_until: str, timeout: int) -> _Response:
        assert timeout > 0
        self.goto_wait_until = wait_until
        self.url = url
        main_route = _Route(
            _Request(
                url, resource_type="document", navigation=True, frame=self.main_frame
            )
        )
        self.routes.append(main_route)
        self.context.route_handler(main_route)
        if self.external_image:
            image_route = _Route(
                _Request(
                    "https://cdn.example/logo.png?tracking=private",
                    resource_type="image",
                    frame=self.main_frame,
                )
            )
            self.routes.append(image_route)
            self.context.route_handler(image_route)
        if self.navigation_timeout:
            raise TimeoutError("Navigation timed out waiting for DOMContentLoaded")
        return _Response()

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)
        if self.hydrated_dom is not None:
            self.dom.update(self.hydrated_dom)

    def evaluate(self, _script: str) -> dict[str, Any]:
        return {"document_available": True, **self.dom}


class _Context:
    def __init__(self, dom: dict[str, Any], **page_options: Any) -> None:
        self.page = _Page(self, dom, **page_options)
        self.route_handler: Any = None
        self.init_script: str | None = None

    def route(self, _pattern: str, handler: Any) -> None:
        self.route_handler = handler

    def add_init_script(self, script: str) -> None:
        self.init_script = script

    def new_page(self) -> _Page:
        return self.page

    def close(self) -> None:
        pass


class _Browser:
    def __init__(self, context: _Context) -> None:
        self.context = context

    def new_context(self, **_kwargs: Any) -> _Context:
        return self.context

    def close(self) -> None:
        pass


def _run_renderer(
    monkeypatch: pytest.MonkeyPatch,
    dom: dict[str, Any],
    **page_options: Any,
) -> tuple[Any, _Page, _Context]:
    context = _Context(dom, **page_options)
    browser = _Browser(context)
    playwright = SimpleNamespace(
        chromium=SimpleNamespace(launch=lambda **_kwargs: browser)
    )

    class _Manager:
        def __enter__(self) -> SimpleNamespace:
            return playwright

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        website_inspector,
        "import_module",
        lambda _name: SimpleNamespace(sync_playwright=lambda: _Manager()),
    )
    outcome = PlaywrightDOMRenderer()((URL,), "sample-cleaning.example", 2)[URL]
    return outcome, context.page, context


def test_blocked_external_image_is_a_warning_and_dom_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, page, context = _run_renderer(
        monkeypatch,
        {
            "ready_state": "complete",
            "title": "Rendered title",
            "meta_description": "Rendered description",
            "h1_headings": ["Rendered H1"],
            "h2_headings": ["Rendered H2"],
            "link_texts": ["Contact"],
            "link_urls": ["https://sample-cleaning.example/contact"],
        },
        external_image=True,
    )

    assert page.goto_wait_until == "domcontentloaded"
    assert len(page.routes) == 2
    assert page.routes[0].continued_headers == {}
    assert page.routes[1].aborted
    assert context.init_script is not None
    assert "document.addEventListener('submit'" in context.init_script
    assert outcome.dom is not None
    assert outcome.dom.h1_headings == ("Rendered H1",)
    assert outcome.error_category == "external_resources_blocked"
    assert "image:external_resources_blocked" in str(outcome.error_message)


def test_navigation_timeout_preserves_readable_partial_dom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, page, _ = _run_renderer(
        monkeypatch,
        {
            "ready_state": "interactive",
            "title": "Partial page title",
            "meta_description": None,
            "h1_headings": ["Observed H1"],
            "h2_headings": [],
            "link_texts": [],
            "link_urls": [],
        },
        navigation_timeout=True,
    )

    assert outcome.dom is not None
    assert outcome.dom.title == "Partial page title"
    assert outcome.dom.h1_headings == ("Observed H1",)
    assert outcome.error_category == "render_timeout"
    assert "Partial DOM was readable" in str(outcome.error_message)
    assert "fields observed: title, h1" in str(outcome.error_message)
    assert page.goto_wait_until == "domcontentloaded"


def test_short_hydration_wait_captures_later_dom_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, page, _ = _run_renderer(
        monkeypatch,
        {
            "ready_state": "interactive",
            "title": "Hydrated title",
            "meta_description": None,
            "h1_headings": [],
            "h2_headings": [],
            "link_texts": [],
            "link_urls": [],
        },
        hydrated_dom={
            "ready_state": "complete",
            "meta_description": "Hydrated description",
            "h1_headings": ["Hydrated H1"],
            "h2_headings": ["Hydrated H2"],
            "link_texts": ["Contact"],
            "link_urls": ["https://sample-cleaning.example/contact"],
        },
    )

    assert outcome.dom is not None
    assert outcome.dom.h1_headings == ("Hydrated H1",)
    assert outcome.dom.h2_headings == ("Hydrated H2",)
    assert outcome.dom.link_urls == ("https://sample-cleaning.example/contact",)
    assert page.waits == [350]
    assert page.goto_wait_until == "domcontentloaded"
