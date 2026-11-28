from pathlib import Path


PREVIEW = Path(__file__).resolve().parents[1] / "spikes" / "starter_s0_03" / "preview"


def test_preview_has_auth_org_forms_and_secure_headers() -> None:
    html = (PREVIEW / "index.html").read_text(encoding="utf-8")
    script = (PREVIEW / "app.js").read_text(encoding="utf-8")
    headers = (PREVIEW / "_headers").read_text(encoding="utf-8")
    config = (PREVIEW / "runtime-config.js").read_text(encoding="utf-8")
    assert 'id="login-form"' in html
    assert 'id="signup-form"' in html
    assert 'id="organization-form"' in html
    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert "console.log" not in script
    assert "crypto.randomUUID()" in script
    assert 'credentials: "omit"' in script
    assert "frame-ancestors 'none'" in headers
    assert "service_role" not in script.lower()
    assert "sb_secret_" not in script
    assert '<script src="./runtime-config.js" defer></script>' in html
    assert '<script src="./app.js" defer></script>' in html
    assert "<style" not in html
    assert "window.AEOS_API_BASE" in config
    assert "window.AEOS_API_BASE ||" in script
    assert "https://*.workers.dev" not in headers
