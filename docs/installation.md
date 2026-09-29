# Install Fusion Harness

Python 3.10 or newer must be available as `python3`. The skill uses only the standard library.
Each CLI transport needs its CLI on `PATH` and signed in: `codex` for `codex-cli`, `claude` for `claude-cli`.

## Link the skill

Clone the repository once and link `skills/fusion` into each skill folder your harnesses read:

```sh
git clone https://github.com/nahuelb/fusion-harness.git ~/Projects/fusion-harness
ln -s ~/Projects/fusion-harness/skills/fusion ~/.agents/skills/fusion
ln -s ~/Projects/fusion-harness/skills/fusion ~/.claude/skills/fusion
```

Codex reads `~/.agents/skills`. Claude Code reads `~/.claude/skills`. Other harnesses document their own skill folder.
If one folder is a link to the other, create only one link. A repository-level `.agents/skills` or `.claude/skills` folder also works for one project.
Start a new task after linking. A running task does not prove that the skill loaded.

## Create the model file

```sh
python3 ~/Projects/fusion-harness/skills/fusion/scripts/model_config.py init
python3 ~/Projects/fusion-harness/skills/fusion/scripts/model_config.py show
```

`init` creates `~/.config/fusion-harness/models.json` from the shipped defaults when the file is missing. It never overwrites an existing file.
`XDG_CONFIG_HOME` moves the default folder. `FUSION_MODELS_FILE` selects any other path.
Change a profile with `model_config.py set`. It validates the result and replaces the file atomically.
Model names are checked at spawn time, not by the schema. If a model is unavailable, the lead reports it and does not substitute another.

## Update

```sh
git -C ~/Projects/fusion-harness pull
```

Links pick up the new files. Start a new task to load them. The model file lives outside the checkout and is not touched.

## Migrate from the Codex plugin

Earlier versions shipped as the Codex plugin `fusion`. Find and remove the installed copy:

```sh
codex plugin list | grep '^fusion@'
codex plugin remove fusion@<marketplace>
```

Remove its marketplace too if nothing else uses it: `codex plugin marketplace remove <marketplace>`.
When the old file `$CODEX_HOME/plugins/fusion/models.json` exists and the new file does not, `init` copies its sidekick model and effort into the `codex` profile. It leaves the old file in place.
The plugin's hooks and session bookkeeping are gone. The lead keeps the sidekick's identity and settings in its own continuation record.
