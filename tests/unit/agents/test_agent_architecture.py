import ast
from dataclasses import fields
from pathlib import Path

from aeos.agents import AgentCapability, AgentDefinition, AgentInvocation


def test_agents_domain_imports_only_its_context_shared_kernel_and_stdlib() -> None:
    package_dir = Path(__file__).parents[3] / "src" / "aeos" / "agents"
    forbidden_contexts = {
        "aeos.organization",
        "aeos.governance",
        "aeos.economics",
        "aeos.workflows",
        "aeos.experiments",
        "aeos.knowledge",
        "aeos.infrastructure",
    }

    for path in package_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not any(
                    node.module == context or node.module.startswith(f"{context}.")
                    for context in forbidden_contexts
                )


def test_agent_contract_fields_contain_no_runtime_research_or_authorization_state() -> (
    None
):
    forbidden = {
        "status",
        "provider",
        "model",
        "model_client",
        "tool",
        "tool_client",
        "permission_grant",
        "research_objective",
        "thesis_variable",
        "study_id",
        "indicator",
        "prompt",
        "memory",
        "transcript",
        "cost",
        "tokens",
    }

    for contract in (AgentCapability, AgentDefinition, AgentInvocation):
        assert not forbidden.intersection(field.name for field in fields(contract))
