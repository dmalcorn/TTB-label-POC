# Finding 01 — `dev_story` phase hangs at startup (stdin not closed)

**Status:** root cause confirmed · **FIXED** — `stdin=subprocess.DEVNULL` applied to
`run_claude`/`run_ci`/`git` in commit `453769d`; stream-json heartbeat + early
stall-abort added in `36b6ac0` (so a future hang is visible and killed in
`stall_timeout_sec`, not 90 min). Verified: a trivial phase logged `session init`
within 1s and returned cleanly with no stdin hang.
**Found:** 2026-06-13, first supervised `--once` run of story 3-1.

## Symptom

The `dev_story` phase started and then hung indefinitely:
- process alive but **idle** — ~2.6 CPU-seconds in 52 minutes,
- **zero** file writes in `app/` or `tests/`,
- no session transcript persisted,
- `run.log` frozen after the "starting phase" line.
Left alone it would burn the full `phase_timeout_sec` (90 min) and halt with nothing.

## Root cause

`run_claude()` calls `subprocess.run(..., capture_output=True)` but **does not close
the child's stdin**. Launched from a *detached* PowerShell background process, the
inherited stdin is an open pipe that never sends EOF. `claude -p` reads stdin when it
isn't a TTY, so it **blocks forever waiting on stdin** before doing any work.

Not MCP (stream init showed `mcp=[]`). Not the skill. Not the prompt.

## Proof

Reproduced the identical phase with streaming + stdout redirected to a file (so stdin
is effectively EOF):

```bash
claude -p "<contents of prompts/dev_story.md>" \
  --output-format stream-json --verbose \
  --permission-mode bypassPermissions --model claude-opus-4-8 --max-turns 250 \
  > repro.jsonl 2>&1
```

It ran perfectly — loaded the skill, read project-context + sprint-status, selected
3-1, wrote a TodoWrite, and began test-first on `tests/test_normalize.py`. The only
difference from the hung run is stdin handling.

## Fix (one line)

In `run_claude()`'s `subprocess.run` call:

```python
proc = subprocess.run(
    cmd,
    cwd=cfg.repo_root,
    env=child_env(),
    text=True,
    capture_output=True,
    stdin=subprocess.DEVNULL,      # <-- REQUIRED: guarantees EOF so claude -p never blocks on stdin
    timeout=c["phase_timeout_sec"],
)
```

Belt-and-suspenders: add `stdin=subprocess.DEVNULL` to the `run_ci()` and `git()`
`subprocess.run` calls too (any spawned tool that might read stdin).

## Follow-up improvements (recommended, not blocking)

- **Heartbeat + early stall-abort.** The harness was blind — it couldn't tell "working"
  from "hung". Watch the child's CPU time and/or its session-transcript mtime; abort
  after N minutes of no progress instead of waiting out `phase_timeout_sec`.
- **Stream for observability.** Consider running phases with
  `--output-format stream-json --verbose` and logging a heartbeat line per event, so
  `run.log` shows live progress and the exact tool call if it ever stalls again.

## Verify after applying

A clean retry of 3-1 should now write `app/normalize.py`, `app/verdict.py`, and their
tests, and advance 3-1 `ready-for-dev -> review`. Diagnose any future silent run with
`--output-format stream-json --verbose` and tail the JSONL.
