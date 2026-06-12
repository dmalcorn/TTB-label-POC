"""Token-gate entry/denial routes (Story 1.5).

`GET /access`  → State 1 entry form (autofocused token input).
`POST /access` → constant-time check; on success set the access cookie and
                 redirect to the protected landing (`GET /`, the Story 1.4 shell);
                 on failure re-render State 2 (clean denial) with HTTP 401.

No Submission/image/benchmark data is ever placed in this router's context — the
denial path returns the gate screen and nothing else (FR-25 no-data-leakage).
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.deps import ACCESS_COOKIE, has_valid_access, token_matches

router = APIRouter()

LANDING_PATH = "/"


def _render_gate(request: Request, *, denied: bool, status_code: int) -> HTMLResponse:
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "access.html", {"denied": denied}, status_code=status_code
    )


@router.get("/access", response_class=HTMLResponse)
def access_form(request: Request) -> Response:
    """Render the entry screen — or skip straight to the landing if already in."""
    settings = request.app.state.settings
    if has_valid_access(request, settings):
        return RedirectResponse(LANDING_PATH, status_code=303)
    return _render_gate(request, denied=False, status_code=200)


@router.post("/access")
def access_submit(request: Request, token: str = Form(default="")) -> Response:
    """Validate the submitted token; set the access cookie or deny cleanly."""
    settings = request.app.state.settings

    if not token_matches(token, settings):
        return _render_gate(request, denied=True, status_code=401)

    response = RedirectResponse(LANDING_PATH, status_code=303)
    response.set_cookie(
        ACCESS_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        # Secure only over HTTPS (Railway), so the cookie still works on local http.
        secure=request.url.scheme == "https",
    )
    return response
