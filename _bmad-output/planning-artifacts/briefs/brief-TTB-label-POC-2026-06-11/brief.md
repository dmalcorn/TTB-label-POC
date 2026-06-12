---
title: "Product Brief: TTB COLA Label Specialist Workspace"
status: ready
created: 2026-06-11
updated: 2026-06-11
---

# Product Brief: TTB COLA Label Specialist Workspace

## Executive Summary

The TTB COLA Label Specialist Workspace is an AI-assisted review tool for the federal specialists
who approve alcohol-beverage labels. Roughly 47 of them review some 150,000 applications a year,
and about half their day goes to rote verification — confirming that the brand name, alcohol
content, and government warning on a bottle match what was filed. The last attempt to automate
this was abandoned for being too slow (30–40 seconds a label, when a specialist can check five by
eye), and that failure left a simple, unforgiving bar: **if results don't appear in about five
seconds, no one will use it.**

This proof of concept clears that bar by running the OCR and compliance checks in the background
the moment an application is submitted, so the review screen is ready the instant a specialist
clicks **"Next Submission"** — no wait. It stacks each filed value against what the machine read on
the label, highlights discrepancies, walks a built-in checklist, and marks every check
**PASS / REVIEW / FAIL** — but the specialist makes the call. It is the only tool aimed at the
*reviewer* rather than the applicant, every choice in it answers a documented reason past tools
failed, and — because it benchmarks two OCR engines and several AI models side by side — it
produces the speed, accuracy, and cost data to inform what TTB should actually buy.

It is, deliberately, a modest and honest prototype: it reads from a mock database, runs entirely
behind the firewall, stores no sensitive data, and claims only what it can demonstrate. Yet the
same pattern could become the specialists' daily workspace — and a template for other government
review work buried in the same routine.

## The Problem

Every modernization attempt the TTB Label Specialists have lived through made their job harder,
not easier. The last one — an automated label scanner — took 30 to 40 seconds per label; a
specialist could check five by eye in that time, so the team quietly went back to doing it by
hand. The lesson stuck: *"If we can't get results back in about 5 seconds, nobody's going to use
it."* After two decades in the same COLA system, a senior specialist assumes the next new tool
will be one more thing to fight with. Anything slow, clunky, or that tries to make the decision
for them gets rejected on contact — no matter how clever it is underneath.

Beneath that earned distrust is a real waste. Roughly 47 specialists (down from over 100 in the
1980s) review about 150,000 applications a year, and by their own account **half of that work is
"essentially data-entry verification"** — confirming the brand name, alcohol content, and
government warning on the bottle match the application, exactly. It is expert judgment spent on
rote matching. The people doing it span a wide range of tech comfort — from a junior analyst who
could have built the tool herself to a 28-year veteran who still prints his email — so the bar is
not merely "fast," it is "obvious enough that a 73-year-old could use it without hunting for a
button." The opportunity is to lift the rote matching off their plate and hand back time for the
judgment only a human should make — but only if the tool earns trust in the first five seconds.

## The Solution

A review workspace that is **already done thinking by the time the specialist sits down.** The
instant an application is submitted, background jobs read the label (OCR) and run the compliance
checks, so when a specialist clicks **"Next Submission," the review screen loads immediately** —
label image, application fields, and advisory findings all present, no wait. The
thirty-seconds-a-label tax that killed the last tool simply does not exist here.

On that screen, each application field is stacked vertically with the machine-read value
directly beneath it and any discrepancy highlighted, so the eye confirms a match in a single
glance. A built-in checklist — the digital descendant of the paper one specialists keep at their
desks — walks the required checks for that beverage type, and the engine marks each
**PASS / REVIEW / FAIL.** Those are recommendations only: the specialist reviews the findings and
records the official disposition — **Approved, Needs Correction, or Rejected.** Speed is the
point; keeping the human in command is what makes the speed trustworthy enough to adopt.

## What Makes This Different

This is a proof of concept, and it is honest about that: there is no moat here — no proprietary
data, no lock-in, nothing a competent team couldn't rebuild. Its edge is **fit** and a
**measurable byproduct**, and both are real.

**It is the only thing aimed at the reviewer.** Every comparable tool on the market — COLAClear,
GetGen, Phantom Ales — helps the *applicant* pre-screen a label before submitting. None serves
the federal Label Specialist on the other side of the desk, who has no purpose-built software at
all and works in a COLA system largely unchanged since 2003. The POC steps into an empty room.

**It is designed around why earlier attempts failed.** The instant-load pipeline exists to beat
the five-second wall that doomed the last scanner; the recommend-don't-decide model exists to
respect the specialist's authority rather than usurp it; the fully local, no-cloud architecture
exists because the government firewall is what crippled the previous vendor's cloud features. The
differentiator is not novelty — it is that every design choice answers a documented failure mode.

**It is a working tool *and* a procurement study.** Rather than betting on a single OCR engine or
one AI model, the POC runs two OCR engines and several language models side by side on the same
labels and records their speed, accuracy, and cost. That produces exactly the "information that
could inform future procurement decisions" the assignment invited: when TTB later decides what to
buy, the evidence is already gathered. The demo is also a measurement instrument.

## Who This Serves

**Primary: the TTB Label Specialist** — a range of people, and the tool is designed for the
hardest end of it. **Dave** — twenty-eight years in, still prints his email, has watched
modernization projects come and go — is the adoption gate: if the screen is obvious and instant
enough that *he* keeps using it past day one, everyone will. He prizes the calls a machine can't
make (is "STONE'S THROW" really a mismatch with "Stone's Throw"? — obviously the same product)
and will abandon anything that slows him down or second-guesses his judgment. At the other end is
**Jenny** — eight months in, fluent with technology, already working from a printed desk checklist
she'd love built into the software. Success for both is identical: clear the routine matching in
seconds and get back to the work that needs a human.

**Secondary: Sarah**, the Deputy Director who sponsors the tool and judges it on adoption and
throughput; and **Marcus** in IT, whose constraints — no outbound cloud calls through the federal
firewall, no PII, runs in the browser off the central system — are non-negotiable boundaries the
product is built to respect.

## Success Criteria

Because this is a proof of concept, the brief commits only to what the prototype can demonstrate.
Each criterion below is measurable on the deployed POC:

- **Ready in under ~5 seconds.** When a specialist clicks "Next Submission," the review screen —
  label, application fields, and advisory findings — is fully loaded in roughly five seconds or
  less, because the OCR and checks were pre-computed at submission. This is the headline
  criterion: the product's identity, and the exact failure that doomed the last tool.
- **Core matching works end to end.** On real and synthetic labels, the engine reads the label
  and checks the brand name, alcohol content, and government warning against the application,
  marking each **PASS / REVIEW / FAIL** — with the government-warning wording verified exactly.
- **It produces procurement evidence.** Running two OCR engines and several models on the same
  labels, the POC reports their speed, accuracy, and cost side by side — including a
  cost-per-1,000-verifications figure — as real data to inform a future buying decision.
- **It is testable and clean.** It deploys to a public URL the evaluators can exercise, with
  organized code and documented approach, tools, assumptions, and trade-offs.

## Scope

**In, for the first version:**

- A **read-only** Label Specialist review workspace over a **mock COLA database** seeded with
  dummy applications — no connection to the real COLA system.
- **All three beverage types** — distilled spirits, wine, and malt beverages — each with its own
  rule set; distilled spirits is the most fully worked example.
- The review experience: a single **"Next Submission"** entry, the vertically stacked
  application-vs-label comparison with discrepancies highlighted, a built-in **checklist**, a step
  **status bar**, advisory **PASS / REVIEW / FAIL** findings, and recording the official
  **disposition** (Approved / Needs Correction / Rejected).
- The **pre-compute pipeline**: background jobs that OCR and analyze each label at submission.
- The **procurement study**: two OCR engines plus several models run on the same labels, with
  speed, accuracy, and cost captured (cloud models run only in an offline benchmark, never in the
  deployed app).
- Local image clean-up (deskew, glare, contrast) to handle imperfect photos without a re-submit.
- A **USWDS**-based interface and a **token-gated** public URL so only evaluators can reach the demo.

**Out, deliberately:**

- **No image upload or data entry** — v1 reads existing records; capturing applications is the
  applicant's system, not this one.
- **No font or dimension-size checking** — it cannot be measured reliably from a photo, and TTB's
  own process disclaims it.
- **No live integration** with the real COLA/.NET system — an API and integration are Phase 2.
- **No authentication system, no PII, no cloud calls** from the deployed app — the token gate, the
  no-PII rule, and the firewall boundary are respected by design, not bolted on.
- **No batch upload** in the reviewer tool — batching is an applicant-side convenience; to the
  specialist, every submission is reviewed one at a time regardless.

## Vision

If it succeeds, the prototype graduates from a standalone demo into the Label Specialists' daily
workspace — integrated with the COLA system through the Phase 2 API, so the assist lives inside
the real workflow rather than beside it. When TTB decides which OCR engine and which AI model to
invest in, the choice rests on the speed, accuracy, and cost this prototype already measured. Day
to day, routine matching is cleared in seconds; the specialists who were most skeptical use it
without thinking about it; and the hours it returns are spent on the judgment calls — the
"STONE'S THROW" reads, the genuinely ambiguous labels — that only a human should make. Fewer of
the errors a tired eye skips slip through, and the government-warning rule is applied the same
exact way every time.

Beyond TTB, the shape of the thing generalizes: any federal review desk buried in routine
document-matching — where an expert's time goes to confirming that one record matches another —
could be served by the same pattern of pre-computed analysis, advice that never overrides the
human, and a design that runs entirely behind the firewall.
