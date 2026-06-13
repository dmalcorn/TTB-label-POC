AUTOMATED PIPELINE MODE — this is a non-interactive execution. There is no human
operator and stdin is closed. You MUST: never display a menu or greeting, never
ask a clarifying question, never wait for input or confirmation. Make the best
decision per the project's conventions and run to completion.

IMMEDIATE ACTION REQUIRED — your VERY FIRST action must be to invoke the agent
persona, NOT a task skill:

  Step 1: Use the Skill tool to invoke **`bmad-agent-dev`** (the developer agent,
          Amelia). Become that persona. Do NOT invoke `bmad-code-review` directly
          — run it through the agent's menu command below.

  Step 2: As the agent, run the code-review command — **CR for story {{STORY}}**
          — and bring story {{STORY}} (currently in `review`) to `done`.

Hard requirements:
- This is an automated pipeline: APPLY the patches you would recommend (fix the
  code), do not merely report findings. Genuine deferrals go in
  `_bmad-output/implementation-artifacts/deferred-work.md` with rationale.
- After applying patches, re-run the pytest suite on the HOST venv; it MUST stay
  green. Do NOT run CI inside the Docker container (frozen baked-in source — see
  CLAUDE.md).
- Do not regress any `_bmad-output/project-context.md` invariant. If a finding
  conflicts with the spine (DESIGN.md / EXPERIENCE.md / architecture.md), the
  spine wins.
- End with `_bmad-output/implementation-artifacts/sprint-status.yaml` showing
  story {{STORY}} at `done`.
- Do NOT commit or push — the orchestrator does that after CI passes.
