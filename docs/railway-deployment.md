# Railway Deployment — TTB-label-POC

Project-specific Railway operating notes for this POC. Distilled from the generic shipyard
`railway-setup-guide.md` — only the parts that apply to **this** app, plus the live project
identity captured 2026-06-12. This POC is a **single FastAPI service, SQLite-on-Volume,
Dockerfile build** — there is **no Postgres, Mailpit, Redis, Celery, email, or Node/Next.js**,
so all of that guidance from the source guide is intentionally dropped.

> Authoritative deploy decisions live in `architecture.md` (D1/D7, §Deployment & Dev Strategy)
> and Story 1.6. This file is the **Railway CLI/API operations** companion to those.

---

## Live project identity (captured 2026-06-12)

| Thing | Value |
|---|---|
| **Workspace** | `dmalcorn's Projects` |
| **Project** | `TTB-label-POC` — id `1f2da48a-1def-4b8a-b74d-5726d927e306` |
| **Environment** | `production` — id `460380a5-0f6f-4832-b3e9-2e506c6c4c2a` |
| **Service** | `ttb-web` — id `5fbc74c4-da0c-4aba-88f3-a0c4c12ff601` |
| **GitHub repo** | `dmalcorn/TTB-label-POC` (branch `main`, auto-deploy on push) |
| **Public URL** | `https://ttb-label-poc-production.up.railway.app` (targetPort **8000**) |
| **Builder** | `DOCKERFILE` at `/Dockerfile` (✅ not Nixpacks — matches D1) |
| **Volume** | **none attached yet** — Story 1.6 AC-1 must add one for `DATABASE_PATH` |

> **Naming note (renamed 2026-06-12):** project and service were initially swapped (project
> `TTB-label-web`, service `TTB-label-POC`). Renamed via `projectUpdate`/`serviceUpdate` to the
> table above. The public URL kept its original `ttb-label-poc-…` prefix (Railway doesn't
> regenerate domains on rename). Internal hostnames are a non-issue here — one service, no
> cross-service reference variables.

---

## CLI auth & this-machine quirks (CLI 4.59.0)

- **Operator owns `railway login`** (browser OAuth). Once logged in, Claude inherits the
  session for every CLI command. `railway whoami` → `dianealcorn@gmail.com`. If any command
  returns `Unauthorized. Please run 'railway login' again`, that's the operator's cue — Claude
  cannot drive the OAuth flow.
- **GraphQL token field:** use `user.accessToken` from `C:\Users\Diane\.railway\config.json`
  (43 chars). **`user.token` is empty** on this CLI version — the generic guide's `['user']['token']`
  is stale here. Endpoint `https://backboard.railway.com/graphql/v2`, header
  `Authorization: Bearer <accessToken>`.
- **`railway add` can return `Unauthorized`** even when `whoami`, `variables --set`, `logs`,
  and direct GraphQL all succeed on the same session. Workaround: create/mutate services via
  GraphQL (`serviceCreate` / `serviceUpdate`) rather than `railway add`. We likely won't need
  `add` at all — there's one service and it already exists.
- **PowerShell:** shell state does not persist between tool calls — reload the token each
  invocation, and single-quote any `${{...}}` reference value so PowerShell doesn't expand it.

## Link-state drifts — re-link before every mutating command

The CLI's project link can revert silently between shell invocations. **Chain
`railway link --project TTB-label-POC && <command>` in one shell call**, or verify first:

```bash
railway status --json | python -c "import json,sys; print(json.load(sys.stdin)['name'])"
# expect: TTB-label-POC
```

## Single-attempt-then-verify (the most important rule)

For any mutating command (`railway redeploy`, `railway variables --set`, GraphQL mutations),
treat empty/ambiguous output as **"unknown outcome," never "failure."** Run **once**, then
verify with `railway status --json` before any retry. Silent success is normal:

| Command | Silent-success behavior |
|---|---|
| `railway redeploy --yes` | No output. Deploy was triggered. Confirm via status/logs. |
| `railway variables --set 'X=Y'` | No output. Var was set. Verify with `--kv \| grep X`. |
| `railway link --project <p>` | No output. CLI is linked. `railway status` confirms. |

> We have no Postgres/Mailpit, so the duplicate-billable-DB hazard from the source guide is
> low — but the discipline still applies to redeploys and variable sets.

## Renaming the project & service

- **Renaming a service does NOT change its internal `*.railway.internal` hostname** (set at
  creation). **Irrelevant for us** — one service, no cross-service references — so a rename is
  purely cosmetic/dashboard ergonomics and safe.
- Rename via the dashboard (Settings → rename) or the `serviceUpdate` GraphQL mutation:

```bash
RAILWAY_TOKEN=$(python -c "import json; print(json.load(open(r'C:\\Users\\Diane\\.railway\\config.json'))['user']['accessToken'])")
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"mutation { serviceUpdate(id: \"5fbc74c4-da0c-4aba-88f3-a0c4c12ff601\", input: { name: \"<new-name>\" }) { id name } }"}'
```

- **Project rename** is dashboard-only ergonomics too (Project Settings → Name); no hostname
  or reference-variable impact for this single-service project.

## `$PORT` reconciliation (Story 1.6 AC-1, Task 1)

Railway injects `$PORT` (defaults to **8080** if unset). Our public domain `targetPort` is
**8000** and the Dockerfile `CMD` hardcodes `--port 8000`. The first build deployed SUCCESS/
RUNNING, so they currently agree — but Story 1.6 must make the start command honor `$PORT`
(`uvicorn app.main:app --host 0.0.0.0 --port $PORT`) and keep `8000` as the compose/local
default, so a future Railway `PORT` change can't silently 404 the edge.

## Failed-first-build → Railpack lock (we dodged it — keep dodging)

If a service's **first** deploy falls back to Railpack and fails, subsequent deploys can ignore
Dockerfile config for the service's lifetime (fix = delete + recreate with the Dockerfile env
baked in). **Our first build already used `DOCKERFILE` and succeeded**, so we're clear — just
don't introduce a Nixpacks/Railpack path. `railway.toml` pinning `builder = "DOCKERFILE"`
(Story 1.6 AC-1) locks this in.

## Environments, not projects

If a staging/preview env is ever needed, use Railway's **environments** within this one project
(`railway environment <name>`) — never a second project. Cross-project reference variables don't
work; cross-environment ones do.

## Secrets hygiene

`railway variables --service <svc> --kv` output **contains secrets** (`ACCESS_TOKEN`, any LLM
keys). Never paste full output into chat, logs, or PR/commit text — pipe through `grep` for the
one name you need. Secrets are never logged by the app either (firewall posture, NFR-2).

## What stays operator-driven (not Claude's job)

- `railway login` (browser OAuth) and API-token rotation.
- Linking the service to the GitHub repo (already done — auto-deploys on push to `main`).
- Billing / plan changes; custom domains.

If a CLI step fails on stale auth or a missing GitHub grant, **stop and ask the operator** —
don't engineer a workaround.

---

## Quick command crib

```bash
# Link + status (chain to beat link drift)
railway link --project TTB-label-POC && railway status --json

# Tail live logs
railway logs --service ttb-web

# Set an env var (single-attempt-then-verify)
railway variables --service ttb-web --set 'LLM_ENABLED=false'
railway variables --service ttb-web --kv | grep '^LLM_ENABLED='

# Trigger a clean redeploy
railway redeploy --service ttb-web --yes
```

_Last updated: 2026-06-12 — captured during Story 1.6 prep._
