You are running NON-INTERACTIVELY inside an unattended overnight batch. There is
no human watching. NEVER ask a question, never wait for input, never present a
menu and stop. Make the best decision yourself following the project's
conventions and proceed to completion.

Task: implement the story that is currently active in the sprint (status
`ready-for-dev` or `in-progress`).

/bmad-dev-story

Hard requirements:
- Implement the active story with test-first discipline (red → green → refactor).
- Satisfy EVERY acceptance criterion. Tasks in the sequence written.
- The pytest suite MUST be green before you finish. Do not weaken or skip tests
  to get there.
- Honor `_bmad-output/project-context.md` invariants exactly: the four
  centralized contracts (import, never re-implement), the firewall/offline
  boundary, the verdict (engine) vs disposition (human) separation, VLM-only
  purity (OCR text never feeds the model), snake_case everywhere, CFR rules as
  data not hard-coded.
- Update sprint-status.yaml: move the story to `review`.
- Do NOT commit, push, or run the code-review skill — later phases do that.
