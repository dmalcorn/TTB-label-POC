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
from datetime import UTC, datetime
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

# Which prompt drives a story out of its current status. `dev_story` is COMBINED:
# it invokes the dev agent persona, which creates-or-verifies the story spec (CS)
# and then implements it (DS) in one session — so `backlog` routes here too, not to
# a separate create step (mirrors the BMAD shipyard factory's combined dev node).
PHASE_FOR_STATUS = {
    "backlog": "dev_story",
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


class Stopped(Exception):
    """User-initiated stop (Ctrl-C). A clean exit — NOT a failure, no alarm."""


# A child killed by a console Ctrl-C/Break exits with this code on Windows
# (0xC000013A, STATUS_CONTROL_C_EXIT). It means the operator stopped the run.
CTRL_C_EXIT = 3221225786


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
        stamp = datetime.now(UTC).strftime("%H:%M:%S")
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
    """First story (file order) that is a real story and not done.

    NEVER returns a retrospective: those are interactive (party-mode review) and
    would stall an unattended run. They're normally named `epic-N-retrospective`
    (already excluded by STORY_KEY_RE), but the explicit guard makes it robust
    even if one is ever named story-style (e.g. `3-9-retrospective`).
    """
    for key, status in statuses.items():
        if "retrospective" in key:
            continue  # interactive — never auto-run
        if not STORY_KEY_RE.match(key):
            continue  # skip epic-N summary lines
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


# --- vetted tool allowlist (specific grant, NOT a blank check) -------------
# Each phase gets ONLY the tools it needs; anything not listed is denied by the
# CLI (headless -p mode can't prompt, so it just denies and the agent continues).
# Adapted from the BMAD shipyard factory's heavily-vetted list, trimmed to this
# project's Python/Windows stack. Deliberately ABSENT: git-write (the orchestrator
# owns commits — and this blocks the git-plumbing-as-write-primitive abuse the
# shipyard hit), and Docker (validation is host-side per CLAUDE.md).
_BASH_PYTHON = ",".join(
    [
        "Bash(python *)",
        "Bash(python3 *)",
        "Bash(pip *)",
        "Bash(pytest *)",
        "Bash(ruff *)",
        "Bash(mypy *)",
        "Bash(.venv/Scripts/python.exe *)",  # the Windows host-venv interpreter
        "Bash(bash *)",  # run scripts/ci.sh and other helper scripts
    ]
)
_BASH_INSPECT = ",".join(
    [
        "Bash(cat *)",
        "Bash(ls *)",
        "Bash(ls)",
        "Bash(head *)",
        "Bash(tail *)",
        "Bash(wc *)",
        "Bash(find *)",
        "Bash(file *)",
        "Bash(echo *)",
    ]
)
# Read-only git only: no add/commit/push/reset/checkout/merge/rebase/stash/rm.
_BASH_GIT_READONLY = ",".join(
    [
        "Bash(git status *)",
        "Bash(git status)",
        "Bash(git log *)",
        "Bash(git log)",
        "Bash(git diff *)",
        "Bash(git diff)",
        "Bash(git show *)",
        "Bash(git show)",
        "Bash(git blame *)",
        "Bash(git ls-files *)",
        "Bash(git ls-files)",
        "Bash(git branch *)",
        "Bash(git branch)",
        "Bash(git rev-parse *)",
    ]
)
_BASE_TOOLS = "Read,Edit,Write,Glob,Grep,Task,TodoWrite,Skill"

# Per-phase lists. For this single-stack Python project the dev / review / fix
# surfaces are the same (all do Python edits + host-side validation); kept as
# separate names so a phase can be tightened independently later.
TOOLS_DEV = f"{_BASE_TOOLS},{_BASH_PYTHON},{_BASH_INSPECT},{_BASH_GIT_READONLY}"
TOOLS_CODE_REVIEW = TOOLS_DEV
TOOLS_FIX = TOOLS_DEV
TOOLS_FOR_PHASE = {"dev_story": TOOLS_DEV, "code_review": TOOLS_CODE_REVIEW}


def _tool_brief(name: str, inp: dict | None, arg_chars: int) -> str:
    """`Edit: app/normalize.py`, `Bash: pytest -q`, etc. — the gist of a tool call."""
    inp = inp or {}
    for key in ("file_path", "path", "command", "pattern", "description", "prompt", "url", "query"):
        val = inp.get(key)
        if val:
            return f"{name}: {str(val).replace(chr(10), ' ')[:arg_chars]}"
    return name


def _render_event(
    evt: dict, *, arg_chars: int = 200, text_chars: int = 2000, result_chars: int = 400
) -> list[str]:
    """Human-readable play-by-play lines for one stream-json event (may be several).

    This is what the operator watches scroll by in the terminal — the model's
    narration, every tool call/edit, and tool results — not a throttled summary.
    Per-item char caps come from the [log] config block so they're tunable.
    """
    t = evt.get("type")
    lines: list[str] = []
    if t == "system":
        lines.append(f"session {evt.get('subtype', 'event')}")
    elif t == "assistant":
        for b in (evt.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            bt = b.get("type")
            if bt == "tool_use":
                lines.append("-> " + _tool_brief(b.get("name", "?"), b.get("input"), arg_chars))
            elif bt == "text":
                txt = (b.get("text") or "").strip()
                if txt:
                    lines.append(txt[:text_chars])
            elif bt == "thinking":
                lines.append("(thinking…)")
    elif t == "user":
        for b in (evt.get("message") or {}).get("content") or []:
            if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                continue
            content = b.get("content")
            snippet = ""
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        snippet = (c.get("text") or "").strip().replace("\n", " ")
                        break
            elif isinstance(content, str):
                snippet = content.strip().replace("\n", " ")
            flag = "error" if b.get("is_error") else "ok"
            lines.append(f"<- result ({flag}) {snippet[:result_chars]}")
    # 'result' is the terminal event — the caller reports cost/turns; nothing here.
    return lines


def run_claude(cfg: Config, log: RunLog, prompt: str, label: str, tools: str) -> None:
    """Run one headless phase, printing a live play-by-play. Raises Halt on failure.

    `tools` is the vetted --allowedTools allowlist for this phase (specific grant,
    not a blank check). Uses --output-format stream-json so the run isn't blind: we
    decode each event and print it so the operator sees real activity, and abort
    EARLY on a stall instead of waiting out the phase_timeout_sec hard cap. See
    auto-run/FINDINGS-01-stdin-hang.md and auto-run/ANALYSIS-and-RECOMMENDATION.md.
    """
    c = cfg.claude
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",  # required by the CLI for stream-json in print (-p) mode
        # --setting-sources project is REQUIRED for the allowlist to actually
        # ENFORCE: it loads ONLY the project's .claude settings (not the user's
        # global / local allows), so --allowedTools becomes the sole allow source
        # and everything else is denied-by-default. Without it, headless -p just
        # pre-approves the listed tools and runs the rest anyway (verified).
        "--setting-sources",
        "project",
        "--allowedTools",
        tools,
        "--model",
        c["model"],
        "--max-turns",
        str(c["max_turns"]),
    ]
    # Only pass --permission-mode when explicitly set (e.g. "bypassPermissions" to
    # revert to allow-everything). Empty = default mode, where the allowlist governs.
    if c.get("permission_mode"):
        cmd += ["--permission-mode", c["permission_mode"]]
    if c.get("fallback_model"):
        cmd += ["--fallback-model", c["fallback_model"]]
    for d in cfg.add_dirs:
        cmd += ["--add-dir", d]
    cmd += list(c.get("extra_args", []))
    # `--` end-of-options separator BEFORE the prompt. Without it the CLI fails
    # with "Input must be provided … when using --print" on a real multi-line
    # prompt (a short one slips through). Both proven factories use `-- <prompt>`.
    cmd += ["--", prompt]

    hard_timeout = int(c["phase_timeout_sec"])
    stall_timeout = int(c.get("stall_timeout_sec", 0))  # 0 = disabled
    heartbeat = max(5, int(c.get("heartbeat_sec", 30)))
    lg = cfg.raw.get("log", {})
    arg_chars = int(lg.get("tool_arg_chars", 200))
    text_chars = int(lg.get("text_chars", 2000))
    result_chars = int(lg.get("result_chars", 400))

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
            # REQUIRED on Windows: without an explicit encoding, text mode decodes
            # the child's output as the cp1252 locale and a reader thread CRASHES on
            # the first non-cp1252 byte (e.g. a smart quote) in the stream-json.
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise Halt("`claude` CLI not found on PATH") from None

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

    short = label.split("__")[-1]  # "dev_story", not the full story__phase
    start = time.monotonic()
    last_event = start
    last_beat = start
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
                stop(
                    f"phase '{label}' stalled — no output for {stall_timeout}s "
                    f"(see {out_path.name})"
                )
            try:
                tag, line = q.get(timeout=2.0)
            except queue.Empty:
                # silence during a long tool run — reassure the watcher it's alive.
                if now - last_beat >= heartbeat:
                    log.say(f"    [{short} {int(now - start)}s] … still working")
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
            el = int(time.monotonic() - start)
            for disp in _render_event(
                evt, arg_chars=arg_chars, text_chars=text_chars, result_chars=result_chars
            ):
                log.say(f"    [{short} {el}s] {disp}")
            last_beat = time.monotonic()

    rc = proc.wait()
    if err_chunks:
        (log.run_dir / f"{label}.stderr.txt").write_text("".join(err_chunks), encoding="utf-8")
    if rc == CTRL_C_EXIT:
        # The operator pressed Ctrl-C — a clean user stop, not a phase failure.
        raise Stopped(f"phase '{label}' interrupted by Ctrl-C")
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
        encoding="utf-8",  # not the cp1252 locale (e.g. unicode filenames in status)
        errors="replace",
        capture_output=True,
        stdin=subprocess.DEVNULL,  # never block on stdin in a detached run (FINDINGS-01)
        check=check,
    )


def tree_dirty(cfg: Config) -> bool:
    return bool(git(cfg, "status", "--porcelain").stdout.strip())


def anything_staged(cfg: Config) -> bool:
    # `git diff --cached --quiet` exits 1 when there ARE staged changes.
    return git(cfg, "diff", "--cached", "--quiet", check=False).returncode != 0


def _gate_failed_to_launch(out: str) -> bool:
    """True when bash couldn't even FIND/RUN the script (a broken gate, not a code failure).

    The classic symptom on Windows was a backslash-mangled path:
    `/bin/bash: C:alcorn…ci.sh: No such file or directory`. Don't waste LLM fix
    attempts on code when the gate itself never ran.
    """
    o = out.lower()
    return "ci.sh" in o and ("no such file or directory" in o or "command not found" in o)


def run_ci(cfg: Config, log: RunLog, fix: bool) -> tuple[bool, str]:
    flag = ["--fix"] if fix else []
    # Pass bash a POSIX path. A Windows backslash path (C:\…\ci.sh) gets its
    # backslashes eaten by bash → "No such file or directory" and the gate never
    # runs. Relative-from-cwd is cleanest; fall back to forward-slashed absolute.
    try:
        script_arg = cfg.ci_script.relative_to(cfg.repo_root).as_posix()
    except ValueError:
        script_arg = str(cfg.ci_script).replace("\\", "/")
    log.say(f"  → bash {script_arg} {' '.join(flag) or '(check)'}")
    # Tell ci.sh which compose service/file to dispatch into, matching [docker].
    env = child_env()
    d = cfg.raw.get("docker", {})
    if d.get("enabled", False):
        env["CI_APP_SERVICE"] = d.get("service", "web")
        env["CI_COMPOSE_FILE"] = d.get("compose_file", "compose.yaml")
    proc = subprocess.run(
        ["bash", script_arg, *flag],
        cwd=cfg.repo_root,
        env=env,
        text=True,
        encoding="utf-8",  # not the cp1252 locale (CI output carries unicode)
        errors="replace",
        capture_output=True,
        stdin=subprocess.DEVNULL,  # never block on stdin in a detached run (FINDINGS-01)
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, combined


def ci_gate(cfg: Config, log: RunLog) -> None:
    """Run CI; if red, run a fix phase and retry, up to ci.fix_attempts. Halt if still red.

    Distinguishes a BROKEN GATE (can't launch) from a real code failure, and hands
    each fresh fix agent the complete CI output so it works the real problem.
    """
    if not cfg.ci_script.exists():
        raise Halt(f"CI gate can't run: script not found at {cfg.ci_script}")

    max_chars = int(cfg.ci.get("max_output_chars", 40000))
    ok, out = run_ci(cfg, log, fix=True)  # first pass also auto-formats
    if not ok and _gate_failed_to_launch(out):
        (log.run_dir / "ci-final-failure.txt").write_text(out, encoding="utf-8")
        raise Halt("CI gate failed to LAUNCH — broken invocation, not a code failure (see ci-final-failure.txt)")

    attempts = int(cfg.ci["fix_attempts"])
    for i in range(attempts):
        if ok:
            log.say("    CI green")
            return
        log.say(f"    CI red — fix attempt {i + 1}/{attempts} (fresh session, full CI output)")
        run_claude(
            cfg,
            log,
            prompt_text("fix", CI_OUTPUT=out[-max_chars:]),
            f"ci-fix-{i + 1}",
            tools=TOOLS_FIX,
        )
        ok, out = run_ci(cfg, log, fix=True)
        if not ok and _gate_failed_to_launch(out):
            (log.run_dir / "ci-final-failure.txt").write_text(out, encoding="utf-8")
            raise Halt("CI gate failed to LAUNCH after a fix — broken invocation (see ci-final-failure.txt)")
    if not ok:
        (log.run_dir / "ci-final-failure.txt").write_text(out, encoding="utf-8")
        raise Halt("CI still red after fix attempts (see ci-final-failure.txt)")
    log.say("    CI green")


def ensure_container(cfg: Config, log: RunLog) -> None:
    """Bring the dev container up once so the CI gate runs INSIDE it (dep parity).

    Non-fatal: if docker is missing, the up fails, or it times out, we WARN and
    continue — scripts/ci.sh degrades cleanly to host-side, which is fine for
    pure-Python work. The image bakes ruff/mypy/pytest, so in-container checks
    actually run (no false-green skip). stdio is inherited so the (one-time) build
    streams live to the terminal.
    """
    d = cfg.raw.get("docker", {})
    if not d.get("enabled", False):
        return
    service = d.get("service", "web")
    compose_file = d.get("compose_file", "compose.yaml")
    timeout = int(d.get("up_timeout_sec", 1200))
    cmd = ["docker", "compose", "-f", compose_file, "up", "-d"]
    if d.get("build"):
        cmd.append("--build")
    cmd.append(service)
    log.say(f"  → {' '.join(cmd)}  (dev container for CI parity; first run builds the image)")
    try:
        proc = subprocess.run(cmd, cwd=cfg.repo_root, env=child_env(), timeout=timeout)
    except FileNotFoundError:
        log.say("  docker not on PATH — CI will run host-side (degraded). See CLAUDE.md.")
        return
    except subprocess.TimeoutExpired:
        log.say(f"  docker compose up exceeded {timeout}s — continuing; CI may run host-side.")
        return
    if proc.returncode != 0:
        log.say(f"  docker compose up failed (exit {proc.returncode}) — CI runs host-side (degraded).")
    else:
        log.say(f"  dev container '{service}' is up — CI will dispatch into it.")


def alarm(cfg: Config, log: RunLog, why: str) -> None:
    """Audible beeps on exit so an overnight operator wakes to fix a stop/failure.

    Windows: real tones via winsound.Beep (the default audio device), looped 3–5×
    like an alarm. Elsewhere / if audio is unavailable: the terminal bell. Never
    raises — a failed beep must not change the run's outcome.
    """
    a = cfg.raw.get("alert", {})
    if not a.get("enabled", True):
        return
    count = max(1, int(a.get("beeps", 5)))
    log.say(f"*** ALARM ({why}) — {count} beeps ***")
    try:
        import winsound  # Windows-only; real tones through the default audio device.

        for _ in range(count):
            winsound.Beep(1000, 500)  # 1 kHz, 500 ms
            time.sleep(0.15)
    except Exception:  # noqa: BLE001 — non-Windows / no audio: fall back to the bell.
        for _ in range(count):
            print("\a", end="", flush=True)
            time.sleep(0.25)


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
        raise Halt(
            "commit failed after 3 attempts (a hook can't auto-fix — see commit-attempt-*.txt)"
        )
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

    res = git(
        cfg,
        "worktree",
        "add",
        str(path),
        "-b",
        branch,
        base_ref,
        check=False,
        cwd=cfg.canonical_repo,
    )
    if res.returncode != 0:
        raise Halt(f"`git worktree add` failed: {(res.stderr or res.stdout).strip()[:400]}")
    log.say(f"  worktree ready: {path}  (branch {branch} off {base_ref})")
    return path, branch


def remove_worktree(cfg: Config, log: RunLog, path: Path) -> None:
    res = git(cfg, "worktree", "remove", "--force", str(path), check=False, cwd=cfg.canonical_repo)
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
        # Pass the short numeric id ("3-3", not the full slug) for the persona's
        # CS/DS/CR commands — deterministic, and the form BMAD expects.
        m = STORY_KEY_RE.match(story)
        story_id = m.group(0).rstrip("-") if m else story
        run_claude(
            cfg,
            log,
            prompt_text(phase, STORY_ID=story_id),
            f"{story}__{phase}",
            tools=TOOLS_FOR_PHASE[phase],
        )

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
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    log = RunLog(SKILL_DIR / "logs" / run_id)

    once = args.once or bool(cfg.run.get("once"))
    max_stories = int(cfg.run.get("max_stories", 0))
    deadline = None
    hours = float(cfg.run.get("max_runtime_hours", 0) or 0)
    if hours:
        deadline = datetime.now(UTC).timestamp() + hours * 3600
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
        log.say(
            f"DRY RUN: would run phases starting at '{PHASE_FOR_STATUS.get(st)}' "
            "→ CI → commit → push"
        )
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
        alarm(cfg, log, "another run holds the lock")
        return 2

    wt_path: Path | None = None
    completed = 0
    halted = False
    user_stopped = False
    try:
        if worktree_enabled:
            # Isolate: branch off the PUSHED base_ref, not the working tree — so a
            # dirty main (or a human editing it) can't bleed in. No dirty-tree guard.
            wt_path, _branch = setup_worktree(cfg, log, run_id)
            cfg.rebind_to(wt_path)
            log.say(f"  phases now run in worktree: {cfg.repo_root}")
        elif cfg.run.get("stop_on_dirty_tree", True) and tree_dirty(cfg):
            log.say(
                "HALT: working tree is dirty. "
                "Commit/stash existing changes before an unattended run."
            )
            log.say(git(cfg, "status", "--short").stdout.rstrip())
            alarm(cfg, log, "working tree is dirty")
            return 2

        # Bring the dev container up once so the CI gate runs inside it (parity).
        ensure_container(cfg, log)

        while True:
            if stop_file.exists():
                log.say("STOP sentinel present — stopping gracefully.")
                user_stopped = True
                break
            if stopping["flag"]:
                log.say("Stop requested (Ctrl-C) — stopping after the current story.")
                user_stopped = True
                break
            if deadline and datetime.now(UTC).timestamp() > deadline:
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
    except Stopped as exc:
        # Operator pressed Ctrl-C mid-phase. Clean stop — NO alarm.
        user_stopped = True
        log.say(f"Stopped by user ({exc}). Stories completed this run: {completed}.")
        return 0
    except Halt as exc:
        halted = True
        log.say(f"HALT: {exc}")
        log.say(f"Stories completed this run: {completed}. Tree left as-is for review.")
        alarm(cfg, log, f"HALT: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 — last-ditch so the night ends cleanly
        halted = True
        log.say(f"UNEXPECTED ERROR: {exc!r}")
        alarm(cfg, log, "unexpected error")
        return 1
    finally:
        if worktree_enabled and wt_path is not None:
            # Leave the worktree on a failure OR a user stop (work may be mid-flight);
            # only auto-remove after a clean, complete finish.
            if halted or user_stopped:
                log.say(
                    f"  worktree LEFT for review: {wt_path} (branch {worktree_branch(cfg, run_id)})"
                )
            elif cfg.worktree.get("cleanup_on_success", True):
                remove_worktree(cfg, log, wt_path)
            else:
                log.say(f"  worktree left (cleanup_on_success=false): {wt_path}")
        lock_path.unlink(missing_ok=True)

    if user_stopped:
        # User-initiated stop (Ctrl-C between phases, or STOP sentinel) — no alarm.
        log.say(f"=== stopped by user | stories completed: {completed} ===")
        return 0
    log.say(f"=== run finished | stories completed: {completed} ===")
    if cfg.raw.get("alert", {}).get("on_success", True):
        alarm(cfg, log, "run finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
