"""Declarative search profiles for the first local-service verticals."""

from dataclasses import dataclass
from enum import StrEnum

from aeos.live.domain.errors import InvalidLiveContract


class Vertical(StrEnum):
    HVAC = "HVAC"
    ROOFING = "ROOFING"
    HOUSE_CLEANING = "HOUSE_CLEANING"


@dataclass(frozen=True, slots=True)
class VerticalProfile:
    vertical: Vertical
    canonical_industry_name: str
    common_customer_categories: tuple[str, ...]
    partner_categories: tuple[str, ...]
    supplier_categories: tuple[str, ...]
    relevant_business_signals: tuple[str, ...]
    common_conversion_points: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.vertical, Vertical):
            raise InvalidLiveContract("vertical must be a Vertical")
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
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must be a tuple of non-blank strings"
                )


VERTICAL_PROFILES: tuple[VerticalProfile, ...] = (
    VerticalProfile(
        vertical=Vertical.HOUSE_CLEANING,
        canonical_industry_name="House Cleaning",
        common_customer_categories=(
            "property managers",
            "real estate agencies",
            "moving companies",
            "apartment communities",
            "vacation rental managers",
        ),
        partner_categories=(
            "property managers",
            "real estate agencies",
            "moving companies",
            "apartment communities",
            "vacation rental managers",
        ),
        supplier_categories=("janitorial supply", "cleaning supply distributors"),
        relevant_business_signals=(
            "service area",
            "recurring service options",
            "booking and quote availability",
            "customer reviews",
        ),
        common_conversion_points=("quote request", "phone call", "online booking"),
    ),
    VerticalProfile(
        vertical=Vertical.HVAC,
        canonical_industry_name="HVAC",
        common_customer_categories=("property managers", "facility managers"),
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
    ),
)


def vertical_profile_for(industry: str) -> VerticalProfile | None:
    """Find a declared profile by its key or canonical industry name."""

    if not isinstance(industry, str) or not industry.strip():
        return None
    normalized = industry.strip().replace("-", " ").replace("_", " ").casefold()
    for profile in VERTICAL_PROFILES:
        aliases = {
            profile.vertical.value.replace("_", " ").casefold(),
            profile.canonical_industry_name.casefold(),
        }
        if normalized in aliases:
            return profile
    return None
