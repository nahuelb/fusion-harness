# Evaluation protocol

Compare the skill with a single-agent baseline on the same repository snapshots and tasks.
Run each harness and transport you want to support: a native Claude Code sidekick, a native Codex sidekick, and a CLI sidekick.
Use at least three runs per task and rotate run order. Record model settings, permissions, and acceptance checks.
Include a bounded code change, a bug investigation, a broad refactor, and correctness-critical analysis.

Record acceptance success, elapsed time, lead and sidekick tokens, handoff count, rework count, lead edits, lead file reads, and required-check results.
Use fresh sessions per trial so session totals match the trial scope. Keep cached input separate from total input.
Do not infer dollar cost from mixed-model sessions or subscription usage from token counts.

## Runtime acceptance

1. A fresh task loads the linked skill and resolves the profile for its harness.
2. A routine implementation brief starts one sidekick without copying the full conversation.
3. A rework brief reaches the same sidekick, which still knows the earlier handoff.
4. A model change in the live file leads to `replace_after_handoff`, and the new sidekick receives the accepted state.
5. The lead reviews the diff and evidence without rerunning passing checks.
6. An invalid model file blocks the next handoff and names the error.

## Instruction scenarios

Record observed behavior separately from the written policy.

- Settled design: the brief states requirements, locations, interfaces, edge cases, and a definition of done without dictating every line.
- Early delegation: the lead's first handoff comes before it reads most of the relevant files, and the lead makes no routine edits.
- Evidence-backed objection: the sidekick reports a concrete plan defect, and the lead decides before execution continues.
- Unsettled interface: the lead delegates discovery, then settles the interface before implementation.
- Grader or production query: the lead authors and judges the logic, and the sidekick only runs the exact recipe.
- Failed check: the sidekick attempts an in-scope fix, reruns the affected checks, and reports remaining blockers.
- Rework: the lead sends one consolidated brief and does not rewrite the sidekick's work itself.
- User update during a handoff: the lead assesses it before waiting again and steers the same sidekick.
- Unrendered UI: the report says visually unverified instead of treating a build as visual proof.

These are evaluation cases, not automated proof of agent behavior.
