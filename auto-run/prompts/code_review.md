You are running NON-INTERACTIVELY inside an unattended overnight batch. There is
no human watching. NEVER ask a question, never wait for input, never present a
menu and stop. Make the best decision yourself following the project's
conventions and proceed to completion.

Task: code-review the story currently in `review` status and bring it to `done`.

/bmad-code-review

Hard requirements:
- Review the story that is currently in `review` status.
- This is an automated pipeline: APPLY the patches you would recommend (fix the
  code), do not merely report findings. Genuine deferrals may be recorded in
  `_bmad-output/implementation-artifacts/deferred-work.md` with rationale.
- After applying patches, re-run the pytest suite; it MUST stay green.
- Do not regress any `_bmad-output/project-context.md` invariant. If a review
  finding conflicts with the spine (DESIGN.md/EXPERIENCE.md/architecture.md),
  the spine wins.
- Update sprint-status.yaml: move the story `review -> done`.
- Do NOT commit or push — the orchestrator does that after CI passes.
