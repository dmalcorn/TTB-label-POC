# Trade-offs & Limitations — TTB COLA Label Specialist POC

*An honest accounting of the design trade-offs made in this AI-assisted TTB
**Certificate of Label Approval (COLA)** **Label Specialist** proof-of-concept, and of the
things it deliberately does **not** do. The take-home brief asks us to "document any
trade-offs or limitations" and states plainly that **"a working core application with
clean code is preferred over ambitious but incomplete features"**
([TTB-take-home-instructions.md](../ref-docs/TTB-take-home-instructions.md)). This
document is how we hold ourselves to that.*

**Beverage focus:** distilled spirits (27 CFR Part 5 + the Part 16 health warning),
with notes where beer (Part 7) and wine (Part 4) diverge.
**Author:** Diane · **Date:** 2026-06-11

**How to read this doc:** **Part A** records *design trade-offs* — each is a decision,
the option we chose, the alternative we rejected, and why. **Part B** records *known
limitations* — what the POC cannot or does not verify — each framed with its mitigation
and future-work path. Limitations are not apologies; several are deliberate,
regulation-aligned scope decisions that mirror TTB's own posture.

**Related docs:**
[approach.md](approach.md) *(the end-to-end design these trade-offs sit
inside)* ·
[assumptions.md](assumptions.md) *(records the IP/test-fixture caveat, the
reviewer-side design gap, and the seeded-data assumption)* ·
[ocr-llm-benchmarking-plan.md](ocr-llm-benchmarking-plan.md) *(the harness
that produces the PENDING cost/accuracy numbers referenced below)* ·
[outbound-calls-inventory.md](outbound-calls-inventory.md) *(the firewall-compliance
proof behind the "no cloud in the request path" trade-offs)* ·
[regulatory-rules-distilled-spirits.md](regulatory-rules-distilled-spirits.md) ·
[presearch.md](presearch.md). These companion deliverables this document cross-links
all exist on disk.

---

# Part A — Design Trade-offs

*Each row of reasoning: **Decision → Chosen → Alternative → Why.** These are the
choices a reviewer would otherwise have to reverse-engineer from the code. Read them as
"here is the cheaper, scope-appropriate option we took, and here is what we'd reach for
at production scale."*

## A1. Persistence — SQLite over PostgreSQL

- **Chosen:** **SQLite** as the POC datastore (single file, zero-config, ships in the
  repo, trivially seedable).
- **Alternative:** PostgreSQL (or the real .NET/Azure COLA database the production
  system uses, per [Marcus Williams' interview](../ref-docs/TTB-take-home-instructions.md)).
- **Why:** The POC only *reads* a **mock** COLA database and stores benchmark/timing
  rows; it has no concurrency, no multi-tenant, and no PII requirements (Marcus: "we're
  not storing anything sensitive for this exercise"). SQLite makes the deliverable
  clone-and-run with no database server to provision — directly serving the brief's
  "working prototype we can access and test." The schema
  ([database-schema.md](database-schema.md)) is written in portable SQL so the migration
  to Postgres is a connection-string change, not a redesign.
- **Trade-off accepted:** no concurrent writers, weaker type enforcement. Irrelevant at
  POC scale; called out here so the production gap is explicit.

## A2. Text extraction — local OCR over cloud Vision-LLM (the "firewall fork")

- **Chosen:** a **local, self-hosted core** — Tesseract + PaddleOCR/PP-OCRv5 OCR, OpenCV,
  and the deterministic rules engine — that is fully sufficient on its own, **plus** an
  LLM extraction/benchmark layer classified `models-internal-endpoint` (provider models in
  the POC, internal endpoints in production) that is **toggleable off**.
- **Alternative considered (and rejected):** making frontier cloud Vision-LLMs the *sole*
  extraction path. They lead on degraded images by a reported 3–4× lower character error
  rate ([research → Technical Trends](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)),
  but a model-only path has no zero-egress fallback.
- **Why this split:** the firewall blocks *external* domains, but the government hosts LLMs
  *inside* the firewall (revised posture — [PRD §10 NFR-2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/prd.md)
  / [addendum A2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/addendum.md)).
  So LLM calls are permitted in the live path *as a stand-in for those internal endpoints* —
  but the **local-first core must still stand alone**, so OCR + rules run zero-egress and the
  model layer toggles off to a provable OCR-only configuration (FR-12). This keeps the prior
  pilot's lesson honored (the local core never depends on a reachable model endpoint) while
  not pretending LLMs are forbidden. See [outbound-calls-inventory.md](outbound-calls-inventory.md).
- **Trade-off accepted:** with the model layer off, lower accuracy on the worst degraded
  images — mitigated by OpenCV preprocessing (deskew/glare/contrast) and the optional
  local-VLM fallback, and quantified by the in-pipeline benchmark so the accuracy cost is
  *measured*, not guessed.

## A3. Benchmarking — multi-OCR / multi-LLM bake-off over a single hard-coded engine

- **Chosen:** run **multiple OCR engines and multiple LLMs over the same extraction
  tasks**, capturing per-engine latency, extracted text, confidence, model name/full
  model ID, and timestamps into the database.
- **Alternative:** pick one OCR engine and one model up front and wire only that.
- **Why:** This is *more* work than the brief strictly requires, but it serves the
  **secondary goal** the brief explicitly invites — *"could potentially inform future
  procurement decisions"* ([Marcus Williams](../ref-docs/TTB-take-home-instructions.md)).
  The research shows the two chosen OCR engines have **complementary** strengths
  (Tesseract = light/clean/CPU-friendly; PaddleOCR = accurate on degraded/complex) and
  that "nothing wins on every scenario" — so picking one blind would be guessing. The
  benchmark turns a guess into data. See
  [ocr-llm-benchmarking-plan.md](ocr-llm-benchmarking-plan.md).
- **Trade-off accepted:** added engineering surface and harness complexity. Justified
  because the procurement-informing output is a primary value driver of the take-home,
  not gold-plating.

## A4. OCR placement — microservice over in-process

- **Chosen:** wrap each OCR engine behind a **uniform interface in a microservice**,
  invoked by background jobs.
- **Alternative:** call the OCR libraries **in-process** inside the web app.
- **Why:** A microservice boundary makes engines **swap/compare-able** without touching
  the app (the whole point of A3), isolates heavy native dependencies (PaddleOCR's stack)
  from the web tier, and lets OCR scale/parallelize independently for the pre-compute
  pipeline (A6). It mirrors the "wrap each engine behind a uniform interface" pattern the
  research recommends.
- **Trade-off accepted:** an extra deployable and an inter-process hop. At POC scale this
  is a local call, not a network cost; the architectural clarity is worth it.

## A5. Scope — cover all three beverage types (spirits worked deepest first)

- **Chosen:** support **all three** beverage types as first-class — distilled spirits (27 CFR
  Part 5), wine (Part 4), beer (Part 7) — each with its own review ruleset doc; implement
  and validate **distilled spirits** end-to-end first as the worked example.
- **Alternative:** spirits-only (narrower), or all three at equal implementation depth at once.
- **Why:** The decision (2026-06-11) is to cover all three so the POC isn't perceived as
  under-delivering on completeness, while spirits goes deepest first to guarantee a *working
  core* (the brief's stated preference). The type-keyed engine plus the parallel rulesets
  ([spirits](regulatory-rules-distilled-spirits.md) · [wine](regulatory-rules-wine.md) ·
  [beer](regulatory-rules-beer.md)) make the other types first-class, not afterthoughts. The
  cross-type **ABV rule differs in all three** (spirits: always; beer: usually optional; wine:
  only >14%) — fully documented in
  [label-requirements-by-type.md](label-requirements-by-type.md).
- **Trade-off accepted:** beer/wine labels aren't reviewed by the POC. The rules engine
  is structured to add them as data, not rewrites (see A8 on CFR-citations-as-data).

## A6. Performance — pre-compute over on-demand processing

- **Chosen:** **pre-compute** OCR + compliance analysis in a **background batch** at
  submission time, so opening "Next Submission" renders an already-analyzed record
  **instantly**.
- **Alternative:** run OCR and the rules engine **on demand** when the agent opens a label.
- **Why:** The brief's hardest performance constraint is **"if we can't get results back
  in about 5 seconds, nobody's going to use it"** — the lesson from the abandoned
  30–40-second pilot ([Sarah Chen](../ref-docs/TTB-take-home-instructions.md)). On-demand
  OCR cannot reliably hit 5 s; pre-compute moves the cost off the agent's interaction
  clock entirely. Note these are **two distinct clocks**: the multi-day *queue latency* TTB
  publishes is unrelated to the per-label *interaction latency* the 5-s rule targets — the
  pre-compute strategy targets the second. *(See the limitation in B4 on what the 5-s
  number does and doesn't yet prove.)*
- **Trade-off accepted:** work is done for submissions that may never be opened, and a
  freshly-arrived submission needs its background pass to finish before it's "instant."
  Acceptable: compute is cheap, and the batch runs ahead of the queue.

## A7. Access control — token gate over full authentication

- **Chosen:** a lightweight **token gate** on the public demo URL.
- **Alternative:** a full authentication/authorization system (login, roles, sessions).
- **Why:** The brief states **authentication is explicitly not a POC feature**. A token
  keeps the public demo from being driven by the open internet or bots, without building
  identity infrastructure that's out of scope and would compete for the time the brief
  wants spent on the working core.
- **Trade-off accepted:** no real user identity, roles, or audit-by-user. Correct for a
  prototype; flagged as a production prerequisite (federal SSO/PIV, role separation).

## A8. Status model — minimal status enum over a full workflow state machine

- **Chosen:** a **minimal `status` enum** plus `submitted_at` / `decided_at` timestamps
  and engine `processing_ms` — enough for time-to-decision, throughput, and the 5-s claim.
- **Alternative:** rebuild COLA's full **workflow state machine** (assignment routing,
  the 30-day correction clock, surrender/withdrawal transitions, etc.).
- **Why:** The discussion register resolved this directly: lightweight metrics **in
  scope**, a heavyweight workflow engine **out of scope**
  ([discussion-points.md §5](../ref-docs/discussion-points.md)). The POC mirrors TTB's
  *real* dispositions (**Approved / Needs Correction / Rejected**) for vocabulary fidelity
  without re-implementing the engine behind them. Related: CFR citations are stored **as
  data, not hard-code**, so the 2022 Part 5 renumbering (and future drift) is a data
  update, not a code change.
- **Trade-off accepted:** the POC doesn't enforce the 30-day clock or assignment routing.
  Documented as Phase-2 workflow integration.

---

# Part B — Known Limitations

*Honest scope boundaries. Each is stated plainly, then framed with **mitigation** (what
we do instead) and **future work** (how it closes). Several are deliberate — they match
TTB's own published posture — and are limitations only in the sense that the POC does not
over-claim.*

## B1. Font / type-size and physical dimensions are not verified — by design

- **Limitation:** the POC does **not** check character height or container dimensions
  against the CFR's millimeter minimums (spirits ≥2 mm / ≥1 mm, §5.53; warning 1/2/3 mm,
  §16.22).
- **Why it's a limitation:** absolute millimeters **cannot be derived from a photo without
  a physical scale reference** — there is no ruler in the frame
  ([Research-Findings.md §3](../ref-docs/Research-Findings.md)).
- **This matches TTB's own disclaimer.** COLAs Online itself disclaims testing
  dimensions/font size and places that burden on the applicant's sworn perjury
  certification. **The POC does the same thing TTB does**, deliberately — so this is a
  scope-alignment decision, not a gap. See the regulatory write-up
  ([regulatory-rules-distilled-spirits.md](regulatory-rules-distilled-spirits.md)).
- **Mitigation / future work:** *conditionally* checkable if a reliable scale arrives —
  e.g., the width × height (inches) COLAs Online already collects at upload → pixels-per-
  inch → mm, combined with OCR bounding-box character heights. Until a trustworthy scale
  is available, the engine reports **"cannot verify type size — physical dimensions
  unknown"** rather than guessing.

## B2. "Same field of vision" spatial inference is hard → flagged REVIEW, not FAIL

- **Limitation:** §5.63 requires brand name + alcohol content + class/type to share the
  **same field of vision** (one viewable side; for a cylinder, 40% of the circumference).
  The POC cannot reliably *prove* spatial co-location across a multi-image submission.
- **Why it's hard:** OCR yields text + bounding boxes *per image*, but "are these on the
  same physical side?" inference across separate front/back/neck images is non-trivial and
  error-prone.
- **Mitigation:** the engine performs a deterministic **presence** check and emits an
  advisory **REVIEW** verdict with a note, rather than asserting a confident pass/fail —
  honoring the brief's **"recommend, don't decide"** mandate. A REVIEW band also curbs the
  costliest error class, **false rejects** (see the regulatory risk assessment).
- **Future work:** layout/region analysis (PaddleOCR ships layout tooling) plus
  image-tag metadata (each upload is tagged brand/neck/back) to raise confidence toward an
  auto-determinable verdict.

## B3. The Government Warning is checked against the regulation, not a maker value (by design)

- **Clarification (not a limitation):** most checks are **app-field ↔ OCR-text** diffs (brand
  name, **class/type** — which *is* a maker-entered Product Class/Type field — ABV,
  name/address). The **Government Warning** is the one mandatory element the applicant does not
  type; it is verified from OCR against the **fixed 27 CFR §16.21 text**.
- **Why this is fine:** the warning's "expected" side is the *statute* (a constant), so it has
  a built-in ground truth and is the single fully-**deterministic** check (exact/normalized
  match enforcing the caps+bold "GOVERNMENT WARNING:" token). The UI signals that this one row
  compares against the *required text*, not a maker value, so the agent isn't hunting for a
  missing left-hand column.
- **Note:** an earlier draft wrongly treated class/type as un-captured; it is a maker-entered
  field and diffs application ↔ OCR like brand name (see
  `../ref-docs/Definition of Terms.txt`, "Product Class/Type").

## B4. Benchmark cost & accuracy numbers are PENDING real runs

- **Limitation:** the POC ships the **framework** for OCR/LLM speed-accuracy-cost
  benchmarking, **not** final figures. Concrete "$ per 1,000 verifications," accuracy
  rankings, and the empirical proof of the ~5-second interaction-latency claim are
  **PENDING actual benchmark runs**.
- **Why:** real numbers require running the harness over a representative fixture set on
  representative hardware (and GPU availability on government infra is itself uncertain —
  CPU-mode runs are needed too).
- **Mitigation:** the schema already captures everything needed to *compute* these once the
  runs happen — model name, full model ID, tokens, latency, confidence, timestamps. The
  **structure** is done; only the data collection remains. The local-OCR path's marginal
  cost is structurally ~$0 at the API level (compute-only, no token charges), which is
  itself a strong early procurement signal even before the cloud comparator runs.
- **Future work:** execute the harness and populate the comparison tables in
  [ocr-llm-benchmarking-plan.md](ocr-llm-benchmarking-plan.md).

## B5. Model-leaderboard numbers are indicative, not authoritative

- **Limitation:** the OCR/VLM accuracy figures cited in the research (e.g., PaddleOCR vs.
  Tesseract gaps, OmniDocBench scores, GLM-OCR/dots.ocr rankings) come from **fast-moving,
  partly vendor-adjacent 2026 leaderboards**.
- **Mitigation:** treat published model scores as **directional/indicative**. The POC's own
  benchmark harness (B4) exists precisely so decisions rest on **our** measured numbers on
  **our** label fixtures, not on third-party leaderboards.
- **Future work:** the local benchmark supersedes the indicative figures once it runs.

## B6. Label artwork is IP → private test fixtures only

- **Limitation:** the POC cannot redistribute real brand label artwork in the public repo
  or deployed demo.
- **Why:** COLA *records* are public government data, but the **label artwork itself is the
  brand owner's trademark / trade dress**
  ([Research-Findings.md §8](../ref-docs/Research-Findings.md)).
- **Mitigation:** real Public-COLA-Registry images are used as **private, local test
  fixtures only**; anything shown **publicly** uses **synthetic / AI-generated** labels
  (which the brief explicitly encourages). No PII or sensitive data is stored either, so
  the only real data-handling concern here is IP, not privacy.
- **Future work:** none required — this is a permanent operating constraint, recorded in
  [assumptions.md](assumptions.md).

## B7. The reviewer-side workflow is designed, not documented by TTB

- **Limitation:** the Label Specialist's queue, the "serve next submission" mechanics, and the
  review screen are **the POC's own design** — they are **not publicly documented by TTB**.
- **Why:** every available source (the COLAs Online manual, the live screens, the public
  registry) is the **applicant / public** side. The **reviewer interface is undocumented
  and unbuilt in public** ([Research-Findings.md §5](../ref-docs/Research-Findings.md)).
- **Mitigation:** this is reframed as the POC's **differentiator**, not a weakness — it
  fills the empty "federal reviewer review workspace" quadrant
  ([presearch.md](presearch.md)). The design uses the **well-documented applicant-side data
  model** (Form 5100.31 fields) as its trustworthy input, and mirrors TTB's real
  dispositions and terminology so it's recognizable to agents.
- **Future work:** validate the designed workflow with actual ALFD examiners.

## B8. No real COLA integration — standalone prototype (Phase 2)

- **Limitation:** the POC does **not** integrate with the live COLA system, STORRd, or any
  TTB production service.
- **Why:** integration carries its own authorization requirements and is **explicitly out
  of scope** — Marcus Williams: *"we're not looking to integrate with COLA directly … think
  of this as a standalone proof-of-concept."* The brief also confirms **API definition is
  Phase 2** ([discussion-points.md §5](../ref-docs/discussion-points.md)).
- **Mitigation:** the POC stands alone on a mock database with a clean read interface, so a
  future API can slot in behind it without reworking the UI or rules engine.
- **Future work:** Phase-2 API definition + integration hooks toward COLA.

## B9. Seeded dummy data only — no live application feed

- **Limitation:** the database is populated with **seeded dummy application data**, not a
  live feed of real submissions.
- **Why:** there is no firewall-safe live source, the POC's v1 scope **excludes image
  upload and field data-entry** (it only *reads* the mock COLA database), and real artwork
  is IP-restricted (B6).
- **Mitigation:** the seed set is built to exercise the rules engine deliberately —
  including known **fail** cases. (Notably, the brief's *own* sample label — "OLD TOM
  DISTILLERY" — is itself a fail case: it's **missing the name-and-address statement and
  the Government Warning**, per [Research-Findings.md §1](../ref-docs/Research-Findings.md)
  — a useful built-in test fixture.) Test-data sourcing is documented in
  [presearch.md](presearch.md).
- **Future work:** wire the Phase-2 API (B8) to a real submission feed.

## B10. The model extracts from the image alone — no OCR-assisted hybrid (deliberate)

- **Decision (2026-06-13):** the model-extraction path is **VLM-only** — the model is handed
  the **label image** and produces its **own** field reading. It is **never** given the OCR
  engines' text (or any other engine's output) as a hint. The OCR text feeds only the
  **deterministic** compliance engine (Field Match, Government Warning — Epic 3); the two
  extraction paths stay fully independent.
- **Why kept pure:** the benchmark's core question is *"how does a model compare to classical
  OCR at reading a label?"* Feeding the model OCR text would measure *"a model tidying up OCR,"*
  conflating the two and invalidating the head-to-head — and the model is meant to be a genuine
  **fallback when OCR is poor**, which only holds if it reads the label itself. So the POC
  benchmarks three clean configurations — **OCR-only**, **OCR + OpenCV preprocessing**, and
  **VLM-only** — each an independent extractor scored against ground truth.
- **Future consideration (explicitly NOT in this POC):** an **OCR + LLM hybrid** — e.g. classical
  OCR for the clean majority with a model on the degraded tail, or an LLM that reconciles/repairs
  OCR output (the COLAClear-style "CV + structured-LLM" architecture). It is a promising
  production pattern and a plausible accuracy/cost sweet spot, but it is deliberately left as
  future work so the POC's comparison stays honest and the firewall story stays simple. Recorded
  here so the write-ups can speak to "what we considered next," and reflected as a scope note in
  [ocr-llm-benchmarking-plan.md](ocr-llm-benchmarking-plan.md).
- **Trade-off accepted:** the POC does not demonstrate the (likely strong) hybrid configuration;
  it demonstrates the clean endpoints the hybrid would interpolate between, with the data to
  judge whether the hybrid is worth building.

---

## Summary — what to take away

| # | Trade-off / Limitation | Posture |
|---|---|---|
| A1 | SQLite over Postgres | Scope-appropriate; portable schema |
| A2 | Local OCR over cloud VLM | Forced by the firewall; benchmark quantifies the cost |
| A3 | Multi-OCR/LLM bake-off | Extra work, serves the procurement goal |
| A4 | OCR microservice | Swap-ability + isolation worth the extra hop |
| A5 | All three types covered; spirits worked deepest first | Completeness + a working core |
| A6 | Pre-compute | The structural answer to the 5-second rule |
| A7 | Token gate | Auth is explicitly out of scope |
| A8 | Minimal status enum | Metrics in, workflow engine out |
| B1 | No font/dimension check | **Deliberate — matches TTB's own disclaimer** |
| B2 | Field-of-vision → REVIEW | Recommend, don't decide |
| B3 | Government Warning checked vs the §16.21 text | Built-in ground truth (the statute); deterministic |
| B4 | Benchmark numbers PENDING | Framework shipped, data collection remains |
| B5 | Leaderboard scores indicative | Our own benchmark supersedes them |
| B6 | Artwork is IP | Fixtures private; public demo synthetic |
| B7 | Reviewer workflow designed | The POC's differentiator |
| B8 | No COLA integration | Phase 2 |
| B9 | Seeded dummy data | Built to exercise the engine, incl. fail cases |
| B10 | VLM reads the image alone — no OCR-assisted hybrid | Deliberate; keeps the benchmark honest, hybrid is future work |

**The through-line:** every limitation in Part B is either (a) a deliberate,
regulation-aligned scope decision that mirrors TTB's own posture, or (b) a clearly bounded
Phase-2 item with the framework already in place — consistent with the brief's preference
for **a working core over ambitious-but-incomplete features**.
