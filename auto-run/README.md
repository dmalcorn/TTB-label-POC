# auto-run — overnight story orchestrator

Drives the BMad cycle for one story at a time, **sequentially**, unattended,
using the **headless Claude CLI on your subscription** (no API key billed):

```
create-story → dev-story → code-review → ci.sh (+ fix loop) → commit → push
```

…then moves to the next story in `sprint-status.yaml`, until there are no
stories left, a cap is hit, or something fails.

## Why Python (not bash)

The hard parts of an unattended multi-hour run — per-phase timeouts, killing a
hung phase, parsing `claude --output-format json`, a CI fix loop, graceful stop,
verifying each story actually advanced — are painful in bash on Windows and
clean in Python. The orchestrator is Python; it shells out to your existing
bash `scripts/ci.sh`, to `git`, and to `claude`. One brain, right tool per step.

## Files

| File | Purpose |
|------|---------|
| `orchestrate.py` | The loop. Reads config, drives phases, verifies, commits, pushes. |
| `config.toml` | Every knob. Edit values, not code. |
| `prompts/*.md` | The headless prompt for each phase (with a "never ask, you're unattended" preamble). |
| `run.ps1` | Windows launcher. Clears `ANTHROPIC_API_KEY` to force subscription auth. |
| `logs/<run-id>/` | Per-run logs: `run.log` + one JSON transcript per phase. (gitignored) |
| `STOP` | Create this file to halt gracefully after the current story. (gitignored) |

## Behavior locked in (from the design Q&A)

- **On failure → halt and leave.** Any unrecoverable error (a phase that doesn't
  advance the story, CI red after fix attempts, a failed push, a timeout) stops
  the whole run and leaves the tree on disk for morning review. Nothing
  half-baked is pushed.
- **Commit + push to the current branch (main)** after each green story.
- **Model: Opus 4.8** (`model = "opus"`). Set `fallback_model = "sonnet"` in
  `config.toml` if overnight Opus rate limits become a problem.

## Truth source = sprint-status.yaml

Each phase MUST advance the story's status (`backlog → ready-for-dev → review →
done`). After every phase the runner re-reads `sprint-status.yaml` and halts if
the status didn't move forward — so a skill that silently failed to update
status can't let the runner push broken work.

## First run — do this in order

1. **Commit or stash the existing uncommitted work first.** The runner refuses
   to start on a dirty tree (`stop_on_dirty_tree = true`). Right now the repo
   has untracked Epic-2 LLM adapters and Epic-3 story files — get those into a
   commit before launching.
2. **Confirm subscription auth, not an API key:**
   ```pwsh
   echo $env:ANTHROPIC_API_KEY   # should be empty; run.ps1 clears it anyway
   claude -p "say ok" --output-format json   # should return JSON, no login prompt
   ```
3. **Dry run** (calls nothing — shows the next story and plan):
   ```pwsh
   pwsh auto-run/run.ps1 -DryRun
   ```
4. **One supervised story** while you watch:
   ```pwsh
   pwsh auto-run/run.ps1 -Once
   ```
5. **Let it run overnight:**
   ```pwsh
   pwsh auto-run/run.ps1
   ```

## Safety rails

- `max_runtime_hours` / `max_stories` — hard bounds on the night.
- `phase_timeout_sec` — a hung phase is killed and the run halts.
- `max_turns` — a runaway phase can't loop forever.
- `STOP` sentinel + Ctrl-C — graceful stop after the current story/phase.
- API key/token stripped from the child env — can't accidentally bill an API key.

## Known risks (read once)

- **Unattended `AskUserQuestion`.** If a skill tries to ask a question, the
  prompt preambles tell it to decide and proceed instead. If a skill still
  stalls, the `phase_timeout_sec` kills it and the run halts — you lose the
  night's remaining stories but not your tree.
- **Quality drift.** Unattended dev+review is not a substitute for your eye.
  Review the commits in the morning before turning anything in.
- **`bypassPermissions`** runs tools without prompting. That's the point, but it
  means a bad phase can change a lot. The halt-on-first-failure policy + git
  history are your undo.
