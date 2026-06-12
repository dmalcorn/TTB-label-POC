# Spine Pair Review — TTB-label-POC

## Overall verdict

**Strong, ship-ready as a downstream contract.** A consumer (architecture, story-dev) can source-extract cleanly: every `{token}` reference resolves to a defined DESIGN.md token, every component named in either spine has both a visual row (DESIGN.md.Components) and a behavioral row (EXPERIENCE.md.Component Patterns), all five sources-frontmatter paths exist, and all three load-bearing user journeys (UJ-1..UJ-3) map to named Key Flows with protagonists, numbered steps, climax beats, and failure paths. The spines are disciplined about the USWDS-inheritance posture and the load-bearing P4 verdict/disposition split. Findings below are refinements, not blockers — the one item worth fixing before downstream pickup is a non-canonical token-reference shorthand and an unstated contrast commitment on two domain combos USWDS doesn't vouch for.

## 1. Flow coverage — strong

Checked: extracted UJ-1, UJ-2, UJ-3 from the PRD §2.3 (the only Key User Journeys; PRD requirements run FR-1..FR-28, not FR-1..FR-12 as the brief stated). Verified each load-bearing journey has a Key Flow with a named protagonist, numbered steps, a labeled climax, and a failure path.

- UJ-1 (Dave / clean bourbon) → Flow 1: protagonist Dave Morrison, 5 numbered steps, explicit **Climax** at step 4, failure path (pre-compute failed → honest per-check error). Includes the UJ-1 "STONE'S THROW"/"Stone's Throw" normalization edge as the failure-of-Flow-2 beat — covered.
- UJ-2 (Jenny / creative Government Warning) → Flow 2: protagonist Jenny Park, 5 steps, **Climax** at step 5, failure path (capitalization-only body diff → amber not red).
- UJ-3 (evaluator / procurement) → Flow 3: 4 steps, **Climax** at step 4 (Benchmark Report). No failure path — acceptable; an evaluator walk-through has no user-error branch to recover from.

### Findings
- **low** Flow 3 has no failure/edge beat while Flows 1–2 do (EXPERIENCE.md:157–164). *Fix:* optional — a one-line "if a provider key is unconfigured at eval time, the Benchmark row shows a labeled gap, not a crash" would mirror FR-12/state-pattern honesty, but its absence is defensible.

## 2. Token completeness — strong

Checked: extracted every YAML frontmatter token and every `{path.to.token}` reference across both files. All color tokens carry hex. All DESIGN.md prose/component references (`{colors.*}`, `{rounded.md}`, `{rounded.pill}`) resolve to defined tokens. No undefined references.

### Findings
- **medium** Load-bearing contrast targets are asserted but not stated as ratios for the two domain combos USWDS does **not** warrant: `beer #B8860B` gold banner on ink `#1B1B1B` text, and the three verdict foregrounds on their `-bg` tints (`pass #2E8540` on `#ECF3EC`, `review #B8860B` on `#FAF3D1`, `fail #B50909` on `#F4E3DB`). DESIGN.md:181 says "beer gold on dark ink text (contrast)" and Accessibility Floor leans on "USWDS AA baseline," but these are *new* domain colors layered on USWDS, so AA inheritance doesn't auto-cover them (DESIGN.md:88–99, 181; EXPERIENCE.md:121). *Fix:* state the computed AA ratio (or "verified ≥4.5:1 / ≥3:1 large") for beer-on-ink and each verdict-tag fg/bg pair, so story-dev has a number to test against rather than a verbal assurance.
- **low** `review #B8860B` (amber) and `beer #B8860B` (gold) are the *same hex*. DESIGN.md:145 acknowledges this and argues spatial separation prevents collision — defensible, but a downstream reader extracting the palette could read it as a copy-paste error. *Fix:* a one-word inline note at the token (`# same hex as review, intentional — never co-located`) removes the ambiguity at the point of extraction.

## 3. Component coverage — strong

Checked: extracted every component named in either spine; verified each domain/brand component has a DESIGN.md.Components visual row AND an EXPERIENCE.md.Component Patterns behavioral row with real rules.

Paired and consistent: Button-primary, Disposition buttons (Needs Correction / Reject), Verdict Tag (pass/review/fail), Field comparison card (match/mismatch/soft), Beverage-type banner, Suggested-verdict Alert, Chevron/Step Indicator, Smart checklist, Image panel (Enhance), Notes field, Disposition action bar, Government Warning card, Benchmark comparison table.

### Findings
- **low** Two components carry behavioral rows in EXPERIENCE but no dedicated DESIGN visual row: **Government Warning card** (EXPERIENCE.md:78) and **Benchmark comparison table** (EXPERIENCE.md:84). Both are arguably covered by inheritance — the GW card is a specialization of `field-card-*` tokens, the table is "USWDS Table as-is" — so this is not a true miss. *Fix:* a one-line DESIGN.md.Components note ("Government Warning card — uses field-card-mismatch/soft tokens in a regulation-vs-label layout") would make the inheritance explicit rather than inferred.
- **low** Step Indicator, Accordion ("Why?"), Modal are named as USWDS-as-is in DESIGN.md:173 and behave in EXPERIENCE — correctly treated as inherited, no custom visual row needed. Noted as confirmation, not a gap.

## 4. State coverage — strong

Checked: walked all six IA surfaces (Token gate, Queue, Review Workspace, Help, Benchmark Report, Operational) against the State Patterns table.

- **Token gate** — absent/invalid covered (EXPERIENCE.md:102). Valid-token success is implicit (lands on Queue) — fine.
- **Queue** — empty queue, empty type-queue, item-not-ready all covered (EXPERIENCE.md:91–93).
- **Review Workspace** — cold load, pipeline failure, LLM-unreachable (FR-12), match/soft/mismatch, can't-verify, open-REVIEW-at-Approve, disposition-recorded all covered (EXPERIENCE.md:90–101). Thorough.

### Findings
- **medium** **Benchmark Report** has a Component Pattern row and a Key-Flow appearance but **no State Patterns entries** — no empty/partial-data state (a model/engine row with no results), no loading state for a study that may not be pre-computed like the review path, no "provider unconfigured" state (EXPERIENCE.md:88–102 vs. 84, 164). Given it was promoted to a "FULL SECOND SURFACE" first-class decision (.decision-log.md:45), its state matrix is thinner than the Review surface's. *Fix:* add 1–3 rows: empty/partial benchmark data, and how an unrun engine/model renders.
- **low** **Help panel** has no explicit state row (no-search-results, KB-empty). Lower stakes than Benchmark, but a "Help search: no matches" treatment would match the Voice/Tone discipline applied elsewhere (EXPERIENCE.md:88–102). *Fix:* one optional row.
- **low** **Operational** surface (demo reset, fixture enqueue) has IA presence but no states — acceptable, it's non-specialist tooling, but a "reset complete" / "enqueue: submitted→processing→ready visible" confirmation is implied by .decision-log and could be one row.

## 5. Visual reference coverage — clean (mocks pending, as expected)

`mockups/` and `wireframes/` directories **do not exist** yet; only an empty `imports/` is present. Both spines correctly defer: EXPERIENCE.md:50 says "Composition reference: mockups rendered at Finalize," and both headers state "Spine wins on conflict." **No spine references a named visual file that does not exist** (unlike the shadcn example, which links specific `mockups/*.html`). Not penalized — this is the parallel-render path. No broken visual cross-refs.

## Pass 2 — Judgment

### 6. Bloat & overspecification — strong

DESIGN.md carries editorial voice appropriately ("a desk that is already tidy," DESIGN.md:129). EXPERIENCE.md prose is tight and behavioral. No pixel specs where tokens cover it (minHeight 48px and the few px sizes are genuine domain constraints — older-eyes type floor, click-target floor — not restatement of token scale). Source restatement is minimal and load-bearing: the P4 verdict/disposition table (EXPERIENCE.md:28–33) restates the PRD distinction, but it is *the* governing constraint and earns its place. Persona bios are one sentence each, used as flow setup, not copied résumés.

- **low** The Foundation section restates form-factor/UI-system/firewall facts that also live in DESIGN.md's intro and the PRD (EXPERIENCE.md:20–24). Justified as the spine's self-contained premise, but it is the one spot where the two spines say nearly the same paragraph. No fix needed; flag only.

### 7. Inheritance discipline — strong

All five `sources:` paths resolve from the run directory (prd.md, addendum.md, brief.md, docs/ux-design-notes.md, domain research .md — all confirmed present). UJ names are verbatim ("Dave clears a clean bourbon," "Jenny catches a creative Government Warning," evaluator/procurement). Component names are identical across DESIGN.md.Components, EXPERIENCE.md.Component Patterns, and State Patterns. P-codes (P1/P2/P4/P5), U-codes (U1/U3/U4), FR-7/FR-12, NFR-1/SM-1, SM-C2 all trace to real PRD/decision-log items.

### Findings
- **medium** EXPERIENCE.md:75 uses the reference `{colors.spirits/wine/beer}` — a slash-shorthand for three tokens. The DESIGN spec's cross-reference syntax is one `{path.to.token}` per reference; a naive resolver that splits on `.` will not expand `spirits/wine/beer`. The three underlying tokens exist, so intent is unambiguous, but the literal string won't auto-resolve. *Fix:* write it as `{colors.spirits} / {colors.wine} / {colors.beer}` (three valid refs) so source-extraction tooling resolves each.
- **low** EXPERIENCE.md:121 contains the literal `{path.to.token}` inside an explanatory sentence about the referencing convention — it is meta-prose, not a real reference, but a strict `{...}` extractor will flag it as an unresolved token. *Fix:* render it as code/inline-literal (backticks already present — confirm the extractor ignores backticked tokens) or reword to avoid the brace pattern.

### 8. Shape fit — strong

DESIGN.md sections are in canonical order: Brand & Style → Colors → Typography → Layout & Spacing → Elevation & Depth → Shapes → Components → Do's and Don'ts. All present, none out of order.

EXPERIENCE.md has every required default: Foundation, Information Architecture, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Key Flows — plus the triggered optionals Inspiration & Anti-patterns (justified: this product makes explicit rejections) and no Responsive & Platform section (correctly omitted — the spine declares desktop-only, "none is planned," so a responsive matrix would be noise). Shape is correct.

## Mechanical notes

- **Sources frontmatter:** all 5 paths resolve (prd / addendum / brief / ux_notes / domain_research). Complete.
- **Token resolution:** all `{colors.*}` and `{rounded.*}` references in DESIGN.md resolve. Two EXPERIENCE.md brace-strings need attention: `{colors.spirits/wine/beer}` (non-canonical multi-ref) and `{path.to.token}` (meta-literal). See findings 7.
- **Color tokens:** every color token has a hex (no CRITICAL misses). `review` and `beer` share `#B8860B` intentionally (DESIGN.md:145).
- **Component name consistency:** identical across all sections of both files. No drift.
- **Verdict icon consistency:** ✓ / ⚠ / ✕ paired with PASS / REVIEW / FAIL is consistent between DESIGN.md:141 and EXPERIENCE.md:124. "color never alone" rule stated in both.
- **Numbering note:** the review brief stated "PRD has FR-1..FR-12"; the actual PRD runs FR-1..FR-28 with UJ-1..UJ-3. Flow coverage was validated against the real UJ set. The extra FRs (FR-13..FR-28) are mostly backend/engine/benchmark requirements correctly surfaced as Component/State behavior rather than as separate flows.
- **Mocks:** `mockups/` and `wireframes/` absent (only empty `imports/`); spines defer to Finalize and reference no missing named file. Clean.
