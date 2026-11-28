"""Pure public HTTP routes for the AEOS Starter API."""

SERVICE = "aeos-starter-api"
RELEASE = "s0-03-org-onboarding-candidate"


def route(method: str, path: str) -> tuple[int, dict[str, object]]:
    """Return deterministic public route responses without external services."""
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
            "stage": "organization_onboarding_candidate",
            "database_connected": False,
            "authentication_endpoint_implemented": True,
            "authentication_live_verified": False,
            "organization_onboarding_api_implemented": True,
            "organization_membership_live_verified": False,
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
                "organization_onboarding_api_candidate",
            ],
            "not_yet_available": [
                "database_migration_applied",
                "database_from_worker_verified",
                "valid_supabase_session_live_verified",
                "organization_membership_e2e",
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
