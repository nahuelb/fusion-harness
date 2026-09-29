# CLI sidekick sessions

`codex-cli` and `claude-cli` run the sidekick as a separate CLI session. Any harness that runs shell commands can use them.

```sh
python3 <skill>/scripts/sidekick.py start --harness <name> --workdir <checkout> --brief-file <brief> [--permission <mode>]
python3 <skill>/scripts/sidekick.py send --transport <transport> --session <id> --model <model> --effort <effort|default> --workdir <checkout> --brief-file <brief> [--permission <mode>]
```

`start` reads the live model file. `send` resumes the recorded session with the recorded settings. Both print JSON with `session`, `report`, and `exit_code`, and exit nonzero with an `error` field on failure.
Both print `Fusion sidekick session: <id>` to standard error as soon as the session exists. Record it before the handoff ends.
Write each brief to a temporary file outside the checkout. The command blocks until the handoff ends. Run it in the background when the harness supports that, and set a timeout long enough for the handoff.
A CLI session cannot receive messages mid-handoff. Include user updates in the next brief. When the user asks to stop, stop the helper; it stops its CLI process before it exits.

Without `--permission`, the CLI uses its own configured sandbox or permission mode, which may not allow edits.
Pass `--permission` only with a mode the user already granted for this work: `read-only` or `workspace-write` for `codex-cli`, and `default`, `acceptEdits`, or `plan` for `claude-cli`. Record it and pass it again on `send`.
Bypass modes are rejected. Report denied commands to the user instead of working around them.
