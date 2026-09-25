"""Immutable static workflow node descriptions."""

from dataclasses import dataclass
from enum import StrEnum

from aeos.core.ids import NodeDefinitionId
from aeos.workflows.domain.errors import InvalidNodeDefinition, InvalidNodeKind


class NodeKind(StrEnum):
    """Minimal architecture-neutral workflow node categories."""

    ACTION = "action"
    DECISION = "decision"
    END = "end"

    @classmethod
    def from_value(cls, value: str) -> "NodeKind":
        try:
            return cls(value.strip())
        except (AttributeError, ValueError) as exc:
            raise InvalidNodeKind() from exc


@dataclass(frozen=True, slots=True)
class NodeDefinition:
    """One immutable, non-executable node in a workflow definition."""

    node_definition_id: NodeDefinitionId
    name: str
    kind: NodeKind
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_definition_id, NodeDefinitionId):
            raise InvalidNodeDefinition("node_definition_id must be a NodeDefinitionId")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidNodeDefinition("node name must not be blank")
        object.__setattr__(self, "name", self.name.strip())
        if not isinstance(self.kind, NodeKind):
            raise InvalidNodeKind()
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidNodeDefinition("description must be a string or None")
