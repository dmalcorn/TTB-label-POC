# auto-run — handoff for the next agent

You're picking up an in-flight effort with Diane to build an **overnight,
unattended story orchestrator** for this repo. Read `auto-run/README.md` first
for what the tool is; this file is the *strategy + process* context that isn't
in the code.

Persona note: Diane works with the BMad "Amelia" dev agent. Be succinct, cite
file paths/AC IDs, test-first. Honor `_bmad-output/project-context.md`.

---

## Current state (as of this handoff)

- The harness is built and committed on `main` (commits `6b6e2c0`, `1f9bc97`).
- A **supervised `--once` run of story 3-1 may be LIVE** in a background process
  when you start. Check: `auto-run/logs/<newest>/run.log`. If it's still running,
  see the parallel-work rules below before you touch git.
- Locked decisions (from the design Q&A): **halt-and-leave on failure**;
  **commit+push to `main`** after each green story (this changes under the
  worktree plan, below); **model = `claude-opus-4-8`** (the `opus` alias resolves
  to 4.5 on this CLI — always use the explicit id); **subscription auth** (strip
  `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the child env).

## How Diane wants to work (the process vision)

Iterate the harness one story at a time until it's trustworthy enough to chain
stories unattended overnight:

1. Launch one story (supervised at first: `pwsh auto-run/run.ps1 -Once`).
2. Watch the run log + inspect the resulting commit/diff for rough edges.
3. Improve the harness (prompts, guards, retries, isolation…).
4. Commit harness improvements to `main` — **`auto-run/` paths only**.
5. Run the next story (3-2, then 3-3…) with the improved harness.
6. Repeat until N consecutive clean stories → trust it for a full overnight chain.

So: get a run going, improve the harness *while it runs*, commit improvements
once it's idle, run the next story. Your job is to make step 3 excellent.

## Parallel-work rules (CRITICAL — single shared working tree)

Diane's windows and the orchestrator all share ONE working dir
(`c:\alcorn\Treasury\TTB-label-POC`) → one git index, one HEAD. While a run is live:

- ✅ **Edit `auto-run/` files freely.** The orchestrator loaded its code at launch
  and its story commits exclude `auto-run/` (`git.exclude_paths`), so your edits
  can't be swept in.
- ⛔ **Run NO git command** (`add`/`commit`/`push`/`pull`/`checkout`) until the run
  is idle. Two processes writing the shared index/HEAD race on `index.lock`.
- After the run is idle: review the story commit, then commit harness changes.

The worktree plan below is what *removes* this constraint — build it first.

---

## Priority improvement #1: run in a dedicated git worktree

**Why:** isolation. A worktree is a second working dir with its **own index**,
sharing the same `.git` object store. The orchestrator commits story work in the
worktree on its own branch while a human commits harness changes on `main` —
**no index contention, no push race.** This is what makes true unattended +
parallel-edit safe.

**Design sketch:**
- Before a run: `git worktree add <path> -b auto/run-<id> origin/main`
  (fresh checkout of latest `main` → automatically includes the newest harness).
- Orchestrator runs with `repo_root = <worktree path>`; everything else unchanged.
- Story commits land on `auto/run-<id>` (per-run) — or `auto/story-<sid>`
  (per-story) if Diane prefers reviewing one branch per story.
- **Replace "push to main directly" with "push the run branch; human reviews &
  merges."** Safer for unattended; fast-forward or PR merge afterward.
- Cleanup: `git worktree remove <path>` on success; leave it on halt for review.
- Config: add a `[worktree]` block — `enabled`, `base_ref`, `branch_prefix`,
  `path_template`, `cleanup_on_success`. Keep the current single-tree mode behind
  `enabled = false` so nothing regresses.
- Caveats: git forbids two worktrees on the same branch (so the run branch must
  differ from `main`); pre-commit/`ci.sh` run in the worktree identically; the
  SQLite DB + generated images are local dev artifacts — fine per worktree.

## Candidate improvement backlog (discuss/prioritize with Diane)

- [ ] **Worktree isolation** (above) — do this first.
- [ ] **Resumable state** — `state.json` exists in `.gitignore` but isn't written
      yet; persist per-phase progress so a killed run can continue, not restart.
- [ ] **Richer commit messages** — derive from the story title / dev summary
      (optionally a tiny `claude -p` call) instead of the `auto: story <id>` stub.
- [ ] **Completion/halt notification** — push notification or email so Diane wakes
      to a status, not a guess.
- [ ] **Cost/turn summary** — aggregate `total_cost_usd`/`num_turns` from each
      phase JSON into a per-run summary line.
- [ ] **Single-instance lock** — refuse to start if another run is active.
- [ ] **AskUserQuestion stall handling** — `phase_timeout_sec` covers it bluntly;
      consider `--output-format stream-json` to detect a stall faster.
- [ ] **Optional `validate-create-story`** step for `backlog` stories before dev.
- [ ] **Pre-run `git pull --rebase`** — only needed in direct-push mode; moot once
      on the worktree+branch model.

## File map

| File | Purpose |
|------|---------|
| `orchestrate.py` | The loop. Phases, status verification, CI gate, commit/push. |
| `config.toml` | All knobs. `[git].exclude_paths` walls off the harness. |
| `prompts/*.md` | Per-phase headless prompts (with "you're unattended, never ask"). |
| `run.ps1` | Windows launcher; clears API key → forces subscription. |
| `logs/<run-id>/` | `run.log` + one JSON transcript per phase. (gitignored) |
| `README.md` | What it is + first-run checklist + known risks. |

Truth source for "next story" and transition verification is
`_bmad-output/implementation-artifacts/sprint-status.yaml`.
