"""Extensible, data-driven profiles for business verticals."""

from dataclasses import dataclass
from enum import StrEnum
import re

from aeos.live.domain.errors import InvalidLiveContract


class Vertical(StrEnum):
    HOUSE_CLEANING = "HOUSE_CLEANING"  # Legacy profile key.
    CLEANING_SERVICES = "CLEANING_SERVICES"
    HVAC = "HVAC"
    CONSTRUCTION = "CONSTRUCTION"
    ROOFING = "ROOFING"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class VerticalProfile:
    vertical: Vertical | str
    canonical_industry_name: str
    common_customer_categories: tuple[str, ...]
    partner_categories: tuple[str, ...]
    supplier_categories: tuple[str, ...]
    relevant_business_signals: tuple[str, ...]
    common_conversion_points: tuple[str, ...]
    service_categories: tuple[str, ...] = ()
    service_aliases: tuple[tuple[str, str], ...] = ()
    aliases: tuple[str, ...] = ()
    direct_competitor_services: tuple[str, ...] = ()
    adjacent_competitor_services: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.vertical, (Vertical, str))
            or not str(self.vertical).strip()
        ):
            raise InvalidLiveContract("vertical must be a non-blank key")
        if (
            not isinstance(self.canonical_industry_name, str)
            or not self.canonical_industry_name.strip()
        ):
            raise InvalidLiveContract("canonical_industry_name must be non-blank")
        for field in (
            "common_customer_categories",
            "partner_categories",
            "supplier_categories",
            "relevant_business_signals",
            "common_conversion_points",
            "service_categories",
            "aliases",
            "direct_competitor_services",
            "adjacent_competitor_services",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must be a tuple of non-blank strings"
                )
        if not isinstance(self.service_aliases, tuple) or any(
            not isinstance(pair, tuple)
            or len(pair) != 2
            or any(not isinstance(item, str) or not item.strip() for item in pair)
            for pair in self.service_aliases
        ):
            raise InvalidLiveContract(
                "service_aliases must contain alias/canonical string pairs"
            )
        known_services = {
            normalize_taxonomy_label(item) for item in self.service_categories
        }
        for _, canonical in self.service_aliases:
            if normalize_taxonomy_label(canonical) not in known_services:
                raise InvalidLiveContract(
                    "service aliases must target a declared service category"
                )


def normalize_taxonomy_label(value: str) -> str:
    """Normalize a service or segment label without applying industry assumptions."""

    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


VERTICAL_PROFILES: tuple[VerticalProfile, ...] = (
    VerticalProfile(
        vertical=Vertical.CLEANING_SERVICES,
        canonical_industry_name="Cleaning Services",
        aliases=("cleaning", "house cleaning", "household services"),
        common_customer_categories=(
            "residential customers",
            "property managers",
            "offices",
            "vacation rental managers",
        ),
        partner_categories=(
            "property managers",
            "real estate agencies",
            "moving companies",
            "vacation rental managers",
        ),
        supplier_categories=(
            "janitorial supply",
            "cleaning supply distributors",
            "cleaning supplies",
        ),
        relevant_business_signals=(
            "service area",
            "recurring service options",
            "booking and quote availability",
            "customer reviews",
        ),
        common_conversion_points=("quote request", "phone call", "online booking"),
        service_categories=(
            "residential cleaning",
            "vacation rental turnover cleaning",
            "deep cleaning",
            "recurring cleaning",
            "commercial cleaning",
            "office cleaning",
        ),
        direct_competitor_services=(
            "residential cleaning",
            "vacation rental turnover cleaning",
            "deep cleaning",
            "recurring cleaning",
        ),
        adjacent_competitor_services=("commercial cleaning", "office cleaning"),
        service_aliases=(
            ("house cleaning", "residential cleaning"),
            ("house cleaner", "residential cleaning"),
            ("home cleaning", "residential cleaning"),
            ("residential house cleaning", "residential cleaning"),
            ("airbnb turnover", "vacation rental turnover cleaning"),
            ("vacation turnover cleaning", "vacation rental turnover cleaning"),
            ("turnover cleaning", "vacation rental turnover cleaning"),
            ("deep clean", "deep cleaning"),
            ("commercial janitorial cleaning", "commercial cleaning"),
            ("janitorial cleaning", "commercial cleaning"),
            ("office janitorial", "office cleaning"),
        ),
    ),
    VerticalProfile(
        vertical=Vertical.HVAC,
        canonical_industry_name="HVAC",
        aliases=("heating ventilation and air conditioning", "heating and cooling"),
        common_customer_categories=(
            "homeowners",
            "property managers",
            "facility managers",
        ),
        partner_categories=(
            "property managers",
            "general contractors",
            "facility management",
        ),
        supplier_categories=("HVAC suppliers", "equipment distributors"),
        relevant_business_signals=(
            "service area",
            "emergency service",
            "licenses",
            "reviews",
        ),
        common_conversion_points=(
            "service call",
            "estimate request",
            "maintenance plan",
        ),
        service_categories=(
            "air conditioning installation",
            "air conditioning repair",
            "preventive HVAC maintenance",
            "commercial HVAC contracts",
            "emergency HVAC service",
        ),
        service_aliases=(
            ("AC installation", "air conditioning installation"),
            ("air conditioner installation", "air conditioning installation"),
            ("AC repair", "air conditioning repair"),
            ("air conditioner repair", "air conditioning repair"),
            ("HVAC repair", "air conditioning repair"),
            ("preventive maintenance", "preventive HVAC maintenance"),
            ("commercial maintenance contract", "commercial HVAC contracts"),
            ("HVAC emergency", "emergency HVAC service"),
        ),
    ),
    VerticalProfile(
        vertical=Vertical.CONSTRUCTION,
        canonical_industry_name="Construction",
        aliases=(
            "general construction",
            "general contracting",
            "building construction",
        ),
        common_customer_categories=(
            "homeowners",
            "property owners",
            "developers",
            "businesses",
        ),
        partner_categories=(
            "architects",
            "developers",
            "property managers",
            "general contractors",
        ),
        supplier_categories=(
            "building material distributors",
            "construction suppliers",
            "equipment rental",
        ),
        relevant_business_signals=(
            "project type",
            "project location",
            "licenses",
            "insurance",
            "bid schedule",
        ),
        common_conversion_points=(
            "estimate request",
            "bid invitation",
            "prequalification",
        ),
        service_categories=(
            "general contracting",
            "remodeling",
            "commercial construction",
            "residential construction",
            "specialty subcontracting",
        ),
        service_aliases=(
            ("general contractor", "general contracting"),
            ("home remodeling", "remodeling"),
            ("commercial building construction", "commercial construction"),
            ("residential building construction", "residential construction"),
            ("specialized subcontracting", "specialty subcontracting"),
        ),
    ),
    VerticalProfile(
        vertical=Vertical.ROOFING,
        canonical_industry_name="Roofing",
        common_customer_categories=("property managers", "real estate agencies"),
        partner_categories=(
            "property managers",
            "real estate agencies",
            "general contractors",
            "restoration companies",
        ),
        supplier_categories=("roofing suppliers", "building material distributors"),
        relevant_business_signals=("service area", "roof types", "licenses", "reviews"),
        common_conversion_points=(
            "inspection request",
            "estimate request",
            "phone call",
        ),
        service_categories=(
            "roof installation",
            "roof repair",
            "roof replacement",
            "roof inspection",
        ),
    ),
    VerticalProfile(
        vertical=Vertical.OTHER,
        canonical_industry_name="Other industry",
        aliases=("other", "custom", "custom industry"),
        common_customer_categories=(),
        partner_categories=(),
        supplier_categories=(),
        relevant_business_signals=(),
        common_conversion_points=(),
    ),
)


def vertical_profile_for(industry: str | Vertical) -> VerticalProfile | None:
    """Find a built-in vertical by key, canonical name, or alias."""

    if not isinstance(industry, (str, Vertical)) or not str(industry).strip():
        return None
    normalized = normalize_taxonomy_label(
        str(industry).replace("_", " ").replace("-", " ")
    )
    for profile in VERTICAL_PROFILES:
        keys = (
            str(profile.vertical),
            str(profile.vertical).replace("_", " "),
            profile.canonical_industry_name,
            *profile.aliases,
        )
        if normalized in {normalize_taxonomy_label(key) for key in keys}:
            return profile
    if normalized == normalize_taxonomy_label(
        Vertical.HOUSE_CLEANING.value.replace("_", " ")
    ):
        return VERTICAL_PROFILES[0]
    return None


def canonical_service_for_vertical(vertical: str | Vertical, service: str) -> str:
    """Canonicalize a service using only its declared vertical's taxonomy."""

    normalized = normalize_taxonomy_label(service)
    profile = vertical_profile_for(vertical)
    if profile is None:
        return normalized
    for alias, canonical in profile.service_aliases:
        if normalized == normalize_taxonomy_label(alias):
            return normalize_taxonomy_label(canonical)
    for category in profile.service_categories:
        if normalized == normalize_taxonomy_label(category):
            return normalize_taxonomy_label(category)
    return normalized


def verticals_match(left: str | Vertical, right: str | Vertical) -> bool:
    """Compare built-in aliases while allowing custom vertical keys."""

    left_profile = vertical_profile_for(left)
    right_profile = vertical_profile_for(right)
    if left_profile and right_profile:
        return normalize_taxonomy_label(
            str(left_profile.vertical)
        ) == normalize_taxonomy_label(str(right_profile.vertical))
    return normalize_taxonomy_label(str(left)) == normalize_taxonomy_label(str(right))
