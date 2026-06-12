# Requirements Mapping — TTB COLA Label Review POC

*Traceability document for the take-home project. Maps every mandatory requirement in
the brief to how this proof-of-concept (POC) satisfies it, separates Diane's
above-and-beyond additions from the brief's minimum, and confirms the core
"recommend, don't decide" alignment.*

**Author:** Diane · **Date:** 2026-06-11

**Ground-truth sources:**
- The brief — [`ref-docs/TTB-take-home-instructions.md`](../ref-docs/TTB-take-home-instructions.md)
- Decision register — [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md)

**Related planning docs (on disk — see [discussion-points §14](../ref-docs/discussion-points.md)):**
- [`docs/approach.md`](approach.md) — overall approach
- [`docs/presearch.md`](presearch.md) — comparable-software landscape
- [`docs/tools-used.md`](tools-used.md), [`docs/assumptions.md`](assumptions.md), [`docs/tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md)
- Existing research: [`ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md)

> **How to read the Status column:** **Planned** = committed in the design and traced to a
> deliverable but not yet built; **Designed** = decision locked in discussion-points;
> **TODO** = mapping or implementation choice still open.

---

## 1. Project Goals

The brief is a job-application take-home (see [`ref-docs/TTB-take-home-instructions.md` L1](../ref-docs/TTB-take-home-instructions.md)).
Two goals are explicit in the decision register ([discussion-points §1, L42–46](../ref-docs/discussion-points.md)):

- **Primary goal — complete the take-home and demonstrate the ability to write working
  code using AI.** This is the success condition that matters: a working, deployed core
  application with clean code. The brief itself states *"A working core application with
  clean code is preferred over ambitious but incomplete features"*
  ([brief L113](../ref-docs/TTB-take-home-instructions.md)).

- **Secondary goal — produce information that could inform a future software project,
  including procurement/purchase decisions.** The brief explicitly invites this framing:
  *"Think of this as a standalone proof-of-concept that could potentially inform future
  procurement decisions"* ([brief L35](../ref-docs/TTB-take-home-instructions.md)). This goal
  justifies the benchmarking/cost-analysis work in §3 below.

**Is there a third goal? My read: no separate third goal — but a clear *strategy* binds the
two.** The above-and-beyond work (multi-OCR/multi-LLM benchmarking, cost analysis, tracing)
is not an independent goal; it is the *mechanism* by which the secondary goal is met, and it
*demonstrates* the primary goal (showing engineering judgment and AI-assisted delivery). One
candidate for a "third goal" — differentiation as an **Label Specialist-side** (federal-reviewer)
tool rather than an applicant-side pre-screen — is better described as the POC's *scope thesis*
([discussion-points §1 L38–41](../ref-docs/discussion-points.md)) than as a goal of its own.
**Conclusion: two goals, with benchmarking/landscape work serving the secondary goal.**
*(TODO: confirm in `approach.md` when written.)*

---

## 2. Mandatory Requirements (from the brief)

These are the requirements the brief actually demands. The brief is light on hard
mandates — it grants free choice of stack ([L63](../ref-docs/TTB-take-home-instructions.md))
and prizes a clean working core over scope ([L113](../ref-docs/TTB-take-home-instructions.md)) —
so "mandatory" here means *core functional checks the stakeholders named*, plus the two
formal deliverables and the evaluation criteria.

### 2A. Core functional requirements

| # | Requirement | Source (brief) | How the POC satisfies it | Status |
|---|---|---|---|---|
| 1 | **Match label artwork against the application** (the core review action) | Sarah Chen, [L15–17](../ref-docs/TTB-take-home-instructions.md) | OCR/LLM extracts label fields; UI shows each application field with extracted value stacked beneath it for direct comparison; discrepancies highlighted. | Planned |
| 2 | **Brand-name match** | [L15](../ref-docs/TTB-take-home-instructions.md) ("Brand name matches? Check.") | Normalized string comparison (case/whitespace-insensitive) so "STONE'S THROW" vs "Stone's Throw" is recognized as a match, surfaced for human confirmation — Dave Morrison's nuance case, [L47](../ref-docs/TTB-take-home-instructions.md). | Planned |
| 3 | **ABV / alcohol-content match** | [L15](../ref-docs/TTB-take-home-instructions.md) ("ABV is correct? Check.") | Numeric ABV extracted and compared to application value; proof shown where present (e.g. "45% Alc./Vol. (90 Proof)", [L89](../ref-docs/TTB-take-home-instructions.md)). | Planned |
| 4 | **Government Health Warning Statement present and exact** | [L15, L57, L77](../ref-docs/TTB-take-home-instructions.md) (mandatory on all alcohol beverages; must be word-for-word; "GOVERNMENT WARNING:" all-caps + bold) | Deterministic exact/normalized match enforcing the all-caps "GOVERNMENT WARNING:" token; catches title-case and reworded warnings (Jenny Park, [L57](../ref-docs/TTB-take-home-instructions.md)). See [discussion-points §7 L150–151](../ref-docs/discussion-points.md). | Planned |
| 5 | **~5-second performance** (results back in about 5s or "nobody's going to use it") | Sarah Chen, [L19](../ref-docs/TTB-take-home-instructions.md) (bold) | **Pre-compute pipeline:** OCR + advisory compliance run in background jobs at submission time, so the review screen renders instantly when the Label Specialist pulls the next item. See [discussion-points §5 L99–105](../ref-docs/discussion-points.md). | Planned |
| 6 | **Ease of use for older / varied tech-comfort users** ("something my mother could figure out"; clean, obvious, no hunting for buttons; half the team over 50) | Sarah Chen, [L21](../ref-docs/TTB-take-home-instructions.md) | USWDS-based UI; single "Next Submission" button; vertical stacked comparison; visible checklist; chevron status bar. See [discussion-points §9 L188–212](../ref-docs/discussion-points.md). | Planned |
| 7 | **Government Warning verification is the highest-value, trickiest check** | Jenny Park, [L57](../ref-docs/TTB-take-home-instructions.md) | Covered by #4; called out separately because the brief stresses its difficulty. | Planned |
| 8 | **Handle the sample distilled-spirits label fields** (Brand, Class/Type, ABV, Net Contents, Government Warning) | [L85–91](../ref-docs/TTB-take-home-instructions.md) | Data model and extraction cover these fields; POC focuses on distilled spirits. See [discussion-points §7 L158–160](../ref-docs/discussion-points.md). | Planned |
| 9 | **Operate under federal constraints** (no reliance on blocked outbound cloud APIs; no sensitive data stored) | Marcus Williams, [L37, L39](../ref-docs/TTB-take-home-instructions.md) | No-outbound-call deployed path; local OCR (Tesseract/PaddleOCR) and OpenCV; LLM/LangChain optional and disablable; documented outbound-call inventory. See [discussion-points §3 L68–80](../ref-docs/discussion-points.md), §6 L126–129. | Designed |

**Wishlist (brief-requested but explicitly "would be huge" / "out of scope for a prototype"):**

| # | Requirement | Source (brief) | How the POC addresses it | Status |
|---|---|---|---|---|
| 10 | **Batch uploads** (importers dump 200–300 applications at once) | Sarah Chen, [L23](../ref-docs/TTB-take-home-instructions.md) | Reframed as an *applicant-side* feature: 300 apps with one signature remain 300 individual submissions with no Label Specialist-side impact; the Label Specialist queue feeds them one at a time. Addressed in the write-up + a `batch-template.csv`. See [discussion-points §13 L250–255](../ref-docs/discussion-points.md). | Planned (write-up) |
| 11 | **Imperfect-image handling** (glare, bad angle, poor lighting) | Jenny Park, [L59](../ref-docs/TTB-take-home-instructions.md) ("maybe out of scope") | Local OpenCV pre-processing (deskew, perspective correction, glare/contrast) — no LLM/cloud call. See [discussion-points §10 L221–223](../ref-docs/discussion-points.md). | Planned |

### 2B. Deliverables (formal)

| # | Deliverable | Source (brief) | How the POC satisfies it | Status |
|---|---|---|---|---|
| D1 | **Source code repository** (all source code) | [L97–98](../ref-docs/TTB-take-home-instructions.md) | Git repo with full source. | Planned |
| D2 | **README with setup and run instructions** | [L99](../ref-docs/TTB-take-home-instructions.md) | README with setup/run steps, referencing each `docs/*.md`. See [discussion-points §14 L268–269](../ref-docs/discussion-points.md). | Planned |
| D3 | **Brief documentation of approach, tools used, assumptions made** | [L100](../ref-docs/TTB-take-home-instructions.md) | `docs/approach.md`, `docs/tools-used.md`, `docs/assumptions.md` (+ `tradeoffs-and-limitations.md`, `presearch.md`) — all on disk. See [discussion-points §14 L261–266](../ref-docs/discussion-points.md). | Done |
| D4 | **Deployed application URL** (working prototype reviewers can access and test) | [L101–102](../ref-docs/TTB-take-home-instructions.md) | Publicly reachable deployed app, protected by lightweight token auth so only an evaluator can interact (auth is not a graded POC feature). See [discussion-points §3 L78–80](../ref-docs/discussion-points.md). | Planned |
| D5 | **Document trade-offs / limitations** | [L113](../ref-docs/TTB-take-home-instructions.md) | `docs/tradeoffs-and-limitations.md`. | Planned |

### 2C. Evaluation criteria (how the brief grades the work)

| # | Criterion | Source (brief) | How the POC targets it | Status |
|---|---|---|---|---|
| E1 | Correctness & completeness of core requirements | [L106](../ref-docs/TTB-take-home-instructions.md) | All four core checks (#1–4) implemented and demonstrable. | Planned |
| E2 | Code quality & organization | [L107](../ref-docs/TTB-take-home-instructions.md) | Modular pipeline (in-process OCR adapters behind one uniform interface, swappable engines); clean repo layout. See [discussion-points §5 L110–115](../ref-docs/discussion-points.md). | Designed |
| E3 | Appropriate technical choices for the scope | [L108](../ref-docs/TTB-take-home-instructions.md) | Local-first stack honoring the firewall constraint; LLM optional and toggleable; Python end-to-end (FastAPI + Jinja2 + SQLite + APScheduler), locked in the architecture. | Designed |
| E4 | User experience & error handling | [L109](../ref-docs/TTB-take-home-instructions.md) | USWDS UI, in-UI help/knowledge base, discrepancy highlighting, image-quality fallback. See [discussion-points §9 L211–212](../ref-docs/discussion-points.md). | Planned |
| E5 | Attention to requirements | [L110](../ref-docs/TTB-take-home-instructions.md) | This traceability doc is the evidence of attention-to-requirements. | Planned |
| E6 | Creative problem-solving | [L111](../ref-docs/TTB-take-home-instructions.md) | Pre-compute strategy beating the abandoned vendor pilot; checklist reframing of Jenny's printed sheet; queue buckets by type/difficulty. | Planned |

---

## 3. Above-and-Beyond Requirements (Diane's additions)

**Everything in this table is beyond the brief's minimum.** It is included to serve the
*secondary goal* (inform future procurement) and to demonstrate engineering depth for the
*primary goal*. None of these is required to satisfy the brief; each is a deliberate extra.
Sources are Diane's decisions in [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md).

| # | Above-and-beyond item | Why beyond the brief | Source (discussion-points) | Status |
|---|---|---|---|---|
| A1 | **Multi-OCR benchmarking** (Tesseract + PaddleOCR, each in its own job, with timing stats) | Brief asks only to match fields; it never asks to compare OCR engines. | [§6 L119–125](../ref-docs/discussion-points.md) | Designed |
| A2 | **Multi-LLM benchmarking + cost analysis** (multiple LLMs on the same extraction; cost per ~1,000 verifications) | Brief doesn't require an LLM at all, let alone comparing them or costing them. | [§6 L123–134](../ref-docs/discussion-points.md) | Designed |
| A3 | **LangChain tracing** for latencies/timings (optional, disablable, stats-only) | Pure instrumentation for the procurement story; not a brief requirement. | [§6 L126–129](../ref-docs/discussion-points.md) | Designed |
| A4 | **Pre-compute pipeline** (background OCR + advisory compliance before the Label Specialist opens the item) | Goes beyond "match fields"; it is an architecture choice to beat the 5s bar dramatically. *(Note: also the engine that satisfies mandatory #5.)* | [§5 L99–109](../ref-docs/discussion-points.md) | Designed |
| A5 | **Visible checklist feature** (reframing Jenny's printed desk checklist) | Brief mentions the printed checklist as context, not as a feature to build. | [§9 L206–208](../ref-docs/discussion-points.md) | Designed |
| A6 | **Chevron-style status bar** (step N of M + overall progress) | UX polish beyond "clean and obvious." | [§9 L209–210](../ref-docs/discussion-points.md) | Designed |
| A7 | **Queue by application type + difficulty buckets** (next wine/spirits/beer; easy vs. troublesome for junior/senior staff) | Brief asks for batch handling, not a routing/specialization queue. | [§8 L169–172](../ref-docs/discussion-points.md) | Designed |
| A8 | **Image enhancement** (OpenCV deskew/perspective/glare/contrast) | Jenny flagged it as "maybe out of scope for a prototype." *(Also addresses wishlist #11.)* | [§10 L221–223](../ref-docs/discussion-points.md) | Designed |
| A9 | **USWDS compliance** (design-system conformance + README statements) | Brief asks for ease-of-use, not federal-design-system conformance. | [§9 L189–191](../ref-docs/discussion-points.md) | Designed |
| A10 | **Token authentication** on the demo URL | Brief explicitly says auth is *not* a POC feature; added only to protect the public demo. | [§3 L78–80](../ref-docs/discussion-points.md) | Designed |
| A11 | **Mock COLA database + data dictionary + submissions schema** | Brief says *not* to integrate with COLA; a modeled mock DB is an added rigor. | [§4 L83–95](../ref-docs/discussion-points.md) | Designed |
| A12 | **CFR-sourced rule write-ups** (distilled-spirits rules, government-warning verification method, per-type requirement lists) | Beyond matching; documents the regulatory basis. | [§7 L141–162](../ref-docs/discussion-points.md) | Planned |
| A13 | **Comparable-software pre-search** (`presearch.md`) | Landscape analysis for the procurement story; not a brief deliverable. | [§12 L236–247](../ref-docs/discussion-points.md) | Planned |
| A14 | **Lightweight processing metrics** (`submitted_at`/`decided_at`, status enum, `processing_ms`) to evidence throughput and the ~5s claim | Measurement infrastructure beyond the functional ask. | [§5 L106–109](../ref-docs/discussion-points.md) | Designed |

---

## 4. Confirmation of Alignment — "Recommend, Don't Decide"

The POC provides **recommendations**; the **human Label Specialist** reviews the findings and
makes the final decision. The software's job is to make the review faster and easier,
**never to make the review decision itself**
([discussion-points §1 L54–57](../ref-docs/discussion-points.md)).

This aligns with the brief, which frames the tool as an *assistant to* — not a replacement
for — the agent's judgment:

- *"a lot of what we do is just… matching… My agents spend half their day doing what's
  essentially data entry verification. It's not that they can't do more complex analysis,
  it's that they're drowning in routine stuff."* — Sarah Chen,
  [brief L17](../ref-docs/TTB-take-home-instructions.md). The tool clears the routine matching;
  the human keeps the analysis.
- *"You can't just pattern match everything… You need judgment."* — Dave Morrison,
  [brief L47](../ref-docs/TTB-take-home-instructions.md). The "STONE'S THROW" case is exactly why
  the engine *flags and recommends* rather than auto-decides.
- *"If something can help me get through my queue faster, great. Just don't make my life
  harder."* — Dave Morrison, [brief L49](../ref-docs/TTB-take-home-instructions.md).

Accordingly the POC distinguishes the **engine verdict** (PASS / REVIEW / FAIL — advisory)
from the **Label Specialist disposition** (Approved / Needs Correction / Rejected — the human's
decision), mirroring TTB's real states
([discussion-points §8 L177–185](../ref-docs/discussion-points.md)). This separation is the
concrete implementation of "recommend, don't decide." Marked **[RESOLVED]** in the register —
alignment confirmed.

---

## 5. Open Items / TODO

- **Confirm goal count** in `approach.md` (two goals + strategy is my read; §1).
- **Python-vs-Bash rationale write-up** — the stack is **locked** (Python end-to-end: FastAPI +
  Jinja2 + SQLite + APScheduler, per the architecture); only the `approach.md` rationale prose
  remains ([discussion-points §5 L112–113](../ref-docs/discussion-points.md)).
- **`docs/` deliverable files — DONE** (approach, tools-used, assumptions,
  tradeoffs-and-limitations, presearch all on disk; D3).
- **All-three-types scope — RESOLVED (2026-06-11):** cover beer, wine, and distilled spirits
  as first-class, each with its own review ruleset
  ([discussion-points §7](../ref-docs/discussion-points.md)). This **removes** the prior
  spirits-only under-coverage risk against evaluation criterion E1.
- **Batch-upload positioning** in the write-up — ensure the reframing (applicant-side, not
  Label Specialist-side) reads as a deliberate scope decision, not an omission, since it is a
  named brief item (#10).
