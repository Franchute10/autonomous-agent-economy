import asyncio

from app import route
from auth import verify_identity


def test_health_is_explicitly_bootstrap_only() -> None:
    status, body = route("GET", "/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["database_connected"] is False
    assert body["authentication_enabled"] is False
    assert body["model_inference_enabled"] is False
    assert body["agent_execution_enabled"] is False


def test_capabilities_do_not_claim_unimplemented_features() -> None:
    status, body = route("GET", "/api/v1/capabilities")
    assert status == 200
    assert body["side_effects"] is False
    assert body["customer_data_enabled"] is False
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


def test_identity_upstream_fail_closed() -> None:
    async def invalid(*args):
        return 401, None

    async def unavailable(*args):
        raise RuntimeError("private detail")

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
    assert asyncio.run(verify_identity(*args, anonymous))[0] == 403
