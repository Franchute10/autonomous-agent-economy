import asyncio

from organizations import organizations

USER_ID = "01aa0000-0000-4000-8000-000000000001"
ORGANIZATION_ID = "01bb0000-0000-4000-8000-000000000002"
IDEMPOTENCY_KEY = "01cc0000-0000-4000-8000-000000000003"
URL = "https://testproject.supabase.co"
KEY = "sb_publishable_test"
TOKEN = "a.b.c"


def run(method, raw_body, request_database):
    database_calls = []

    async def request_user(url, key, token):
        return 200, {"id": USER_ID, "is_anonymous": False}

    async def database(url, method, key, token, payload):
        database_calls.append((url, method, key, token, payload))
        return await request_database(url, method, key, token, payload)

    result = asyncio.run(
        organizations(
            method,
            raw_body,
            IDEMPOTENCY_KEY,
            "Bearer " + TOKEN,
            URL,
            KEY,
            request_user,
            database,
        )
    )
    return result, database_calls


def test_create_organization_uses_authenticated_identity_and_sanitizes_response():
    async def database(*args):
        return 200, [
            {
                "organization_id": ORGANIZATION_ID,
                "name": "Acme",
                "role": "owner",
                "created_by": "forged-or-private",
            }
        ]

    result, calls = run(
        "POST",
        '{"name":"  Acme  ","user_id":"forged","organization_id":"other"}',
        database,
    )

    assert result == (
        201,
        {
            "organization": {
                "id": ORGANIZATION_ID,
                "name": "Acme",
                "role": "owner",
            }
        },
    )
    assert len(calls) == 1
    url, method, key, token, payload = calls[0]
    assert url == URL + "/rest/v1/rpc/create_organization"
    assert method == "POST"
    assert key == KEY
    assert token == TOKEN
    assert payload == {"p_name": "Acme", "p_creation_key": IDEMPOTENCY_KEY}


def test_list_organizations_scopes_query_to_verified_user():
    async def database(*args):
        return 200, [
            {
                "organization_id": ORGANIZATION_ID,
                "role": "owner",
                "organization": {
                    "id": ORGANIZATION_ID,
                    "name": "Acme",
                    "created_at": "2026-11-28T00:00:00Z",
                },
            }
        ]

    result, calls = run("GET", None, database)

    assert result[0] == 200
    assert result[1]["organizations"] == [
        {
            "id": ORGANIZATION_ID,
            "name": "Acme",
            "created_at": "2026-11-28T00:00:00Z",
            "role": "owner",
        }
    ]
    assert len(calls) == 1
    assert "user_id=eq." + USER_ID in calls[0][0]


def test_invalid_name_and_wrong_method_do_not_call_database():
    async def database(*args):
        raise AssertionError("database must not be called")

    invalid, calls = run("POST", '{"name":" "}', database)
    assert invalid == (400, {"error": "invalid_organization_name"})
    assert calls == []

    wrong_method = asyncio.run(
        organizations(
            "DELETE",
            None,
            IDEMPOTENCY_KEY,
            "Bearer " + TOKEN,
            URL,
            KEY,
            lambda *args: None,
            database,
        )
    )
    assert wrong_method == (
        405,
        {"error": "method_not_allowed", "allowed_methods": ["GET", "POST"]},
    )


def test_missing_or_invalid_identity_fails_before_database():
    calls = []

    async def request_user(*args):
        calls.append("auth")
        return 401, None

    async def database(*args):
        calls.append("database")
        return 200, []

    result = asyncio.run(
        organizations(
            "GET",
            None,
            None,
            None,
            None,
            URL,
            KEY,
            request_user,
            database,
        )
    )
    assert result == (401, {"error": "authentication_required"})
    assert calls == []


def test_database_failure_is_sanitized():
    async def database(*args):
        return 500, {"message": "sensitive database details"}

    result, calls = run("GET", None, database)
    assert result == (503, {"error": "database_unavailable"})
    assert len(calls) == 1
