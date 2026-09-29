# Sidekick runtimes

`model_config.py resolve` returns a `transport`, a `model`, and a `reasoning_effort` for your harness.
A `null` effort means the transport's default. Inspect the live tool schemas before you call a tool; names change between versions.
Start every new sidekick's first brief with: `Read <skill>/references/sidekick.md and follow it for this whole session.` Paste the contract instead when the sidekick cannot read that path.

## Native subagents

Use `native` only when the harness has a subagent that keeps its context across messages and accepts a model choice.

In Claude Code:

- Start: call the `Agent` tool with a general-purpose agent type, the resolved `model` alias, and the contract line plus the brief as the prompt.
- Continue: call `SendMessage` with the agent ID from the start result. A new `Agent` call starts a fresh agent without context; never use it for a follow-up.
- Wait: the harness notifies you when the agent finishes. Do not poll, and never write its report yourself.
- The `Agent` tool has no effort parameter, so keep the Claude Code profile's effort `null`.
- Close: stop sending to the agent. Stop it with the harness's task-stop tool only when it must end mid-handoff.

In Codex:

| Operation | Tool | Fields |
| --- | --- | --- |
| Start | `spawn_agent` | `agent_type: "default"`, `model`, `reasoning_effort`, `fork_context: false`, `message` |
| Continue | `send_input` | `target`, `message` |
| Steer running work | `send_input` | `target`, `message`, `interrupt: true` |
| Wait | `wait_agent` | `targets`, a bounded `timeout_ms` |
| Close | `close_agent` | the live schema's ID field |

Never use a custom agent with a pinned model. The live model file selects the model.

## CLI sessions

`codex-cli` and `claude-cli` run the sidekick as a separate CLI session. Any harness that runs shell commands can use them.

```sh
python3 <skill>/scripts/sidekick.py start --harness <name> --workdir <checkout> --brief-file <brief>
python3 <skill>/scripts/sidekick.py send --transport <transport> --session <id> --model <model> --effort <effort|default> --workdir <checkout> --brief-file <brief>
```

`start` reads the live model file. `send` resumes the recorded session with the recorded settings. Both print JSON with `session`, `report`, and `exit_code`, and exit nonzero with an `error` field on failure.
Write each brief to a temporary file outside the checkout. The command blocks until the handoff ends. Run it in the background when the harness supports that, and set a timeout long enough for the handoff.
A CLI session cannot receive messages mid-handoff. When a user update must apply at once, stop the process and send a corrected brief to the same session. Otherwise include the update in the next brief.
`codex-cli` runs with the `workspace-write` sandbox. `claude-cli` runs with `acceptEdits`, and the user's Claude Code rules decide other tools. Report denied commands; never add bypass flags.
From Claude Code, use `codex-cli` for a Codex sidekick. The Codex plugin's rescue flow resumes only its most recent task, so it cannot address a specific sidekick session.

## Other harnesses

Add a profile named after the harness when it has a native subagent that meets the requirements above. Otherwise the `default` profile applies, and it must use a CLI transport.

## Runtime state

Do not assume that shell state, the working directory, or background processes survive between handoffs unless you checked.
Use absolute paths. Make environment setup reproducible. The lead owns long-lived servers through process handles it can inspect.
The sidekick may run a short-lived server and tests within one handoff and then clean them up.

## Replace the sidekick

On `replace_after_handoff`, let the running handoff finish, review its result, and close the old sidekick.
Resolve again, start the new sidekick, and put the accepted state in the brief's `Continuity` field.
A replacement keeps the facts you pass on, not the old conversation or its prompt cache.
If the runtime rejects the model or effort, report the mismatch. Do not substitute another model.
