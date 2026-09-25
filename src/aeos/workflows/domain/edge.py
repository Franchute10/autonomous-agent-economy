"""Immutable directed structural workflow edges."""

from dataclasses import dataclass

from aeos.core.ids import EdgeDefinitionId, NodeDefinitionId
from aeos.workflows.domain.errors import InvalidWorkflowDefinition, SelfEdgeNotAllowed


@dataclass(frozen=True, slots=True)
class EdgeDefinition:
    """An unconditional source-to-target relationship."""

    edge_definition_id: EdgeDefinitionId
    source_node_id: NodeDefinitionId
    target_node_id: NodeDefinitionId

    def __post_init__(self) -> None:
        if not isinstance(self.edge_definition_id, EdgeDefinitionId):
            raise InvalidWorkflowDefinition(
                "edge_definition_id must be an EdgeDefinitionId"
            )
        if not isinstance(self.source_node_id, NodeDefinitionId):
            raise InvalidWorkflowDefinition("source_node_id must be a NodeDefinitionId")
        if not isinstance(self.target_node_id, NodeDefinitionId):
            raise InvalidWorkflowDefinition("target_node_id must be a NodeDefinitionId")
        if self.source_node_id == self.target_node_id:
            raise SelfEdgeNotAllowed()
