from cors import cors_headers


def test_cors_allows_only_the_dedicated_https_pages_project() -> None:
    result = cors_headers("https://264d0cc8.aeos-starter-preview.pages.dev")
    assert result["access-control-allow-origin"] == (
        "https://264d0cc8.aeos-starter-preview.pages.dev"
    )
    assert result["access-control-allow-methods"] == "GET,POST,OPTIONS"
    assert result["access-control-allow-headers"] == (
        "authorization,content-type,idempotency-key"
    )
    assert "access-control-allow-credentials" not in result


def test_cors_rejects_non_https_and_confusable_origins() -> None:
    assert cors_headers("http://aeos-starter-preview.pages.dev") == {}
    assert cors_headers("https://aeos-starter-preview.pages.dev.attacker.example") == {}
    assert cors_headers("https://other.pages.dev") == {}
    assert cors_headers(None) == {}
