# Claude Code sidekick

The `Agent` tool takes only model aliases and no effort. `resolve` pins the exact model and effort in a generated agent definition at `~/.claude/agents/fusion-sidekick.md`, or under `CLAUDE_CONFIG_DIR`, and returns its `agent_type`.
Claude Code reloads agent definitions only between turns.

- If `reload_required` is true, the definition changed during this turn. Run `sleep 2` as a background command and end your turn. Continue when the completion notification arrives; the next turn uses the new definition. Do your planning first, so the pause costs nothing.
- If `restart_required` is true, the agents folder did not exist when this session started, and Claude Code does not watch it. Ask the user to restart Claude Code once, then continue.
- If `error` is present, or the `Agent` tool reports that the type does not exist, stop and report the error. Never fall back to a general-purpose agent or a model alias, and do not write agent definitions by hand.
- Start: call the `Agent` tool with the returned `agent_type`, no `model` parameter, and the brief as the prompt. The definition already points the sidekick to its contract.
- Continue: call `SendMessage` with the agent ID from the start result. A new `Agent` call starts a fresh agent without context; never use it for a follow-up.
- Wait: the harness notifies you when the agent finishes. Do not poll, and never write its report yourself.
- Close: stop sending to the agent. Stop it with the harness's task-stop tool only when it must end mid-handoff.

On `replace_after_handoff`, the running sidekick keeps its old settings until its handoff ends. Resolve after reviewing it, pause for the reload when required, then start the new sidekick.
For a Codex sidekick from Claude Code, set the profile's transport to `codex-cli` and follow [CLI sessions](cli.md). The Codex plugin's rescue flow resumes only its most recent task, so it cannot address a specific sidekick session.
