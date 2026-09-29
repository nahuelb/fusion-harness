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
PERMISSIONS = {'codex-cli': ('read-only', 'workspace-write'), 'claude-cli': ('default', 'acceptEdits', 'plan')}
NESTED_SESSION_VARIABLES = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT')


def codex_command(settings, session, workdir, output, permission):
    effort = settings['reasoning_effort']
    tuning = ['-c', f'model_reasoning_effort="{effort}"'] if effort else []
    if session:
        sandbox = ['-c', f'sandbox_mode="{permission}"'] if permission else []
        return ['codex', 'exec', 'resume', session, '--json', '-m', settings['model'], *tuning, *sandbox, '-o', output, '-']
    sandbox = ['-s', permission] if permission else []
    return ['codex', 'exec', '--json', '-C', workdir, *sandbox, '-m', settings['model'], *tuning, '-o', output, '-']


def claude_command(settings, session, resume, permission):
    effort = settings['reasoning_effort']
    tuning = ['--effort', effort] if effort else []
    identity = ['--resume', session] if resume else ['--session-id', session]
    mode = ['--permission-mode', permission] if permission else []
    return ['claude', '-p', '--output-format', 'json', '--model', settings['model'], *tuning, *identity, *mode]


def codex_thread(line):
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if isinstance(event, dict) and event.get('type') == 'thread.started':
        return event.get('thread_id')
    return None


def announce(session):
    print(f'Fusion sidekick session: {session}', file=sys.stderr, flush=True)


def execute(command, brief, workdir, environment, on_line=None):
    with tempfile.TemporaryFile('w+') as errors:
        process = subprocess.Popen(command, cwd=workdir, env=environment, text=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
        process.stdin.write(brief)
        process.stdin.close()
        lines = []
        for line in process.stdout:
            lines.append(line)
            if on_line:
                on_line(line)
        code = process.wait()
        errors.seek(0)
        return code, ''.join(lines), errors.read()


def run(settings, brief, workdir, session=None, permission=None):
    transport = settings['transport']
    environment = {k: v for k, v in os.environ.items() if k not in NESTED_SESSION_VARIABLES}
    result = {'transport': transport, 'model': settings['model'], 'reasoning_effort': settings['reasoning_effort'],
              'permission': permission, 'workdir': workdir, 'session': session}
    if transport == 'codex-cli':
        def capture(line):
            thread = None if result['session'] else codex_thread(line)
            if thread:
                result['session'] = thread
                announce(thread)

        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / 'report.txt'
            code, _, stderr = execute(codex_command(settings, session, workdir, str(output), permission), brief, workdir, environment, capture)
            result['report'] = output.read_text().strip() if output.exists() else ''
    else:
        if not session:
            result['session'] = str(uuid.uuid4())
            announce(result['session'])
        command = claude_command(settings, result['session'], bool(session), permission)
        code, stdout, stderr = execute(command, brief, workdir, environment)
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {}
        result['session'] = payload.get('session_id') or result['session']
        result['report'] = str(payload.get('result') or '').strip()
        if payload.get('is_error'):
            result['error'] = result['report'] or 'The Claude CLI reported an error.'
    result['exit_code'] = code
    if code and 'error' not in result:
        result['error'] = stderr.strip()[-2000:] or f'{transport} exited with {code}.'
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
    send.add_argument('--effort', required=True, help='Use "default" or "null" when the sidekick has no explicit effort.')
    for sub in (start, send):
        sub.add_argument('--workdir', required=True)
        sub.add_argument('--brief-file', help='Read the brief from this file instead of standard input.')
        sub.add_argument('--permission', help='A sandbox or permission mode the user already granted; omit it to use the CLI configuration.')
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
        else:
            settings = {'transport': args.transport, 'model': args.model, 'reasoning_effort': model_config.effort_argument(args.effort)}
        allowed = PERMISSIONS[settings['transport']]
        if args.permission and args.permission not in allowed:
            raise ValueError(f'--permission for {settings["transport"]} must be one of {list(allowed)}.')
        result = run(settings, brief, workdir, getattr(args, 'session', None), args.permission)
        if args.command == 'start':
            result['profile'] = settings['profile']
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Fusion sidekick: {exc}\n')
    print(json.dumps(result, indent=2))
    if result.get('error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
