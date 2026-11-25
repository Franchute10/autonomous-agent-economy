from app import route


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
