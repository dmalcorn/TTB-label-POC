AUTOMATED PIPELINE MODE — this is a non-interactive execution. There is no human
operator and stdin is closed. You MUST: never display a menu or greeting, never
ask a clarifying question, never wait for input or confirmation. When a workflow
step would normally HALT to ask the operator, the operator is unavailable but the
workflow's contract still binds you — derive what the step needs from the trigger
prompt, project state, and git history, and continue. Proceed with best judgment
on tie-breaks. Do not run `sleep` or poll background tasks.

TOOL PERMISSIONS: you have a scoped allowlist (Read/Edit/Write/Glob/Grep/Skill,
Python + pytest/ruff/mypy, `bash`, read-only git, file inspection). git is
READ-ONLY — no add/commit/push (the pipeline commits); Docker is not granted, so
validate on the host venv. BASH: do NOT prefix commands with `cd` (your working
directory is already the project root), and never combine `cd` with output
redirection (`>`, `>>`, `| tee`) — that is denied. Run e.g. `pytest -q tests/...`
or `bash scripts/ci.sh`, not `cd <path> && pytest ... > out`. If a command is
denied, it's outside the grant — take an allowed path, don't retry it verbatim.

IMMEDIATE ACTION REQUIRED — your VERY FIRST action must be to invoke the agent
persona, NOT a task skill:

  Step 1: Use the Skill tool to invoke **`bmad-agent-dev`** (the developer agent).
          Adopt that persona fully. Do NOT invoke `bmad-create-story` or
          `bmad-dev-story` directly — run them only through the agent's menu
          commands below.

  Step 2: As that agent, do BOTH of the following for story **{{STORY_ID}}** in
          this one session, carrying context forward without re-reading the
          planning artifacts twice:

          (a) CREATE-OR-VERIFY the story spec. If the spec for story {{STORY_ID}}
              does not exist yet, run the create-story command — **CS for story
              {{STORY_ID}}** — to create it with full implementation context, then
              continue. If it already exists, verify it is complete and correct,
              then continue — do NOT recreate it.

          (b) IMPLEMENT it — **DS for story {{STORY_ID}}**: test-first
              (red → green → refactor), satisfy EVERY acceptance criterion, tasks
              in the sequence written. The pytest suite MUST be green before you
              finish; never weaken or skip tests to get there.

  Step 3: After completing the work, end your response with this block:

          === AGENT IDENTIFICATION ===
          Agent: [your agent type, e.g. DEV Agent]
          Persona: [your persona name, from the agent file you loaded]
          Loaded files:
            - [exact path to each file you read during activation]
          === END IDENTIFICATION ===

Hard requirements:
- Honor `_bmad-output/project-context.md` exactly: the four centralized contracts
  (import, never re-implement), the firewall/offline boundary, the verdict (engine)
  vs disposition (human) separation, VLM-only purity (OCR text never feeds the
  model), snake_case everywhere, CFR rules as data (never hard-coded in Python).
- Validate on the HOST venv (`bash scripts/ci.sh` or `.venv/Scripts/python.exe -m
  pytest -q`); do NOT run CI inside the Docker container (it holds a frozen,
  baked-in copy of the source). See CLAUDE.md.
- End with `_bmad-output/implementation-artifacts/sprint-status.yaml` showing
  story {{STORY_ID}} at `review`.
- Do NOT commit, push, or run the code-review skill — later phases do that.
