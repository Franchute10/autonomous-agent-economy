"""Structural errors for the workflow definition domain."""

from aeos.core.errors import DomainError


class InvalidWorkflowDefinition(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_workflow_definition", message)


class InvalidWorkflowName(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_workflow_name", "workflow name must not be blank")


class InvalidNodeDefinition(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_node_definition", message)


class InvalidNodeKind(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_node_kind", "node kind is not an approved value")


class DuplicateNodeDefinition(DomainError):
    def __init__(self) -> None:
        super().__init__("duplicate_node_definition", "node identity is duplicated")


class DuplicateEdgeDefinition(DomainError):
    def __init__(self) -> None:
        super().__init__("duplicate_edge_definition", "edge identity is duplicated")


class DuplicateStructuralEdge(DomainError):
    def __init__(self) -> None:
        super().__init__("duplicate_structural_edge", "directed edge is duplicated")


class MissingEdgeSourceNode(DomainError):
    def __init__(self) -> None:
        super().__init__("missing_edge_source_node", "edge source node is not defined")


class MissingEdgeTargetNode(DomainError):
    def __init__(self) -> None:
        super().__init__("missing_edge_target_node", "edge target node is not defined")


class InvalidEntryNode(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_entry_node", "entry node is not defined")


class MissingEntryNode(DomainError):
    def __init__(self) -> None:
        super().__init__("missing_entry_node", "workflow must declare an entry node")


class UnreachableNode(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "unreachable_node", "every node must be reachable from an entry"
        )


class SelfEdgeNotAllowed(DomainError):
    def __init__(self) -> None:
        super().__init__("self_edge_not_allowed", "direct self-edges are not allowed")


class EndNodeHasOutgoingEdge(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "end_node_has_outgoing_edge",
            "an END node must not have outgoing edges",
        )


class InvalidWorkflowRunState(DomainError):
    def __init__(self, message: str = "invalid workflow run status") -> None:
        super().__init__("invalid_workflow_run_state", message)


class InvalidWorkflowRunTransition(DomainError):
    def __init__(self, message: str = "workflow run transition is not allowed") -> None:
        super().__init__("invalid_workflow_run_transition", message)


class InvalidNodeRunState(DomainError):
    def __init__(self, message: str = "invalid node run status") -> None:
        super().__init__("invalid_node_run_state", message)


class InvalidNodeRunTransition(DomainError):
    def __init__(self, message: str = "node run transition is not allowed") -> None:
        super().__init__("invalid_node_run_transition", message)


class InvalidNodeAttemptState(DomainError):
    def __init__(self, message: str = "invalid node attempt status") -> None:
        super().__init__("invalid_node_attempt_state", message)


class InvalidNodeAttemptTransition(DomainError):
    def __init__(self, message: str = "node attempt transition is not allowed") -> None:
        super().__init__("invalid_node_attempt_transition", message)


class InvalidLifecycleTimestamp(DomainError):
    def __init__(self, message: str = "lifecycle timestamps are inconsistent") -> None:
        super().__init__("invalid_lifecycle_timestamp", message)


class InvalidAttemptNumber(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_attempt_number",
            "attempt_number must be an int greater than or equal to 1",
        )
