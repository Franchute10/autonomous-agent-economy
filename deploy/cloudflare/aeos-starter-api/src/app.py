"""Pure public HTTP routes for the AEOS Starter API."""

from auth import URL_PATTERN

SERVICE = "aeos-starter-api"
RELEASE = "s1-02-auth-org-onboarding-candidate"


def public_config(
    method: str, supabase_url: object, publishable_key: object
) -> tuple[int, dict[str, object]]:
    """Expose only the public Supabase URL and publishable client key."""
    if method != "GET":
        return 405, {"error": "method_not_allowed", "allowed_methods": ["GET"]}
    if (
        not isinstance(supabase_url, str)
        or URL_PATTERN.fullmatch(supabase_url) is None
        or not isinstance(publishable_key, str)
        or not publishable_key.startswith("sb_publishable_")
        or len(publishable_key) > 512
        or any(ord(char) < 33 for char in publishable_key)
    ):
        return 503, {"error": "configuration_unavailable"}
    return 200, {
        "service": SERVICE,
        "supabase_url": supabase_url,
        "supabase_publishable_key": publishable_key,
    }


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
            "stage": "auth_and_organization_onboarding_candidate",
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
                "supabase_public_auth_configuration",
                "supabase_identity_endpoint",
                "organization_onboarding_api_candidate",
            ],
            "not_yet_available": [
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
            "side_effects": True,
            "customer_data_enabled": True,
        }

    return 404, {"error": "not_found", "service": SERVICE}
