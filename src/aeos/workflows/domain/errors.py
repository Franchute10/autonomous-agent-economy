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
