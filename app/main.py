"""FastAPI application factory for the TTB COLA Label Specialist POC.

Story 1.1 establishes the deterministic, offline-pinned skeleton: an app factory
plus a `GET /healthz` liveness route. Startup performs ZERO network I/O, no OCR,
no model import — this is what makes the `docker run --network none` boot
(AC-5 / AR-8) and the 5-second read contract (AR-5) hold from day one. Later
stories mount the routers, static assets, and the APScheduler sweep here.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.db.connection import connect, init_db
from app.db.seed import seed
from app.pipeline.scheduler import shutdown_scheduler, start_scheduler
from app.web.deps import gate_enabled, has_valid_access, is_exempt
from app.web.routes_access import router as access_router
from app.web.routes_benchmark import router as benchmark_router
from app.web.routes_queue import router as queue_router
from app.web.routes_review import router as review_router

# Project root (parent of the `app/` package): where `static/` and `templates/`
# live, both locally and in the Docker image (WORKDIR /app). Resolving from the
# module path keeps the app cwd-independent.
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

logger = logging.getLogger(__name__)


def _seed_if_empty(db_path: str) -> None:
    """Populate an empty database with the fixture corpus (Story 1.6, AC-2).

    A fresh Railway Volume starts empty; without this the gated landing would sit
    on an empty DB. Runs Story 1.3's transactional ``seed()`` ONLY when
    ``submissions`` has zero rows, so a redeploy never clobbers in-Volume state
    mid-session (full reset is Epic 6's explicit ``POST /reset``). Bootstrap work
    at startup like ``init_db`` — never on a request/render path, so the 5-second
    read contract (AR-5) is intact. Reads baked-in fixtures + writes the local
    SQLite file only: zero egress, so ``docker run --network none`` still boots.

    Boot-degraded posture (code review 2026-06-12): ``seed()`` is transactional
    (rolls back on failure), but a fixture/data error must NOT take the whole
    service down. We swallow + log any seed failure so the app still boots on an
    empty DB — a reachable demo beats a Railway ``ON_FAILURE`` crash-loop. The
    ``count == 0`` guard means the next clean boot retries the seed.
    """
    with connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    if count == 0:
        try:
            seed(db_path)
        except Exception:
            logger.exception(
                "Seed-if-empty failed; booting on an empty database. "
                "The next clean startup will retry the seed."
            )


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
    async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
        # Local file work only (DDL + WAL) — no network, so this is safe at
        # startup and under `docker run --network none`.
        init_db(settings.database_path)
        # Fill a fresh (empty) Volume DB with the seeded corpus so the gated
        # landing never sits on an empty DB (AC-2). Idempotent + startup-only.
        _seed_if_empty(settings.database_path)
        # Start the in-process background sweep AFTER init + seed so it always
        # finds a ready DB (Story 2.2). In-process, zero egress — the
        # `docker run --network none` boot still holds. Guarded by
        # `scheduler_enabled` so a TestClient lifespan can opt out.
        start_scheduler(app_)
        try:
            yield
        finally:
            shutdown_scheduler(app_)

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
    # Queue screen & Next Submission (Story 4.1). Carries no exemption, so the
    # access_gate middleware above protects /queue and /next like every screen.
    app.include_router(queue_router)
    # Review Workspace shell (Story 4.3) — GET /review/{id}, the target POST /next
    # redirects to. A pure pre-computed DB read (AR-5); no exemption, so the token
    # gate protects it too.
    app.include_router(review_router)
    # Benchmark Report (Story 5.4) — GET /benchmark, the evaluator procurement study.
    # A pure pre-computed DB read (AR-5) that CONSUMES the 5.2 scorer + 5.3 cost stats;
    # carries no exemption, so the token gate protects it like every screen.
    app.include_router(benchmark_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness probe. Pure in-memory response — no DB, no network."""
        return {"status": "ok"}

    @app.get("/")
    def index() -> RedirectResponse:
        """Send the app root to the review Queue — the reviewer's home screen.

        Story 1.4 served a static USWDS shell demonstrator here; Epic 4 shipped the
        real screens, so the root now redirects an authenticated reviewer straight
        to /queue. The token gate above still bounces an unauthenticated request to
        /access first. Pure redirect — no DB read, no OCR/model, no network (AR-5).
        """
        return RedirectResponse("/queue", status_code=303)

    return app


app = create_app()
