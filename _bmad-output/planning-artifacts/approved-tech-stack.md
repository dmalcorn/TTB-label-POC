---
title: Approved Tech Stack — TTB COLA Label Specialist POC
status: approved
created: 2026-06-12
updated: 2026-06-12
versions_verified: 2026-06-12
---

# Approved Tech Stack — TTB COLA Label Specialist Workspace (POC)

The locked, version-pinned technology stack for the POC. Every version below was **verified against
its upstream source on 2026-06-12** (web-checked, not from memory). This file is the version-of-record
companion to:

- [`architecture.md`](architecture.md) — the **decision authority** (D1–D8) for *why* each choice was made.
- [`../../docs/tools-used.md`](../../docs/tools-used.md) — the per-tool **rationale, role, and local-vs-cloud** narrative.
- [`../../docs/outbound-calls-inventory.md`](../../docs/outbound-calls-inventory.md) — the firewall **classification** source.

> **Firewall classification key (PRD NFR-2 / addendum A2):** `none` = no network at all · `local` =
> localhost/on-prem only · `internal-endpoint` = `models-internal-endpoint` (cloud API in the POC,
> in-firewall endpoint in production; toggleable off via `LLM_ENABLED=false`).

> **Pinning policy:** pin to the **minor** line shown (`~=major.minor`) and let patch updates flow,
> except where a single patch is named. Exact pins + license verification are finalized at the
> dependency-pinning step (`tools-used.md` TODO-LIC). Model **weights** carry their own licenses,
> distinct from the framework that loads them.

---

## 1. Language & Runtime

| Component | Approved version (as of 2026-06-12) | Class | License | Source |
|---|---|---|---|---|
| **Python** | **3.13.x** (approved base); latest is **3.14.6**, 2026-06-10 | `none` | PSF | [python.org/downloads](https://www.python.org/downloads/) |

**Note — bump the Dockerfile base.** The architecture's Dockerfile sketch shows `python:3.11-slim`;
approve **`python:3.13-slim`** (mature wheels across every dependency below; 3.11 is still supported but
two lines behind). 3.14.6 is the absolute latest and is viable, but 3.13.x is the conservative pin.

---

## 2. Web / Application Layer

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **FastAPI** | **0.136.x** (0.136.3, 2026-05-23) | `local` | MIT | [pypi.org/project/fastapi](https://pypi.org/project/fastapi/) |
| **Uvicorn** (`uvicorn[standard]`) | **0.49.0**, 2026-06-03 | `local` | BSD-3 | [pypi.org/project/uvicorn](https://pypi.org/project/uvicorn/) |
| **Pydantic** (v2) | **2.13.4**, 2026-05-06 | `none` | MIT | [pypi.org/project/pydantic](https://pypi.org/project/pydantic/) |
| **Jinja2** | **3.1.6**, 2025-03-05 (still latest) | `none` | BSD-3 | [pypi.org/project/Jinja2](https://pypi.org/project/Jinja2/) |
| **python-multipart** | **0.0.32** (latest 0.0.x) | `none` | Apache-2.0 | [pypi.org/project/python-multipart](https://pypi.org/project/python-multipart/) |
| **APScheduler** | **3.11.2** (3.x stable) | `local` | MIT | [pypi.org/project/APScheduler](https://pypi.org/project/APScheduler/) |

**Note — APScheduler stays on 3.x.** The 4.0 line is still pre-release; pin the **3.11.x** stable line
(`~=3.11`). Sufficient for the in-process single-service sweep (D3).

---

## 3. Data Layer

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **SQLite** (engine) | **3.53.2**, 2026-06-03 | `local` | Public domain | [sqlite.org](https://sqlite.org/) |
| **`sqlite3`** (Python stdlib driver) | bundled with Python 3.13.x | `none` | PSF | stdlib |

**Note — stdlib bundles its own SQLite.** Python ships its own SQLite build via the `sqlite3` module;
3.53.2 is the upstream latest, but the runtime version is whatever the chosen Python base image bundles
(typically very recent on `python:3.13-slim`). No separate SQLite install needed. WAL mode enabled (D1).

---

## 4. OCR & Image Processing

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **Tesseract** (engine binary, via apt) | **5.5.2** (latest 5.5.x) | `none` | Apache-2.0 | [github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract/releases) |
| **pytesseract** (wrapper) | **0.3.13** | `none` | Apache-2.0 | [pypi.org/project/pytesseract](https://pypi.org/project/pytesseract/) |
| **PaddleOCR** (+ PP-OCRv5 models) | **3.4.0**, 2026-01-29 | `none`¹ | Apache-2.0 | [pypi.org/project/paddleocr](https://pypi.org/project/paddleocr/) |
| **OpenCV** (`opencv-python-headless`) | **4.13.0.92**, 2026-02-05 | `none` | Apache-2.0 (OpenCV) / MIT (packaging) | [pypi.org/project/opencv-python](https://pypi.org/project/opencv-python/) |

**Note — Tesseract via apt.** Installed as a system package in the Dockerfile (`apt-get install tesseract-ocr`);
the apt-provided version tracks the base image's distro (5.5.x on current Debian). The 5.5.2 upstream tag
is the reference latest.

¹ **PaddleOCR weights are pinned offline.** PaddleOCR downloads weights on first run; the Dockerfile bakes
them at build time so runtime is `none` (no network) — resolves `outbound-calls-inventory.md` TODO-2.
PaddleOCR 3.4.0 also ships **PaddleOCR-VL-1.5 (~0.9B VLM, 94.5% OmniDocBench)** — a strong candidate for the
local-VLM slot (§5).

---

## 5. LLM & Tracing

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **LangChain** (tracing only) | **1.3.7**, 2026-06-10 (core 1.4.6) | `local` | MIT | [pypi.org/project/langchain](https://pypi.org/project/langchain/) |
| **openai** (Python SDK) | **2.41.1**, 2026-06-10 | `internal-endpoint` | Apache-2.0 | [pypi.org/project/openai](https://pypi.org/project/openai/) |
| **anthropic** (Python SDK) | **0.79.0**, 2026-02-07 | `internal-endpoint` | MIT | [pypi.org/project/anthropic](https://pypi.org/project/anthropic/) |
| **google-genai** (Python SDK) | **2.8.0**, 2026-06-03 | `internal-endpoint` | Apache-2.0 | [pypi.org/project/google-genai](https://pypi.org/project/google-genai/) |
| **Ollama** (optional local-VLM runtime) | **0.30.7**, 2026-06-07 | `local` | MIT | [github.com/ollama/ollama](https://github.com/ollama/ollama/releases) |

**Notes:**
- **LangChain is local-only here** — used for tracing/timing capture into the local DB, no telemetry egress
  (`LANGCHAIN_TRACING_ENABLED=false` / local mode). Pin the **1.x** line.
- **Provider SDKs are the only `internal-endpoint` components.** They are configuration-gated
  (`LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`); `LLM_ENABLED=false` disables them entirely → zero-egress
  OCR-only path (FR-12).
- **Local VLM (zero-egress model option):** either **PaddleOCR-VL-1.5** (§4) or a small VLM served via
  **Ollama** (e.g. a GLM-OCR / Qwen3-VL-class model). Model weights carry their own licenses — confirm at
  selection (`tools-used.md` TODO-LLM-1).

---

## 6. UI / Design System

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **USWDS** (`@uswds/uswds`, compiled assets, self-hosted) | **3.13.x** (latest 3.x line) | `none` | Public domain (US Gov, CC0-class); bundled fonts OFL | [github.com/uswds/uswds/releases](https://github.com/uswds/uswds/releases) |

**Note — confirm the exact 3.x patch at vendoring.** The 3.x line is on a monthly cadence (3.10–3.13
released across 2025→2026); vendor the **latest tagged 3.x** compiled bundle (CSS/JS/fonts/icon-sprite) into
`static/uswds/` — **no CDN, no Node build** required. Pin the exact tag in `requirements`/lockfile notes when vendored.

---

## 7. Tooling (dev / quality)

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **ruff** (lint + format) | **0.15.x** (latest, 2026-06-11) | `none` | MIT | [pypi.org/project/ruff](https://pypi.org/project/ruff/) |
| **pytest** | **9.0.3**, 2026-04-07 | `none` | MIT | [pypi.org/project/pytest](https://pypi.org/project/pytest/) |

---

## 8. Container & Deployment

| Component | Approved version | Class | License | Source |
|---|---|---|---|---|
| **Docker Engine** (dev: Docker Desktop) | **29.x** (29.5.3, 2026-06) | host | Apache-2.0 (Moby) | [docs.docker.com/engine/release-notes/29](https://docs.docker.com/engine/release-notes/29/) |
| **Railway** (deploy: **Pro plan**) | managed PaaS (no version) — Dockerfile build, single service, Volume | host | — | [railway.app](https://railway.app/) |

**Note — Docker is the offline-pinned artifact.** The Dockerfile bakes native deps (Tesseract, OpenCV/Paddle
libs), pinned model weights, vendored USWDS, and seeded fixtures; built on Docker Desktop, deployed to Railway
Pro **from the Dockerfile (not Nixpacks)**.

---

## 9. Summary — full pin list (requirements sketch)

```text
# Python 3.13.x (Docker base: python:3.13-slim)
fastapi~=0.136
uvicorn[standard]~=0.49
pydantic~=2.13
jinja2~=3.1
python-multipart~=0.0.32   # POST form parsing for the token gate (Story 1.5)
apscheduler~=3.11
pytesseract~=0.3
paddleocr~=3.4
opencv-python-headless~=4.13
langchain~=1.3
openai~=2.41          # internal-endpoint (toggleable)
anthropic~=0.79       # internal-endpoint (toggleable)
google-genai~=2.8     # internal-endpoint (toggleable)
# dev
ruff~=0.15
pytest~=9.0
# system (apt, in Dockerfile): tesseract-ocr (5.5.x), libgl1, libglib2.0-0
# vendored (no pip): USWDS 3.13.x compiled assets → static/uswds/
# optional: ollama (local-VLM runtime) — only if the local VLM is served via Ollama
```

> Exact patch pins and per-package license confirmation are finalized at the dependency-pinning step
> (`tools-used.md` TODO-LIC). This table is the source of version-of-record; if any pin changes, update
> this file and note the date.
