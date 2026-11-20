"""Manual URL classification and bounded public-site diagnosis command."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import cast

from aeos.application.live.business_url_diagnosis import (
    BusinessURLPlatform,
    build_business_url_diagnosis_report,
    classify_business_url,
    render_business_url_diagnosis_markdown,
)
from aeos.application.live.inspect_business_website import inspect_business_website
from aeos.live.adapters.website_inspector import (
    WebsiteInspectionError,
    WebsiteInspector,
)
from aeos.live.domain.profile import BusinessProfile, parse_business_profile_document
from aeos.live.domain.url_policy import safe_url_for_report
from aeos.live.ports.website import WebsiteInspectionResult


def run_business_url_diagnosis_command(
    url: str,
    *,
    output_directory: Path,
    profile_path: Path | None = None,
) -> int:
    classified = classify_business_url(url)
    profile = _load_profile(profile_path) if profile_path is not None else None
    started_at = datetime.now(timezone.utc)
    inspection: WebsiteInspectionResult | None = None
    failure_category: str | None = None
    failure_stage: str | None = None
    inspection_status = "NOT_STARTED"

    if classified.platform is BusinessURLPlatform.WEBSITE:
        try:
            inspection = inspect_business_website(WebsiteInspector(), classified.url)
            inspection_status = "SUCCEEDED"
        except WebsiteInspectionError as error:
            inspection_status = "FAILED"
            failure_category = error.category
            failure_stage = error.stage

    report = build_business_url_diagnosis_report(
        classified.url,
        profile=profile,
        inspection=inspection,
        inspection_status=inspection_status,
        failure_category=failure_category,
        failure_stage=failure_stage,
        inspected_at=(
            inspection.details.inspected_at.isoformat()
            if inspection is not None and inspection.details is not None
            else started_at.isoformat()
            if classified.platform is BusinessURLPlatform.WEBSITE
            else None
        ),
    )
    if failure_category:
        diagnosis = cast(dict[str, object], report["url_diagnosis"])
        diagnosis["failure"] = {
            "category": failure_category,
            "stage": failure_stage,
        }

    output_directory.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    slug = _url_slug(classified.url)
    json_path = output_directory / f"{slug}-{stamp}.json"
    markdown_path = output_directory / f"{slug}-{stamp}.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(
        render_business_url_diagnosis_markdown(report), encoding="utf-8"
    )

    diagnosis = cast(dict[str, object], report["url_diagnosis"])
    print(f"Tipo de URL: {diagnosis['platform']}")
    print(f"Estado: {diagnosis['inspection_status']}")
    print(f"Hallazgos confirmados: {len(cast(list[object], diagnosis['findings']))}")
    print(
        "Verificaciones pendientes (INCONCLUSIVE): "
        f"{len(cast(list[object], diagnosis['pending_verifications']))}"
    )
    print(f"JSON: {json_path.resolve()}")
    print(f"Markdown: {markdown_path.resolve()}")
    print("Overpass: no iniciado; no se hizo investigación de mercado.")
    if classified.platform is not BusinessURLPlatform.WEBSITE:
        print("La plataforma requiere evidencia o acceso autorizado del propietario.")
    return 2 if inspection_status == "FAILED" else 0


def _load_profile(path: Path) -> BusinessProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile JSON must contain an object")
    return parse_business_profile_document(payload)


def _url_slug(url: str) -> str:
    host = (safe_url_for_report(url) or "business").split("//", 1)[-1]
    host = host.split("/", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", host.casefold()).strip("-")
    return slug[:48] or "business-url"


if __name__ == "__main__":
    raise SystemExit("Use python -m aeos.live.real_demo --diagnose-url URL")
