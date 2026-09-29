# Install Fusion Harness

Python 3.10 or newer must be available as `python3`. The skill uses only the standard library.
Each CLI transport needs its CLI on `PATH` and signed in: `codex` for `codex-cli`, `claude` for `claude-cli`.

## Install with the skills CLI

```sh
npx skills add nahuelb/fusion-harness -g -a claude-code -a codex
python3 ~/.agents/skills/fusion/scripts/model_config.py init
```

The [skills CLI](https://github.com/vercel-labs/skills) needs Node.js. It copies the skill to `~/.agents/skills/fusion`, which Codex reads, and links it from `~/.claude/skills/fusion` for Claude Code.
Use `-a` for other agents, or drop `-g` to install into the current project. Start a new task after installing; a running task does not prove that the skill loaded.
Run `init` before you start Claude Code, so the session loads the sidekick definition it writes.
Update with `npx skills update fusion -g` and run `init` again. Remove with `npx skills remove fusion -g`.

## Install from a checkout

Use a checkout when you develop the skill, so edits apply without reinstalling:

```sh
git clone https://github.com/nahuelb/fusion-harness.git ~/Projects/fusion-harness
ln -s ~/Projects/fusion-harness/skills/fusion ~/.agents/skills/fusion
ln -s ~/Projects/fusion-harness/skills/fusion ~/.claude/skills/fusion
```

Codex reads `~/.agents/skills`. Claude Code reads `~/.claude/skills`. Other harnesses document their own skill folder.
If one folder is a link to the other, create only one link. Update with `git pull`.

## Create the model file

The first Fusion run creates the file when it is missing, but a Claude Code session then needs a restart. To create or inspect it yourself:

```sh
python3 ~/.agents/skills/fusion/scripts/model_config.py init
python3 ~/.agents/skills/fusion/scripts/model_config.py show
```

`init` creates `~/.config/fusion-harness/models.json` from the shipped defaults when the file is missing. It never overwrites an existing file.
`XDG_CONFIG_HOME` moves the default folder. `FUSION_MODELS_FILE` selects any other path.
Change a profile with `model_config.py set`. It validates the result and replaces the file atomically.
`init`, `set`, and `sync` also write `~/.claude/agents/fusion-sidekick.md`, which pins the Claude Code sidekick's exact model and effort. Start a new Claude Code session after changing it.
Model names are checked at spawn time, not by the schema. If a model is unavailable, the lead reports it and does not substitute another.

## Migrate from the Codex plugin

Earlier versions shipped as the Codex plugin `fusion`. Find and remove the installed copy:

```sh
codex plugin list | grep '^fusion@'
codex plugin remove fusion@<marketplace>
```

Remove its marketplace too if nothing else uses it: `codex plugin marketplace remove <marketplace>`.
When the old file `$CODEX_HOME/plugins/fusion/models.json` exists and the new file does not, `init` copies its sidekick model and effort into the `codex` profile. It leaves the old file in place.
The plugin's hooks and session bookkeeping are gone. The lead keeps the sidekick's identity and settings in its own continuation record.
