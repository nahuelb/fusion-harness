# Usage accounting

The helper reads local Claude Code transcripts and Codex session logs. Run it in the current agent. Do not delegate it or change configuration.

Run `python3 <skill>/scripts/token_usage.py` for the current session. It uses `CLAUDE_CODE_SESSION_ID` in Claude Code and `CODEX_THREAD_ID` in Codex, and never picks the latest session on its own.
For another session, pass `--claude-session <exact-id>` or `--session <exact-codex-thread-id>`. Resolve a task name or link to its exact ID first. Ask for the ID only when no lookup can resolve it.
Add each CLI sidekick session with `--cli-sidekick <id>`, using the session ID that `sidekick.py` printed. It may be a Claude Code session or a Codex thread.
For Codex rollout files the user supplies, pass `--lead <absolute-path>` and one `--sidekick <absolute-path>` per sidekick instead.
Never expose prompts, tool output, or full logs from these files.

## Attribute roles

The selected session is the lead. Subagents of type `fusion-sidekick`, or with the native Codex sidekick role, are sidekicks. Other subagents stay unclassified.
Rerun with one `--sidekick-id <id>` per sidekick when the user names them or this conversation holds their spawn results.
Never infer roles from model names, token volume, directories, or recency. Keep unclassified subagents visible.

## Report

State the session and observation time. These are whole-session totals, not a Fusion-only interval.
Show input, cached input, output, reasoning output, and total tokens per role. For Claude Code rows, also show cache writes.
Cached input and cache writes are part of input, and reasoning output is part of output. Do not add them twice.
Compute shares only from complete counters. Keep missing usage unknown and surface the helper's warnings.
Do not claim dollar cost, subscription quota, or savings from token counts.
