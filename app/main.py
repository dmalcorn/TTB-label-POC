"""FastAPI application factory for the TTB COLA Label Specialist POC.

Story 1.1 establishes the deterministic, offline-pinned skeleton: an app factory
plus a `GET /healthz` liveness route. Startup performs ZERO network I/O, no OCR,
no model import — this is what makes the `docker run --network none` boot
(AC-5 / AR-8) and the 5-second read contract (AR-5) hold from day one. Later
stories mount the routers, static assets, and the APScheduler sweep here.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Routers, static mounts, and the background scheduler are wired in by later
    stories; the skeleton only needs to boot and report health.
    """
    # Resolve settings eagerly so a malformed environment surfaces at startup —
    # but absent keys are valid (features simply off), so this never raises on a
    # clean environment.
    get_settings()

    app = FastAPI(title="TTB Label Review", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness probe. Pure in-memory response — no DB, no network."""
        return {"status": "ok"}

    return app


app = create_app()
