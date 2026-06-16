# Assumptions — TTB COLA Label Review POC

*The numbered assumptions this proof-of-concept (POC) is built on. Each entry is a
one-line statement plus a short rationale/implication. Assumptions are grouped by
theme and numbered **A1, A2, …** with stable IDs so other planning docs can cite
them (e.g. [`requirements-mapping.md`](requirements-mapping.md) references the
above-and-beyond items this list backs).*

**Beverage focus:** distilled spirits (27 CFR Part 5 + the Part 16 health warning),
with notes where beer (Part 7) and wine (Part 4) diverge.
**Author:** Diane · **Date:** 2026-06-11

**Ground-truth sources:**
- The brief — [`ref-docs/TTB-take-home-instructions.md`](../ref-docs/TTB-take-home-instructions.md)
- Decision register — [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md)
- First-pass research — [`ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md)
- Domain research report — [`_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)

**Related docs:** [`approach.md`](approach.md) · [`tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md) · [`requirements-mapping.md`](requirements-mapping.md) · [`presearch.md`](presearch.md) · [`data-dictionary.md`](data-dictionary.md)

> **How to read an assumption:** each is a *deliberate working premise* — not a proven
> fact. Where the brief, the CFR, or the research forced the choice, it is cited.
> Where the POC is *filling a documented gap* (most importantly the reviewer-side UI),
> the assumption says so and points at the evidence. Open implementation choices are
> marked **TODO**. Many assumptions have a downstream consequence captured in
> [`tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md).

---

## 1. Scope & Intent

**A1. The POC builds the *Label Specialist* (federal reviewer) side only.**
The prototype presents application + label data to a reviewer and captures their
disposition; it is not the applicant's filing system.
*Rationale/implication:* the brief and register frame this as the reviewer's workspace
([discussion-points §1](../ref-docs/discussion-points.md)); the applicant side already
exists (COLAs Online) and is out of scope.

**A2. v1 *reads* from a mock COLA database — no image upload and no field data-entry.**
The POC displays and assists over already-submitted records; capturing new applications
is explicitly not the intent.
*Rationale/implication:* per [discussion-points §1 L47–49](../ref-docs/discussion-points.md).
This bounds the UI to a read-and-disposition surface and lets the data model be *seeded*
rather than *entered* (see A11).

**A3. All three beverage types are in scope (beer, wine, distilled spirits), each with its
own review ruleset; distilled spirits is the most fully worked example.**
Each type has a dedicated ruleset doc
([spirits](regulatory-rules-distilled-spirits.md) · [wine](regulatory-rules-wine.md) ·
[beer](regulatory-rules-beer.md)); the engine, checklist, and fixtures are type-keyed.
Distilled spirits carries the deepest worked detail (the brief's sample label is a spirits
label).
*Rationale/implication:* decision of 2026-06-11 to cover all three first-class
([discussion-points §7](../ref-docs/discussion-points.md)); the chief cross-type trap to
honor is that **the ABV rule differs in all three**
([Research-Findings §1](../ref-docs/Research-Findings.md)).

**A4. The engine *recommends*; the human Label Specialist *decides*.**
The software produces an advisory verdict per element; it never issues the review
itself.
*Rationale/implication:* "recommend, don't decide" is locked
([discussion-points §1 L54–57](../ref-docs/discussion-points.md)) and aligns with the
brief. Concretely this separates the **engine verdict** (PASS / REVIEW / FAIL) from the
**Label Specialist disposition** (Approved / Needs Correction / Rejected) — see A7.

**A5. An API and any COLA-system integration are phase two, not the POC.**
The POC is a standalone prototype; integration with the real .NET COLA system is
explicitly deferred.
*Rationale/implication:* per the brief (Marcus Williams,
[L35](../ref-docs/TTB-take-home-instructions.md)) and
[discussion-points §5 L114–115](../ref-docs/discussion-points.md). Keeps scope minimal
and avoids the COLA system's separate authorization requirements.

## 2. Roles & Terminology

**A6. The three core roles/terms are *applicant*, *Label Specialist*, and *submissions*.**
*Applicant* = the industry member who files a COLA; *Label Specialist* = the federal employee
who reviews it; *submissions* = the queue of applications awaiting review.
*Rationale/implication:* fixed in
[discussion-points §2 L60–65](../ref-docs/discussion-points.md). These terms are used
consistently across all docs and the UI.

**A7. Dispositions mirror TTB's real states — Approved / Needs Correction / Rejected —
not invented "Pass/Fail."**
The Label Specialist records one of TTB's actual outcomes; "review" is informal, not a
disposition.
*Rationale/implication:* per [Research-Findings §7](../ref-docs/Research-Findings.md) and
[discussion-points §8 L177–185](../ref-docs/discussion-points.md). Matches vocabulary
agents already know (Needs Correction = fixable, 30-day clock; Rejected = terminal).

## 3. The Reviewer-Side Interface (the documented gap the POC fills)

**A8. The TTB reviewer-side UI, queue, and "serve-next" mechanics are NOT publicly
documented — so the POC designs them.**
No provided source describes the reviewer interface or how applications are queued and
served; the POC invents this experience using the well-documented applicant-side data
model (Form 5100.31 fields) as input.
*Rationale/implication:* explicitly established in
[Research-Findings §5](../ref-docs/Research-Findings.md) ("the TTB-specialist/reviewer
interface … are NOT documented anywhere in the provided sources … for the prototype, we
get to design it"). This is the POC's differentiator — no competing tool occupies the
federal-reviewer quadrant ([presearch.md §2](presearch.md)). Every reviewer-UX decision
(single "Next Submission" button, queue buckets, vertical stacked comparison, checklist)
is therefore a *design proposal*, not a reproduction of an existing screen.

**A9. Session start and "next item" are an assumed get-next-item → load-review-screen
flow.**
On login the Label Specialist is served the next submission directly (no pick-from-list);
optional routing by beverage type or difficulty bucket is a design proposal.
*Rationale/implication:* the mechanics are undocumented (A8); the assumed flow follows
[discussion-points §8 L164–176](../ref-docs/discussion-points.md). The "ASSIGNED" status
in TTB data implies per-specialist assignment but gives no mechanics.

## 4. Operating Environment & Deployment

**A10. Label Specialists work off a web URL on CPU-only, no-local-disk workstations; no GPU is
assumed.**
The reviewer accesses the tool through a browser (a URL to the central system); the POC
assumes no local installation, no local persistence, and no GPU.
*Rationale/implication:* working theory from
[discussion-points §3 L73–77](../ref-docs/discussion-points.md); GPU uncertainty noted in
the domain research (Technical Trends → Challenges). **Implication: benchmark OCR in
CPU mode too** — do not rely on PaddleOCR's GPU throughput numbers; persistence lives in
the central database, not on the workstation.

**A11. The deployed app is *local-first*, and its LLM calls model *government-internal*
endpoints (revised 2026-06-11).**
The firewall blocks *external* domains but the government hosts LLMs *inside* the firewall.
So the core (OCR, OpenCV, rules, DB, tracing) runs fully local (`none`/`local`), while LLM
extraction + benchmark calls are classified **`models-internal-endpoint`**: in production they
terminate inside the firewall, and the POC's cloud-API calls are a documented stand-in. The
model layer is **toggleable off**, leaving a provable zero-egress OCR-only path (FR-12).
*Rationale/implication:* original constraint per the brief (Marcus Williams,
[L39](../ref-docs/TTB-take-home-instructions.md)) and
[discussion-points §3 L68–72](../ref-docs/discussion-points.md); **revised by Diane during the
PRD** — see [PRD §10 NFR-2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/prd.md)
and [addendum A2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/addendum.md).
Drives the local-first stack and the three-way-classified
[outbound-calls inventory](outbound-calls-inventory.md). *(Supersedes the earlier "cloud VLMs
only in an offline harness, never deployed" assumption.)*

**A12. LangChain/LLM tracing is stats-only and disablable, so it never conflicts with the
firewall constraint.**
LangChain is included to gather latency/timing stats locally; it is easy to turn off and
emits no telemetry to the cloud.
*Rationale/implication:* per
[discussion-points §6 L126–129](../ref-docs/discussion-points.md). Lets the POC keep the
instrumentation value while honoring A11.

**A13. Authentication is not a graded POC feature; a lightweight token gates the demo URL.**
Auth is explicitly out of scope per the brief; a token is added only to keep the public
demo from being driven by the public or bots.
*Rationale/implication:* per
[discussion-points §3 L78–80](../ref-docs/discussion-points.md). The token protects the
deployed URL ([requirements-mapping D4 / A10](requirements-mapping.md)) without
pretending to be production-grade identity management.

## 5. Data, Privacy & Test Fixtures

**A14. The mock COLA DB is seeded with dummy applications and contains no PII.**
Records are synthetic/dummy data shaped to the Form 5100.31 field set; nothing sensitive
is stored.
*Rationale/implication:* per the brief (Marcus Williams,
[L37](../ref-docs/TTB-take-home-instructions.md)) and
[discussion-points §4 L83–84](../ref-docs/discussion-points.md). The GDPR/CCPA privacy
branch is largely N/A by design — the only real data concern is IP (A15).

**A15. Label artwork is brand IP — registry images are private test fixtures only;
anything public is synthetic.**
COLA *records* are public government data, but label *artwork* is the brand owner's
trademark/trade dress, so real label images are used as internal fixtures and never
redistributed in the repo or demo.
*Rationale/implication:* per [Research-Findings §8](../ref-docs/Research-Findings.md) and
[presearch.md §3](presearch.md). Public-facing demo/screenshots use AI-generated/synthetic
labels (which the brief encourages); the provided "OLD TOM DISTILLERY" sample doubles as a
synthetic **fail** fixture.

**A16. The database carries three field categories: application fields, OCR-extracted
fields, and engine/disposition fields.**
The schema separates maker-entered application values, values read off the label by OCR,
and the engine verdict + Label Specialist disposition.
*Rationale/implication:* per
[discussion-points §4 L90–92](../ref-docs/discussion-points.md) and the
[data-dictionary](data-dictionary.md). The OCR fields *mirror* the matchable application
fields to drive the vertical-stacked discrepancy display. The Government Warning is the one
element with no maker field — it is diffed against the §16.21 statutory text instead (A17).

## 6. Verification Logic — What Can and Cannot Be Diffed

**A17. Class/type designation IS a maker-entered application field (so it is diffable);
the Government Warning is NOT a typed field but is verified against the fixed regulatory text.**
The COLAs Online application captures the beverage *type* (wine / spirits / malt) **and** the
**Product Class/Type designation** as a maker-entered code (typed or via lookup — see
`../ref-docs/Definition of Terms.txt`, "Product Class/Type"). So class/type is a normal
**application ↔ OCR field-match**, like brand name (`ocr_class_type` mirrors it). The
**Government Warning** is the one mandatory element the applicant does *not* type (they attest
to the label artwork); it is verified from OCR against the **fixed 27 CFR §16.21 text** — a
*deterministic* check whose "expected" side is the regulation (a constant), enforcing the
caps+bold "GOVERNMENT WARNING:" token.
*Rationale/implication:* every label element except the warning has a maker value to diff;
the warning's ground truth is the statute, not a maker field — so it never lacks an expected
value. *(This corrects an earlier mis-reading that treated class/type as un-captured.)*
Grounded in `../ref-docs/Definition of Terms.txt` and
[Research-Findings §2](../ref-docs/Research-Findings.md).

**A18. Brand name, ABV, net contents, and name/address ARE maker-entered, so these are
true application-↔-OCR field matches.**
For these fields a maker-entered value exists, so the engine compares it to the OCR'd
label value with normalization/tolerance.
*Rationale/implication:* per
[data-dictionary §1](data-dictionary.md) and the brief's core matching action
([L15–17](../ref-docs/TTB-take-home-instructions.md)). Normalization handles Dave
Morrison's "STONE'S THROW" vs "Stone's Throw" case
([brief L47](../ref-docs/TTB-take-home-instructions.md)) so an obvious match isn't
false-flagged. *(These four, plus **class/type** (A17), the **Government Warning** (A17), and
**country of origin** (A18a) make up exactly the **seven** elements the engine checks on every
type.)*

**A18a. Country of origin IS one of the seven checked elements — an import-aware card.**
Country of origin is a real comparison **card**, not an omission: it keys off the application's
**import / source-of-product** flag. `IMPORTED` ⇒ the filed country (e.g. "Scotland") is
field-matched against the label; `DOMESTIC` ⇒ **auto-PASS** with "Not imported" (we trust the
flag rather than attempting US-state recognition).
*Rationale/implication:* completes the seven common elements (brand name, class/type, alcohol
content, net contents, name & address, Government Warning, country of origin); detailed in
[`tradeoffs-and-limitations.md` B2](tradeoffs-and-limitations.md).

**A19. The ABV-present requirement is not hard-coded; matching branches on beverage type.**
"ABV must always be present" is true only for spirits — beer is usually optional, wine
only above 14% — so the check is conditioned on `product_class_type`.
*Rationale/implication:* per [Research-Findings §1](../ref-docs/Research-Findings.md) and
the [data-dictionary per-type ABV note](data-dictionary.md). A naive always-required rule
would false-reject beer and table wine.

## 7. Images & Multi-Label Handling

**A20. A submission carries 1–10 label images and mandatory elements are checked across
the *union* of all of them.**
A label may span front/brand, back, neck, and strip images; the verifier accepts the set
and looks for required elements across all images, not on a single one.
*Rationale/implication:* per
[discussion-points §4 L88–89](../ref-docs/discussion-points.md) and
[Research-Findings §4, §6](../ref-docs/Research-Findings.md). The "same field of vision"
rule (§5.63) is the hard exception — spatial co-location is checkable-where-determinable,
else flagged REVIEW.

**A21. Accepted image formats are JPG/JPEG/JPE and TIFF/TIF (RGB, ≤750 KB, ≤10 files);
PNG support is an assumption / enhancement TODO.**
The POC matches the live COLAs Online baseline (JPG/TIFF only); modern PNG uploads are a
proposed enhancement, not a confirmed requirement.
*Rationale/implication:* baseline from
[Research-Findings §6](../ref-docs/Research-Findings.md) and
[discussion-points §10 L216–218](../ref-docs/discussion-points.md);
[data-dictionary §2](data-dictionary.md) marks `PNG` **TODO confirm**.

**A22. Imperfect images are improved locally (OpenCV) without a re-submit cycle — no LLM
or cloud call required.**
Glare, skew, and off-angle shots are corrected by open-source, on-prem preprocessing
before OCR.
*Rationale/implication:* per
[discussion-points §10 L221–223](../ref-docs/discussion-points.md) and the domain research
(Innovation Patterns). Honors Jenny Park's wish
([brief L59](../ref-docs/TTB-take-home-instructions.md)) while staying firewall-safe
(A11).

## 8. Compliance Posture

**A23. The engine *recommends, does not decide* — and never auto-approves.**
Every element gets an advisory PASS / REVIEW / FAIL; false approves are caught by the
mandatory human-in-the-loop.
*Rationale/implication:* the implementation of A4; tolerance bands plus a REVIEW band curb
the costliest error (false rejects). See the domain research (Risk Assessment).

**A24. Font size and physical dimensions are NOT checked.**
The POC does not verify type-size compliance.
*Rationale/implication:* absolute millimeters cannot be derived from a photo without a
reliable physical scale reference, and COLAs Online itself disclaims testing
dimensions/font size (the applicant swears compliance). Per
[Research-Findings §3](../ref-docs/Research-Findings.md) and
[discussion-points §7 L153–155](../ref-docs/discussion-points.md); documented as a
deliberate, regulation-aligned limitation in
[tradeoffs-and-limitations.md](tradeoffs-and-limitations.md).

**A25. The Government Warning is verified deterministically (exact/normalized), no LLM
needed.**
The warning is checked by string/regex comparison to the §16.21 wording, enforcing the
caps+bold "GOVERNMENT WARNING:" token and "separate and apart" placement.
*Rationale/implication:* per [Research-Findings §2](../ref-docs/Research-Findings.md);
catches the "title case / reworded / smaller font" abuse Jenny Park described
([brief L57](../ref-docs/TTB-take-home-instructions.md)). (The "expected" side is the §16.21
statutory text, not a maker field — see A17.)

## 9. Regulatory & Model Currency

**A26. CFR citations use the post-2022 Part 5 modernization renumbering.**
All distilled-spirits section numbers reflect the current (post-2022) 27 CFR Part 5
numbering, treated as data rather than hard-coded.
*Rationale/implication:* per the domain research (Regulatory section; Risk → regulatory
drift). Any rule set citing the *old* Part 5 numbers would now be wrong; storing CFR
citations as data lets the rules engine track future drift.

**A27. The Government Warning text and type-size table are verified against the local
27 CFR Part 16 PDF.**
27 CFR Part 16 (§16.21 wording, §16.22 type-size) is verified against the local file
[`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf).
*Rationale/implication:* originally cross-checked against the eCFR mirror
([Research-Findings §2](../ref-docs/Research-Findings.md), 2026-06-09) and now verified
line-by-line against the local Part 16 PDF, which completes the offline rule set (the
other three CFR PDFs only cross-reference Part 16).

**A28. Model/benchmark numbers (OCR/LLM accuracy, speed, cost) are *indicative*, not
authoritative.**
Reported 2026 leaderboard scores and per-engine benchmarks are directional; real figures
come from the POC's own benchmark run.
*Rationale/implication:* per the domain research (Technical Trends — "treat specific scores
as indicative"; leaderboards are fast-moving and vendor-adjacent). The procurement-grade
$/1,000-verifications and accuracy claims must be produced by the POC's harness, not
quoted from third parties.

**A29. ~90% of COLA applications are filed online (vs. paper); exact yearly counts are a
TODO.**
The POC assumes structured, clean, electronically-filed input as the norm.
*Rationale/implication:* per the domain research (Domain Scale & Structure; *Confidence:
MEDIUM*) and [presearch.md §5](presearch.md). Exact 2024/2025/2026 online-vs-paper counts
are **TODO** (Public COLA Registry resisted automated fetch). Online dominance is *why*
the POC can assume structured fields to pull from the DB.

---

## Quick Index

| Theme | Assumptions |
|---|---|
| Scope & Intent | A1–A5 |
| Roles & Terminology | A6–A7 |
| Reviewer-Side Interface (design gap) | A8–A9 |
| Operating Environment & Deployment | A10–A13 |
| Data, Privacy & Test Fixtures | A14–A16 |
| Verification Logic (diffable vs. rule-checked) | A17–A19 |
| Images & Multi-Label Handling | A20–A22 |
| Compliance Posture | A23–A25 |
| Regulatory & Model Currency | A26–A29 |

**Cross-links:** consequences and known gaps for many of these assumptions are detailed in
[`tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md); the overall
design rationale lives in [`approach.md`](approach.md); brief-requirement
traceability is in [`requirements-mapping.md`](requirements-mapping.md).
