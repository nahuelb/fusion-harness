#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

import model_config


CLI_TRANSPORTS = ('codex-cli', 'claude-cli')
NESTED_SESSION_VARIABLES = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT')


def codex_command(settings, session, workdir, output):
    effort = settings['reasoning_effort']
    tuning = ['-c', f'model_reasoning_effort="{effort}"'] if effort else []
    if session:
        return ['codex', 'exec', 'resume', session, '--json', '-m', settings['model'], *tuning,
                '-c', 'sandbox_mode="workspace-write"', '-o', output, '-']
    return ['codex', 'exec', '--json', '-C', workdir, '-s', 'workspace-write', '-m', settings['model'], *tuning, '-o', output, '-']


def claude_command(settings, session, resume):
    effort = settings['reasoning_effort']
    tuning = ['--effort', effort] if effort else []
    identity = ['--resume', session] if resume else ['--session-id', session]
    return ['claude', '-p', '--output-format', 'json', '--model', settings['model'], *tuning, *identity,
            '--permission-mode', 'acceptEdits']


def codex_session(stdout):
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get('type') == 'thread.started' and event.get('thread_id'):
            return event['thread_id']
    return None


def run(settings, brief, workdir, session=None):
    transport = settings['transport']
    environment = {k: v for k, v in os.environ.items() if k not in NESTED_SESSION_VARIABLES}
    result = {'transport': transport, 'model': settings['model'], 'reasoning_effort': settings['reasoning_effort'], 'workdir': workdir}
    if transport == 'codex-cli':
        with tempfile.TemporaryDirectory() as scratch:
            output = str(Path(scratch) / 'report.txt')
            process = subprocess.run(codex_command(settings, session, workdir, output), input=brief, cwd=workdir,
                                     env=environment, capture_output=True, text=True)
            report = Path(output).read_text() if Path(output).exists() else ''
        result['session'] = session or codex_session(process.stdout)
        result['report'] = report.strip()
    else:
        identity = session or str(uuid.uuid4())
        process = subprocess.run(claude_command(settings, identity, bool(session)), input=brief, cwd=workdir,
                                 env=environment, capture_output=True, text=True)
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError:
            payload = {}
        result['session'] = payload.get('session_id') or identity
        result['report'] = str(payload.get('result') or '').strip()
        if payload.get('is_error'):
            result['error'] = result['report'] or 'The Claude CLI reported an error.'
    result['exit_code'] = process.returncode
    if process.returncode and 'error' not in result:
        result['error'] = process.stderr.strip()[-2000:] or f'{transport} exited with {process.returncode}.'
    if not result['session']:
        result['error'] = result.get('error') or 'The CLI did not report a session ID; this sidekick cannot be resumed.'
    return result


def main():
    parser = argparse.ArgumentParser(description='Run one Fusion handoff through a CLI sidekick session.')
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('start')
    start.add_argument('--harness', required=True)
    send = commands.add_parser('send')
    send.add_argument('--transport', choices=CLI_TRANSPORTS, required=True)
    send.add_argument('--session', required=True)
    send.add_argument('--model', required=True)
    send.add_argument('--effort', required=True, help='Use "default" when the sidekick has no explicit effort.')
    for sub in (start, send):
        sub.add_argument('--workdir', required=True)
        sub.add_argument('--brief-file', help='Read the brief from this file instead of standard input.')
    args = parser.parse_args()
    try:
        workdir = str(Path(args.workdir).expanduser().resolve(strict=True))
        brief = Path(args.brief_file).read_text() if args.brief_file else sys.stdin.read()
        if not brief.strip():
            raise ValueError('The brief is empty.')
        if args.command == 'start':
            settings = model_config.resolve(args.harness)
            if settings['transport'] not in CLI_TRANSPORTS:
                raise ValueError(f'Profile {settings["profile"]} uses the native transport; spawn a native subagent instead.')
            result = run(settings, brief, workdir)
            result['profile'] = settings['profile']
        else:
            effort = None if args.effort == 'default' else args.effort
            settings = {'transport': args.transport, 'model': args.model, 'reasoning_effort': effort}
            result = run(settings, brief, workdir, args.session)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Fusion sidekick: {exc}\n')
    print(json.dumps(result, indent=2))
    if result.get('error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
