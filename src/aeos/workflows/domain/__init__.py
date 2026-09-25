"""Immutable workflow definition models."""

from aeos.workflows.domain.edge import EdgeDefinition
from aeos.workflows.domain.errors import (
    DuplicateEdgeDefinition,
    DuplicateNodeDefinition,
    DuplicateStructuralEdge,
    EndNodeHasOutgoingEdge,
    InvalidEntryNode,
    InvalidNodeDefinition,
    InvalidNodeKind,
    InvalidWorkflowDefinition,
    InvalidWorkflowName,
    MissingEdgeSourceNode,
    MissingEdgeTargetNode,
    MissingEntryNode,
    SelfEdgeNotAllowed,
    UnreachableNode,
)
from aeos.workflows.domain.node import NodeDefinition, NodeKind
from aeos.workflows.domain.definition import WorkflowDefinition

__all__ = [
    "DuplicateEdgeDefinition",
    "DuplicateNodeDefinition",
    "DuplicateStructuralEdge",
    "EndNodeHasOutgoingEdge",
    "EdgeDefinition",
    "InvalidEntryNode",
    "InvalidNodeDefinition",
    "InvalidNodeKind",
    "InvalidWorkflowDefinition",
    "InvalidWorkflowName",
    "MissingEdgeSourceNode",
    "MissingEdgeTargetNode",
    "MissingEntryNode",
    "NodeDefinition",
    "NodeKind",
    "SelfEdgeNotAllowed",
    "UnreachableNode",
    "WorkflowDefinition",
]
