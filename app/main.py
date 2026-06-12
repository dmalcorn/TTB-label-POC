"""FastAPI application factory for the TTB COLA Label Specialist POC.

Story 1.1 establishes the deterministic, offline-pinned skeleton: an app factory
plus a `GET /healthz` liveness route. Startup performs ZERO network I/O, no OCR,
no model import — this is what makes the `docker run --network none` boot
(AC-5 / AR-8) and the 5-second read contract (AR-5) hold from day one. Later
stories mount the routers, static assets, and the APScheduler sweep here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.db.connection import init_db
from app.web.deps import gate_enabled, has_valid_access, is_exempt
from app.web.routes_access import router as access_router

# Project root (parent of the `app/` package): where `static/` and `templates/`
# live, both locally and in the Docker image (WORKDIR /app). Resolving from the
# module path keeps the app cwd-independent.
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Routers, static mounts, and the background scheduler are wired in by later
    stories; the skeleton boots, initializes the local database, and reports
    health.
    """
    # Resolve settings eagerly so a malformed environment surfaces at startup —
    # but absent keys are valid (features simply off), so this never raises on a
    # clean environment.
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Local file work only (DDL + WAL) — no network, so this is safe at
        # startup and under `docker run --network none`.
        init_db(settings.database_path)
        yield

    app = FastAPI(title="TTB Label Review", version="0.1.0", lifespan=lifespan)

    # Self-hosted assets (vendored USWDS + brand layer) served same-origin under
    # /static — no CDN, no Google Fonts (NFR-2/AR-8). Local file serving only.
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Server-rendered Jinja2 templates (no SPA, no build step). Template render is
    # a pure local operation — the 5s read-path contract (AR-5) is unaffected.
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Shared with the web routers (token gate, later screens) via app.state so the
    # startup config + one templates env are reused, never re-created.
    app.state.settings = settings
    app.state.templates = templates

    # Token gate (Story 1.5). App-wide guard: every non-exempt route requires a
    # valid access cookie once ACCESS_TOKEN is configured; `/healthz`, `/access`,
    # and `/static/*` stay exempt. Fail-open when unconfigured (clone-and-run).
    # A redirect/cookie compare only — no DB read on the deny path (AR-5 intact).
    @app.middleware("http")
    async def access_gate(request: Request, call_next):  # type: ignore[no-untyped-def]
        if (
            gate_enabled(settings)
            and not is_exempt(request.url.path)
            and not has_valid_access(request, settings)
        ):
            return RedirectResponse("/access", status_code=303)
        return await call_next(request)

    app.include_router(access_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness probe. Pure in-memory response — no DB, no network."""
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        """Render the vendored-USWDS app shell.

        Minimal demonstrator for Story 1.4 — pure template render, no DB read, no
        OCR/inference/model import, no network. Later stories (1.5 token gate, 4.x
        queue/review) replace the content block with the real screens.
        """
        return templates.TemplateResponse(request, "index.html")

    return app


app = create_app()
