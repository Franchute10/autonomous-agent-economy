"""Declared, non-authorizing experiment resource exposure limits."""

from dataclasses import dataclass

from aeos.core import ResourceId, ResourceQuantity
from aeos.experiments.domain.errors import InvalidExperimentResourceExposure


@dataclass(frozen=True, slots=True)
class ExperimentResourceExposureLimit:
    """A strictly positive upper-bound declaration for one resource."""

    resource_id: ResourceId
    quantity: ResourceQuantity

    def __post_init__(self) -> None:
        if not isinstance(self.resource_id, ResourceId):
            raise InvalidExperimentResourceExposure("resource_id must be a ResourceId")
        if not isinstance(self.quantity, ResourceQuantity):
            raise InvalidExperimentResourceExposure(
                "quantity must be a ResourceQuantity"
            )
        if self.quantity.quantity <= 0:
            raise InvalidExperimentResourceExposure(
                "exposure quantity must be strictly positive"
            )
