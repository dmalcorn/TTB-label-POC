AUTOMATED PIPELINE MODE — this is a non-interactive execution. There is no human
operator and stdin is closed. You MUST: never display a menu or greeting, never
ask a clarifying question, never wait for input or confirmation. Make the best
decision per the project's conventions and run to completion.

TOOL PERMISSIONS: you have a scoped allowlist. git is READ-ONLY (the pipeline
commits). Validate with `bash scripts/ci.sh` — the pipeline brings the dev
container up and ci.sh runs the checks inside it (native-OCR parity), else
host-side; you don't run `docker` yourself. BASH: do NOT
prefix commands with `cd` (cwd is already the project root), and never combine
`cd` with output redirection (`>`, `| tee`) — that is denied. If a command is
denied, it's outside the grant; take an allowed path, don't retry it verbatim.

PROBING / VERIFYING THE CODE: to exercise the real code empirically, write a
small `_probe.py` at the REPO ROOT (so `app` imports work), run
`.venv/Scripts/python.exe _probe.py`, then remove it with
`.venv/Scripts/python.exe -c "import os; os.remove('_probe.py')"`. Do NOT use
`PYTHONPATH=`/`export`, `/c/tmp`, `rm`/`del`/`sed`, or a multi-line `python -c`
(all denied). Run the full `bash scripts/ci.sh` at most ONCE near the end (the
pipeline re-runs CI after this phase); use targeted `pytest tests/test_<x>.py`
while iterating.

IMMEDIATE ACTION REQUIRED — your VERY FIRST action must be to invoke the agent
persona, NOT a task skill:

  Step 1: Use the Skill tool to invoke **`bmad-agent-dev`** (the developer agent).
          Adopt that persona fully. Do NOT invoke `bmad-code-review` directly —
          run it through the agent's menu command below.

  Step 2: As that agent, run the code-review command — **CR for story
          {{STORY_ID}}** — and bring story {{STORY_ID}} (currently in `review`)
          to `done`.

  Step 1b: BUILDING THE REVIEW DIFF — run each `git diff` as a SINGLE command;
          never chain commands with `;`, `&&`, or `echo` (the compound form is
          denied: "multiple operations require approval"). For tracked changes use
          one `git diff <baseline> -- <paths>` call. For UNTRACKED new files, do
          NOT fight `git diff --no-index` — you have already `Read` them, so treat
          each untracked file's full content as the "new file" in the diff payload.

  Step 2a: REVIEW SUBAGENTS — the code-review workflow spawns parallel review
          layers (Blind Hunter / adversarial, Edge Case Hunter, Acceptance
          Auditor) via the Task tool. In THIS environment the BMAD review-layer
          *agent types* (`bmad-review-adversarial-general`,
          `bmad-review-edge-case-hunter`) are NOT registered — only
          `general-purpose`, `Explore`, `Plan` (and built-ins) exist. Do NOT try
          to spawn the layers by those bmad names (it fails and wastes turns).
          Invoke each layer as a **`general-purpose`** Task agent with that
          layer's adversarial/edge-case prompt embedded. For the **Blind Hunter**,
          embed ONLY the story diff in its prompt and instruct it to read no
          project files / use no other context — preserve its diff-only blindness.

  Step 3: After completing the work, end your response with this block:

          === AGENT IDENTIFICATION ===
          Agent: [your agent type, e.g. DEV Agent]
          Persona: [your persona name, from the agent file you loaded]
          Loaded files:
            - [exact path to each file you read during activation]
          === END IDENTIFICATION ===

Hard requirements:
- This is an automated pipeline: APPLY the patches you would recommend (fix the
  code), do not merely report findings. Genuine deferrals go in
  `_bmad-output/implementation-artifacts/deferred-work.md` with rationale.
- After applying patches, re-run the suite (`bash scripts/ci.sh`); it MUST stay
  green. It runs in the dev container when the pipeline has it up (native-OCR
  parity), else host-side. See CLAUDE.md.
- Do not regress any `_bmad-output/project-context.md` invariant. If a finding
  conflicts with the spine (DESIGN.md / EXPERIENCE.md / architecture.md), the
  spine wins.
- End with `_bmad-output/implementation-artifacts/sprint-status.yaml` showing
  story {{STORY_ID}} at `done`.
- Do NOT commit or push — the orchestrator does that after CI passes.
