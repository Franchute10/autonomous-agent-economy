"""Pure HTTP routing for the AEOS Starter API bootstrap."""

SERVICE = "aeos-starter-api"
RELEASE = "s0-04"


def route(method: str, path: str) -> tuple[int, dict[str, object]]:
    """Return a deterministic response without external services or side effects."""
    if method != "GET":
        return 405, {
            "error": "method_not_allowed",
            "service": SERVICE,
            "allowed_methods": ["GET"],
        }

    if path in {"/", "/health", "/api/health"}:
        return 200, {
            "status": "ok",
            "service": SERVICE,
            "release": RELEASE,
            "stage": "bootstrap",
            "database_connected": False,
            "authentication_endpoint_implemented": True,
            "authentication_live_verified": False,
            "organization_membership_enabled": False,
            "model_inference_enabled": False,
            "agent_execution_enabled": False,
        }

    if path == "/api/v1/capabilities":
        return 200, {
            "service": SERVICE,
            "release": RELEASE,
            "available": [
                "health",
                "capability_catalog",
                "supabase_identity_endpoint",
            ],
            "not_yet_available": [
                "organization_onboarding",
                "organization_membership",
                "tenant_persistence",
                "task_persistence",
                "workflow_runtime",
                "agent_invocations",
                "evidence_storage",
                "human_approvals",
                "model_inference",
            ],
            "side_effects": False,
            "customer_data_enabled": False,
        }

    return 404, {"error": "not_found", "service": SERVICE}
