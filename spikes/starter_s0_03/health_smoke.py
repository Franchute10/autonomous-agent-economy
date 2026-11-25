"""S0-03 local ASGI probe; not an AEOS runtime or deployed service."""

import unittest

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"service": "aeos-starter-spike", "status": "alive"}


@app.get("/readyz")
def readiness() -> JSONResponse:
    # Fail closed: a live HTTP process does not prove infrastructure readiness.
    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "postgresql": "not_configured",
            "auth": "not_configured",
            "model": "not_configured",
        },
    )


class HealthSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_liveness(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")

    def test_readiness_fails_closed(self) -> None:
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["postgresql"], "not_configured")
        self.assertEqual(response.json()["auth"], "not_configured")
        self.assertEqual(response.json()["model"], "not_configured")

    def test_no_task_execution_endpoint(self) -> None:
        self.assertEqual(self.client.post("/tasks", json={}).status_code, 404)

    def test_no_mutation_on_health_endpoint(self) -> None:
        self.assertEqual(self.client.post("/healthz").status_code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
