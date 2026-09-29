# Handoff format

Omit fields that do not apply. A brief must enable action without another planning round trip.
The sidekick never sees the user's messages or your conversation. Pass on every requirement, decision, and constraint it needs.

```text
Goal: <one verifiable outcome>
Workdir: <absolute checkout path>
Own: <files or bounded area; preserve other changes>
Requirements: <hard requirements and invariants from the task, verbatim>
Settled inputs: <facts, derived results, and prior passing checks; do not derive again>
Hypotheses: <claims the plan depends on that the sidekick must check first>
Action: <what changes and why, relevant locations, settled interfaces and data shapes, hard edge cases, test cases>
Done when: <observable completion criteria>
Verify:
<verbatim command>
Pass: <observable result>
Constraints: <scope, permission boundary, processes the lead owns>
Runtime state: <servers or long commands from earlier handoffs and whether to reuse or leave them running>
Visual evidence: <required rendered states and screenshot paths>
Continuity: <accepted state for a replacement sidekick; omit for the same sidekick>
Report: changed paths, checks and results, evidence paths, deviations, blockers.
```

For discovery, state the question and the evidence you need. Review the answer and settle the design before you brief implementation.
For rework, put all findings in one brief and state which earlier results remain accepted.
