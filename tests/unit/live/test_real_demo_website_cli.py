"""Compatibility checks for the existing LIVE demo CLI routing."""

from pathlib import Path
import argparse

import pytest

from aeos.live import real_demo


def test_inspection_cli_routes_to_website_flow_without_market_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Path]] = []

    def inspect(url: str, *, output_directory: Path) -> int:
        calls.append((url, output_directory))
        return 7

    monkeypatch.setattr(real_demo, "run_website_inspection_command", inspect)
    assert (
        real_demo.main(
            ["--inspect-website", "https://example.com", "--output-dir", "out"]
        )
        == 7
    )
    assert calls == [("https://example.com", Path("out"))]


def test_existing_profile_flag_keeps_its_current_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Path] = []

    def profile(args: argparse.Namespace) -> int:
        seen.append(args.profile)
        return 3

    monkeypatch.setattr(real_demo, "_run_profile", profile)
    assert real_demo.main(["--profile", "profile.json"]) == 3
    assert seen == [Path("profile.json")]
