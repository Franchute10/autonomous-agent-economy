"""Operator command for Manatee County's read-only procurement import path."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Sequence

from aeos.application.live.procurement_acquisition import (
    build_acquisition_report,
    build_synthetic_profile_preview,
    render_acquisition_markdown,
)
from aeos.live.adapters.manatee_procurement import (
    AcquisitionState,
    load_manual_import,
)
from aeos.live.domain.profile import parse_business_profile_document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import manually supplied Manatee County solicitation data and create "
            "a read-only, evidence-limited acquisition report."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of", type=_iso_date, default=date.today())
    parser.add_argument(
        "--synthetic-demo-profile",
        type=Path,
        help=(
            "Optional fictional example profile. Produces a separate synthetic "
            "preview; it is never used as the tenant's real profile."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    batch = load_manual_import(args.input)
    report = build_acquisition_report(
        batch,
        as_of=args.as_of,
        profile=None,
        profile_status="UNAVAILABLE",
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "acquisition-report.json"
    markdown_path = args.output_dir / "acquisition-report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_acquisition_markdown(report), encoding="utf-8")

    if args.synthetic_demo_profile is not None:
        profile_payload = json.loads(
            args.synthetic_demo_profile.read_text(encoding="utf-8")
        )
        profile = parse_business_profile_document(profile_payload)
        if not profile.is_fictional_example:
            raise ValueError("--synthetic-demo-profile must be explicitly fictional")
        preview = build_synthetic_profile_preview(profile, as_of=args.as_of)
        preview_json = args.output_dir / "synthetic-demo.json"
        preview_markdown = args.output_dir / "synthetic-demo.md"
        preview_json.write_text(
            json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        preview_markdown.write_text(
            _render_synthetic_markdown(preview), encoding="utf-8"
        )
        print(f"Synthetic demonstration: {preview_markdown}")

    print(f"Acquisition JSON: {json_path}")
    print(f"Acquisition Markdown: {markdown_path}")
    if batch.state is AcquisitionState.BLOCKED:
        return 2
    if batch.state is AcquisitionState.MALFORMED:
        return 3
    return 0


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def _render_synthetic_markdown(preview: dict[str, object]) -> str:
    lines = [
        "# Synthetic Qualification Preview",
        "",
        "**Synthetic only. This is not an observed procurement opportunity.**",
        "",
        f"- Profile: {_markdown_text(preview.get('business_profile', 'UNKNOWN'))}",
        f"- Vertical: {_markdown_text(preview.get('vertical', 'UNKNOWN'))}",
        f"- Preview classification: {preview.get('status', 'UNKNOWN')}",
        f"- Commercial fit score: {preview.get('commercial_fit_score', 'UNKNOWN')}",
        f"- Actionable: {preview.get('actionable', False)}",
        f"- Capacity review required: {preview.get('capacity_review_required', 'UNKNOWN')}",
        "",
        str(preview.get("note", "")),
        "",
    ]
    reasons = preview.get("classification_reasons")
    if isinstance(reasons, list) and reasons:
        lines.extend(["## Synthetic scoring reasons", ""])
        lines.extend(f"- {_markdown_text(reason)}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def _markdown_text(value: object) -> str:
    text = "UNKNOWN" if value is None else str(value)
    text = " ".join(text.split())
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~])", r"\\\1", text)


if __name__ == "__main__":
    sys.exit(main())
