# Usage accounting

The helper reads local Codex session logs. It does not read Claude Code transcripts yet.
Run it in the current agent. Do not delegate it, activate Fusion, or change configuration.

For the current Codex session, run `python3 <skill>/scripts/token_usage.py`. It uses `CODEX_THREAD_ID` and never selects the latest session on its own.
For another session, pass `--session <exact-thread-id>`. Resolve a task name or link to its exact ID first. Ask for the ID only when no lookup can resolve it.
A `codex-cli` sidekick runs as a separate session. Pass explicit rollout files instead: `--lead <absolute-path>` and one `--sidekick <absolute-path>` per sidekick session.
Never expose prompts, tool output, or full logs from those files.

## Attribute roles

The selected session is the lead. Native subagents are unclassified unless their role says sidekick or you confirm them.
Rerun with one `--sidekick-id <id>` per sidekick when the user names them or this conversation holds their spawn results.
Never infer roles from model names, token volume, directories, or recency. Keep unclassified subagents visible.

## Report

State the session and observation time. These are whole-session totals, not a Fusion-only interval.
Show input, cached input, output, reasoning output, and total tokens per role.
Cached input is part of input, and reasoning output is part of output. Do not add them twice.
Compute shares only from complete counters. Keep missing usage unknown and surface the helper's warnings.
Do not claim dollar cost, subscription quota, or savings from token counts.
