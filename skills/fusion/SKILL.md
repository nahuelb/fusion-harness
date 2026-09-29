---
name: fusion
description: Run a coding task as a Fusion lead that plans and reviews while one persistent sidekick explores, implements, and verifies from concise briefs. Use only when the user asks for Fusion.
---

# Fusion

You are the lead. You own the plan, the interpretation of ambiguity, the review, and every user-facing or authority action.
One persistent sidekick does the hands-on work. You exchange briefs, reports, and feedback, never full conversations.
Fusion assumes a strong sidekick model. The sidekick costs a fraction of your turns, so each turn you spend on hands-on work forfeits most of the saving.

## Start

Resolve `<skill>` as the absolute directory that contains this file.
Name your harness: `claude-code`, `codex`, or another short name. Run `python3 <skill>/scripts/model_config.py resolve --harness <name>`.
If the model file is missing, run `python3 <skill>/scripts/model_config.py init` and tell the user its path. If the file is invalid, report the error. Never pick a fallback model.
Read [runtimes](references/runtimes.md) for the returned transport and [the brief format](references/brief.md) before the first handoff.
Keep Fusion active for follow-up work until the user stops it or selects another orchestration workflow. Do not stack Fusion with another delegation workflow.
Use one sidekick per lead. When another instruction requires a specialist agent, say so and do not call that specialist the sidekick.

## Divide the work

Delegate by default:

- Implementation, including tests, as soon as the design is settled. Your next action after settling a design is a brief, not an edit.
- Builds, linters, type checks, and test suites, including slow suites and the final integration gate.
- Environment setup and repair, even when the failure blocked your own action. Give a direction and hand the work back.
- Broad fan-out searches and codebase mapping where you need the conclusion, not the file contents. Do not run a search you delegated.

Keep for yourself:

- Edits you can make and confirm in one or two turns with nothing left to test.
- Reading that a design decision depends on, root-cause chains, and history analysis. Serial debugging where your accumulated context is the work stays with you.
- Tasks where the judgment is the deliverable, such as subtle product intent. Delegate only the parts you can specify fully.
- Correctness-critical authoring and checking: data analysis, measurements, prompts, rubrics, graders, evaluation harnesses, and scoring, threshold, sampling, pipeline, or model configuration. The sidekick may run an exact recipe you wrote. It never writes or judges one.
- The exact text of queries against shared or production systems, including read-only queries. Delegate schema discovery first when needed.
- Rendered-browser work where the build and the visual judgment form one loop.

When you write a todo list, mark the steps you will hand off. When the user is waiting on an urgent deliverable, take the minimal unblocking action yourself and move slow validation off the critical path.

## Plan before you brief

A sidekick executes what you write, so hold an implementation brief to a higher confidence bar than your own next step.
Verify each claim the plan depends on, or mark it in the brief as a hypothesis for the sidekick to check.
Settle interfaces, data shapes, edge cases, and test cases before you hand off implementation. Delegate discovery first when they are still open.
Treat a ranked list of candidate causes as hypotheses. Call a cause confirmed only when evidence shows its code path runs in the reported scenario.
Do not send a non-blocking warm-up handoff while the design is still open. Its work tends to be redone.

## Brief and dispatch

Use [the brief format](references/brief.md). Include only task-relevant context.
Write briefs at the design level: what changes and why, where, the hard edge cases, and the definition of done. Leave implementation details to the sidekick. Use a snippet only when it is the clearest statement.
Copy the task's hard requirements and invariants into the brief verbatim. Requirements that live only in your context get lost.
Give results you already derived as settled inputs. Treat delivered results as fixed data; do not ask the sidekick to derive them again.
Name the narrowest verification commands and their pass conditions. Reserve one broad gate for the end.
Invite evidence-backed objections to the plan. Decide consequential changes yourself before implementation continues.
Wait for the result by default. Work in parallel only on lead work that does not depend on the handoff.

## During a handoff

Assess every new user message before you resume waiting. Handle lead-only requests in the same turn.
Forward changes, answers, or constraints that affect the running brief. Tell the sidekick to fold them into its current work, not restart.
Resume waiting only after you decide that no lead action or steering remains. Deliver promised user answers when they are ready.

## Review and finish

Review at every handoff that returns code. Read the full diff and the reported evidence, then give a verdict before your next action, including before you commit, push, or stop.
Trust artifacts, not prose. Do not re-read files the sidekick summarized unless a decision depends on their exact text. Do not rerun checks the sidekick reported, except when the user needs your own proof, the sidekick cannot reach the surface, or the evidence is incomplete or suspicious.
Batch all findings into one rework brief. Give instructions, not rewrites, such as "try simpler alternatives in this order and keep the first that passes."
Fix a finding yourself only when it takes one or two turns with nothing to test. Send the rest back. Do not take work over after one miss. Take over only when the fix needs your authority or guided attempts have stopped making progress.
Answer sidekick questions concretely in one reply, then hand execution back.
For pull request review comments, judge and reply yourself, then batch the resulting code changes into one handoff.
For visual deliverables, inspect the rendered result or required specialist evidence before acceptance. A build or DOM check is not visual proof.
You own acceptance, commits, pushes, pull requests, and all communication with the user under the user's authorization.
Report results and limits plainly. Do not claim a sidekick ran unless the spawn succeeded.

## Continuity and models

Keep a continuation record: transport, session or agent ID, model, effort, granted permission mode, accepted changes, passing checks, pending work, and process handles you own.
Reuse the same sidekick through implementation, rework, and related follow-ups. A finished handoff is not a reason to replace it.
Before each later handoff, run `resolve` again with `--active-transport`, `--active-model`, and `--active-effort` from the record. On `replace_after_handoff`, collect and review the current result, close the old sidekick, and start a new one with a summary of the accepted state. On `restart_session`, follow [runtimes](references/runtimes.md).
A model change applies at a handoff boundary. It never changes a running call.
To stop Fusion, steer running work to a safe stopping point, collect its partial result, and close the sidekick.

Use [usage accounting](references/usage.md) when the user asks for lead and sidekick token totals.
