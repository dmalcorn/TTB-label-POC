#!/usr/bin/env python3
"""Overnight story orchestrator for the TTB label POC.

Drives the BMad cycle for one story at a time, sequentially, unattended:

    create-story -> dev-story -> code-review -> ci.sh (+ fix loop) -> commit -> push

then moves to the next story. It NEVER runs phases in parallel.

Design choices (see auto-run/README.md and config.toml):
- Python, not bash: per-phase timeouts, JSON parsing, a resumable state file,
  and a fix loop are all painful in bash on Windows.
- Headless Claude CLI on the *subscription* (ANTHROPIC_API_KEY is stripped from
  the child env so it can't silently override the logged-in session).
- Halt-and-leave on failure: on any unrecoverable error the run stops with a
  clean local commit history and the broken story's work left on disk for review.
- Truth lives in sprint-status.yaml: each phase must ADVANCE the story's status
  or the run halts. We never push work a phase failed to complete.

Usage:
    python auto-run/orchestrate.py            # run until done / failure / cap
    python auto-run/orchestrate.py --once      # exactly one story, then stop
    python auto-run/orchestrate.py --dry-run   # show the plan, call nothing
    python auto-run/orchestrate.py --config path/to/config.toml

Graceful stop: create a file named  auto-run/STOP  and the runner halts after
the current story finishes (it checks before starting each story). Ctrl-C also
stops after the current phase.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --- status model ---------------------------------------------------------

# Forward-only story lifecycle. A phase must move the story to a higher rank.
STATUS_RANK = {
    "backlog": 0,
    "ready-for-dev": 1,
    "in-progress": 2,
    "review": 3,
    "done": 4,
}
DONE = "done"

# Which prompt drives a story out of its current status.
PHASE_FOR_STATUS = {
    "backlog": "create_story",
    "ready-for-dev": "dev_story",
    "in-progress": "dev_story",  # a dev phase that was interrupted; resume it
    "review": "code_review",
}

STORY_KEY_RE = re.compile(r"^\d+-\d+-")  # e.g. "3-1-normalization-..."
SKILL_DIR = Path(__file__).resolve().parent

# Windows consoles default to cp1252 and choke on the arrows/emoji we log.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


class Halt(Exception):
    """Unrecoverable: stop the run, leave the tree as-is for morning review."""


# --- config ---------------------------------------------------------------


@dataclass
class Config:
    raw: dict
    # `repo_root` is WHERE PHASES RUN: the main checkout in single-tree mode, or
    # the worktree once one is set up (rebound in main, along with sprint_status
    # and ci_script). `canonical_repo` is the main checkout where .git lives —
    # the only place `git worktree add/remove/prune` may run. They're equal until
    # a worktree is created.
    repo_root: Path
    canonical_repo: Path
    sprint_status: Path
    ci_script: Path
    add_dirs: list[str]

    @property
    def run(self) -> dict:
        return self.raw["run"]

    @property
    def claude(self) -> dict:
        return self.raw["claude"]

    @property
    def ci(self) -> dict:
        return self.raw["ci"]

    @property
    def git(self) -> dict:
        return self.raw["git"]

    @property
    def worktree(self) -> dict:
        return self.raw.get("worktree", {"enabled": False})

    def rebind_to(self, work_root: Path) -> None:
        """Point phase/CI/status paths at a new working dir (the worktree)."""
        paths = self.raw["paths"]
        self.repo_root = work_root
        self.sprint_status = (work_root / paths["sprint_status"]).resolve()
        self.ci_script = (work_root / paths["ci_script"]).resolve()


def load_config(path: Path) -> Config:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    paths = raw["paths"]
    repo_root = (path.parent / paths["repo_root"]).resolve()
    return Config(
        raw=raw,
        repo_root=repo_root,
        canonical_repo=repo_root,
        sprint_status=(repo_root / paths["sprint_status"]).resolve(),
        ci_script=(repo_root / paths["ci_script"]).resolve(),
        add_dirs=list(paths.get("add_dirs", [])),
    )


# --- logging --------------------------------------------------------------


@dataclass
class RunLog:
    run_dir: Path
    log_file: Path = field(init=False)

    def __post_init__(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.run_dir / "run.log"

    def say(self, msg: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{stamp}] {msg}"
        print(line, flush=True)
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


# --- sprint-status parsing ------------------------------------------------


def read_statuses(cfg: Config) -> dict[str, str]:
    """Parse the `development_status:` block. Dependency-free (no PyYAML)."""
    text = cfg.sprint_status.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    in_block = False
    for line in text.splitlines():
        if line.strip().startswith("development_status:"):
            in_block = True
            continue
        if not in_block:
            continue
        if line and not line[0].isspace():
            break  # left the indented block
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        key, _, val = s.partition(":")
        out[key.strip()] = val.split("#", 1)[0].strip()
    return out


def next_story(statuses: dict[str, str]) -> str | None:
    """First story (file order) that is a real story and not done."""
    for key, status in statuses.items():
        if not STORY_KEY_RE.match(key):
            continue  # skip epic-N, *-retrospective
        if status != DONE:
            return key
    return None


def status_of(cfg: Config, story: str) -> str:
    return read_statuses(cfg).get(story, "backlog")


# --- the claude headless call --------------------------------------------


def child_env() -> dict[str, str]:
    """Force the subscription session: strip key/token overrides."""
    env = dict(os.environ)
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(var, None)
    return env


def _summarize_event(evt: dict) -> str:
    """One-line, human-readable gist of a stream-json event for the heartbeat."""
    t = evt.get("type")
    if t == "system":
        return f"session {evt.get('subtype', 'event')}"
    if t == "assistant":
        blocks = (evt.get("message") or {}).get("content") or []
        tools = [
            b.get("name")
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name")
        ]
        if tools:
            return "tool: " + ", ".join(tools)
        if any(isinstance(b, dict) and b.get("type") == "thinking" for b in blocks):
            return "thinking"
        return "writing"
    if t == "user":
        return "tool result"
    if t == "result":
        return f"result ({evt.get('subtype', '')})"
    return str(t or "event")


def run_claude(cfg: Config, log: RunLog, prompt: str, label: str) -> None:
    """Run one headless phase, streaming events for a live heartbeat. Raises Halt on failure.

    Uses --output-format stream-json so the run isn't blind: we log a progress
    line as events arrive, and abort EARLY on a stall (no events for
    stall_timeout_sec) instead of waiting out the full phase_timeout_sec hard cap.
    See auto-run/FINDINGS-01-stdin-hang.md.
    """
    c = cfg.claude
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",  # required by the CLI for stream-json in print (-p) mode
        "--permission-mode",
        c["permission_mode"],
        "--model",
        c["model"],
        "--max-turns",
        str(c["max_turns"]),
    ]
    if c.get("fallback_model"):
        cmd += ["--fallback-model", c["fallback_model"]]
    for d in cfg.add_dirs:
        cmd += ["--add-dir", d]
    cmd += list(c.get("extra_args", []))
    cmd.append(prompt)  # positional prompt last

    hard_timeout = int(c["phase_timeout_sec"])
    stall_timeout = int(c.get("stall_timeout_sec", 0))  # 0 = disabled
    heartbeat = max(5, int(c.get("heartbeat_sec", 30)))

    log.say(
        f"  → claude phase '{label}' (model={c['model']}, max_turns={c['max_turns']}, "
        f"hard={hard_timeout}s, stall={stall_timeout or 'off'}s)"
    )
    out_path = log.run_dir / f"{label}.jsonl"

    # stdin=DEVNULL is REQUIRED: a detached child blocks forever on an inherited
    # stdin pipe that never sends EOF (FINDINGS-01).
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cfg.repo_root,
            env=child_env(),
            text=True,
            bufsize=1,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise Halt("`claude` CLI not found on PATH")

    # Windows can't select() on pipes, so drain each stream in a daemon thread and
    # feed a queue the main loop polls — that lets us enforce the timeouts.
    q: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def drain(stream, tag: str) -> None:
        try:
            for line in stream:
                q.put((tag, line))
        finally:
            q.put((tag, None))  # EOF sentinel

    threading.Thread(target=drain, args=(proc.stdout, "out"), daemon=True).start()
    threading.Thread(target=drain, args=(proc.stderr, "err"), daemon=True).start()

    start = time.monotonic()
    last_event = start
    last_beat = start
    seen_any = False
    result_evt: dict | None = None
    err_chunks: list[str] = []
    eofs = 0

    def stop(reason: str) -> None:
        proc.kill()
        raise Halt(reason)

    with out_path.open("w", encoding="utf-8") as fh:
        while eofs < 2:  # both stdout and stderr drained
            now = time.monotonic()
            if now - start > hard_timeout:
                stop(f"phase '{label}' exceeded {hard_timeout}s hard timeout (see {out_path.name})")
            if stall_timeout and now - last_event > stall_timeout:
                stop(f"phase '{label}' stalled — no output for {stall_timeout}s (see {out_path.name})")
            try:
                tag, line = q.get(timeout=2.0)
            except queue.Empty:
                if now - last_beat >= heartbeat:
                    log.say(f"    … {label}: idle {int(now - last_event)}s")
                    last_beat = now
                continue
            if line is None:
                eofs += 1
                continue
            last_event = time.monotonic()
            if tag == "err":
                err_chunks.append(line)
                continue
            fh.write(line)
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "result":
                result_evt = evt
            if not seen_any or time.monotonic() - last_beat >= heartbeat:
                log.say(f"    … {label}: {_summarize_event(evt)}")
                last_beat = time.monotonic()
                seen_any = True

    rc = proc.wait()
    if err_chunks:
        (log.run_dir / f"{label}.stderr.txt").write_text("".join(err_chunks), encoding="utf-8")
    if rc != 0:
        raise Halt(f"phase '{label}' exited {rc} (see {out_path.name})")
    if result_evt is None:
        raise Halt(f"phase '{label}' produced no result event (see {out_path.name})")
    if result_evt.get("is_error"):
        raise Halt(f"phase '{label}' reported is_error (see {out_path.name})")

    cost = result_evt.get("total_cost_usd")
    turns = result_evt.get("num_turns")
    log.say(f"    done ({label}): turns={turns} cost_usd={cost}")


def prompt_text(name: str, **subs: str) -> str:
    text = (SKILL_DIR / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    for key, val in subs.items():
        text = text.replace("{{" + key + "}}", val)
    return text


# --- git + ci -------------------------------------------------------------


def git(
    cfg: Config, *args: str, check: bool = True, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    # Default cwd is the working tree (cfg.repo_root). Worktree management must
    # pass cwd=cfg.canonical_repo — you cannot `git worktree remove` from inside
    # the worktree being removed.
    return subprocess.run(
        ["git", *args],
        cwd=cwd or cfg.repo_root,
        env=child_env(),
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,  # never block on stdin in a detached run (FINDINGS-01)
        check=check,
    )


def tree_dirty(cfg: Config) -> bool:
    return bool(git(cfg, "status", "--porcelain").stdout.strip())


def anything_staged(cfg: Config) -> bool:
    # `git diff --cached --quiet` exits 1 when there ARE staged changes.
    return git(cfg, "diff", "--cached", "--quiet", check=False).returncode != 0


def run_ci(cfg: Config, log: RunLog, fix: bool) -> tuple[bool, str]:
    flag = ["--fix"] if fix else []
    log.say(f"  → ci.sh {' '.join(flag) or '(check)'}")
    proc = subprocess.run(
        ["bash", str(cfg.ci_script), *flag],
        cwd=cfg.repo_root,
        env=child_env(),
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,  # never block on stdin in a detached run (FINDINGS-01)
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, combined


def ci_gate(cfg: Config, log: RunLog) -> None:
    """Run CI; if red, run a fix phase and retry, up to ci.fix_attempts. Halt if still red."""
    ok, out = run_ci(cfg, log, fix=True)  # first pass also auto-formats
    attempts = int(cfg.ci["fix_attempts"])
    for i in range(attempts):
        if ok:
            log.say("    CI green")
            return
        log.say(f"    CI red — fix attempt {i + 1}/{attempts}")
        run_claude(cfg, log, prompt_text("fix", CI_OUTPUT=out[-12000:]), f"ci-fix-{i + 1}")
        ok, out = run_ci(cfg, log, fix=True)
    if not ok:
        (log.run_dir / "ci-final-failure.txt").write_text(out, encoding="utf-8")
        raise Halt("CI still red after fix attempts (see ci-final-failure.txt)")
    log.say("    CI green")


def commit_and_push(cfg: Config, log: RunLog, story: str) -> None:
    if not cfg.git["commit"]:
        log.say("  commit disabled in config — skipping")
        return
    msg = (
        f"auto: story {story}\n\n"
        "Driven by the auto-run overnight orchestrator "
        "(create-story -> dev-story -> code-review -> CI).\n\n"
        "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
    )
    # Scope staging so a story commit can NEVER include excluded paths (e.g. the
    # auto-run/ harness, which a human may be editing in parallel). Positive '.'
    # + exclude pathspecs from the repo root.
    excludes = list(cfg.git.get("exclude_paths", []))
    pathspec = [".", *(f":(exclude){p}" for p in excludes)]

    # pre-commit fixers may rewrite files and fail the first commit; re-add and retry.
    committed = False
    for attempt in range(3):
        git(cfg, "add", "-A", "--", *pathspec)
        if not anything_staged(cfg):
            raise Halt(
                f"nothing staged to commit for {story} "
                f"(no changes outside excludes={excludes}; did a phase produce nothing?)"
            )
        res = git(cfg, "commit", "-m", msg, check=False)
        if res.returncode == 0:
            committed = True
            break
        log.say(f"    commit attempt {attempt + 1} failed (pre-commit?) — re-staging")
        (log.run_dir / f"commit-attempt-{attempt + 1}.txt").write_text(
            res.stdout + "\n" + res.stderr, encoding="utf-8"
        )
    if not committed:
        raise Halt("commit failed after 3 attempts (a hook can't auto-fix — see commit-attempt-*.txt)")
    log.say(f"  committed {story}")

    if cfg.git["push"]:
        # -u sets upstream on first push of a fresh worktree branch; harmless on
        # repeat. In worktree mode HEAD is the per-run branch, so this pushes the
        # run branch for human review — never a direct write to main.
        res = git(cfg, "push", "-u", cfg.git["remote"], "HEAD", check=False)
        if res.returncode != 0:
            (log.run_dir / "push-failure.txt").write_text(res.stdout + "\n" + res.stderr, "utf-8")
            raise Halt("git push failed (committed locally; see push-failure.txt)")
        branch = git(cfg, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
        log.say(f"  pushed {branch} to {cfg.git['remote']}")
        if cfg.worktree.get("enabled"):
            log.say(f"  → review & merge: open a PR for '{branch}' (do NOT auto-merge)")


# --- worktree isolation ---------------------------------------------------


def worktree_path(cfg: Config, run_id: str) -> Path:
    rel = cfg.worktree.get("path_template", "../ttb-autorun-{run_id}").replace("{run_id}", run_id)
    return (cfg.canonical_repo / rel).resolve()


def worktree_branch(cfg: Config, run_id: str) -> str:
    return f"{cfg.worktree.get('branch_prefix', 'auto/run')}-{run_id}"


def setup_worktree(cfg: Config, log: RunLog, run_id: str) -> tuple[Path, str]:
    """Create a fresh worktree on its own branch off the PUSHED base_ref.

    Runs entirely against the canonical repo. Returns (path, branch). Raises
    Halt if the worktree can't be created (no half-state to clean up).
    """
    wt = cfg.worktree
    base_ref = wt.get("base_ref", "origin/main")
    remote = cfg.git.get("remote", "origin")
    path = worktree_path(cfg, run_id)
    branch = worktree_branch(cfg, run_id)

    # Refresh remote-tracking refs so base_ref is current. Best-effort: an
    # offline/transient fetch failure shouldn't abort the night — we branch off
    # whatever origin/main we last saw and log the staleness.
    fr = git(cfg, "fetch", remote, check=False, cwd=cfg.canonical_repo)
    if fr.returncode != 0:
        why = fr.stderr.strip()[:160]
        log.say(f"  worktree: fetch warning (using last-known {base_ref}) — {why}")

    # Clear any stale registrations / a same-named branch from a prior re-run so
    # `worktree add -b` can recreate cleanly (git forbids two worktrees/one branch).
    git(cfg, "worktree", "prune", check=False, cwd=cfg.canonical_repo)
    git(cfg, "branch", "-D", branch, check=False, cwd=cfg.canonical_repo)

    res = git(cfg, "worktree", "add", str(path), "-b", branch, base_ref,
              check=False, cwd=cfg.canonical_repo)
    if res.returncode != 0:
        raise Halt(f"`git worktree add` failed: {(res.stderr or res.stdout).strip()[:400]}")
    log.say(f"  worktree ready: {path}  (branch {branch} off {base_ref})")
    return path, branch


def remove_worktree(cfg: Config, log: RunLog, path: Path) -> None:
    res = git(cfg, "worktree", "remove", "--force", str(path),
              check=False, cwd=cfg.canonical_repo)
    if res.returncode != 0:
        why = (res.stderr or res.stdout).strip()[:200]
        log.say(f"  worktree remove warning (leaving on disk) — {why}")
    else:
        log.say(f"  worktree removed: {path}")


# --- per-story drive ------------------------------------------------------


def drive_story(cfg: Config, log: RunLog, story: str) -> None:
    """Run whatever phases remain to take `story` to done, verifying each transition."""
    while True:
        status = status_of(cfg, story)
        if status == DONE:
            break
        if status not in PHASE_FOR_STATUS:
            raise Halt(f"story {story} in unexpected status '{status}'")
        phase = PHASE_FOR_STATUS[status]
        log.say(f"  story {story}: status={status} → phase={phase}")
        run_claude(cfg, log, prompt_text(phase), f"{story}__{phase}")

        new = status_of(cfg, story)
        if STATUS_RANK.get(new, -1) <= STATUS_RANK.get(status, -1):
            raise Halt(
                f"phase '{phase}' did not advance {story} (still '{new}' from '{status}'). "
                "The skill likely didn't update sprint-status.yaml — stopping."
            )
        log.say(f"  story {story}: {status} → {new}")

    log.say(f"  story {story}: reached done — running CI gate")
    ci_gate(cfg, log)
    commit_and_push(cfg, log, story)
    log.say(f"✓ story {story} complete")


# --- main loop ------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Overnight BMad story orchestrator")
    ap.add_argument("--config", default=str(SKILL_DIR / "config.toml"))
    ap.add_argument("--once", action="store_true", help="do one story then stop")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, call nothing")
    args = ap.parse_args()

    cfg = load_config(Path(args.config).resolve())
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log = RunLog(SKILL_DIR / "logs" / run_id)

    once = args.once or bool(cfg.run.get("once"))
    max_stories = int(cfg.run.get("max_stories", 0))
    deadline = None
    hours = float(cfg.run.get("max_runtime_hours", 0) or 0)
    if hours:
        deadline = datetime.now(timezone.utc).timestamp() + hours * 3600
    stop_file = SKILL_DIR / "STOP"

    # Ctrl-C: ask for a graceful stop after the current phase.
    stopping = {"flag": False}

    def on_sigint(_sig, _frm):
        stopping["flag"] = True
        log.say("SIGINT received — will stop after the current story.")

    signal.signal(signal.SIGINT, on_sigint)

    log.say(f"=== auto-run {run_id} | repo={cfg.repo_root} | model={cfg.claude['model']} ===")

    worktree_enabled = bool(cfg.worktree.get("enabled"))

    if args.dry_run:
        statuses = read_statuses(cfg)
        story = next_story(statuses)
        if not story:
            log.say("DRY RUN: no stories left — nothing to do.")
            return 0
        st = statuses[story]
        log.say(f"DRY RUN: next story = {story} (status={st})")
        log.say(f"DRY RUN: would run phases starting at '{PHASE_FOR_STATUS.get(st)}' → CI → commit → push")
        if worktree_enabled:
            log.say(
                f"DRY RUN: would create worktree at {worktree_path(cfg, run_id)} "
                f"on branch '{worktree_branch(cfg, run_id)}' off {cfg.worktree.get('base_ref')} "
                "(dirty-tree guard skipped in worktree mode)"
            )
        else:
            log.say(f"DRY RUN: single-tree mode | tree dirty = {tree_dirty(cfg)}")
        log.say(f"DRY RUN: once={once} | max_stories={max_stories}")
        return 0

    # Single-instance lock: two concurrent runs race on the shared .git and could
    # both try to `worktree add`. Atomic O_EXCL create; released only by the holder.
    lock_path = SKILL_DIR / ".run.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        try:
            existing = lock_path.read_text(encoding="utf-8").strip() or "?"
        except OSError:
            existing = "?"
        log.say(f"HALT: another run holds {lock_path.name} (pid {existing}). Delete it if stale.")
        return 2

    wt_path: Path | None = None
    completed = 0
    halted = False
    try:
        if worktree_enabled:
            # Isolate: branch off the PUSHED base_ref, not the working tree — so a
            # dirty main (or a human editing it) can't bleed in. No dirty-tree guard.
            wt_path, _branch = setup_worktree(cfg, log, run_id)
            cfg.rebind_to(wt_path)
            log.say(f"  phases now run in worktree: {cfg.repo_root}")
        elif cfg.run.get("stop_on_dirty_tree", True) and tree_dirty(cfg):
            log.say("HALT: working tree is dirty. Commit/stash existing changes before an unattended run.")
            log.say(git(cfg, "status", "--short").stdout.rstrip())
            return 2

        while True:
            if stop_file.exists():
                log.say("STOP sentinel present — halting gracefully.")
                break
            if stopping["flag"]:
                break
            if deadline and datetime.now(timezone.utc).timestamp() > deadline:
                log.say(f"Runtime budget ({hours}h) reached — not starting another story.")
                break
            if max_stories and completed >= max_stories:
                log.say(f"Reached max_stories={max_stories} — stopping.")
                break

            story = next_story(read_statuses(cfg))
            if not story:
                log.say("No stories left — all done. 🎉")
                break

            log.say(f"--- starting story {story} ({completed + 1}) ---")
            drive_story(cfg, log, story)
            completed += 1

            if once:
                log.say("--once set — stopping after one story.")
                break
    except Halt as exc:
        halted = True
        log.say(f"HALT: {exc}")
        log.say(f"Stories completed this run: {completed}. Tree left as-is for review.")
        return 1
    except Exception as exc:  # noqa: BLE001 — last-ditch so the night ends cleanly
        halted = True
        log.say(f"UNEXPECTED ERROR: {exc!r}")
        return 1
    finally:
        if worktree_enabled and wt_path is not None:
            if halted:
                log.say(
                    f"  worktree LEFT for review: {wt_path} "
                    f"(branch {worktree_branch(cfg, run_id)})"
                )
            elif cfg.worktree.get("cleanup_on_success", True):
                remove_worktree(cfg, log, wt_path)
            else:
                log.say(f"  worktree left (cleanup_on_success=false): {wt_path}")
        lock_path.unlink(missing_ok=True)

    log.say(f"=== run finished | stories completed: {completed} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
