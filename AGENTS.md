# Project boundaries

Read `~/.agents/AGENTS.md` before work when it exists.
Fusion Harness is one portable agent skill in `skills/fusion`. It must work in Claude Code, Codex, and any harness that loads skills and runs shell commands.
Keep harness-specific details in `skills/fusion/references/runtimes.md`. Check current official documentation and the live tool schemas before you change a runtime mapping.
Preserve one sidekick per lead, bounded handoffs, lead acceptance, and the user's permission boundaries. Never add sandbox or approval bypass flags to a transport.
Assume strong sidekick models. Do not add guidance or settings for weak sidekicks.

Use Python's standard library unless a dependency has a concrete benefit. Run `python3 scripts/check.py` before committing.
Test changes to model resolution, replacement decisions, CLI transports, and token accounting.
Keep runtime state, user model files, credentials, and raw session logs out of Git.

## Sources and research

Base instruction changes on public sources, such as Cognition's blog posts, and on this project's own tests. Cite public sources in the README.
Write all tracked text in original prose. Do not copy third-party prompts, diagrams, or images.
Keep research notes in `research/`, which Git ignores. Tracked files must not describe how third-party software was inspected, and must not name inspected versions or quote their internals.

## Live model configuration

The live file is `~/.config/fusion-harness/models.json`, `$XDG_CONFIG_HOME/fusion-harness/models.json`, or the path in `FUSION_MODELS_FILE`.
The lead reads it before every handoff. Changes must not require reinstalling or relinking the skill.
Keep shipped defaults in `skills/fusion/config/models.default.json`. Never overwrite an existing user file.
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
