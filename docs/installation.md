# Install Fusion Harness

Python 3.10 or newer must be available as `python3`. The skill uses only the standard library.
Each CLI transport needs its CLI on `PATH` and signed in: `codex` for `codex-cli`, `claude` for `claude-cli`.

## Install with the skills CLI

```sh
npx skills add nahuelb/fusion-harness -g -a claude-code -a codex
```

The [skills CLI](https://github.com/vercel-labs/skills) needs Node.js. It copies the skill to `~/.agents/skills/fusion`, which Codex reads, and links it from `~/.claude/skills/fusion` for Claude Code.
Use `-a` for other agents, or drop `-g` to install into the current project. Start a new task after installing; a running task does not prove that the skill loaded.
Update with `npx skills update fusion -g`. Remove with `npx skills remove fusion -g`.

## Install from a checkout

Use a checkout when you develop the skill, so edits apply without reinstalling:

```sh
git clone https://github.com/nahuelb/fusion-harness.git ~/Projects/fusion-harness
ln -s ~/Projects/fusion-harness/skills/fusion ~/.agents/skills/fusion
ln -s ~/Projects/fusion-harness/skills/fusion ~/.claude/skills/fusion
```

Codex reads `~/.agents/skills`. Claude Code reads `~/.claude/skills`. Other harnesses document their own skill folder.
If one folder is a link to the other, create only one link. Update with `git pull`.

## Sidekick settings

No setup is needed. The skill ships defaults for each harness, and the lead saves your choices when you name a sidekick model or effort.
Your choices live in `~/.config/fusion-harness/models.json`. `XDG_CONFIG_HOME` moves the folder, and `FUSION_MODELS_FILE` selects any other path. The file holds only the fields you changed.
You can also manage them directly:

```sh
python3 ~/.agents/skills/fusion/scripts/model_config.py show
python3 ~/.agents/skills/fusion/scripts/model_config.py set --profile claude-code --model claude-sonnet-5-5 --effort high
python3 ~/.agents/skills/fusion/scripts/model_config.py reset --profile claude-code
```

Model names are checked when the sidekick starts. If a model is unavailable, the lead reports it and does not substitute another.
In Claude Code, the lead writes `~/.claude/agents/fusion-sidekick.md` to pin the exact model and effort. It never replaces a file with that name that it did not generate.

## Migrate from the Codex plugin

Earlier versions shipped as the Codex plugin `fusion`. Find and remove the installed copy:

```sh
codex plugin list | grep '^fusion@'
codex plugin remove fusion@<marketplace>
```

Remove its marketplace too if nothing else uses it: `codex plugin marketplace remove <marketplace>`.
Settings from the old plugin are not imported. Tell the lead your preferred sidekick once, and it saves the choice.
The plugin's hooks and session bookkeeping are gone. The lead keeps the sidekick's identity and settings in its own continuation record.
