# Project boundaries

Read `~/.agents/AGENTS.md` before work when it exists.
Fusion Harness is one portable agent skill in `skills/fusion`. It must work in Claude Code, Codex, and any harness that loads skills and runs shell commands.
Keep harness-specific details in the transport references: `claude-code.md`, `codex.md`, and `cli.md` under `skills/fusion/references/`. Check current official documentation and the live tool schemas before you change a runtime mapping.
Preserve one sidekick per lead, bounded handoffs, lead acceptance, and the user's permission boundaries. Never add sandbox or approval bypass flags to a transport.
Assume strong sidekick models. Do not add guidance or settings for weak sidekicks.

Use Python's standard library unless a dependency has a concrete benefit. Run `python3 scripts/check.py` before committing.
Test changes to model resolution, replacement decisions, CLI transports, and token accounting.
Keep runtime state, user model files, credentials, and raw session logs out of Git.

## Sources and research

Base instruction changes on public sources, such as Cognition's blog posts, and on this project's own tests. Cite public sources in the README.
Write all tracked text in original prose. Do not copy third-party prompts. Credit any third-party image next to where it appears.
Keep research notes in `research/`, which Git ignores. Tracked files must not describe how third-party software was inspected, and must not name inspected versions or quote their internals.

## Live model configuration

Built-in defaults for each harness live in `skills/fusion/config/models.default.json`. The skill must work with no setup step.
The user's saved choices live in `~/.config/fusion-harness/models.json`, `$XDG_CONFIG_HOME/fusion-harness/models.json`, or the path in `FUSION_MODELS_FILE`. That file stores only overrides, so later default changes still reach fields the user did not set.
The lead reads the settings before every handoff. Changes must not require reinstalling the skill or restarting the harness, except where the harness itself cannot reload.
A model change takes effect at a handoff boundary. Never claim it changes a running call.
The lead is always the current session's model.

## Git workflow

Use $review-before-push before any push, PR creation, or PR update.
Read its shared instructions at `~/.agents/skills/review-before-push/SKILL.md`.
Review the complete outgoing diff and fix confirmed findings before publishing.

Use pull requests for substantive changes. Small, non-behavioral changes may go directly to `main`.
Describe the problem, intended behavior, tradeoffs, and validation in each PR.
Merge with a merge commit. Preserve individual commits; do not squash or rebase when merging.
Include the problem, approach, and PR reference in the merge message.
Monitor GitHub checks to completion and investigate failures.

## Local skill updates

The skill is linked from this checkout, so `main` in this checkout is what runs.
Keep the checkout on reviewed `main` when you are not working on a branch. Do not leave unmerged work checked out in a linked checkout without telling the user.
After runtime changes, verify skill loading in a fresh task. Existing tasks do not prove that an update loaded.
Report push, merge, and runtime verification separately.
