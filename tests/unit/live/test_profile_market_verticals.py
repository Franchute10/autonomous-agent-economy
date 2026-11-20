"""Offline profile-scoped coverage for documented OSM vertical mappings."""

import json
from pathlib import Path
from typing import cast

import pytest

from aeos.live.adapters.overpass import OverpassRequestError
from aeos.live.real_demo import main as real_demo_main

ROOT = Path(__file__).parents[3]
HVAC_FIXTURE = ROOT / "examples/live/business_profiles/fictional_hvac_company.json"


def _write_profile(tmp_path: Path, vertical: str) -> Path:
    payload = cast(dict[str, object], json.loads(HVAC_FIXTURE.read_text()))
    old_name = cast(str, payload["business_name"])
    name = f"Synthetic {vertical.replace('_', ' ').title()} Profile"
    payload["business_name"] = name
    payload["industry"] = vertical.replace("_", " ").title()
    payload["vertical"] = vertical
    for item in cast(list[dict[str, object]], payload["field_evidence"]):
        if item.get("subject") == old_name:
            item["subject"] = name
    path = tmp_path / "business-profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _report(output_dir: Path) -> tuple[dict[str, object], str]:
    report = cast(
        dict[str, object],
        json.loads(next(output_dir.glob("*.json")).read_text(encoding="utf-8")),
    )
    markdown = next(output_dir.glob("*.md")).read_text(encoding="utf-8")
    return report, markdown


def _provider(report: dict[str, object]) -> dict[str, object]:
    sources = cast(dict[str, object], report["sources_and_research_date"])
    return cast(dict[str, object], sources["provider"])


@pytest.mark.parametrize(
    ("vertical", "elements", "query_tags", "expected_counts"),
    (
        (
            "HVAC",
            (
                {
                    "type": "node",
                    "id": 501,
                    "tags": {"name": "Synthetic HVAC service", "craft": "hvac"},
                },
                {
                    "type": "node",
                    "id": 502,
                    "tags": {"name": "Synthetic HVAC equipment shop", "shop": "hvac"},
                },
                {
                    "type": "node",
                    "id": 503,
                    "tags": {
                        "name": "Synthetic property manager",
                        "office": "property_management",
                    },
                },
            ),
            ('["craft"="hvac"]', '["shop"="hvac"]'),
            (1, 1, 1, 1),
        ),
        (
            "ROOFING",
            (
                {
                    "type": "node",
                    "id": 601,
                    "tags": {"name": "Synthetic roofer", "craft": "roofer"},
                },
                {
                    "type": "node",
                    "id": 602,
                    "tags": {
                        "name": "Synthetic roofing supplier",
                        "shop": "trade",
                        "trade": "roofing",
                    },
                },
                {
                    "type": "node",
                    "id": 603,
                    "tags": {
                        "name": "Synthetic property manager",
                        "office": "property_management",
                    },
                },
                {
                    "type": "node",
                    "id": 604,
                    "tags": {
                        "name": "Synthetic real estate agency",
                        "office": "estate_agent",
                    },
                },
            ),
            ('["craft"="roofer"]', '["shop"="trade"]["trade"="roofing"]'),
            (1, 1, 1, 2),
        ),
    ),
)
def test_supported_verticals_make_one_simulated_search_and_map_only_supported_categories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    vertical: str,
    elements: tuple[dict[str, object], ...],
    query_tags: tuple[str, ...],
    expected_counts: tuple[int, int, int, int],
) -> None:
    profile = _write_profile(tmp_path, vertical)
    queries: list[str] = []
    endpoints: list[str] = []

    def simulated_provider(
        query: str, endpoint: str, timeout: int, max_bytes: int
    ) -> bytes:
        queries.append(query)
        endpoints.append(endpoint)
        return json.dumps({"elements": list(elements)}).encode("utf-8")

    monkeypatch.setattr("aeos.live.adapters.overpass._http_post", simulated_provider)
    output = tmp_path / "output"
    endpoint = "https://overpass.example/api/interpreter"
    real_demo_main(
        [
            "--profile",
            str(profile),
            "--output-dir",
            str(output),
            "--overpass-endpoint",
            endpoint,
            "--confirm-market-discovery",
        ]
    )
    console = capsys.readouterr().out
    report, _ = _report(output)
    provider = _provider(report)
    competition = cast(dict[str, object], report["competitive_environment"])
    counts = (
        len(cast(list[object], competition["same_sector_unqualified"])),
        len(cast(list[object], report["suppliers"])),
        len(cast(list[object], report["potential_customers"])),
        len(cast(list[object], report["partners_and_channels"])),
    )

    assert len(queries) == 1
    assert all(tag in queries[0] for tag in query_tags)
    assert provider["status"] == "COMPLETED_WITH_RESULTS"
    assert provider["request_count"] == 1
    assert provider["attempt_count"] == 1
    assert provider["retry_count"] == 0
    assert endpoints == [endpoint]
    assert provider["result_count"] == len(elements)
    assert counts == expected_counts
    assert "Discovery counts (COMPLETED_WITH_RESULTS)" in console
    assert f"{len(elements)} organizations" in console
    assert "Market discovery: COMPLETED_WITH_RESULTS" in console
    assert "attempts: 1 | retries: 0" in console


@pytest.mark.parametrize("confirmed", (False, True))
def test_home_remodeling_is_unsupported_and_sends_no_provider_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    confirmed: bool,
) -> None:
    profile = _write_profile(tmp_path, "HOME_REMODELING")

    def unexpected_provider_call(
        query: str, endpoint: str, timeout: int, max_bytes: int
    ) -> bytes:
        raise AssertionError("unsupported vertical must not call the provider")

    monkeypatch.setattr(
        "aeos.live.adapters.overpass._http_post", unexpected_provider_call
    )
    output = tmp_path / "output"
    argv = ["--profile", str(profile), "--output-dir", str(output)]
    if confirmed:
        argv.append("--confirm-market-discovery")
    real_demo_main(argv)
    console = capsys.readouterr().out
    report, markdown = _report(output)
    provider = _provider(report)

    assert provider["status"] == "UNSUPPORTED"
    assert provider["request_count"] == 0
    assert provider["attempt_count"] == 0
    assert provider["result_count"] is None
    assert "does not identify residential" in str(provider["unsupported_reason"])
    assert "**UNSUPPORTED**" in markdown
    assert "No hubo búsqueda para este vertical" in markdown
    assert "Discovery counts (UNSUPPORTED): not searched" in console
    assert "Market discovery: UNSUPPORTED" in console
    assert "no search sent (0 attempts)" in console


@pytest.mark.parametrize("vertical", ("HVAC", "HOUSE_CLEANING"))
def test_supported_profile_without_confirmation_does_not_contact_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    vertical: str,
) -> None:
    profile = _write_profile(tmp_path, vertical)
    provider_calls = 0

    def unexpected_adapter(*args: object, **kwargs: object) -> object:
        raise AssertionError("discovery without confirmation must not build adapter")

    def unexpected_provider_call(
        query: str, endpoint: str, timeout: int, max_bytes: int
    ) -> bytes:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("discovery without confirmation must not call provider")

    monkeypatch.setattr(
        "aeos.live.real_demo.OverpassMarketDiscovery", unexpected_adapter
    )
    monkeypatch.setattr(
        "aeos.live.adapters.overpass._http_post", unexpected_provider_call
    )
    output = tmp_path / "output"
    exit_code = real_demo_main(["--profile", str(profile), "--output-dir", str(output)])
    console = capsys.readouterr().out
    report, markdown = _report(output)
    provider = _provider(report)
    competition = cast(dict[str, object], report["competitive_environment"])
    market_counts = cast(dict[str, object], competition["counts"])

    assert provider_calls == 0
    assert exit_code == 1  # The synthetic profile lacks required assessment data.
    assert provider["status"] == "NOT_RUN"
    assert provider["request_count"] == 0
    assert provider["attempt_count"] == 0
    assert provider["retry_count"] == 0
    assert provider["result_count"] is None
    assert competition["market_result_available"] is False
    assert market_counts["all_discovered_entities"] is None
    assert market_counts["potential_competitors"] is None
    assert market_counts["verified_competitors"] is None
    assert report["potential_customers"] is None
    assert report["partners_and_channels"] is None
    assert report["suppliers"] is None
    assert "NOT_RUN" in markdown
    assert (
        "No se ejecutó la búsqueda; los conteos de competidores no están disponibles."
        in markdown
    )
    assert "no se puede determinar si hay organizaciones" in markdown
    assert "Competidores verificados: 0" not in markdown
    assert "Competidores potenciales: 0" not in markdown
    assert "Discovery counts (NOT_RUN): unavailable" in console
    assert "Market discovery: NOT_RUN" in console
    assert "no search sent (0 attempts)" in console


def test_provider_504_is_failed_and_market_result_remains_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    profile = _write_profile(tmp_path, "HVAC")

    def simulated_504(query: str, endpoint: str, timeout: int, max_bytes: int) -> bytes:
        raise OverpassRequestError(
            "Overpass returned HTTP 504 Gateway Timeout",
            status_code=504,
            category="http_status_error",
            request_reached_http_server=True,
            phase="response_headers",
        )

    monkeypatch.setattr("aeos.live.adapters.overpass._http_post", simulated_504)
    output = tmp_path / "output"
    assert (
        real_demo_main(
            [
                "--profile",
                str(profile),
                "--output-dir",
                str(output),
                "--confirm-market-discovery",
            ]
        )
        == 2
    )
    console = capsys.readouterr().out
    report, markdown = _report(output)
    provider = _provider(report)

    assert provider["status"] == "FAILED"
    assert provider["http_status"] == 504
    assert provider["request_count"] == 1
    assert provider["attempt_count"] == 1
    assert provider["retry_count"] == 0
    assert provider["result_count"] is None
    assert "resultado del mercado es desconocido" in markdown
    assert "no entity count or market absence can be inferred" in str(
        report["executive_summary"]
    )
    assert "returned 0 named organizations" not in str(report["executive_summary"])
    assert "No se pueden determinar los conteos de competidores" in markdown
    assert "Competidores verificados: 0" not in markdown
    assert "Discovery counts (FAILED): unavailable" in console
    assert "market result is unknown" in console
    assert "Market discovery: FAILED" in console
    assert "attempts: 1 | retries: 0 | HTTP status: 504" in console
    assert "Discovery counts (FAILED): 0" not in console


def test_completed_zero_result_is_distinct_from_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    profile = _write_profile(tmp_path, "ROOFING")
    calls = 0

    def simulated_empty_provider(
        query: str, endpoint: str, timeout: int, max_bytes: int
    ) -> bytes:
        nonlocal calls
        calls += 1
        return b'{"elements": []}'

    monkeypatch.setattr(
        "aeos.live.adapters.overpass._http_post", simulated_empty_provider
    )
    output = tmp_path / "output"
    real_demo_main(
        [
            "--profile",
            str(profile),
            "--output-dir",
            str(output),
            "--confirm-market-discovery",
        ]
    )
    console = capsys.readouterr().out
    report, markdown = _report(output)
    provider = _provider(report)

    assert calls == 1
    assert provider["status"] == "COMPLETED_NO_RESULTS"
    assert provider["request_count"] == 1
    assert provider["result_count"] == 0
    assert provider["error"] is None
    assert "La búsqueda terminó correctamente" in markdown
    assert "Discovery counts (COMPLETED_NO_RESULTS): 0 organizations" in console
    assert "Market discovery: COMPLETED_NO_RESULTS" in console
    assert "attempts: 1 | retries: 0 | HTTP status: 200" in console
