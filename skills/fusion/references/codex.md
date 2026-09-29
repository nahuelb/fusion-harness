# Codex sidekick

| Operation | Tool | Fields |
| --- | --- | --- |
| Start | `spawn_agent` | `agent_type: "default"`, `model`, `reasoning_effort`, `fork_context: false`, `message` |
| Continue | `send_input` | `target`, `message` |
| Steer running work | `send_input` | `target`, `message`, `interrupt: true` |
| Wait | `wait_agent` | `targets`, a bounded `timeout_ms` |
| Close | `close_agent` | the live schema's ID field |

Never use a custom agent with a pinned model. The live model file selects the model.
Use bounded waits so user messages can reach you. Do not poll in a loop.
