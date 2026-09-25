"""Immutable workflow graph definition and deterministic validation."""

from dataclasses import dataclass

from aeos.core import (
    NodeDefinitionId,
    OrganizationId,
    VersionRef,
    WorkflowDefinitionId,
)
from aeos.workflows.domain.edge import EdgeDefinition
from aeos.workflows.domain.errors import (
    DuplicateEdgeDefinition,
    DuplicateNodeDefinition,
    DuplicateStructuralEdge,
    EndNodeHasOutgoingEdge,
    InvalidEntryNode,
    InvalidWorkflowDefinition,
    InvalidWorkflowName,
    MissingEdgeSourceNode,
    MissingEdgeTargetNode,
    MissingEntryNode,
    UnreachableNode,
)
from aeos.workflows.domain.node import NodeDefinition, NodeKind


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """An immutable, explicitly versioned static workflow graph."""

    workflow_definition_id: WorkflowDefinitionId
    organization_id: OrganizationId
    version_ref: VersionRef
    name: str
    nodes: tuple[NodeDefinition, ...]
    edges: tuple[EdgeDefinition, ...]
    entry_node_ids: tuple[NodeDefinitionId, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_definition_id, WorkflowDefinitionId):
            raise InvalidWorkflowDefinition(
                "workflow_definition_id must be a WorkflowDefinitionId"
            )
        if not isinstance(self.organization_id, OrganizationId):
            raise InvalidWorkflowDefinition("organization_id must be an OrganizationId")
        if not isinstance(self.version_ref, VersionRef):
            raise InvalidWorkflowDefinition("version_ref must be a VersionRef")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidWorkflowName()
        object.__setattr__(self, "name", self.name.strip())

        if not isinstance(self.nodes, tuple):
            raise InvalidWorkflowDefinition("nodes must be a tuple")
        if not isinstance(self.edges, tuple):
            raise InvalidWorkflowDefinition("edges must be a tuple")
        if not isinstance(self.entry_node_ids, tuple):
            raise InvalidWorkflowDefinition("entry_node_ids must be a tuple")
        nodes = self.nodes
        edges = self.edges
        entries = self.entry_node_ids

        if not nodes:
            raise InvalidWorkflowDefinition("workflow must contain at least one node")
        if not entries:
            raise MissingEntryNode()
        if any(not isinstance(node, NodeDefinition) for node in nodes):
            raise InvalidWorkflowDefinition("nodes must contain NodeDefinition values")
        if any(not isinstance(edge, EdgeDefinition) for edge in edges):
            raise InvalidWorkflowDefinition("edges must contain EdgeDefinition values")
        if any(not isinstance(entry, NodeDefinitionId) for entry in entries):
            raise InvalidEntryNode()

        node_ids = tuple(node.node_definition_id for node in nodes)
        if len(set(node_ids)) != len(node_ids):
            raise DuplicateNodeDefinition()
        edge_ids = tuple(edge.edge_definition_id for edge in edges)
        if len(set(edge_ids)) != len(edge_ids):
            raise DuplicateEdgeDefinition()
        node_id_set = set(node_ids)
        if any(entry not in node_id_set for entry in entries):
            raise InvalidEntryNode()
        if len(set(entries)) != len(entries):
            raise InvalidEntryNode()

        pairs = tuple((edge.source_node_id, edge.target_node_id) for edge in edges)
        if len(set(pairs)) != len(pairs):
            raise DuplicateStructuralEdge()
        for edge in edges:
            if edge.source_node_id not in node_id_set:
                raise MissingEdgeSourceNode()
            if edge.target_node_id not in node_id_set:
                raise MissingEdgeTargetNode()
            if self.node_by_id(edge.source_node_id).kind is NodeKind.END:
                raise EndNodeHasOutgoingEdge()

        outgoing: dict[NodeDefinitionId, list[NodeDefinitionId]] = {
            node_id: [] for node_id in node_ids
        }
        for edge in edges:
            outgoing[edge.source_node_id].append(edge.target_node_id)
        reachable = set(entries)
        frontier = list(entries)
        while frontier:
            current = frontier.pop(0)
            for successor in outgoing[current]:
                if successor not in reachable:
                    reachable.add(successor)
                    frontier.append(successor)
        if reachable != node_id_set:
            raise UnreachableNode()

    @property
    def terminal_node_ids(self) -> tuple[NodeDefinitionId, ...]:
        sources = {edge.source_node_id for edge in self.edges}
        return tuple(
            node.node_definition_id
            for node in self.nodes
            if node.node_definition_id not in sources
        )

    def node_by_id(self, node_id: NodeDefinitionId) -> NodeDefinition:
        if not isinstance(node_id, NodeDefinitionId):
            raise TypeError("node_id must be a NodeDefinitionId")
        for node in self.nodes:
            if node.node_definition_id == node_id:
                return node
        raise KeyError(node_id)

    def outgoing_edges(self, node_id: NodeDefinitionId) -> tuple[EdgeDefinition, ...]:
        if not isinstance(node_id, NodeDefinitionId):
            raise TypeError("node_id must be a NodeDefinitionId")
        return tuple(edge for edge in self.edges if edge.source_node_id == node_id)

    def incoming_edges(self, node_id: NodeDefinitionId) -> tuple[EdgeDefinition, ...]:
        if not isinstance(node_id, NodeDefinitionId):
            raise TypeError("node_id must be a NodeDefinitionId")
        return tuple(edge for edge in self.edges if edge.target_node_id == node_id)
