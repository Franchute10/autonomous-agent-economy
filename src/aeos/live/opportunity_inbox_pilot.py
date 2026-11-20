"""Offline single-tenant inbox CLI; production callers must use tenant services."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from typing import Sequence, cast

from aeos.application.live.opportunity_inbox import (
    import_record,
    record_manual_contact,
    record_open_verification,
    record_quote,
    record_response,
    resolve_possible_duplicate_pair,
    render_follow_up_report,
    render_opportunity_report_markdown,
    update_status,
)
from aeos.application.live.manual_request_capture import capture_manual_request
from aeos.live.adapters.opportunity_inbox import LocalOpportunityInbox
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.opportunity_inbox import OpportunityStatus


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORE = ROOT / "artifacts/live/fictional-cleaning-002d/opportunities.json"
DEFAULT_REPORT = ROOT / "artifacts/live/fictional-cleaning-002d/opportunity-inbox-es.md"
DEFAULT_CAPTURE_DIRECTORY = ROOT / "artifacts/live/manual-request-captures"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import, qualify, and track actual cleaning demand. All contact and "
            "quote actions remain manual and require owner approval."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser(
        "capture-request",
        help="Save a manually pasted public request with source evidence; no fetch.",
    )
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--output", type=Path)
    capture.add_argument("--output-dir", type=Path, default=DEFAULT_CAPTURE_DIRECTORY)

    add = commands.add_parser(
        "import", help="Import one authorized manual opportunity."
    )
    add.add_argument("--input", type=Path, required=True)
    add.add_argument("--store", type=Path, default=DEFAULT_STORE)

    for name, help_text in (
        ("report", "Generate the Spanish Opportunity Inbox report."),
        ("review", "Review classification, score, and source evidence."),
        ("follow-ups", "Generate a Spanish manual follow-up report."),
    ):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--store", type=Path, default=DEFAULT_STORE)
        sub.add_argument("--as-of", type=_iso_date, default=date.today())
        if name == "report":
            sub.add_argument("--output", type=Path, default=DEFAULT_REPORT)
        elif name == "review":
            sub.add_argument("--opportunity-id", required=True)
        else:
            sub.add_argument(
                "--output",
                type=Path,
                default=ROOT
                / "artifacts/live/fictional-cleaning-002d/follow-ups-es.md",
            )

    status = commands.add_parser(
        "status", help="Record a manual pipeline state update."
    )
    _add_record_args(status)
    status.add_argument(
        "--status",
        required=True,
        choices=[
            OpportunityStatus.NEEDS_REVIEW.value,
            OpportunityStatus.EXPIRED.value,
            OpportunityStatus.DISQUALIFIED.value,
        ],
    )
    status.add_argument("--actor", required=True)
    status.add_argument("--note", required=True)

    approve = commands.add_parser(
        "approve-contact", help="Record owner approval for one contact."
    )
    _add_record_args(approve)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--note", required=True)

    verify_open = commands.add_parser(
        "verify-open", help="Record a manual recheck that the source is still open."
    )
    _add_record_args(verify_open)
    verify_open.add_argument("--actor", required=True)
    verify_open.add_argument("--note", required=True)

    contact = commands.add_parser(
        "record-contact", help="Record a contact already made manually."
    )
    _add_record_args(contact)
    contact.add_argument("--actor", required=True)
    contact.add_argument("--channel", required=True)
    contact.add_argument("--note", required=True)
    contact.add_argument("--next-action", required=True)
    contact.add_argument("--follow-up-date", type=_iso_date)

    approve_quote_parser = commands.add_parser(
        "approve-quote", help="Record owner approval for one quote action."
    )
    _add_record_args(approve_quote_parser)
    approve_quote_parser.add_argument("--approved-by", required=True)
    approve_quote_parser.add_argument("--note", required=True)

    quote = commands.add_parser(
        "record-quote", help="Record a quote already sent manually."
    )
    _add_record_args(quote)
    quote.add_argument("--actor", required=True)
    quote.add_argument("--channel", required=True)
    quote.add_argument("--note", required=True)
    quote.add_argument("--next-action", required=True)
    quote.add_argument("--follow-up-date", type=_iso_date)

    response = commands.add_parser(
        "record-response", help="Record a response received by a person."
    )
    _add_record_args(response)
    response.add_argument(
        "--status",
        required=True,
        choices=[
            OpportunityStatus.REPLIED.value,
            OpportunityStatus.QUOTE_REQUESTED.value,
            OpportunityStatus.WON.value,
            OpportunityStatus.LOST.value,
        ],
    )
    response.add_argument("--actor", required=True)
    response.add_argument("--note", required=True)
    response.add_argument("--next-action", required=True)
    response.add_argument("--follow-up-date", type=_iso_date)

    resolve = commands.add_parser(
        "resolve-duplicate", help="Resolve one possible-duplicate pair manually."
    )
    _add_record_args(resolve)
    resolve.add_argument("--related-opportunity-id", required=True)
    resolve.add_argument(
        "--resolution", required=True, choices=["DISTINCT", "SAME_REQUEST"]
    )
    resolve.add_argument("--canonical-opportunity-id")
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--note", required=True)

    commands.add_parser(
        "audit-history", help="List saved records with lifecycle audit issues."
    ).add_argument("--store", type=Path, default=DEFAULT_STORE)
    return parser


def _add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--opportunity-id", required=True)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command in {"approve-contact", "approve-quote"}:
        print(
            "Approval commands are disabled here until an authenticated tenant context is wired; --approved-by is not identity proof.",
            file=sys.stderr,
        )
        return 2
    try:
        if args.command == "capture-request":
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise InvalidLiveContract("input must contain one JSON object")
            capture = capture_manual_request(payload)
            output_path = args.output or (
                args.output_dir / f"{capture['capture_id']}.json"
            )
            _write_output(
                output_path,
                json.dumps(capture, ensure_ascii=False, indent=2) + "\n",
            )
            print(f"Captura manual guardada: {capture['capture_id']}")
            print(f"Acceso: {capture['access_status']}")
            intent_assessment = cast(
                dict[str, object], capture["intent_assessment"]
            )
            print(
                "Intención explícita en el texto: "
                f"{intent_assessment['explicit_intent']}"
            )
            print("Comprador confirmado: no; no se contactó al autor.")
            print(f"Archivo: {output_path.resolve()}")
            return 0
        inbox = LocalOpportunityInbox(args.store)
        if args.command == "import":
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise InvalidLiveContract("input must contain one JSON object")
            imported_record = import_record(payload)
            saved, inserted = inbox.add(imported_record)
            if inserted:
                print(
                    f"Importada: {saved.opportunity.opportunity_id}; estado DISCOVERED."
                )
            else:
                print(
                    f"Duplicado ignorado: ya existe {saved.opportunity.opportunity_id}."
                )
            print("No se envió ningún contacto ni cotización.")
            return 0
        records = inbox.list_records()
        if args.command == "audit-history":
            issues = inbox.audit_history()
            print(json.dumps(issues, ensure_ascii=False, indent=2))
            return 1 if issues else 0
        if args.command == "report":
            markdown = render_opportunity_report_markdown(records, as_of=args.as_of)
            _write_output(args.output, markdown)
            print(f"Reporte en español: {args.output.resolve()}")
            return 0
        if args.command == "follow-ups":
            _write_output(
                args.output,
                render_follow_up_report(records, as_of=args.as_of),
            )
            print(f"Seguimientos en español: {args.output.resolve()}")
            return 0
        record = inbox.get(args.opportunity_id)
        if record is None:
            raise InvalidLiveContract("opportunity ID was not found")
        now = datetime.now(timezone.utc)
        if args.command == "resolve-duplicate":
            related = inbox.get(args.related_opportunity_id)
            if related is None:
                raise InvalidLiveContract("related opportunity ID was not found")
            resolved_pair = resolve_possible_duplicate_pair(
                record,
                related,
                is_same_request=args.resolution == "SAME_REQUEST",
                canonical_opportunity_id=args.canonical_opportunity_id,
                actor=args.actor,
                note=args.note,
                occurred_at=now,
            )
            inbox.put_many(resolved_pair)
            print(
                f"Relación revisada: {args.opportunity_id}, "
                f"{args.related_opportunity_id}; {args.resolution}."
            )
            return 0
        if args.command == "review":
            print(
                render_opportunity_report_markdown((record,), as_of=args.as_of),
                end="",
            )
            return 0
        if args.command == "status":
            updated = update_status(
                record,
                OpportunityStatus(args.status),
                actor=args.actor,
                note=args.note,
                occurred_at=now,
            )
        elif args.command == "approve-contact":
            raise InvalidLiveContract("authenticated tenant approval is required")
        elif args.command == "verify-open":
            updated = record_open_verification(
                record,
                actor=args.actor,
                note=args.note,
                occurred_at=now,
            )
        elif args.command == "record-contact":
            updated = record_manual_contact(
                record,
                actor=args.actor,
                channel=args.channel,
                note=args.note,
                next_action=args.next_action,
                follow_up_date=args.follow_up_date,
                occurred_at=now,
            )
        elif args.command == "approve-quote":
            raise InvalidLiveContract("authenticated tenant approval is required")
        elif args.command == "record-quote":
            updated = record_quote(
                record,
                actor=args.actor,
                channel=args.channel,
                note=args.note,
                next_action=args.next_action,
                follow_up_date=args.follow_up_date,
                occurred_at=now,
            )
        else:
            updated = record_response(
                record,
                status=OpportunityStatus(args.status),
                actor=args.actor,
                note=args.note,
                next_action=args.next_action,
                follow_up_date=args.follow_up_date,
                occurred_at=now,
            )
        inbox.put(updated)
        print(f"{updated.opportunity.opportunity_id}: {updated.status.value}")
        print("AEOS registró el estado; no envió mensajes, ofertas ni cotizaciones.")
        return 0
    except (OSError, ValueError, InvalidLiveContract, json.JSONDecodeError) as error:
        print(f"opportunity inbox error: {error}", file=sys.stderr)
        return 2


def _write_output(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


if __name__ == "__main__":
    raise SystemExit(main())
