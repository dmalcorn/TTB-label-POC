# UX Design Notes — TTB COLA Label Specialist POC

*Planning document for the user experience of the Label Specialist's review workspace.
This is the federal **reviewer's** side of the COLA process — the application +
label data are pulled from the (mock) COLA database, presented for fast human
review, and the Label Specialist's disposition is captured. The POC **recommends, it
does not decide.***

**Author:** Diane · **Drafted:** 2026-06-11

**Source documents (the basis for every decision below):**

- [`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) — §3 token
  auth, §8 Label Specialist Workflow & Queue, §9 UI/UX & Design System (the bulk of the
  source).
- [`../ref-docs/TTB-take-home-instructions.md`](../ref-docs/TTB-take-home-instructions.md)
  — stakeholder interviews (Sarah Chen, Dave Morrison, Jenny Park, Marcus Williams).
- [`../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  — domain research (workflow, dispositions, verdict model, monitor framing).

**Cross-linked planning docs:**

- [`./regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
  — the review ruleset that drives which checks appear on the review screen
  and which rows are "OCR-detected, verify" vs. field-match.
- `./approach.md` *(planned — see [`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md)
  §14)* — how the rules engine, pre-compute pipeline, and verdict/disposition model
  are operationalized behind this UI.

---

## 1. Design Principles & Userbase

These principles are the lens for every screen. They come straight from the
stakeholder interviews
([TTB-take-home-instructions.md](../ref-docs/TTB-take-home-instructions.md)).

| # | Principle | Why (source) |
|---|---|---|
| **P1** | **"Something my mother could figure out."** Clean, obvious, no hunting for buttons. | Sarah Chen: "Half our team is over 50… my mother is 73… clean, obvious, no hunting for buttons." |
| **P2** | **One primary action per screen.** The next thing to do is always the biggest, most obvious thing on the page. | Mixed tech comfort (Dave prints his emails; Jenny is fresh out of college). Reduce the navigation surface. |
| **P3** | **Fast.** The screen and the AI assist must appear in **~5 seconds** or it won't be used. | Sarah: "If we can't get results back in about 5 seconds, nobody's going to use it." Handled by background pre-compute (see [approach.md](./approach.md)); the **UI's** job is to never block on that work and to show instantly-loaded, pre-computed results. |
| **P4** | **Recommend, don't decide.** The UI shows an advisory verdict; the human records the disposition. | [discussion-points.md](../ref-docs/discussion-points.md) §1, §8; [regulatory-rules-distilled-spirits.md](./regulatory-rules-distilled-spirits.md) §1. |
| **P5** | **Respect judgment.** The tool surfaces matches/mismatches but never overrides the human (the "STONE'S THROW" vs "Stone's Throw" case). | Dave Morrison: "You need judgment." |
| **P6** | **Built for big screens.** Min 24", likely 27" or dual-24". Use the width; don't cram. | [discussion-points.md](../ref-docs/discussion-points.md) §9. |
| **P7** | **Federal-standard look.** USWDS components and tokens, self-hosted. | [discussion-points.md](../ref-docs/discussion-points.md) §9; see §10 below. |

### Creative ideas for the "no hunting for buttons" mandate (P1/P2)

- **A single, persistent primary action.** Every screen has exactly one large,
  high-contrast primary button in a fixed location (bottom-right action bar).
  On the queue screen it is **Next Submission**; on the review screen it is
  **Record Disposition**. Muscle memory beats menus for an older userbase.
- **No global nav menu to get lost in.** Replace a top nav with a slim, fixed
  **utility header** (agency seal, agent name, Help search box) and a **fixed
  bottom action bar**. The middle is 100% the task. Nothing to "hunt" through.
- **Big targets, big type.** Default body ≥ 16px, action buttons ≥ 48px tall
  (USWDS large variants). Generous spacing — we have a 27" screen, use it (P6).
- **Plain-language everywhere.** "Next Submission," "Approve," "Send back for
  correction," "Reject" — never internal codes or jargon.
- **Color is reinforcement, never the only signal.** Every status also carries an
  icon + a word (USWDS accessibility + the older-eyes/colorblind reality). See §4.
- **Progressive disclosure.** Show the verdict and the fields that need attention
  first; tuck the regulation citations and raw OCR text behind a clearly-labeled
  "Why?" expander so the default view stays calm.

---

## 2. Information Architecture & Screen Map

The POC is intentionally **two screens plus support surfaces** — minimal, per P2.

```
  ┌────────────────────────────────────────────────────────────────────┐
  │  Token gate  (lightweight token auth — protects the public demo)    │
  │  discussion-points.md §3                                            │
  └───────────────┬────────────────────────────────────────────────────┘
                  │
                  ▼
  ┌────────────────────────────────────────────────────────────────────┐
  │  (1) QUEUE / "Get Next" screen                                      │
  │      - Big "Next Submission" button (serves next item directly)     │
  │      - Optional: pick next by type (Wine / Spirits / Beer)          │
  │      - Optional: pick bucket (Likely-compliant / Troublesome)       │
  │      - Small stats strip (how many waiting, avg time-to-decision)   │
  └───────────────┬────────────────────────────────────────────────────┘
                  │  serves the next submission directly (no list)
                  ▼
  ┌────────────────────────────────────────────────────────────────────┐
  │  (2) REVIEW screen  (the heart of the POC — see §6 wireframe)       │
  │      - Beverage-type banner (instant)                               │
  │      - Chevron status bar (step N of M)                             │
  │      - Label image(s)  |  Vertical stacked field comparison         │
  │      - Built-in checklist (guides required checks)                  │
  │      - Advisory verdict (PASS / REVIEW / FAIL)                      │
  │      - Disposition action bar (Approved / Needs Correction / Reject)│
  └───────────────┬────────────────────────────────────────────────────┘
                  │  records disposition → back to (1) for the next item
                  ▼
            (loop)  +  Help search / knowledge base available everywhere
```

> **Why no list view?** [discussion-points.md](../ref-docs/discussion-points.md) §8
> decides a single **Next Submission** button serves the next item directly — no
> queue list to scan, choose from, or get lost in. This is the strongest possible
> expression of P1/P2.

---

## 3. The Queue / "Get Next" Screen

The default experience is **one button.** The agent logs in (token), lands here,
clicks **Next Submission**, and is dropped straight onto a fully pre-computed
review screen.

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ [seal]  TTB Label Review                       Agent: J. Park   [?] │ utility header
  ├──────────────────────────────────────────────────────────────────────────┤
  │                                                                            │
  │                                                                            │
  │                        ┌──────────────────────────────┐                   │
  │                        │      ▶  NEXT SUBMISSION       │   ← single, huge  │
  │                        └──────────────────────────────┘     primary action│
  │                                                                            │
  │     Pick a type (optional):   [ Any ▾ ]  Wine · Spirits · Beer            │
  │     Pick a queue (optional):  ( ) Any   ( ) Likely compliant  ( ) Needs   │
  │                                                       a closer look        │
  │                                                                            │
  │     ── Today ────────────────────────────────────────────────────────     │
  │     38 waiting   ·   12 reviewed by you   ·   avg 4.6s to load             │
  │                                                                            │
  └──────────────────────────────────────────────────────────────────────────┘
```

**Design decisions:**

- **Next Submission** is the primary action. Clicking it with no other selection
  serves the single oldest/highest-priority eligible submission — zero decisions
  required. (P2)
- **Optional: select next by application type** (Wine / Spirits / Beer) — lets an
  agent specialize, since required checks differ by type. Presented as an
  *optional* dropdown so the default path stays a single click.
  ([discussion-points.md](../ref-docs/discussion-points.md) §8, "consider".)
- **Optional: two-bucket queue** — *Likely compliant* vs. *Needs a closer look*
  (the internal "very-likely-compliant vs. troublesome" split). Junior staff pull
  the easy bucket; senior staff pull the complex one. Plain-language labels, not
  "junior/senior." ([discussion-points.md](../ref-docs/discussion-points.md) §8,
  "consider".) The bucket is assigned by the pre-compute engine from the count and
  severity of REVIEW/FAIL flags — see [approach.md](./approach.md).
- **Stats strip** is informational only (supports the throughput story / the ~5s
  claim), not interactive — nothing to hunt through.

> **TODO — session start / "first item on login":** [discussion-points.md](../ref-docs/discussion-points.md)
> §8 flags how a session reaches its first label as OPEN.
> **Recommendation:** on login, land on the Queue screen and **auto-focus** the
> Next Submission button (Enter triggers it) — but do **not** auto-open a
> submission. One deliberate click gives the agent control and avoids "the screen
> jumped at me," which matters for low-tech-comfort users (P1).

---

## 4. Advisory Verdict vs. Disposition (Recommend, Don't Decide)

This distinction is load-bearing and must be visually unmistakable (P4).

- **Engine verdict** (advisory, per element and overall): **PASS / REVIEW / FAIL.**
  This is the *software's* recommendation. "REVIEW" = the engine cannot confirm
  deterministically (e.g., same-field-of-vision, image quality) and is asking a
  human to look. ([regulatory-rules-distilled-spirits.md](./regulatory-rules-distilled-spirits.md)
  §1; domain research, Implementation Considerations.)
- **Label Specialist disposition** (the real decision the human records): **Approved /
  Needs Correction / Rejected** — TTB's actual states.
  ([discussion-points.md](../ref-docs/discussion-points.md) §8 RESOLVED.)

**Visual treatment — keep them in separate visual registers so they are never
confused:**

| | Engine verdict (advice) | Label Specialist disposition (decision) |
|---|---|---|
| Where | Top-of-screen **summary banner** + per-row badges | **Bottom action bar** buttons |
| Style | USWDS **Alert / Tag** components, muted fill, labeled "Suggested:" | USWDS **Button** components, full-saturation, the agent presses one |
| Wording | "Suggested verdict: REVIEW — 2 items need your eyes" | "Approve" · "Send back for correction" · "Reject" |
| Color (with icon + word, never color alone) | PASS = green ✓ · REVIEW = amber ⚠ · FAIL = red ✕ | Decision buttons use USWDS button styles, not the verdict palette |

The summary banner literally reads as advice, e.g.:
> ⚠ **Suggested verdict: REVIEW.** 4 of 6 checks passed automatically. 2 need your
> review (Class/Type, Government Warning). You decide.

---

## 5. The Review Screen — Field Comparison & Discrepancy Highlighting

### 5.1 Instant beverage-type identification

The agent must see the beverage type the instant the screen loads, because the
required checks differ by type
([discussion-points.md](../ref-docs/discussion-points.md) §9;
[regulatory-rules-distilled-spirits.md](./regulatory-rules-distilled-spirits.md)
on cross-type divergence).

**Treatment:** a full-width **beverage-type banner** at the very top of the review
content — large word + icon + distinct accent color per type (e.g., Spirits =
amber/brown, Wine = burgundy, Beer = gold). Color is reinforcement; the **word**
("DISTILLED SPIRITS") is always present. This is the first thing the eye lands on.

### 5.2 Vertical stacked field comparison (the core interaction)

Per [discussion-points.md](../ref-docs/discussion-points.md) §9: show each
application field with the OCR/LLM-retrieved value **immediately below it**, not
side-by-side. Horizontal layouts force the eyes too far apart on a wide monitor;
stacking keeps the two values within a single short vertical saccade.

```
  ┌─ Brand Name ───────────────────────────────────────────────┐
  │  Application:   OLD TOM DISTILLERY                          │   ← maker-entered
  │  On label (OCR): OLD TOM DISTILLERY                  ✓ match│   ← retrieved value
  └────────────────────────────────────────────────────────────┘

  ┌─ Alcohol Content ──────────────────────────────────────────┐
  │  Application:   45% Alc./Vol. (90 Proof)                    │
  │  On label (OCR): 45% Alc/Vol  90 Proof              ⚠ check │  ← normalized-equal,
  │      “Punctuation differs; values match. Your call.”        │     flagged advisory
  └────────────────────────────────────────────────────────────┘
```

Each field card is one tight vertical unit: the **Application** value, then the
**On label (OCR)** value directly beneath it, then a status chip on the right.

### 5.3 Discrepancy highlighting (concrete visual treatment)

When OCR ≠ maker-entered value
([discussion-points.md](../ref-docs/discussion-points.md) §9 REQUEST):

- **Match:** quiet. Thin neutral border, small green ✓ "match" chip. Do not shout
  about things that are fine — keep the screen calm (P1).
- **Mismatch:** **the whole field card gets a thick left border + tinted
  background** (USWDS error tint), and the **two differing values are shown with
  character-level diff highlighting** — the changed span in each value gets a
  colored underline/highlight so the eye jumps straight to *what* differs, not just
  *that* it differs.

```
  ┃┌─ Net Contents ─────────────────────────────────────────────┐   ┃ = thick
  ┃│  Application:   750 mL                                      │     amber/red
  ┃│  On label (OCR): 700 mL                          ✕ mismatch │     left bar +
  ┃│                     ▔▔▔  (the “50” vs “00” span highlighted)│     tint fill
  ┃└────────────────────────────────────────────────────────────┘
```

- **Soft/normalized mismatch** (the "STONE'S THROW" / punctuation-only case, P5):
  a distinct **amber "check" state**, not a red "mismatch." The card explains in
  plain language ("Capitalization differs; text otherwise matches") so the agent
  exercises judgment instead of reflexively rejecting. This directly honors Dave
  Morrison's point and the false-reject risk in the domain research.
- **Severity ordering:** mismatches float to the top of the field list; clean
  matches sink to the bottom. The agent's eyes start where the work is.

### 5.4 The Government Warning — checked against the required statutory text

The Government Warning is the one mandatory element the applicant does **not** type
(they attest to the label artwork). It is verified from OCR against the **fixed text
mandated by 27 CFR §16.21** — so the comparison target is the *regulation*, not a maker
value, and the check is fully **deterministic** (PASS/FAIL). Render it as a
"required vs. on-label" row:

```
  ┌─ Government Warning  (checked against 27 CFR §16.21) ───────┐
  │  Required: “GOVERNMENT WARNING: (1) According to the …”     │
  │  On label (OCR): “GOVERNMENT WARNING: (1) According to…”    │
  │  ⚠ REVIEW — caps/bold of “GOVERNMENT WARNING:” needs a look │
  │  ▸ Why?  27 CFR Part 16 — exact wording + caps/bold token   │
  └────────────────────────────────────────────────────────────┘
```

**Class/type is *not* a special case:** it **is** a maker-entered application field
(the COLAs Online "Product Class/Type" code — see `../ref-docs/Definition of Terms.txt`),
so it renders as a normal stacked application ↔ OCR comparison row (§5.2/§5.3), with the
designation's regulatory validity shown as an extra "Why?" note. Only the Government
Warning uses the "compare-against-the-rule" layout above.

---

## 6. Full Review Screen Wireframe

Putting it together for a 27" / dual-24" layout (P6): label image(s) on the left,
the stacked comparison + checklist on the right, chevron on top, action bar on
the bottom.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ [seal] TTB Label Review                              Agent: J. Park   [ search?] │ utility header
├──────────────────────────────────────────────────────────────────────────────────────┤
│  🥃  DISTILLED SPIRITS        TTB ID 26-12345        Suggested verdict: ⚠ REVIEW       │ bev-type + verdict
├──────────────────────────────────────────────────────────────────────────────────────┤
│   ① Identity ▸▸ ② Mandatory text ▸▸ ③ Gov. Warning ▸▸ ④ Conditional ▸▸ ⑤ Decide        │ CHEVRON (step 3 of 5)
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│   LABEL IMAGE(S)                  │   FIELD COMPARISON (vertical stacked)               │
│  ┌─────────────────────────────┐  │  ┌─ Brand Name ───────────────────────────────┐    │
│  │                             │  │  │ Application:   OLD TOM DISTILLERY            │    │
│  │      [front label img]      │  │  │ On label (OCR): OLD TOM DISTILLERY    ✓ match│    │
│  │                             │  │  └─────────────────────────────────────────────┘    │
│  └─────────────────────────────┘  │  ┌─ Alcohol Content ──────────────────────────┐    │
│  ◂ 1 of 3 ▸   [ front | back | + ] │  │ Application:   45% Alc./Vol. (90 Proof)      │    │
│  [ zoom + ]  [ enhance: deskew ]  │  │ On label (OCR): 45% Alc/Vol 90 Proof  ⚠ check│    │
│                                   │  └─────────────────────────────────────────────┘    │
│   CHECKLIST (guides your review)  │ ┃┌─ Net Contents ─────────────────────────────┐    │
│   ☑ Brand name present & matches  │ ┃│ Application:   750 mL                        │    │
│   ☑ ABV present & in field of view│ ┃│ On label (OCR): 700 mL              ✕ mismatch│   │
│   ◻ Class/type valid (verify)     │ ┃└─────────────────────────────────────────────┘    │
│   ◻ Gov. Warning exact (verify)   │  ┌─ Class/Type ───────────────────────────────┐    │
│   ◻ Net contents = std of fill    │  │ Application:   KY Straight Bourbon           │    │
│                                   │  │ On label (OCR): KY Straight Bourbon   ✓ match│   │
│   ◻ Name/address present          │  └─────────────────────────────────────────────┘    │
│   — 2 of 6 done —                 │  ┌─ Gov. Warning (checked against §16.21) ────┐    │
│                                   │  │ ⚠ REVIEW — caps/bold needs a look           │    │
│                                   │  └─────────────────────────────────────────────┘    │
├───────────────────────────────────┴────────────────────────────────────────────────────┤
│  Notes: [_________________________________]      [ ✓ Approve ] [ ↩ Needs Correction ] [ ✕ Reject ] │ action bar
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Layout notes:**

- **Left = evidence, right = comparison.** The label image and the field values are
  on screen simultaneously (a 27" makes this comfortable) so the agent never
  toggles between "what's claimed" and "what's printed."
- **Image controls** include OCR-friendly enhancements (deskew/perspective/glare —
  OpenCV, local, no cloud call; see domain research and [approach.md](./approach.md))
  so a marginally-bad photo can be cleaned up in place instead of bounced back —
  Jenny Park's wish.
- **Notes field** lives next to the action bar — required when the disposition is
  Needs Correction or Reject, so the maker gets a clear reason.

---

## 7. Built-in Checklist (reframing Jenny Park's desk checklist)

Jenny Park keeps a **printed checklist on her desk** and checks each item "with my
eyes." The POC turns that paper into a guided, in-screen checklist
([discussion-points.md](../ref-docs/discussion-points.md) §9). Design approaches:

**Recommended approach — "smart pre-checked checklist":**

- The checklist is **generated from the ruleset** for the beverage type
  ([regulatory-rules-distilled-spirits.md](./regulatory-rules-distilled-spirits.md)),
  so it always matches the regs and updates if the regs do.
- The engine **pre-checks the items it could verify automatically** (PASS items
  arrive already ticked, shown muted) and **leaves the human items unticked and
  highlighted** (REVIEW/FAIL items the agent must eyeball). This is the key
  reframing: the software does the boring ticks, the human does the judgment ticks
  — exactly Sarah Chen's "they're drowning in routine stuff" pain.
- **Clicking a checklist item scrolls to / highlights the matching field card**, so
  the checklist doubles as a table of contents for the review.
- A small **"2 of 6 done"** progress counter ties the checklist to the chevron's
  notion of completeness without nagging.
- **Soft gate, not a hard block:** the agent *can* record a disposition before every
  item is ticked, but if they Approve with open REVIEW items, a calm USWDS modal
  confirms ("2 items weren't reviewed — approve anyway?"). Respect judgment (P5),
  but make skips deliberate.

**Alternative considered:** a purely manual checklist (nothing pre-checked). Rejected
— it preserves Jenny's pain instead of relieving it, and gives the agent no time
savings.

> **TODO — checklist persistence:** should tick state persist if an agent navigates
> away mid-review? **Recommendation:** yes, persist per-submission tick state with
> the pre-computed record so a returning agent resumes where they left off; clear it
> only on disposition. Confirm in [approach.md](./approach.md).

---

## 8. Chevron Status Bar (process steps)

Per [discussion-points.md](../ref-docs/discussion-points.md) §9, show process steps
in a **chevron-style status bar** (step N of M + overall progress). USWDS has a
**Step Indicator** component that renders exactly this; use it (self-hosted, see §10).

**Recommended steps for the review flow (5 steps):**

```
   ① Identity  ▸▸  ② Mandatory text  ▸▸  ③ Gov. Warning  ▸▸  ④ Conditional  ▸▸  ⑤ Decide
   (done)          (done)               (current)            (upcoming)          (upcoming)
```

1. **Identity** — brand name, beverage type, TTB ID confirmed.
2. **Mandatory text** — ABV, class/type, net contents, name/address.
3. **Government Warning** — the one deterministic, high-scrutiny check.
4. **Conditional** — country of origin, sulfites, age statement, etc. *(only the
   triggered ones appear)*.
5. **Decide** — record the disposition.

- The chevron is **informational and clickable** — clicking a step scrolls the
  comparison panel to that group. It is **not** a wizard that hides content; on a
  27" everything is visible at once and the chevron just shows *where you are* and
  *how far is left* (P1 — orientation without hunting).
- The current step is high-contrast; done steps carry a ✓; upcoming steps are muted.

> **TODO — single review vs. multi-step wizard:** for the POC, all field cards are
> visible simultaneously and the chevron is an orientation/progress indicator, not a
> paginated wizard. **Recommendation:** keep it single-page with the chevron as a
> progress map — pagination would add the "hunting/clicking" we're trying to remove.

---

## 9. In-UI Help & Knowledge Base

Per [discussion-points.md](../ref-docs/discussion-points.md) §9: clear, easy-to-find
help, **searchable**, with a **knowledge base** of answers.

- **Persistent Help affordance:** a `[?]` / **Help** control in the fixed utility
  header — same place on every screen (P2). One predictable spot, never hunted for.
- **Searchable help:** clicking it opens a panel with a single prominent search box
  ("Ask a question…"). The knowledge base is **local content** (no cloud call —
  firewall-safe) seeded with the questions an agent actually hits:
  - "What exactly must the Government Warning say?" (links the Part 16 text from
    [regulatory-rules-distilled-spirits.md](./regulatory-rules-distilled-spirits.md)).
  - "Why didn't the tool check the font size?" (the deliberate non-goal).
  - "The names differ only in capitalization — is that a real mismatch?" (the
    STONE'S THROW guidance).
  - "What's the difference between Needs Correction and Rejected?"
- **Contextual help inline:** every "Why?" expander on a field card is micro-help
  that explains the verdict with its CFR citation — help that comes to the agent
  instead of making them search.
- **Knowledge base as a browsable list** under the search box (top FAQs), so a
  low-search-comfort agent (Dave) can scan rather than type.

> **TODO — KB content ownership:** the KB is only as good as its seeded answers.
> **Recommendation:** seed it from the regulatory ruleset doc + the documented
> non-goals so it ships useful on day one; mark it as a living doc.

---

## 10. USWDS Compliance Statements (README-ready)

The POC adopts the **U.S. Web Design System (USWDS)** so the tool looks and behaves
like a federal government application and meets federal accessibility expectations
([discussion-points.md](../ref-docs/discussion-points.md) §9). The following
statements are written to drop into the README.

> **USWDS adoption.** The Label Specialist workspace is built on the **U.S. Web Design
> System (USWDS)**, the design system mandated for federal public-facing web
> applications. The UI uses USWDS **design tokens** (color, spacing, typography
> scale) and **components** — Header, Button, Alert, Tag, Step Indicator
> (chevron), Accordion (the "Why?" expanders), Modal, Table, and Form controls —
> rather than bespoke styling.

> **Self-hosted assets — no CDN, firewall-safe.** All USWDS assets (compiled CSS,
> JavaScript, fonts, and icon sprites) are **vendored and served from the
> application itself**. The app makes **no outbound request to any CDN or external
> host** for styling or scripts, satisfying the TTB firewall / no-outbound-calls
> constraint ([discussion-points.md](../ref-docs/discussion-points.md) §3). This is
> documented in [`./outbound-calls-inventory.md`](./outbound-calls-inventory.md).

> **Component sourcing.** Components are taken from the official USWDS component
> library (the `uswds`/`@uswds/uswds` package and the USWDS GitHub repository) and
> used per its documented markup, rather than reimplemented — so the POC tracks the
> federal standard and its accessibility fixes.

> **Accessibility.** Because USWDS components ship to **Section 508 / WCAG 2.x AA**
> targets, the POC inherits keyboard navigation, focus states, ARIA roles, and
> sufficient color contrast. The design additionally never relies on **color
> alone** — every status carries an **icon and a text label** — which serves the
> older, varied-vision userbase (P1) and colorblind users.

> **Large-screen / federal-look conventions.** Layout follows USWDS grid and
> spacing tokens, tuned for the agency's **minimum 24" (likely 27" or dual-24")**
> monitors, with USWDS **large** button and input variants for big, easy targets.

> **Plain-language content.** Per the federal **Plain Writing Act** and USWDS
> content guidance, all labels and actions use plain language ("Send back for
> correction," not internal status codes).

---

## 11. Accessibility & Older-Userbase Specifics

Beyond what USWDS gives for free (P1, half the team is 50+):

- **Minimum 16px body, 18–20px for comparison values;** never use the smallest USWDS
  type step for primary content.
- **Color + icon + word for every status** (✓ match / ⚠ check / ✕ mismatch; PASS /
  REVIEW / FAIL). Tested against the USWDS contrast tokens.
- **Big click targets** (≥ 48px) for all primary actions; generous hit areas on
  checklist items.
- **Keyboard-first power path** for high-volume agents (Jenny): `N` = Next
  Submission, `A`/`C`/`R` = Approve / Needs Correction / Reject (with the confirm
  modal), arrow keys to move between image faces. Documented in the Help panel — but
  the mouse path is always fully sufficient (Dave).
- **No timeouts that lose work;** notes and tick state persist (see §7 TODO).
- **Calm default state:** clean matches are quiet; only problems draw the eye. The
  screen should feel reassuring, not alarming, to a cautious user.

---

## 12. Open UX Questions (TODO register)

Consolidated from the inline TODOs above, each with a recommendation:

| # | Open question (source) | Recommendation |
|---|---|---|
| U1 | How does a session start / reach the first label? ([discussion-points.md](../ref-docs/discussion-points.md) §8) | Land on Queue, auto-focus **Next Submission** (Enter triggers), but require one click to open a submission — don't auto-open. |
| U3 | Checklist tick-state persistence on navigate-away (§7) | Persist per-submission with the pre-computed record; clear on disposition. |
| U4 | Chevron as wizard vs. progress map (§8) | Single-page review; chevron is an orientation/progress map, not a paginating wizard. |
| U5 | Knowledge-base content ownership (§9) | Seed from the regulatory ruleset + documented non-goals; treat as a living doc. |
| U6 | Two-bucket queue labeling — does exposing "junior/senior" routing feel hierarchical to agents? (§3) | Use task-language ("Likely compliant" / "Needs a closer look"), never staff seniority labels in the UI. |
| U7 | Disposition reason requirement — is a note mandatory for Needs Correction / Reject? | Recommend **yes** (the maker needs a reason); make the Notes field required for those two dispositions, optional for Approve. Confirm with stakeholder. |

---

## 13. Traceability — where each requirement is addressed

| Requirement (source) | Addressed in |
|---|---|
| USWDS compliance + self-host, README statements ([discussion-points.md](../ref-docs/discussion-points.md) §9) | §10 |
| Min 24" / 27" / dual-24" large-screen design (§9) | §1 (P6), §6, §10 |
| Intuitive, no hunting for buttons (§9; brief) | §1, §2, §3 |
| Next Submission direct serve; by-type; two-bucket queue (§8) | §3 |
| Instant beverage type (§9) | §5.1, §6 |
| Vertical stacked field comparison (§9) | §5.2, §6 |
| Discrepancy highlighting (§9) | §5.3 |
| Government Warning checked vs §16.21 required text (compare-against-the-rule) | §5.4 |
| Class/type as a standard application↔OCR field-match comparison (validity is a separate sub-check) | §5.2, §5.3 |
| Built-in checklist (§9; Jenny Park) | §7 |
| Chevron status bar (§9) | §8 |
| Searchable help + knowledge base (§9) | §9 |
| Recommend-don't-decide: verdict vs. disposition (§1, §8) | §4 |
| Token auth protecting the demo (§3) | §2 |
```
