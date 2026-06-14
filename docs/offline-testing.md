# Running the app offline (local dev server)

How to run the TTB Label Review app on your laptop **with no internet connection**.

The app is **zero-egress by design** (NFR-2 / AR-8), so being offline changes nothing
about how it runs:

- **Static assets are vendored** — USWDS + Treasury brand layer are served same-origin
  from `static/`; there is no CDN or Google Fonts call.
- **Data is local** — a SQLite file that **auto-seeds from baked fixtures** on first
  boot (`app/main.py` → `_seed_if_empty`); the seed reads `fixtures/` only.
- **OCR weights are baked into the Docker image** at build time, so the OCR engine
  loads them from disk with no download.
- **The LLM layer is off by default** (`LLM_ENABLED=false`) — the OCR-only / deterministic
  path is fully functional with no keys and no network.

There are two ways to run it. Pick based on whether you need the **OCR review pipeline**.

| | Option A — Docker | Option B — Host venv |
|---|---|---|
| Full review workflow (OCR → populated queue) | ✅ yes | ❌ no (queue stays empty) |
| Real Tesseract + PaddleOCR | ✅ baked into image | ❌ natives not installed host-side |
| Startup speed | slower (container) | ✅ instant |
| Good for | the real demo / review screens | shell, routes, templates, CSS, tests |

---

## Option A — Docker (recommended: full app + real OCR)

This runs the complete stack — including the background sweep that OCRs each submission
and promotes it `RECEIVED → READY_FOR_REVIEW`, so the **queue populates and the review
screens have data**.

**Prerequisite — the image must already be built.** Building needs the internet (apt
packages, pip, and the one-time PaddleOCR weight bake); *running* does not. You already
have a full OCR image:

```powershell
docker images ttb-label-poc
# ttb-label-poc:2.4   2.82GB   ...   <-- use the most recent tag
```

Run it (PowerShell), with your laptop offline:

```powershell
docker run --rm -e LLM_ENABLED=false -p 8000:8000 ttb-label-poc:2.4
```

Then open **http://localhost:8000** — the root redirects to the review **Queue**. Give
the background sweep a few seconds on first boot to OCR the seeded submissions; the
"N waiting" count then climbs and **Next Submission** serves a review screen.

Notes:

- `-p 8000:8000` uses Docker's local bridge network for the published port — that's
  loopback to your machine, **not** an outbound call. Your laptop having no internet is
  fine; the app never reaches out.
- `LLM_ENABLED=false` keeps it provably zero-egress (OCR-only). Leave it off when offline.
- The container filesystem is **ephemeral** — the DB resets each run (and re-seeds). For
  persistence across runs, mount a volume:

  ```powershell
  docker run --rm -e LLM_ENABLED=false -e DATABASE_PATH=/data/app.db `
    -v ttb-data:/data -p 8000:8000 ttb-label-poc:2.4
  ```

- To build a **fresh** image (needs internet, ~minutes — bakes the OCR weights):

  ```powershell
  docker build -t ttb-label-poc:dev .
  ```

---

## Option B — Host venv (fastest; app/UI/routes — but no OCR)

This boots the FastAPI app straight from the project venv (Python 3.14). It auto-seeds
the local DB from `fixtures/` (zero network) and serves every screen, the token gate,
and the static assets.

```powershell
# from the repo root, with your laptop offline:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open **http://localhost:8000** (redirects to `/queue`).

> [!IMPORTANT]
> **The queue will be empty on the host venv.** The OCR engines (`paddleocr`,
> `pytesseract`) are **not installed on the host** — they live only in the Docker image.
> The seed inserts submissions as `RECEIVED`, and without OCR the background sweep can't
> promote them to `READY_FOR_REVIEW`, so nothing reaches the queue. Use **Option A** when
> you need the populated review workflow.

To silence the sweep's repeated "OCR unavailable" errors in the console, disable it:

```powershell
$env:SCHEDULER_ENABLED = "false"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Option B is the right choice for: the app **shell**, **routing**, the **queue empty
state**, the **token gate**, **template/CSS** work, and running the **test suite**.

---

## Getting in (token gate)

- **No `ACCESS_TOKEN` set ⇒ the gate is open** (fail-open for clone-and-run). You go
  straight to the queue — this is the easy default for local dev.
- **`ACCESS_TOKEN` set ⇒ you're gated.** You'll land on `/access`; paste the token to
  enter. (`-e ACCESS_TOKEN=secret` for Docker, `$env:ACCESS_TOKEN="secret"` for the venv.)

---

## Running the tests offline

The host venv has every pure-Python dependency, so the full check suite runs offline:

```bash
bash scripts/ci.sh          # format → lint → typecheck → tests
```

(The OCR-native tests run only inside the Docker container; host-side they're skipped /
treated as missing imports. See `CLAUDE.md`.)

---

## Proving zero-egress (the NFR-2 smoke test)

To *prove* the app boots and serves with **no network capability at all**:

```powershell
docker run --rm --network none -e LLM_ENABLED=false ttb-label-poc:2.4
```

`--network none` strips the container of every network interface, so a successful boot
proves zero outbound dependency. Because there's then **no published port to browse**,
the container's built-in `HEALTHCHECK` probes `GET /healthz` from *inside* the container —
check it succeeds:

```powershell
# in another terminal:
docker ps                       # STATUS shows "(healthy)" once the probe passes
# or inspect the last probe result:
docker inspect --format '{{json .State.Health}}' <container-id>
```

This is a **verification**, not a usable server. For day-to-day offline use, run with `-p`
as in Option A — an offline laptop is fine because the app makes no outbound calls.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Port 8000 already in use | Use another port: venv `--port 8001`; Docker `-p 8001:8000`. |
| Host-venv queue is empty | Expected — no OCR on the host. Use Option A (Docker) for the review workflow. |
| Submissions stuck at "Processing" (host) | Same cause — the OCR sweep can't run host-side; expected. |
| Want to reset the data | Host: delete `data/app.db` (it re-seeds on next boot). Docker: just rerun (ephemeral), or remove the `ttb-data` volume. |
| Asked for a token unexpectedly | `ACCESS_TOKEN` is set in your environment — unset it for an open local gate. |
| Worried about egress | Keep `LLM_ENABLED=false`; confirm with the `--network none` smoke test above. |
