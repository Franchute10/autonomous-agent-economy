import pytest
from typing import cast

from aeos.core import (
    EdgeDefinitionId,
    NodeDefinitionId,
    OrganizationId,
    VersionRef,
    WorkflowDefinitionId,
)
from aeos.workflows.domain import (
    DuplicateStructuralEdge,
    DuplicateEdgeDefinition,
    DuplicateNodeDefinition,
    EndNodeHasOutgoingEdge,
    EdgeDefinition,
    InvalidEntryNode,
    InvalidWorkflowDefinition,
    InvalidWorkflowName,
    MissingEdgeSourceNode,
    MissingEdgeTargetNode,
    NodeDefinition,
    NodeKind,
    SelfEdgeNotAllowed,
    UnreachableNode,
    WorkflowDefinition,
)


def node(value: str) -> NodeDefinition:
    return NodeDefinition(NodeDefinitionId(value), value, NodeKind.ACTION)


def edge(value: str, source: str, target: str) -> EdgeDefinition:
    return EdgeDefinition(
        EdgeDefinitionId(value), NodeDefinitionId(source), NodeDefinitionId(target)
    )


def workflow(
    nodes: tuple[NodeDefinition, ...],
    edges: tuple[EdgeDefinition, ...],
    entries: tuple[str, ...],
) -> WorkflowDefinition:
    return WorkflowDefinition(
        WorkflowDefinitionId("workflow-1"),
        OrganizationId("org-1"),
        VersionRef("workflow", "1"),
        "Example",
        nodes,
        edges,
        tuple(NodeDefinitionId(entry) for entry in entries),
    )


def test_linear_workflow_and_terminals() -> None:
    definition = workflow(
        (node("a"), node("b"), node("c")),
        (edge("ab", "a", "b"), edge("bc", "b", "c")),
        ("a",),
    )
    assert definition.terminal_node_ids == (NodeDefinitionId("c"),)


def test_single_node_workflow_is_valid_and_terminal() -> None:
    assert workflow((node("a"),), (), ("a",)).terminal_node_ids == (
        NodeDefinitionId("a"),
    )


def test_end_without_outgoing_edge_is_valid_and_end_with_edge_is_rejected() -> None:
    end = NodeDefinition(NodeDefinitionId("end"), " End ", NodeKind.END)
    assert workflow((end,), (), ("end",)).terminal_node_ids == (
        NodeDefinitionId("end"),
    )
    with pytest.raises(EndNodeHasOutgoingEdge):
        workflow(
            (node("a"), end),
            (edge("ae", "a", "end"), edge("ea", "end", "a")),
            ("a",),
        )


def test_action_terminal_and_cyclic_workflow_without_end_are_valid() -> None:
    assert workflow((node("a"),), (), ("a",)).terminal_node_ids == (
        NodeDefinitionId("a"),
    )
    assert (
        workflow(
            (node("a"), node("b")),
            (edge("ab", "a", "b"), edge("ba", "b", "a")),
            ("a",),
        ).terminal_node_ids
        == ()
    )


def test_cycles_and_entry_with_incoming_edge_are_valid() -> None:
    definition = workflow(
        (node("a"), node("b")), (edge("ab", "a", "b"), edge("ba", "b", "a")), ("a",)
    )
    assert definition.terminal_node_ids == ()


def test_multiple_entries_are_valid() -> None:
    definition = workflow(
        (node("a"), node("b"), node("c")),
        (edge("ac", "a", "c"), edge("bc", "b", "c")),
        ("a", "b"),
    )
    assert definition.entry_node_ids == (NodeDefinitionId("a"), NodeDefinitionId("b"))


@pytest.mark.parametrize(
    "edges, error",
    [
        ((edge("ab", "a", "b"), edge("ab-2", "a", "b")), DuplicateStructuralEdge),
        ((edge("xa", "x", "a"),), MissingEdgeSourceNode),
        ((edge("ax", "a", "x"),), MissingEdgeTargetNode),
    ],
)
def test_structural_edge_validation(
    edges: tuple[EdgeDefinition, ...], error: type[Exception]
) -> None:
    with pytest.raises(error):
        workflow((node("a"), node("b")), edges, ("a",))


def test_unreachable_nodes_and_invalid_entries_are_rejected() -> None:
    with pytest.raises(UnreachableNode):
        workflow((node("a"), node("b"), node("c")), (edge("ab", "a", "b"),), ("a",))
    with pytest.raises(InvalidEntryNode):
        workflow((node("a"),), (), ("missing",))


def test_empty_workflow_and_blank_name_are_rejected() -> None:
    with pytest.raises(InvalidWorkflowDefinition):
        workflow((), (), ())
    with pytest.raises(InvalidWorkflowName):
        WorkflowDefinition(
            WorkflowDefinitionId("workflow-1"),
            OrganizationId("org-1"),
            VersionRef("workflow", "1"),
            " ",
            (node("a"),),
            (),
            (NodeDefinitionId("a"),),
        )


def test_duplicate_node_and_edge_ids_are_rejected() -> None:
    with pytest.raises(DuplicateNodeDefinition):
        workflow((node("a"), node("a")), (), ("a",))
    with pytest.raises(DuplicateEdgeDefinition):
        workflow(
            (node("a"), node("b"), node("c")),
            (
                edge("same", "a", "b"),
                EdgeDefinition(
                    EdgeDefinitionId("same"),
                    NodeDefinitionId("b"),
                    NodeDefinitionId("c"),
                ),
            ),
            ("a",),
        )


def test_self_edge_is_rejected() -> None:
    with pytest.raises(SelfEdgeNotAllowed):
        edge("aa", "a", "a")


def test_collections_and_models_are_immutable() -> None:
    definition = workflow((node("a"),), (), ("a",))
    with pytest.raises(AttributeError):
        definition.name = "changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        definition.nodes += (node("b"),)  # type: ignore[misc]


def test_workflow_requires_tuples_and_preserves_supplied_tuples() -> None:
    nodes = (node("a"),)
    edges: tuple[EdgeDefinition, ...] = ()
    entries = (NodeDefinitionId("a"),)
    definition = WorkflowDefinition(
        WorkflowDefinitionId("workflow-1"),
        OrganizationId("org-1"),
        VersionRef("workflow", "1"),
        " Example ",
        nodes,
        edges,
        entries,
    )
    assert definition.nodes is nodes
    assert definition.edges is edges
    assert definition.entry_node_ids is entries
    assert definition.name == "Example"
    with pytest.raises(InvalidWorkflowDefinition):
        WorkflowDefinition(
            WorkflowDefinitionId("w"),
            OrganizationId("o"),
            VersionRef("w", "1"),
            "w",
            cast(tuple[NodeDefinition, ...], list(nodes)),
            edges,
            entries,
        )
    with pytest.raises(InvalidWorkflowDefinition):
        WorkflowDefinition(
            WorkflowDefinitionId("w"),
            OrganizationId("o"),
            VersionRef("w", "1"),
            "w",
            nodes,
            cast(tuple[EdgeDefinition, ...], list(edges)),
            entries,
        )
    with pytest.raises(InvalidWorkflowDefinition):
        WorkflowDefinition(
            WorkflowDefinitionId("w"),
            OrganizationId("o"),
            VersionRef("w", "1"),
            "w",
            nodes,
            edges,
            cast(tuple[NodeDefinitionId, ...], list(entries)),
        )


def test_lookup_helpers_require_typed_ids() -> None:
    definition = workflow((node("a"),), (), ("a",))
    with pytest.raises(TypeError):
        definition.node_by_id("a")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        definition.outgoing_edges("a")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        definition.incoming_edges("a")  # type: ignore[arg-type]
    assert definition.outgoing_edges(NodeDefinitionId("missing")) == ()
    assert definition.incoming_edges(NodeDefinitionId("missing")) == ()
