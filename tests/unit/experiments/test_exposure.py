from datetime import datetime, timezone
from typing import Any, cast

import pytest

from aeos.core import ExperimentId, OrganizationId, ResourceId, ResourceQuantity
from aeos.experiments import (
    DuplicateExperimentResource,
    ExperimentCriterion,
    ExperimentPreregistration,
    ExperimentResourceExposureLimit,
    InvalidExperimentPreregistration,
    InvalidExperimentResourceExposure,
)


def make_preregistration(
    maximum_resource_exposure: object,
) -> ExperimentPreregistration:
    return ExperimentPreregistration(
        ExperimentId("exp-1"),
        OrganizationId("org-1"),
        "hypothesis",
        "objective",
        (ExperimentCriterion("success"),),
        (ExperimentCriterion("kill"),),
        cast(Any, maximum_resource_exposure),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_exposure_limit_reuses_typed_resource_contracts() -> None:
    quantity = ResourceQuantity("100", "input_tokens")
    value = ExperimentResourceExposureLimit(ResourceId("tokens"), quantity)
    assert value.resource_id == ResourceId("tokens")
    assert value.quantity is quantity


@pytest.mark.parametrize(
    "quantity", [ResourceQuantity("0", "unit"), ResourceQuantity("-1", "unit")]
)
def test_exposure_limit_must_be_strictly_positive(quantity: ResourceQuantity) -> None:
    with pytest.raises(InvalidExperimentResourceExposure):
        ExperimentResourceExposureLimit(ResourceId("r"), quantity)


def test_exposure_limit_rejects_wrong_types() -> None:
    with pytest.raises(InvalidExperimentResourceExposure):
        ExperimentResourceExposureLimit(cast(Any, object()), ResourceQuantity("1", "u"))
    with pytest.raises(InvalidExperimentResourceExposure):
        ExperimentResourceExposureLimit(ResourceId("r"), cast(Any, object()))


def test_exposure_collection_is_non_empty_tuple_and_rejects_duplicates() -> None:
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(maximum_resource_exposure=())
    with pytest.raises(InvalidExperimentPreregistration):
        make_preregistration(
            maximum_resource_exposure=[
                ExperimentResourceExposureLimit(
                    ResourceId("r"), ResourceQuantity("1", "u")
                )
            ]
        )
    same = ExperimentResourceExposureLimit(ResourceId("r"), ResourceQuantity("1", "u"))
    with pytest.raises(DuplicateExperimentResource):
        make_preregistration(maximum_resource_exposure=(same, same))


def test_different_resources_remain_independent_and_unconverted() -> None:
    first = ExperimentResourceExposureLimit(
        ResourceId("money"), ResourceQuantity("5", "USD")
    )
    second = ExperimentResourceExposureLimit(
        ResourceId("tokens"), ResourceQuantity("100", "input_tokens")
    )
    value = make_preregistration(maximum_resource_exposure=(first, second))
    assert value.maximum_resource_exposure == (first, second)
