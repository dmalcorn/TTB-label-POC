# Approach — TTB COLA Label Specialist POC

**Status:** Central planning document (pre-implementation). · **Last updated:** 2026-06-11
**Audience:** TTB reviewers and the POC engineering team.

This is the central "Approach" document for the TTB **Certificate of Label Approval (COLA)**
**Label Specialist** proof-of-concept. It ties together the design decisions captured in the
discussion register and the domain research into one coherent technical plan, and points to
the sibling docs that detail each piece.

**Ground-truth sources (all local — no outbound calls):**

- [`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) — the decision
  register (esp. §1 scope, §3 constraints, §5 processing architecture, §6 OCR/LLM, §8 workflow).
- [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) — first-pass CFR /
  workflow / image findings.
- [Domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  — esp. *Domain Scale & Structure* (the two clocks), *Regulatory Requirements* (the
  implementation matrix), and *Technical Trends* (OCR engines, the firewall fork, image cleanup).

**Sibling docs this approach orchestrates:**

- [`regulatory-rules-distilled-spirits.md`](regulatory-rules-distilled-spirits.md) — the
  review ruleset (the verification engine's authority).
- [`label-requirements-by-type.md`](label-requirements-by-type.md) — mandatory elements by
  beverage type.
- [`database-schema.md`](database-schema.md) / [`data-dictionary.md`](data-dictionary.md) — the
  mock COLA data model the POC reads from.
- [`outbound-calls-inventory.md`](outbound-calls-inventory.md) — proof the deployed path makes
  no firewall-relevant outbound calls.
- [`applicant-workflow-distilled-spirits.md`](applicant-workflow-distilled-spirits.md) — the
  submitter side that produces the data we review.
- [`presearch.md`](presearch.md) — the comparable-software landscape and the POC's differentiation.
- [`requirements-mapping.md`](requirements-mapping.md) — mandatory vs. above-and-beyond requirements.

---

## 1. Overview & Guiding Principles

The POC builds the **Label Specialist's** (federal reviewer's) side of the COLA process — the
workspace the domain research confirms is undocumented and unbuilt in public, while the
applicant side is well-covered ([Research-Findings §5](../ref-docs/Research-Findings.md)). It
**reads** seeded application + label data from a **mock COLA database**, presents it to the
Label Specialist with as much automated assistance as possible, and captures their decision. It does
**not** capture new applications, upload images, or enter field data — that is the applicant
side, out of scope for v1 ([discussion-points §1](../ref-docs/discussion-points.md)).

Five principles drive every design choice below:

1. **Recommend, don't decide.** The software produces *advisory recommendations*; the human
   Label Specialist reviews them and makes the final call. The engine emits an advisory
   **PASS / REVIEW / FAIL** verdict per check; the human issues the real TTB disposition —
   **Approved / Needs Correction / Rejected**. These are two separate vocabularies and must
   never be conflated (see [§4](#4-verification-engine-design) and
   [`database-schema.md` §3](database-schema.md)). The engine **never auto-approves** — the
   human-in-the-loop is the safety control against false approves.

2. **Speed (the right clock).** The POC must beat the agency's abandoned 5–10-minute
   pre-screen pilot. It does so by **pre-computing** OCR + analysis in the background on
   submission, so opening the "Next Submission" screen is **instant** (~5 s interaction
   latency). This targets *per-label interaction latency*, which is a different clock from
   TTB's multi-day queue turnaround (see [§3](#3-the-pre-compute-pipeline-the-centerpiece)).

3. **Clarity for an older, varied-tech user base.** The reviewer population skews older with
   wide-ranging tech comfort ("something my mother could figure out"). The UI favors a single
   **"Next Submission"** button over a queue to pick from, **vertical stacked** field
   comparison (application value with the OCR/LLM value directly beneath it), prominent
   beverage-type display, a visible **checklist**, and clear in-UI help. (UI specifics are a
   separate UX doc; this approach only notes where architecture serves them.)

4. **Firewall-safe, local-first.** The deployed app is **local-first**: OCR (Tesseract +
   PaddleOCR), OpenCV preprocessing, the rules/compliance engine, and LangChain tracing all
   run **fully local**, and tracing never sends telemetry off-host. **LLM API calls *are*
   permitted in the deployed live path** — for field extraction and for benchmark-stat
   capture — where they **model government-internal LLM endpoints**: in a real TTB deployment
   these calls terminate inside the firewall, so the POC's cloud-API calls (OpenAI / Gemini /
   Anthropic) are a *stand-in* for internal services, not a firewall violation (revised by
   Diane during the PRD, 2026-06-11; see PRD §10 NFR-2 and addendum A2). Because OCR, rules,
   and preprocessing stay fully local, the **OCR-only path proves a zero-egress configuration
   exists** — with LLMs toggled off the pipeline still completes and the review screen still
   functions (FR-12). The outbound-call inventory remains a mandatory deliverable; every entry
   is classified **none / local / models-internal-endpoint**. Every component is itemized in
   [`outbound-calls-inventory.md`](outbound-calls-inventory.md).

5. **Minimal, honest scope.** Lifecycle is a **minimal status enum + timestamps**, not a
   heavyweight workflow state machine ([discussion-points §5](../ref-docs/discussion-points.md)).
   **Font / dimension size is NOT checked** — it cannot be derived from a photo without a
   physical scale reference, and TTB itself disclaims testing it. We document this as a
   deliberate, regulation-aligned limitation.

---

## 2. System Architecture (High Level)

```
              DEPLOYED (TTB environment — local-first; outbound = none/local/models-internal-endpoint)
   ┌───────────────────────────────────────────────────────────────────────────────────┐
   │                                                                                     │
   │   ┌────────────┐      ┌──────────────────┐        ┌───────────────────────────┐    │
   │   │  Web UI    │◄────►│   App server      │◄──────►│   Mock COLA database       │   │
   │   │ (USWDS,    │ HTTP │ (Python: FastAPI/ │  SQL   │  submissions, label_images │   │
   │   │  self-     │      │  Flask, read path)│        │  ocr_results, llm_results, │   │
   │   │  hosted)   │      └─────────┬─────────┘        │  field_comparisons,        │   │
   │   └────────────┘                │                  │  checklist_items,          │   │
   │     "Next Submission"           │ enqueue /        │  audit_events              │   │
   │     loads pre-computed result   │ read results     └─────────────┬─────────────┘   │
   │                                 ▼                                │ read/write       │
   │                       ┌───────────────────────┐                 │                  │
   │                       │  Background workers    │◄────────────────┘                  │
   │                       │  (pre-compute pipeline)│                                    │
   │                       │  ┌──────────────────┐  │     ┌───────────────────────────┐  │
   │                       │  │ OpenCV enhance   │  │     │  OCR microservice          │  │
   │                       │  │ OCR (Tesseract,  │──┼────►│  (optional; pluggable      │  │
   │                       │  │  PaddleOCR)      │  │     │   engines, uniform iface,  │  │
   │                       │  │ analysis/verify  │  │     │   per-engine timing)       │  │
   │                       │  └──────────────────┘  │     └───────────────────────────┘  │
   │                       │  ┌──────────────────┐  │                                    │
   │                       │  │ LLM extraction + │  │  ── classified models-internal-    │
   │                       │  │ benchmark capture│──┼────►   endpoint: in production these│
   │                       │  │ (OpenAI/Gemini/  │  │       terminate inside the TTB     │
   │                       │  │  Claude / local) │  │       firewall. Toggle-off ⇒ the   │
   │                       │  └──────────────────┘  │       OCR-only zero-egress config. │
   │                       └───────────────────────┘                                     │
   └───────────────────────────────────────────────────────────────────────────────────┘

   Firewall posture (PRD NFR-2 / addendum A2): OCR, OpenCV, rules, and LangChain tracing are
   fully local (tracing never egresses telemetry). LLM calls in the live path MODEL government-
   internal endpoints — the deployed POC's cloud-API calls stand in for in-firewall services.
   The OCR-only path (LLMs toggled off) is the provable zero-egress configuration (FR-12).
```

**Components:**

- **Web UI** — server-rendered or thin SPA, referencing **USWDS** patterns; all assets
  (CSS/JS/fonts/icons) **self-hosted**, no CDN. Lightweight token auth protects the public
  demo URL (auth is explicitly not a POC feature, per the brief). Read-only: it serves
  pre-computed results and records the Label Specialist's disposition.
- **App server** — a **Python** web service (FastAPI or Flask — see [§8](#8-python-vs-bash-recommendation)).
  Talks only to the local DB and local workers. No outbound internet calls.
- **Mock COLA database** — SQLite (likely POC default) or PostgreSQL; the schema and the three
  field categories (APPLICATION / OCR-EXTRACTED / FUTURE) are in
  [`database-schema.md`](database-schema.md).
- **Background workers** — the pre-compute pipeline: OpenCV enhancement → OCR (Tesseract +
  PaddleOCR) → LLM extraction + benchmark-stat capture → analysis/verification. They write
  `ocr_results`, `llm_results`, `field_comparisons`, `checklist_items`, roll up the engine
  verdict, and flip `status` to `READY_FOR_REVIEW`. LLM calls in this path **model
  government-internal endpoints** (PRD NFR-2 / addendum A2) and are classified
  `models-internal-endpoint` in the outbound-call inventory; they are **toggleable off**, and
  the OCR-only path is the provable zero-egress configuration (FR-12).
- **Optional OCR microservice** — wraps each OCR engine behind one uniform interface so engines
  can be swapped/compared with per-engine timing ([§6](#6-ocr-microservice-feasibility)).
- **Benchmark instrumentation** — because every Submission already flows through multiple OCR
  engines and LLMs, speed/accuracy/cost stats are captured **in the live pipeline** as a
  byproduct (the procurement study, PRD §4.5). A toggleable, **local-only** LangChain trace
  records model identity and timing into the DB; no telemetry leaves the host. (Cloud-API LLM
  calls here are the same `models-internal-endpoint` stand-in as the extraction path — they are
  not a separate walled-off harness; the firewall control is the OCR-only toggle-off, not
  exclusion of LLMs from the deployment.)

> **TODO (deployment topology).** Web framework (FastAPI vs. Flask) and DB (SQLite vs.
> PostgreSQL) are open. **Recommendation:** FastAPI + SQLite for the POC (async background-job
> friendliness; zero-config DB), portable to PostgreSQL via the CHECK-constrained-enum schema.

---

## 3. The Pre-Compute Pipeline (the centerpiece)

This is the structural answer to the abandoned pilot. Instead of running OCR + compliance
analysis **while the Label Specialist waits** (the 5–10-minute pilot's fatal flaw), the POC does all
heavy work **ahead of time, in the background, on submission**. When the Label Specialist clicks
**"Next Submission,"** everything — extracted text, field comparisons, checklist verdicts — is
**already computed and waiting in the database**.

### Step-by-step flow

```
  submission seeded into mock queue
            │  status = RECEIVED;  audit_events: SEEDED
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ BACKGROUND WORKER picks up new RECEIVED records (batch step)  │
  │            status → PROCESSING;  audit: OCR_STARTED           │
  └──────────────────────────┬──────────────────────────────────┘
                             ▼
  (1) IMAGE ENHANCE  ── OpenCV: deskew / perspective / glare / contrast (per image)
                             ▼
  (2) OCR (parallel) ── Tesseract  ┐
                        PaddleOCR  ┼─► ocr_results (text + confidence + latency_ms, per engine/image)
                        [PP-OCRv5] ┘     audit: OCR_COMPLETED
                             ▼
  (3) ANALYSIS / VERIFY ── reconcile OCR text → extract field values
                        ── field_comparisons (app value vs extracted value → MATCH/MISMATCH/…)
                        ── checklist_items (per CFR check → PASS/REVIEW/FAIL)
                        ── optional LOCAL LLM fallback when OCR confidence/match is poor
                             ▼
  (4) ROLL UP ── engine_verdict (PASS/REVIEW/FAIL) + processing_ms onto submissions
            │     status → READY_FOR_REVIEW;  audit: ANALYSIS_COMPLETED, READY
            ▼
  ════════════════════════════════════════════════════════════════
  LABEL SPECIALIST clicks "Next Submission"  ──►  serves a READY_FOR_REVIEW row INSTANTLY
            status → IN_REVIEW (audit: OPENED) … human decides … status → DECIDED
            (disposition: Approved / Needs Correction / Rejected; audit: DECIDED)
```

(Mirrors the seeded-vs-computed and write-order detail in
[`database-schema.md` §5](database-schema.md).)

### How it beats the abandoned 5-minute pilot

The pilot put the slow work (OCR + rule checking) **on the critical path of a waiting human**,
so the agent stared at a spinner for minutes and abandoned the tool. The POC moves that exact
work **off** the human's critical path and **before** it. By submission time the result is
pre-baked, so the only thing happening when the agent clicks "Next Submission" is a fast
database read of already-computed rows. The expensive computation still happens — it just
happens **when no one is waiting**.

### The two clocks (state this explicitly)

There are **two distinct latency metrics**, and the POC's speed claim is about the *second*
([domain research — Domain Scale & Structure](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)):

| Clock | What it measures | Typical magnitude | POC's relationship to it |
|---|---|---|---|
| **Queue latency** | End-to-end time from filing to disposition (agency backlog) | ~2–6 days (spirits); 85%-in-15-days goal | **Unchanged** by the POC; this is workforce/throughput, not UI. |
| **Interaction latency** | Time for the review screen + assist to appear once an agent opens a submission | **~5 s target** | **What the pre-compute pipeline optimizes.** This is the brief's "5-second" requirement. |

Stating this prevents anyone confusing the POC's ~5 s screen-load claim with TTB's published
multi-day turnaround — they are different clocks, and pre-computing in the background only
touches the interaction clock.

---

## 4. Verification Engine Design

The engine evaluates each mandatory CFR check and assigns it a verdict. The **authority** for
*which* checks exist and their citations is
[`regulatory-rules-distilled-spirits.md`](regulatory-rules-distilled-spirits.md) and
[`label-requirements-by-type.md`](label-requirements-by-type.md); CFR citations are stored as
**data** (`checklist_items.cfr_citation`) so the 2022 Part 5 renumbering — and future drift —
needs no code change.

### Four check strategies (the implementation matrix)

Each check is one of four types (matching the domain research's *deterministic vs. LLM* matrix
and COLAClear's validated CV + structured-LLM + hand-coded-rules architecture):

| Strategy | How it works | Example checks | Verdict tendency |
|---|---|---|---|
| **Deterministic** | String/regex + lookup tables; no LLM. | **Government Warning** (exact/normalized match, enforce caps+bold `GOVERNMENT WARNING:` token), ABV format, standards of fill, net-contents format | Confident PASS/FAIL |
| **Field-match (app ↔ OCR)** | Normalized string compare with a **tolerance band**. | Brand name, ABV *value*, name/address | PASS/REVIEW (tolerance guards false mismatch) |
| **Hybrid (rules + LLM-on-ambiguity)** | Rules first; local LLM only for ambiguous designations. | Class/type validity, conflicting designations, statement of composition | PASS/REVIEW/FAIL |
| **Flag-as-REVIEW** | Not auto-decidable → advisory note, defer to human. | Same-field-of-vision spatial inference, image-quality cases, font size (out of scope) | REVIEW |

**Why hybrid, not pure-deterministic or pure-LLM:** rule-bound elements (the Government
Warning above all) are deterministic and must stay that way — an LLM's nondeterminism is a
liability there. But genuinely ambiguous judgments (is "Kentucky Straight Bourbon Whiskey" a
valid class/type designation? do two labels carry conflicting designations?) benefit from LLM
reasoning. The engine uses the **cheapest correct tool per check** and reserves the LLM for
ambiguity and OCR-degradation fallback.

### The PASS / REVIEW / FAIL verdict model

- **PASS** — check satisfied; nothing flagged.
- **REVIEW** — not auto-decidable (ambiguity, missing scale reference, spatial inference, or a
  field that can't be verified) → advisory note, **defer to the human**. This is the
  false-reject safety valve: when unsure, the engine says REVIEW rather than FAIL.
- **FAIL** — a deterministic check failed (e.g., the Government Warning is missing or reworded).

Per-check verdicts live in `checklist_items`; the submission's `engine_verdict` is their
roll-up. **"REVIEW" is an engine band, not a disposition** — the TTB term for a fixable problem
is **Needs Correction**, and only the human chooses it
([`database-schema.md` §3.2](database-schema.md),
[Research-Findings §7](../ref-docs/Research-Findings.md)). **False rejects are the costliest
error** (needless correction cycles), so the tolerance band + REVIEW verdict exist specifically
to curb them — including the cross-type ABV trap and the "STONE'S THROW vs Stone's Throw"
over-strict-match case.

### Class/type and the Government Warning — how each is verified (important)

Two clarifications shape the comparison logic:

- **Class/type designation** *is* a **maker-entered** application field — the COLAs Online
  "Product Class/Type" code, typed or via lookup (`../ref-docs/Definition of Terms.txt`,
  "Product Class/Type"). So it is a normal **application ↔ OCR field-match**, exactly like
  brand name: the stacked comparison shows the maker's class/type above the OCR'd class/type
  with tolerance-based matching, and the designation's *regulatory validity* is an additional
  hybrid (rules + LLM-on-ambiguity) check layered on top.
- **Government Warning** is the one mandatory element the applicant does **not** type (they
  attest to the label artwork). It is verified from OCR against the **fixed 27 CFR §16.21
  text** — a fully **deterministic** check whose "expected" side is the *regulation* (a
  constant), enforcing the caps+bold "GOVERNMENT WARNING:" token. It never lacks a ground
  truth; it simply compares against the statute rather than a maker field. In the UI this row
  reads "required text vs. on-label text," PASS/FAIL.

In the data model, `class_type_designation` is a populated application column matched against
`ocr_class_type`; the warning has no application column because its ground truth is the
§16.21 constant, compared against `ocr_gov_warning_text`.

---

## 5. Processing States & Analytics

Lifecycle is deliberately **minimal** — a small `status` enum plus timestamps, **not** a
rebuilt COLA workflow engine ([discussion-points §5 RESOLVED](../ref-docs/discussion-points.md)).
Timestamps and an append-only `audit_events` timeline do the analytic heavy lifting.

**Status enum** (full detail in [`database-schema.md` §3.1](database-schema.md)):

`RECEIVED` → `PROCESSING` → `READY_FOR_REVIEW` → `IN_REVIEW` → `DECIDED`

The real TTB states `ASSIGNED` / `WITHDRAWN` / `SURRENDERED` are out of scope for a read-only
POC; `ASSIGNED` folds into `READY_FOR_REVIEW`/`IN_REVIEW`. The Label Specialist's **disposition**
(Approved / Needs Correction / Rejected) is a separate field set only at `DECIDED`.

**Metrics captured** (the lightweight substrate that supports the speed and procurement claims):

| Metric | Source | Supports |
|---|---|---|
| **Interaction latency** | screen-load timing vs. `READY_FOR_REVIEW` | the ~5 s claim (the right clock) |
| **Pre-compute time** | `submissions.processing_ms` (sum of OCR + analysis) | "the heavy work happened off the critical path" |
| **Per-OCR-engine latency + confidence** | `ocr_results.latency_ms`, `confidence`, `ran_on_cpu` | which OCR is faster/more accurate (procurement) |
| **Per-LLM latency + tokens + model identity** | `llm_results` (model name/id/full id, tokens, latency) | $/1,000-verifications cost analysis |
| **Time-to-decision / throughput** | `submitted_at` → `decided_at`; `audit_events` | workload analytics |
| **Verdict distribution** | `checklist_items.verdict`, `engine_verdict` | PASS/REVIEW/FAIL mix; queue-bucketing input |

These feed both the brief's benchmark deliverables and the optional queue-bucket idea
(very-likely-compliant vs. troublesome), which is derivable from `engine_verdict` **at query
time** — no extra column.

---

## 6. OCR Microservice — Feasibility & Proposal

[discussion-points §5](../ref-docs/discussion-points.md) asks to explore running OCR as a
**microservice** that makes engines easy to swap and compare. This is feasible and worthwhile;
the multi-engine timing data is itself a procurement deliverable.

**Proposal — a pluggable OCR service behind one uniform interface:**

- **Uniform interface.** Every engine implements the same contract, e.g.
  `ocr(image_bytes, opts) -> { engine_name, engine_version, text, word_boxes, confidence,
  latency_ms, ran_on_cpu, status }`. This is exactly the shape `ocr_results` stores
  ([`database-schema.md` §1.3](database-schema.md)), so adding an engine is a new adapter, not a
  schema change.
- **Pluggable engines.** Tesseract and PaddleOCR ship first; **PP-OCRv5** is a strong local
  candidate to add (a ~5M-param model reportedly rivaling far larger VLMs). New engines register
  by name.
- **Per-engine timing.** Each engine runs as its **own background job** on each image, recording
  `latency_ms` and whether it ran CPU-only (government infra has no guaranteed GPU — benchmark
  CPU mode too). Engines can run **in parallel** per image.
- **Deployment shape — TODO.** It can run **in-process** (a Python module with adapters) or as a
  **separate HTTP service** (localhost only — still zero outbound calls).
  **Recommendation:** start **in-process** with a clean adapter interface for the POC, and
  extract it to a localhost microservice only if engine isolation, language/runtime separation
  (PaddleOCR's heavier deps), or independent scaling justifies it. The uniform interface means
  this is a deployment decision, not a redesign.

Whether in-process or a service, it makes **no outbound calls** — models are pinned and shipped
offline ([`outbound-calls-inventory.md`](outbound-calls-inventory.md), TODO-2).

---

## 7. Image Enhancement Approach

Jenny Park's request — "fix glare / bad angle **without** bouncing the label back to the
submitter for a correction cycle" — is solvable with **open-source, local, non-LLM**
preprocessing. **No cloud call and no LLM are required**
([domain research — Technical Trends → Image-Quality Remediation](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md);
[Research-Findings §… image handling](../ref-docs/Research-Findings.md)).

A local **OpenCV (`cv2`)** stage runs **before OCR** on each image:

- **Deskew** — detect skew angle, rotate to horizontal.
- **Perspective correction** — rectify off-angle / photographed-at-a-tilt shots.
- **Glare / uneven-lighting mitigation** — adaptive thresholding, CLAHE contrast.
- **Denoise / binarize / grayscale** — standard OCR-prep cleanup.

These are cheap CPU operations that measurably lift OCR accuracy on exactly the "imperfect
image" cases the brief calls out, while keeping everything **on-prem**. Because enhancement is a
pre-OCR pipeline stage, a Label Specialist never has to send a usable-but-imperfect label back —
the system improves it in place. (`unpaper` is an optional complement for scanned sheets.)

> **Scope guard.** Enhancement aids *readability*; it does **not** enable font-size measurement
> (still out of scope — no physical scale reference; see [§1](#1-overview--guiding-principles)
> principle 5).

---

## 8. Python vs. Bash Recommendation

**Recommendation: Python** for all system components ([discussion-points §5 OPEN](../ref-docs/discussion-points.md)).

| Dimension | Python | Bash |
|---|---|---|
| **OCR / vision libraries** | First-class bindings: `pytesseract`, `paddleocr`, `opencv-python` (`cv2`) | Only by shelling out to CLIs; no structured access to bounding boxes/confidence |
| **LLM / tracing** | Native LangChain + provider SDKs; the benchmark harness is naturally Python | None |
| **Data handling** | Native DB drivers, JSON, dataframes; clean reads/writes to the schema | Brittle text munging; no real DB/JSON story |
| **Testability** | `pytest`, mockable units, CI-friendly | Hard to unit-test; mostly integration scripts |
| **Maintainability** | Typed, structured, readable for a team that inherits it | Fragile past a few dozen lines; poor error handling |
| **Web app** | FastAPI/Flask serve the read-only UI directly | Not a web-app language |

Bash is fine for a one-line glue script, but the POC's substance — OCR orchestration, the
verification engine, the pre-compute workers, the benchmark harness, and the web server — all
depend on libraries and data structures that are **Python-native and Bash-absent**. Building
this in Bash would mean shelling out to those same Python tools anyway, with worse error
handling and no testability. **Python end-to-end** is the clear choice; Bash is relegated to
trivial setup/run shims documented in the README.

---

## 9. Phasing

**Phase 1 — the POC (this deliverable):**

- Read-only Label Specialist workspace over the **mock COLA DB** (seeded fixtures, no upload/entry).
- **Pre-compute pipeline:** OpenCV enhancement → local OCR (Tesseract + PaddleOCR) → LLM
  extraction + benchmark capture (`models-internal-endpoint`, toggleable) → verification engine;
  background workers; instant "Next Submission".
- **Verification engine** with the four check strategies and the PASS/REVIEW/FAIL model, grounded
  in [`regulatory-rules-distilled-spirits.md`](regulatory-rules-distilled-spirits.md); distilled
  spirits primary.
- **Minimal lifecycle** (status enum + timestamps + `audit_events`) and the analytics metrics.
- **LangChain local tracing** (toggleable, no egress) and the **in-pipeline multi-OCR/multi-LLM
  benchmark** (model layer classified `models-internal-endpoint`, toggleable off to a zero-egress
  OCR-only path) to produce the accuracy/speed/cost comparison.
- USWDS-aligned, self-hosted UI behind lightweight token auth; full
  [`outbound-calls-inventory.md`](outbound-calls-inventory.md).

**Phase 2 — API + integration ([discussion-points §5](../ref-docs/discussion-points.md)):**

- An **API definition** exposing the Label Specialist capabilities and supporting **integration with
  existing COLA systems** (read from the real COLA database rather than the mock).
- Expand benchmark coverage; **promote the best-performing local OCR/model** based on collected
  stats (the procurement-informing goal).
- Optionally extract the OCR microservice to a standalone localhost service; normalize the
  model-identity tables; broaden beyond spirits if warranted.

---

## 10. Open Choices (TODO summary)

- **TODO (web framework / DB).** FastAPI vs. Flask; SQLite vs. PostgreSQL.
  **Recommendation:** FastAPI + SQLite for the POC, portable to PostgreSQL.
- **TODO (OCR service shape).** In-process adapters vs. localhost HTTP microservice.
  **Recommendation:** in-process behind a uniform interface; extract later if justified.
- **TODO (class/type validity confidence).** Class/type field-matches application ↔ OCR like
  brand name; the open question is how strictly to judge the *regulatory validity* of the
  designation. **Recommendation:** the field-match drives the verdict; flag REVIEW only when
  the designation isn't a recognized class/type.
- **TODO (queue buckets).** Splitting the queue into easy/hard for junior/senior staff.
  **Recommendation:** derive from `engine_verdict` at query time, not a new column.
- **TODO (LangChain local-only flags).** Final env-var names that force local tracing and
  disable cloud telemetry — see [`outbound-calls-inventory.md`](outbound-calls-inventory.md)
  TODO-3.
- **TODO (PP-OCRv5).** Add as a third OCR engine. **Recommendation:** yes, as a local-friendly,
  high-accuracy comparator in the benchmark.
