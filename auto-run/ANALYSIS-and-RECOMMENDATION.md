# Factory analysis → recommendation for TTB-LABEL-POC

**Date:** 2026-06-13 · **Author:** Amelia (dev agent), for Diane
**Question:** Diane dislikes invisible background runs and wants to *watch the work live in the
VS Code terminal*. Mine three proven/failed "factory" orchestrators for what works, then
recommend an approach for this project.

---

## 1. The three references (what each taught us)

| Codebase | Stack | Drives Claude via | Outcome | Core lesson |
|---|---|---|---|---|
| `6-Shipyard\shipyard` | Python + LangGraph | **`claude` CLI subprocess**, stream-json decoded **and re-printed live** | **Ran 29 h unattended ✅** | How to be *visible* AND *parseable* at once; bash-first; bounded retries; resume |
| `8-Capstone\factory\shipyard` | Python + LangGraph | same CLI subprocess, output captured | Built pawprintrecipes but **got STUCK fixing** ❌ | The fix-loop failure mode — *exactly our risk* |
| `gauntlet factory-25mar26` (root `build-loop.sh`) | **Bash** (Linux-only) | `claude --print … -- "$(cat prompt)" </dev/null >out 2>&1` | **Stalled a lot** ❌ | Don't fight interactive menus from a non-interactive driver |
| `…\minimum-viable-factory` (teacher's) | Python 3.12 | **`claude-agent-sdk` in-process**, `bypassPermissions` | Clean, stall-free ✅ | SDK + bypassPermissions kills the menu/permission stall; but observability is *externalized* (Linear/Slack/LangSmith), not terminal |

(Relay components ignored throughout, per Diane.)

---

## 2. Two decisive lessons

### Lesson A — Visibility is an *execution-model* choice, not a feature to bolt on

There are three observed models:

1. **Background + captured output** (what *we* did, and the capstone). Output goes to a file;
   the operator is blind. The heartbeat was me trying to reconstruct, badly, what a terminal
   would show for free. **This is the model to abandon.**
2. **Externalized dashboards** (teacher's MVP). Headless server streams progress to Linear /
   Slack / LangSmith. Stall-free and elegant — but it is the *opposite* of "watch it in my
   terminal." Wrong fit for Diane.
3. **Foreground + live-decoded event stream** (the 29-hour winner). The orchestrator runs in
   the *foreground terminal*; each `claude` phase is a subprocess emitting
   `--output-format stream-json`, and the parent **parses every JSON event and prints a
   human-readable play-by-play** — tool calls, file edits, text, with elapsed-time tags like
   `[dev_story 123s] -> Edit: app/normalize.py`. stdin is closed so it can't hang; stdout is
   decoded so you see real activity.

**Model 3 is exactly what Diane wants.** Crucially, the 29-hour success used the *same CLI-subprocess
family our current `auto-run` already uses* — we simply (a) ran it detached instead of foreground,
and (b) summarized into a heartbeat instead of decoding the full stream. The bones are right; the
delivery was wrong.

> Key reframe: **our core mistake was launching detached.** `orchestrate.py` already `print()`s
> to stdout — run it in the foreground VS Code terminal and that output *is* live. The upgrade is
> heartbeat → full decoded event stream.

### Lesson B — "Stall" and "stuck" are two different failures; we must beat both

- **STALL** (gauntlet bash factory): the agent *can't proceed* — it hit an interactive BMAD menu
  or a permission prompt it can't answer over a stdin-closed `--print` session, and burned the
  full 15–45 min timeout doing nothing. Evidence: a bolted-on `/proc` "freeze-diagnostic"
  watchdog, menu-detection regexes, and a "no menus, no questions" prompt arms race
  (`build-loop.sh:1100-1124, 1264+`). **Cure:** `bypassPermissions` + stdin closed + prompt
  discipline that forces the first action. (Our orchestrator already does the first two.)

- **STUCK** (capstone) — *this is our real danger*. The fix loop never converged because:
  1. **Each fix attempt was a fresh, stateless `claude --print` session** — no memory of the last
     attempt; it re-diagnosed the same file and contradicted itself across cycles.
  2. **It fed only the *first* failing CI phase, truncated to 5000 chars.** CI gates run in order
     (fmt→lint→typecheck→migrations→tests); each cycle fixed one gate and *unmasked the next*.
  3. **Flat cycle budget** (`MAX_CI_CYCLES=4`) < number of independent failure classes → guaranteed
     exhaustion on any story tripping 4+ gates.
  4. **"Halt and wait for a human" was the only terminal — in a headless run with nobody watching.**
     One wedged story dead-stopped the whole 169-story backlog at story 132 ($46 spent).
  5. **Timeout killed the agent mid-edit**, leaving uncommitted changes that leaked into the next
     story's commit.

---

## 3. What our current `auto-run` already gets right (keep it)

- CLI-subprocess family on **subscription auth** (API key stripped) — the *proven* 29-h family.
- `stdin=subprocess.DEVNULL` (FINDINGS-01) and `bypassPermissions` — both anti-stall levers.
- **sprint-status.yaml as the source of truth**, with a forward-only status gate per phase.
- **Bash-first CI gate** (`scripts/ci.sh`) — deterministic checks, LLM only to fix on red. (This is
  literally the 29-h winner's headline pattern.)
- Bounded retry caps; commit scoping that walls off `auto-run/`; STOP sentinel; single-instance lock.

We do **not** need to rebuild on LangGraph or the SDK. For a single-project, ~dozen-story POC, the
lean while-loop over sprint-status is sufficient; LangGraph's value (nested state machines, SQLite
crash-resume) is overkill here and adds weight. The SDK is tempting (no arg-escaping bugs) but it
risks the **subscription-auth** model and removes the clean subprocess boundary — and the 29-h proof
point is the CLI path, not the SDK.

---

## 4. The immediate bug, explained by the references

Our `dev_story` phase died instantly with *"Input must be provided … when using --print."*
**Both working references pass the prompt after a `--` end-of-options separator:**
- shipyard: `cli_args.extend(["--", prompt])`
- bash factory: `… -- "$(cat prompt)"`

Our code does `cmd.append(prompt)` with **no `--`**. The short smoke-test prompt slipped through; the
real multi-line prompt did not. **Fix: pass `["--", prompt]`.** High confidence — it's how both
survivors invoke the CLI.

---

## 5. Recommended solution for TTB-LABEL-POC

A focused rework of the existing orchestrator — not a rewrite. Decisions, each with rationale:

### 5.1 Run in the **foreground** of the VS Code terminal (the core change)
Launch is `python -m auto-run.orchestrate --once` (or a thin `run.ps1`) **run directly in the
terminal Diane is watching** — never detached / `run_in_background`. The orchestrator's stdout *is*
the live view. This single change is 80 % of what she asked for.

### 5.2 Replace the heartbeat with a **live decoded event stream**
Port shipyard's `_print_stream_event`: for each stream-json line, print a compact human line —
`[<phase> <elapsed>s] text…`, `-> Edit: <path>`, `-> Bash: <cmd>`, `<- result (ok|error, $cost, N turns)`.
Diane sees every tool call and edit as it happens. Keep the full `{phase}.jsonl` on disk for forensics.
(stderr drained on a daemon thread so the pipe can't deadlock — shipyard pattern.)

### 5.3 Keep the **CLI subprocess + subscription auth** path; apply the `--` fix
Add the `--` separator. Keep `bypassPermissions`, `stdin=DEVNULL`, `GIT_TERMINAL_PROMPT=0`.

### 5.4 Redesign the **fix loop** to beat "stuck" (the capstone autopsy → our spec)
1. **Stateful repair:** run the fix attempts in **one resumable Claude session**
   (`claude --resume <session-id>`) so each attempt builds on the last instead of re-diagnosing.
2. **Feed the *complete* CI failure set, untruncated.** Make `ci.sh` (or a wrapper) report **all**
   failing phases in one pass — not just the first — so a single fix addresses them together.
3. **Budget by *progress*, not a flat count:** continue only while the failing-gate set *shrinks*;
   abort the moment a cycle makes no measurable progress (and cap absolute attempts as a backstop).
4. **Revert partial edits on timeout/abort** (`git stash`/`checkout`) so a killed attempt never leaks
   into the next unit's commit.
5. **Supervised halt is fine — because Diane is watching.** The capstone's fatal flaw was halting
   with nobody there. In a foreground supervised run, **halt-clean-and-surface** is correct: stop,
   print exactly what's wedged and the resume command, and let Diane intervene. (Autonomous
   skip/quarantine/continue is a *later* upgrade for true overnight mode, not needed now.)

### 5.5 Keep the lean loop; add lightweight resume only if needed
Stay with the sprint-status while-loop. If crash-resume matters later, copy shipyard's tiny
`session.json` (`resume_story_index` + counters) rather than adopting LangGraph.

### 5.6 Anti-stall levers (already mostly present — keep/verify)
stdin closed · `bypassPermissions` · per-phase timeout → kill → treat as failure · bounded+progress
retries · prompt preambles that forbid menus/questions and force the first action · `GIT_TERMINAL_PROMPT=0`.

---

## 6. Build plan (incremental, watched)

1. **Fix `--` + foreground + decoded stream** → re-run **3-1 supervised in the terminal**. Confirm it
   actually writes `normalize.py`/`verdict.py` while Diane watches. *(Smallest change that unblocks.)*
2. **Harden the fix loop** (stateful `--resume`, full-CI output, progress budget, revert-on-abort).
3. **Chain a second story** (3-2) supervised; tune the live output.
4. Only then revisit unattended/overnight + worktree isolation (already built, off by default).

---

## 7. Decisions for Diane

- **D1 — Approach:** rework the existing CLI-subprocess orchestrator (foreground + live decode +
  smarter fix loop), *not* a rebuild on SDK/LangGraph. **(Recommended.)**
- **D2 — Visibility rendering:** decoded stream-json play-by-play in the terminal. **(Recommended.)**
- **D3 — Stuck policy for now:** supervised *halt-clean-and-surface* (you're watching) rather than
  autonomous skip/continue. **(Recommended; autonomous escalation deferred to overnight mode.)**
