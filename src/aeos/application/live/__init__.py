"""LIVE application use cases."""

from aeos.application.live.assess_business import (
    assess_business,
    rank_opportunities,
    render_assessment_summary,
)
from aeos.application.live.profile_assessment import assess_business_profile
from aeos.application.live.market_intelligence import (
    build_market_report,
    prioritize_opportunities,
    render_combined_market_report_markdown,
    render_market_report_markdown,
)
from aeos.application.live.business_report import (
    build_business_report,
    render_business_report_markdown,
)
from aeos.application.live.opportunity_activation import (
    attach_research_evidence,
    assess_capacity,
    assess_prospect,
    build_activation_report,
    generate_outreach_materials,
    render_activation_report_markdown,
    render_outreach_markdown,
    render_prospect_brief_markdown,
)

__all__ = [
    "assess_business",
    "assess_business_profile",
    "attach_research_evidence",
    "assess_capacity",
    "assess_prospect",
    "build_activation_report",
    "build_business_report",
    "build_market_report",
    "prioritize_opportunities",
    "generate_outreach_materials",
    "rank_opportunities",
    "render_assessment_summary",
    "render_business_report_markdown",
    "render_activation_report_markdown",
    "render_outreach_markdown",
    "render_prospect_brief_markdown",
    "render_combined_market_report_markdown",
    "render_market_report_markdown",
]
