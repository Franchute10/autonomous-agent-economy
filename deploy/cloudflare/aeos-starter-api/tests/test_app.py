import asyncio

from app import route
from auth import verify_identity


def test_health_reports_candidate_status_without_claiming_live_verification() -> None:
    status, body = route("GET", "/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["database_connected"] is False
    assert body["authentication_endpoint_implemented"] is True
    assert body["authentication_live_verified"] is False
    assert body["organization_onboarding_api_implemented"] is True
    assert body["organization_membership_live_verified"] is False
    assert body["model_inference_enabled"] is False
    assert body["agent_execution_enabled"] is False


def test_capabilities_do_not_claim_unimplemented_features() -> None:
    status, body = route("GET", "/api/v1/capabilities")
    assert status == 200
    assert body["side_effects"] is True
    assert body["customer_data_enabled"] is True
    assert "supabase_identity_endpoint" in body["available"]
    assert "organization_onboarding_api_candidate" in body["available"]
    assert "database_from_worker_verified" in body["not_yet_available"]
    assert "organization_membership_e2e" in body["not_yet_available"]
    assert "task_persistence" in body["not_yet_available"]
    assert "model_inference" in body["not_yet_available"]


def test_non_get_methods_are_rejected() -> None:
    status, body = route("POST", "/health")
    assert status == 405
    assert body["error"] == "method_not_allowed"


def test_unknown_paths_are_not_found() -> None:
    status, body = route("GET", "/unknown")
    assert status == 404
    assert body["error"] == "not_found"


# Supabase identity adapter: no network or real user data.
def test_identity_gate() -> None:
    calls = []

    async def upstream(url, key, token):
        calls.append((url, key, token))
        return 200, {
            "id": "01aa0000-0000-4000-8000-000000000001",
            "is_anonymous": False,
            "user_metadata": {"organization_id": "forged"},
        }

    url = "https://testproject.supabase.co"
    key = "sb_publishable_test"
    assert asyncio.run(verify_identity(None, url, key, upstream))[0] == 401
    assert (
        asyncio.run(verify_identity("Bearer a.b.c", url, "sb_secret_test", upstream))[0]
        == 503
    )
    assert calls == []

    status, body = asyncio.run(verify_identity("Bearer a.b.c", url, key, upstream))
    assert status == 200
    assert body == {
        "user_id": "01aa0000-0000-4000-8000-000000000001",
        "authenticated": True,
    }
    assert len(calls) == 1


def test_identity_rejects_invalid_inputs_before_upstream() -> None:
    calls = []

    async def upstream(*args):
        calls.append(args)
        return 200, {
            "id": "01aa0000-0000-4000-8000-000000000001",
            "is_anonymous": False,
        }

    url = "https://testproject.supabase.co"
    key = "sb_publishable_test"
    assert asyncio.run(verify_identity("Basic a.b.c", url, key, upstream))[0] == 401
    assert (
        asyncio.run(verify_identity("Bearer malformed", url, key, upstream))[0] == 401
    )
    assert (
        asyncio.run(
            verify_identity(
                "Bearer a.b.c", "http://testproject.supabase.co", key, upstream
            )
        )[0]
        == 503
    )
    assert (
        asyncio.run(verify_identity("Bearer a.b.c", url, "anon_legacy_key", upstream))[
            0
        ]
        == 503
    )
    assert calls == []


def test_identity_upstream_fail_closed() -> None:
    async def invalid(*args):
        return 401, None

    async def unavailable(*args):
        raise RuntimeError("private detail")

    async def server_error(*args):
        return 500, None

    async def anonymous(*args):
        return 200, {"is_anonymous": True}

    args = (
        "Bearer a.b.c",
        "https://testproject.supabase.co",
        "sb_publishable_test",
    )
    assert asyncio.run(verify_identity(*args, invalid))[0] == 401
    assert asyncio.run(verify_identity(*args, unavailable)) == (
        503,
        {"error": "authentication_unavailable"},
    )
    assert asyncio.run(verify_identity(*args, server_error)) == (
        503,
        {"error": "authentication_unavailable"},
    )
    assert asyncio.run(verify_identity(*args, anonymous))[0] == 403


def test_identity_malformed_upstream_user_fails_closed() -> None:
    async def missing_anonymous_flag(*args):
        return 200, {"id": "01aa0000-0000-4000-8000-000000000001"}

    async def invalid_user_id(*args):
        return 200, {"id": "not-a-uuid", "is_anonymous": False}

    async def non_object_user(*args):
        return 200, ["unexpected", "payload"]

    args = (
        "Bearer a.b.c",
        "https://testproject.supabase.co",
        "sb_publishable_test",
    )
    expected = (503, {"error": "authentication_unavailable"})
    assert asyncio.run(verify_identity(*args, missing_anonymous_flag)) == expected
    assert asyncio.run(verify_identity(*args, invalid_user_id)) == expected
    assert asyncio.run(verify_identity(*args, non_object_user)) == expected
