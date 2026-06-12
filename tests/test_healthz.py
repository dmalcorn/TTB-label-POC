"""Skeleton liveness test (AC-2, AC-4, AC-5).

Doubles as the placeholder test that gates the tooling setup and as the
regression guarding the `GET /healthz` contract every later story relies on.
Kept import-light so collection never pulls deferred extraction deps.
"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_200_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_boots_with_empty_environment(monkeypatch) -> None:
    """Absent LLM/token keys must not raise — the zero-egress boot contract (AR-9)."""
    for key in (
        "ACCESS_TOKEN",
        "LLM_ENABLED",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LANGCHAIN_TRACING_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
