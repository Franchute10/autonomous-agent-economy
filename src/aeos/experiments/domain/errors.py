"""Structural errors for the Experiments domain."""

from aeos.core.errors import DomainError


class InvalidExperimentPreregistration(DomainError):
    def __init__(self, message: str = "invalid experiment preregistration") -> None:
        super().__init__("invalid_experiment_preregistration", message)


class InvalidExperimentCriterion(DomainError):
    def __init__(self, message: str = "invalid experiment criterion") -> None:
        super().__init__("invalid_experiment_criterion", message)


class InvalidExperimentResourceExposure(DomainError):
    def __init__(self, message: str = "invalid experiment resource exposure") -> None:
        super().__init__("invalid_experiment_resource_exposure", message)


class DuplicateExperimentResource(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_experiment_resource",
            "an experiment cannot declare duplicate exposure limits for a resource",
        )


class InvalidExperimentState(DomainError):
    def __init__(self, message: str = "invalid experiment state") -> None:
        super().__init__("invalid_experiment_state", message)


class InvalidExperimentTransition(DomainError):
    def __init__(self, message: str = "experiment transition is not allowed") -> None:
        super().__init__("invalid_experiment_transition", message)


class InvalidExperimentTimestamp(DomainError):
    def __init__(self, message: str = "invalid experiment timestamp") -> None:
        super().__init__("invalid_experiment_timestamp", message)
