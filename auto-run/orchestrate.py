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
import re
import signal
import subprocess
import sys
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
    repo_root: Path
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


def load_config(path: Path) -> Config:
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    paths = raw["paths"]
    repo_root = (path.parent / paths["repo_root"]).resolve()
    return Config(
        raw=raw,
        repo_root=repo_root,
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


def run_claude(cfg: Config, log: RunLog, prompt: str, label: str) -> None:
    """Run one headless phase. Raises Halt on any failure."""
    c = cfg.claude
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
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

    log.say(f"  → claude phase '{label}' (model={c['model']}, max_turns={c['max_turns']})")
    out_path = log.run_dir / f"{label}.json"
    try:
        proc = subprocess.run(
            cmd,
            cwd=cfg.repo_root,
            env=child_env(),
            text=True,
            capture_output=True,
            timeout=c["phase_timeout_sec"],
        )
    except subprocess.TimeoutExpired:
        raise Halt(f"phase '{label}' exceeded {c['phase_timeout_sec']}s timeout")
    except FileNotFoundError:
        raise Halt("`claude` CLI not found on PATH")

    out_path.write_text(proc.stdout or "", encoding="utf-8")
    if proc.stderr:
        (log.run_dir / f"{label}.stderr.txt").write_text(proc.stderr, encoding="utf-8")

    if proc.returncode != 0:
        raise Halt(f"phase '{label}' exited {proc.returncode} (see {out_path.name})")

    try:
        env = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        raise Halt(f"phase '{label}' produced non-JSON output (see {out_path.name})")

    if env.get("is_error"):
        raise Halt(f"phase '{label}' reported is_error (see {out_path.name})")

    cost = env.get("total_cost_usd")
    turns = env.get("num_turns")
    log.say(f"    done ({label}): turns={turns} cost_usd={cost}")


def prompt_text(name: str, **subs: str) -> str:
    text = (SKILL_DIR / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    for key, val in subs.items():
        text = text.replace("{{" + key + "}}", val)
    return text


# --- git + ci -------------------------------------------------------------


def git(cfg: Config, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cfg.repo_root,
        env=child_env(),
        text=True,
        capture_output=True,
        check=check,
    )


def tree_dirty(cfg: Config) -> bool:
    return bool(git(cfg, "status", "--porcelain").stdout.strip())


def run_ci(cfg: Config, log: RunLog, fix: bool) -> tuple[bool, str]:
    flag = ["--fix"] if fix else []
    log.say(f"  → ci.sh {' '.join(flag) or '(check)'}")
    proc = subprocess.run(
        ["bash", str(cfg.ci_script), *flag],
        cwd=cfg.repo_root,
        env=child_env(),
        text=True,
        capture_output=True,
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
    # pre-commit fixers may rewrite files and fail the first commit; re-add and retry.
    committed = False
    for attempt in range(3):
        git(cfg, "add", "-A")
        if not tree_dirty(cfg):
            raise Halt(f"nothing staged to commit for {story} (did a phase produce no changes?)")
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
        res = git(cfg, "push", cfg.git["remote"], "HEAD", check=False)
        if res.returncode != 0:
            (log.run_dir / "push-failure.txt").write_text(res.stdout + "\n" + res.stderr, "utf-8")
            raise Halt("git push failed (committed locally; see push-failure.txt)")
        log.say(f"  pushed to {cfg.git['remote']}")


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

    if args.dry_run:
        statuses = read_statuses(cfg)
        story = next_story(statuses)
        if not story:
            log.say("DRY RUN: no stories left — nothing to do.")
            return 0
        st = statuses[story]
        log.say(f"DRY RUN: next story = {story} (status={st})")
        log.say(f"DRY RUN: would run phases starting at '{PHASE_FOR_STATUS.get(st)}' → CI → commit → push")
        log.say(f"DRY RUN: tree dirty = {tree_dirty(cfg)} | once={once} | max_stories={max_stories}")
        return 0

    if cfg.run.get("stop_on_dirty_tree", True) and tree_dirty(cfg):
        log.say("HALT: working tree is dirty. Commit/stash existing changes before an unattended run.")
        log.say(git(cfg, "status", "--short").stdout.rstrip())
        return 2

    completed = 0
    try:
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
        log.say(f"HALT: {exc}")
        log.say(f"Stories completed this run: {completed}. Tree left as-is for review.")
        return 1
    except Exception as exc:  # noqa: BLE001 — last-ditch so the night ends cleanly
        log.say(f"UNEXPECTED ERROR: {exc!r}")
        return 1

    log.say(f"=== run finished | stories completed: {completed} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
