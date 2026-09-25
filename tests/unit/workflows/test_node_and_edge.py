import pytest

from aeos.core import EdgeDefinitionId, NodeDefinitionId
from aeos.core.errors import DomainError
from aeos.workflows.domain import (
    EdgeDefinition,
    InvalidNodeKind,
    NodeDefinition,
    NodeKind,
)


def test_node_kind_is_approved_and_deterministic() -> None:
    assert NodeKind.from_value("action") is NodeKind.ACTION
    assert str(NodeKind.ACTION) == "action"
    assert NodeKind.ACTION == NodeKind("action")
    with pytest.raises(InvalidNodeKind):
        NodeKind.from_value(" ")


def test_node_and_edge_are_immutable() -> None:
    node = NodeDefinition(NodeDefinitionId("n"), " Node ", NodeKind.ACTION)
    edge = EdgeDefinition(
        EdgeDefinitionId("e"), node.node_definition_id, NodeDefinitionId("m")
    )
    with pytest.raises(AttributeError):
        node.name = "changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        edge.source_node_id = NodeDefinitionId("m")  # type: ignore[misc]
    assert node.name == "Node"


def test_node_kind_rejects_non_approved_value() -> None:
    with pytest.raises((InvalidNodeKind, ValueError, DomainError)):
        NodeKind.from_value("provider-specific")


def test_node_kind_is_closed() -> None:
    assert tuple(NodeKind) == (NodeKind.ACTION, NodeKind.DECISION, NodeKind.END)
