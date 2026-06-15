AUTOMATED PIPELINE MODE — non-interactive, no human operator, stdin is closed.
NEVER ask a question, never wait for input. Make the fix and proceed.

FIRST ACTION: use the Skill tool to invoke **`bmad-agent-dev`** (the developer
agent) and work as that persona — do not invoke a task skill bare.

TOOL PERMISSIONS: scoped allowlist. git is READ-ONLY (the pipeline commits).
Validate with `bash scripts/ci.sh` — the pipeline brings the dev container up and
ci.sh runs the checks inside it (native-OCR parity), else host-side; you don't run
`docker` yourself. BASH: do NOT prefix commands
with `cd` (cwd is already the project root), and never combine `cd` with output
redirection — that is denied. If a command is denied, it's outside the grant;
take an allowed path, don't retry it verbatim.

The local CI gate failed. Its combined output is below between the markers.

----- CI OUTPUT BEGIN -----
{{CI_OUTPUT}}
----- CI OUTPUT END -----

Task: fix the ROOT CAUSE so `bash scripts/ci.sh` passes cleanly — every phase:
ruff format, ruff lint, mypy, pytest.

Hard requirements:
- Make minimal, correct changes consistent with `_bmad-output/project-context.md`.
- Do NOT disable a check, add blanket ignores, loosen mypy, xfail/skip tests, or
  weaken assertions to make the gate go green. Fix the actual problem.
- Re-run the relevant checks yourself to confirm before finishing.
- Do not commit or push.

After completing the work, end your response with this block:

=== AGENT IDENTIFICATION ===
Agent: [your agent type, e.g. DEV Agent]
Persona: [your persona name, from the agent file you loaded]
Loaded files:
  - [exact path to each file you read during activation]
=== END IDENTIFICATION ===
