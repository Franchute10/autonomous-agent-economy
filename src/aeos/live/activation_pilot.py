"""Single-tenant Sample Cleaning Company pilot; not a production tenant interface."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Sequence

from aeos.application.live.opportunity_activation import (
    assess_prospect,
    build_activation_report,
    due_followups,
    generate_outreach_materials,
    operational_capacity_from_profile,
    render_activation_report_markdown,
    render_outreach_markdown,
    render_prospect_brief_markdown,
)

from aeos.live.adapters.market_research import load_manual_market_research
from aeos.live.adapters.opportunity_pipeline import LocalOpportunityPipeline
from aeos.live.adapters.prospect_research import (
    build_activation_prospects,
    load_prospect_research,
)
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.opportunity_activation import (
    PipelineRecord,
    PipelineStatus,
    ProspectAssessment,
    ProspectClassification,
)
from aeos.live.domain.profile import parse_business_profile_document


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE = (
    ROOT / "examples/live/business_profiles/fictional_cleaning_company.json"
)
DEFAULT_MARKET_RESEARCH = (
    ROOT / "examples/live/market_research/fictional_cleaning_markets.json"
)
DEFAULT_PROSPECT_SOURCES = (
    ROOT / "examples/live/opportunity_activation/fictional_cleaning_prospects.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts/live/fictional-cleaning-002b2/activation"
DEFAULT_PIPELINE = DEFAULT_OUTPUT / "pipeline.json"
PROSPECT_IDS = (
    "buyer-sample-1",
    "buyer-sample-2",
    "buyer-sample-3",
    "buyer-sample-4",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evidence-backed Sample Cleaning Company prospect qualification, draft generation, "
            "and manually approved pipeline tracking. No outreach is sent."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("report", "Generate combined and individual Spanish activation reports."),
        ("research", "Write one evidence-backed prospect brief."),
        ("outreach", "Generate dual-language drafts for a qualified prospect."),
        ("status", "Manually update a prospect's pipeline status."),
        ("approve-contact", "Record owner approval before a manual contact."),
        ("record-contact", "Record a contact already made by a human."),
        ("record-quote", "Record a quote sent manually outside AEOS."),
        ("record-response", "Record a received response, meeting, or quote request."),
        ("follow-ups", "List manual follow-ups due on or before a date."),
    ):
        sub = commands.add_parser(name, help=help_text)
        _add_common_paths(sub)
        if name in {
            "research",
            "outreach",
            "status",
            "approve-contact",
            "record-contact",
            "record-quote",
            "record-response",
        }:
            sub.add_argument("--prospect-id", required=True, choices=PROSPECT_IDS)
        if name in {"report", "research", "outreach"}:
            sub.add_argument("--as-of", type=_iso_date, default=date.today())
            sub.add_argument("--stale-after-days", type=int, default=90)
        if name == "status":
            sub.add_argument(
                "--status",
                required=True,
                choices=[item.value for item in PipelineStatus],
            )
            sub.add_argument("--actor", required=True)
            sub.add_argument("--note", required=True)
        elif name == "approve-contact":
            sub.add_argument("--approved-by", required=True)
            sub.add_argument("--note", required=True)
        elif name == "record-contact":
            sub.add_argument("--actor", required=True)
            sub.add_argument("--channel", required=True)
            sub.add_argument("--details", required=True)
            sub.add_argument("--next-action", required=True)
            sub.add_argument("--follow-up-date", type=_iso_date)
        elif name == "record-response":
            response_statuses = (
                PipelineStatus.REPLIED,
                PipelineStatus.MEETING_SCHEDULED,
                PipelineStatus.QUOTE_REQUESTED,
                PipelineStatus.LOST,
                PipelineStatus.DISQUALIFIED,
            )
            sub.add_argument(
                "--status",
                required=True,
                choices=[item.value for item in response_statuses],
            )
            sub.add_argument("--actor", required=True)
            sub.add_argument("--outcome", required=True)
            sub.add_argument("--next-action", required=True)
            sub.add_argument("--follow-up-date", type=_iso_date)
        elif name == "record-quote":
            sub.add_argument("--actor", required=True)
            sub.add_argument("--channel", required=True)
            sub.add_argument("--details", required=True)
            sub.add_argument("--next-action", required=True)
            sub.add_argument("--follow-up-date", type=_iso_date)
        elif name == "follow-ups":
            sub.add_argument("--on", type=_iso_date, default=date.today())
    return parser


def _add_common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--market-research", type=Path, default=DEFAULT_MARKET_RESEARCH)
    parser.add_argument(
        "--prospect-sources", type=Path, default=DEFAULT_PROSPECT_SOURCES
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pipeline", type=Path, default=DEFAULT_PIPELINE)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "approve-contact":
        print(
            "Contact approval is disabled until an authenticated tenant "
            "context is wired; --approved-by is not identity proof.",
            file=sys.stderr,
        )
        return 2

    if args.command in {
        "status",
        "record-contact",
        "record-quote",
        "record-response",
    }:
        try:
            record = _load_pipeline_record(args.pipeline, args.prospect_id)
        except (InvalidLiveContract, OSError) as error:
            print(f"Pipeline operation blocked: {error}", file=sys.stderr)
            return 2
        print(
            f"Pipeline event for {record.prospect_id} is blocked: this single-tenant "
            "CLI has no authenticated tenant-owner context. No event was recorded.",
            file=sys.stderr,
        )
        return 2

    if args.command == "follow-ups":
        try:
            pipeline = LocalOpportunityPipeline(args.pipeline)
            return _print_followups(pipeline, args.on)
        except (InvalidLiveContract, OSError) as error:
            print(f"Could not read follow-up pipeline: {error}", file=sys.stderr)
            return 2

    try:
        profile_document = json.loads(args.profile.read_text(encoding="utf-8"))
        profile = parse_business_profile_document(profile_document)
        _, markets = load_manual_market_research(args.market_research)
        prospect_sources = load_prospect_research(args.prospect_sources)
        prospects = build_activation_prospects(markets, prospect_sources)
        capacity = operational_capacity_from_profile(profile)
        assessments = tuple(
            assess_prospect(
                prospect,
                profile,
                capacity,
                as_of=args.as_of,
                stale_after_days=args.stale_after_days,
            )
            for prospect in prospects
        )
    except (OSError, json.JSONDecodeError, InvalidLiveContract, ValueError) as error:
        print(f"Could not load activation preview: {error}", file=sys.stderr)
        return 2

    output_dir: Path = args.output_dir
    if args.command == "report":
        report = build_activation_report(
            profile,
            assessments,
            snapshot_at=args.as_of,
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "activation-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (output_dir / "activation-report.md").write_text(
                render_activation_report_markdown(report),
                encoding="utf-8",
            )
        except OSError as error:
            print(f"Could not write activation preview: {error}", file=sys.stderr)
            return 2
        print(f"Activation preview written to {output_dir}.")
        return 0

    if args.command == "research":
        assessment = _assessment_by_id(assessments, args.prospect_id)
        rank = _rank_of(assessments, args.prospect_id)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"prospect-{args.prospect_id}.md").write_text(
                render_prospect_brief_markdown(assessment, rank=rank),
                encoding="utf-8",
            )
        except OSError as error:
            print(f"Could not write prospect preview: {error}", file=sys.stderr)
            return 2
        return 0

    if args.command == "outreach":
        assessment = _assessment_by_id(assessments, args.prospect_id)
        if (
            assessment.fit_classification
            is not ProspectClassification.QUALIFIED_PROSPECT
        ):
            print(
                "Outreach preview is unavailable for an unqualified prospect.",
                file=sys.stderr,
            )
            return 2
        materials = generate_outreach_materials(assessment, profile)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"outreach-{args.prospect_id}.md").write_text(
                render_outreach_markdown(assessment.prospect.organization, materials),
                encoding="utf-8",
            )
        except OSError as error:
            print(f"Could not write outreach preview: {error}", file=sys.stderr)
            return 2
        return 0

    print(f"Unsupported command: {args.command}", file=sys.stderr)
    return 2


def _load_pipeline_record(path: Path, prospect_id: str) -> PipelineRecord:
    record = LocalOpportunityPipeline(path).get(prospect_id)
    if record is None:
        raise InvalidLiveContract(f"pipeline has no record for {prospect_id}")
    return record


def _print_followups(pipeline: LocalOpportunityPipeline, as_of: date) -> int:
    due = due_followups(pipeline.list_records(), as_of=as_of)
    if not due:
        print(f"No follow-ups due on or before {as_of.isoformat()}.")
        return 0
    for item in due:
        print(
            f"{item.follow_up_date} | {item.organization} | {item.market} | "
            f"{item.status.value} | {item.next_action or 'next action not set'}"
        )
    return 0


def _assessment_by_id(
    assessments: tuple[ProspectAssessment, ...], prospect_id: str
) -> ProspectAssessment:
    for item in assessments:
        if item.prospect.prospect_id == prospect_id:
            return item
    raise ValueError(f"unknown prospect: {prospect_id}")


def _rank_assessments(
    assessments: tuple[ProspectAssessment, ...],
) -> tuple[ProspectAssessment, ...]:
    return tuple(
        sorted(
            assessments,
            key=lambda item: (
                0
                if item.fit_classification is ProspectClassification.QUALIFIED_PROSPECT
                else 1,
                0 if item.prospect.market.casefold() == "sample-city-one" else 1,
                -item.fit_score,
            ),
        )
    )


def _rank_of(assessments: tuple[ProspectAssessment, ...], prospect_id: str) -> int:
    for index, item in enumerate(_rank_assessments(assessments), start=1):
        if item.prospect.prospect_id == prospect_id:
            return index
    raise ValueError(f"unknown prospect: {prospect_id}")


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


if __name__ == "__main__":
    raise SystemExit(main())
