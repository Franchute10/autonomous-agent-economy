"""Declarative experiment criterion value object."""

from dataclasses import dataclass

from aeos.experiments.domain.errors import InvalidExperimentCriterion


@dataclass(frozen=True, slots=True)
class ExperimentCriterion:
    """One immutable textual criterion; it has no evaluation behavior."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise InvalidExperimentCriterion("criterion text must be a string")
        text = self.text.strip()
        if not text:
            raise InvalidExperimentCriterion("criterion text must not be blank")
        object.__setattr__(self, "text", text)
