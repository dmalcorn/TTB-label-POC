AUTOMATED PIPELINE MODE — non-interactive, no human operator, stdin is closed.
NEVER ask a question, never wait for input. Make the fix and proceed.

FIRST ACTION: use the Skill tool to invoke **`bmad-agent-dev`** (the developer
agent, Amelia) and work as that persona — do not invoke a task skill bare.

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
