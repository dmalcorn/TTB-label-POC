You are running NON-INTERACTIVELY inside an unattended overnight batch. There is
no human watching. NEVER ask a question, never wait for input, never present a
menu and stop. Make the best decision yourself following the project's
conventions and proceed to completion.

Task: create the NEXT story in the sprint plan, and only that one.

/bmad-create-story

Hard requirements:
- Create exactly ONE story file: the next story whose status is `backlog` in
  `_bmad-output/implementation-artifacts/sprint-status.yaml`, in sprint order.
- Fill it with the full implementation context the skill specifies. Honor
  `_bmad-output/project-context.md` (the four contracts, firewall/offline
  posture, verdict-vs-disposition separation, VLM-only purity, UI fidelity).
- Update sprint-status.yaml: move that story `backlog -> ready-for-dev`.
- DO NOT write application code in this phase. Stop after the story file and the
  status update are saved.
