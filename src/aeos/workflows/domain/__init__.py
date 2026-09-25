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
    InvalidAttemptNumber,
    InvalidLifecycleTimestamp,
    InvalidNodeAttemptState,
    InvalidNodeAttemptTransition,
    InvalidNodeRunState,
    InvalidNodeRunTransition,
    InvalidWorkflowRunState,
    InvalidWorkflowRunTransition,
)
from aeos.workflows.domain.node import NodeDefinition, NodeKind
from aeos.workflows.domain.definition import WorkflowDefinition
from aeos.workflows.domain.attempt import NodeAttempt, NodeAttemptStatus
from aeos.workflows.domain.node_run import NodeRun, NodeRunStatus
from aeos.workflows.domain.run import WorkflowRun, WorkflowRunStatus

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
    "WorkflowRun",
    "WorkflowRunStatus",
    "NodeRun",
    "NodeRunStatus",
    "NodeAttempt",
    "NodeAttemptStatus",
    "InvalidAttemptNumber",
    "InvalidLifecycleTimestamp",
    "InvalidNodeAttemptState",
    "InvalidNodeAttemptTransition",
    "InvalidNodeRunState",
    "InvalidNodeRunTransition",
    "InvalidWorkflowRunState",
    "InvalidWorkflowRunTransition",
]
