# Claude Code sidekick

The `Agent` tool takes only model aliases and no effort. The skill pins the exact model and effort in a generated agent definition instead. `init`, `set`, and `sync` write it to `~/.claude/agents/fusion-sidekick.md`, or under `CLAUDE_CONFIG_DIR`.

- `resolve` returns `agent_type` and `agent_file_current`. If `agent_file_current` is false, `error` is present, or the `Agent` tool reports that the type does not exist, stop and report the error. Ask the user to run `python3 <skill>/scripts/model_config.py sync` and start a new session. Do not write agent definitions by hand, and never fall back to a general-purpose agent or a model alias.
- Start: call the `Agent` tool with the returned `agent_type`, no `model` parameter, and the brief as the prompt. The agent definition already points the sidekick to its contract.
- Continue: call `SendMessage` with the agent ID from the start result. A new `Agent` call starts a fresh agent without context; never use it for a follow-up.
- Wait: the harness notifies you when the agent finishes. Do not poll, and never write its report yourself.
- Close: stop sending to the agent. Stop it with the harness's task-stop tool only when it must end mid-handoff.

A session keeps the definition it loaded at start, and the helper cannot see which one it loaded.
When the Claude Code profile changed during this session, including through your own `set`, ask the user to start a new session before the next handoff.
On `restart_session`, let the running handoff finish and review it. Then ask the user to start a new session, and give them a summary of the accepted state to paste in. Do not start a replacement sidekick in this session.
For a Codex sidekick from Claude Code, set the profile to `codex-cli` and follow [CLI sessions](cli.md). The Codex plugin's rescue flow resumes only its most recent task, so it cannot address a specific sidekick session.
