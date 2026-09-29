# Fusion Harness

A portable agent skill that applies the lead and sidekick pattern Cognition describes for [Devin Fusion](https://cognition.com/blog/devin-fusion).
It works in Claude Code, Codex, and any agent harness that loads skills and runs shell commands.
This project is independent and not affiliated with Cognition.

## How it works

![Fusion workflow: the main agent plans and reviews; one persistent sidekick explores, implements, and checks the work.](image.png)

*Diagram: [Cognition](https://cognition.com/blog/local-fusion).*

The lead is the model you are already talking to. It owns the plan, ambiguity, review, and everything the user sees.
One persistent sidekick explores the code, implements changes, and runs the checks. The two exchange briefs, reports, and feedback, never full conversations.
Each side keeps its own context, so each can reuse its prompt cache across handoffs.
The lead delegates early, writes briefs with requirements and a definition of done, and reviews evidence instead of redoing work.
Fusion assumes a strong sidekick model. Strong sidekicks need less review, which often makes the pair cheaper overall.

## Install

```sh
npx skills add nahuelb/fusion-harness -g -a claude-code -a codex
```

This uses the [skills CLI](https://github.com/vercel-labs/skills). It installs the skill in `~/.agents/skills/fusion` for Codex and links it for Claude Code. There is no setup step.
Start a task with `/fusion <task>` in Claude Code or `$fusion <task>` in Codex. In other harnesses, ask the agent to use the fusion skill.
Update with `npx skills update fusion -g`. See [installation](docs/installation.md) for other agents, a development checkout, and migration from the earlier Codex plugin.

## Models

The lead is the model of your current session. The sidekick defaults depend on the harness:

| Harness | Sidekick | Effort | Transport |
| --- | --- | --- | --- |
| Claude Code | `claude-sonnet-5-5` | medium | Claude Code subagent |
| Codex | `gpt-6-luna` | high | Codex subagent |
| Any other | `gpt-6-luna` | high | Codex CLI session |

The defaults target an Opus 5.5 lead at medium or high effort in Claude Code.
To pick another sidekick, say so when you start: `/fusion use claude-sonnet-5 at high effort as the sidekick. <task>`. The lead saves your choice as your default for future sessions.
Ask the lead to reset the sidekick to go back to the built-in defaults. Use exact model IDs; aliases such as `sonnet` move to a newer model on release.

Your choices live in `~/.config/fusion-harness/models.json`, which holds only what you changed. A sidekick can also run as a separate CLI session from any harness, through `codex-cli` or `claude-cli`. For example, this makes Claude Code use a Codex sidekick:

```sh
python3 ~/.agents/skills/fusion/scripts/model_config.py set --profile claude-code --transport codex-cli --model gpt-6-luna --effort high
```

A change applies at the next handoff. A running sidekick finishes its current handoff first.
In Claude Code, the lead pins the sidekick's model and effort in a generated `~/.claude/agents/fusion-sidekick.md`. Claude Code reloads that file between turns, so after a change the lead pauses for one short background command before it starts the sidekick.

## Limits

The skill is instructions plus small helpers. Nothing enforces delegation, and it does not recreate Devin's model routing or compaction.
Claude Code needs one restart only if `~/.claude/agents` did not exist when the session started.
Cost savings and quality have not been benchmarked for this skill. Token accounting reads Codex session logs only.

## Development

```sh
python3 scripts/check.py
```

[AGENTS.md](AGENTS.md) holds the contributor rules. [Evaluation](docs/evaluation.md) describes how to compare the skill with a single-agent baseline.

## Sources

- [Devin Fusion: Frontier Performance at 60% Lower Cost](https://cognition.com/blog/devin-fusion)
- [Making Fable Cheaper Than Opus](https://cognition.com/blog/making-fable-cheaper-than-opus)
- [Introducing Fusion in Devin Desktop & CLI](https://cognition.com/blog/local-fusion)
- [Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working)
- [Devin is now up to 40% more cost-efficient](https://devin.ai/blog/more-efficient-devin)

## License

[MIT](LICENSE). The instruction text is original to this project. The workflow diagram is Cognition's, from their Fusion posts.
