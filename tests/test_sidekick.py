import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/fusion/scripts'
sys.path.insert(0, str(SCRIPTS))
import sidekick


CODEX = {'transport': 'codex-cli', 'model': 'gpt-6-sol', 'reasoning_effort': 'medium'}
CLAUDE = {'transport': 'claude-cli', 'model': 'sonnet', 'reasoning_effort': None}


def returning(stdout='', code=0, stderr=''):
    return lambda command, brief, workdir, environment, on_line=None: (code, stdout, stderr)


class CodexTransportTests(unittest.TestCase):
    def fake_codex(self, command, brief, workdir, environment, on_line=None):
        self.calls.append((command, {'input': brief, 'cwd': workdir, 'env': environment}))
        Path(command[command.index('-o') + 1]).write_text('Report text\n')
        events = [json.dumps({'type': 'thread.started', 'thread_id': 'thread-1'}) + '\n', json.dumps({'type': 'turn.completed'}) + '\n']
        for line in events:
            on_line(line)
        return 0, ''.join(events), ''

    def setUp(self):
        self.calls = []

    def test_start_sets_model_effort_and_captures_session_early(self):
        with patch.object(sidekick, 'execute', side_effect=self.fake_codex), patch.object(sidekick, 'announce') as announce:
            result = sidekick.run(CODEX, 'brief', '/work')
        command, kwargs = self.calls[0]
        self.assertEqual(command[:3], ['codex', 'exec', '--json'])
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertNotIn('-s', command)
        announce.assert_called_once_with('thread-1')
        self.assertEqual(command[command.index('-C') + 1], '/work')
        self.assertEqual(kwargs['input'], 'brief')
        self.assertEqual((result['session'], result['report'], result['exit_code']), ('thread-1', 'Report text', 0))
        self.assertNotIn('error', result)

    def test_granted_sandbox_is_passed_on_start_and_resume(self):
        with patch.object(sidekick, 'execute', side_effect=self.fake_codex), patch.object(sidekick, 'announce'):
            sidekick.run(CODEX, 'brief', '/work', permission='workspace-write')
            sidekick.run(CODEX, 'brief', '/work', 'thread-1', 'workspace-write')
        self.assertEqual(self.calls[0][0][self.calls[0][0].index('-s') + 1], 'workspace-write')
        self.assertIn('sandbox_mode="workspace-write"', self.calls[1][0])

    def test_send_resumes_the_recorded_session(self):
        with patch.object(sidekick, 'execute', side_effect=self.fake_codex), patch.object(sidekick, 'announce') as announce:
            result = sidekick.run(CODEX, 'next brief', '/work', 'thread-1')
        command, kwargs = self.calls[0]
        self.assertEqual(command[:4], ['codex', 'exec', 'resume', 'thread-1'])
        announce.assert_not_called()
        self.assertEqual(kwargs['cwd'], '/work')
        self.assertEqual(result['session'], 'thread-1')

    def test_missing_session_is_an_error(self):
        with patch.object(sidekick, 'execute', side_effect=returning()):
            result = sidekick.run(CODEX, 'brief', '/work')
        self.assertIn('session', result['error'])

    def test_failure_reports_stderr(self):
        with patch.object(sidekick, 'execute', side_effect=returning('', 2, 'model not available')):
            result = sidekick.run(CODEX, 'brief', '/work', 'thread-1')
        self.assertEqual(result['exit_code'], 2)
        self.assertIn('model not available', result['error'])


class ClaudeTransportTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def fake_claude(self, command, brief, workdir, environment, on_line=None):
        self.calls.append((command, {'input': brief, 'cwd': workdir, 'env': environment}))
        session = command[command.index('--resume') + 1] if '--resume' in command else command[command.index('--session-id') + 1]
        return 0, json.dumps({'type': 'result', 'is_error': False, 'result': 'Done', 'session_id': session}), ''

    def test_start_announces_new_session_and_keeps_configured_permissions(self):
        with patch.dict(os.environ, {'CLAUDECODE': '1'}), patch.object(sidekick, 'execute', side_effect=self.fake_claude), \
                patch.object(sidekick, 'announce') as announce:
            result = sidekick.run(CLAUDE, 'brief', '/work')
        command, kwargs = self.calls[0]
        self.assertIn('--session-id', command)
        self.assertNotIn('--permission-mode', command)
        announce.assert_called_once_with(command[command.index('--session-id') + 1])
        self.assertNotIn('--effort', command)
        self.assertFalse(any('dangerously' in part or 'bypass' in part for part in command))
        self.assertNotIn('CLAUDECODE', kwargs['env'])
        self.assertEqual(result['report'], 'Done')
        self.assertEqual(result['session'], command[command.index('--session-id') + 1])

    def test_send_resumes_with_recorded_effort_and_granted_mode(self):
        settings = {**CLAUDE, 'reasoning_effort': 'high'}
        with patch.object(sidekick, 'execute', side_effect=self.fake_claude):
            result = sidekick.run(settings, 'brief', '/work', 'session-1', 'acceptEdits')
        command, _ = self.calls[0]
        self.assertEqual(command[command.index('--permission-mode') + 1], 'acceptEdits')
        self.assertEqual(command[command.index('--resume') + 1], 'session-1')
        self.assertEqual(command[command.index('--effort') + 1], 'high')
        self.assertEqual(result['session'], 'session-1')

    def test_cli_error_result_is_reported(self):
        payload = json.dumps({'is_error': True, 'result': 'Permission denied', 'session_id': 's'})
        with patch.object(sidekick, 'execute', side_effect=returning(payload, 1)):
            result = sidekick.run(CLAUDE, 'brief', '/work')
        self.assertEqual(result['error'], 'Permission denied')


class CommandLineTests(unittest.TestCase):
    def test_start_refuses_native_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            models = Path(temp) / 'models.json'
            environment = {**os.environ, 'FUSION_MODELS_FILE': str(models)}
            subprocess.run([sys.executable, str(SCRIPTS / 'model_config.py'), 'init'], env=environment, capture_output=True, check=True)
            process = subprocess.run([sys.executable, str(SCRIPTS / 'sidekick.py'), 'start', '--harness', 'claude-code', '--workdir', temp],
                                     input='brief', env=environment, capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn('native', process.stderr)

    def test_bypass_permission_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for transport, mode in (('codex-cli', 'danger-full-access'), ('claude-cli', 'bypassPermissions')):
                process = subprocess.run([sys.executable, str(SCRIPTS / 'sidekick.py'), 'send', '--transport', transport, '--session', 's',
                                          '--model', 'm', '--effort', 'default', '--workdir', temp, '--permission', mode],
                                         input='brief', capture_output=True, text=True)
                self.assertEqual(process.returncode, 1)
                self.assertIn('--permission', process.stderr)

    @unittest.skipUnless(os.name == 'posix', 'uses a POSIX shell stub')
    def test_cancelling_the_helper_stops_the_cli_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / 'child.pid'
            stub = root / 'codex'
            stub.write_text(f'#!/bin/sh\necho $$ > {marker}\nexec sleep 60\n')
            stub.chmod(0o755)
            environment = {**os.environ, 'PATH': f'{root}{os.pathsep}{os.environ["PATH"]}'}
            helper = subprocess.Popen([sys.executable, str(SCRIPTS / 'sidekick.py'), 'send', '--transport', 'codex-cli', '--session', 's',
                                       '--model', 'm', '--effort', 'default', '--workdir', temp],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, text=True)
            helper.stdin.write('brief')
            helper.stdin.close()
            deadline = time.monotonic() + 10
            while not marker.exists() or not marker.read_text().strip():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)
            child = int(marker.read_text())
            helper.terminate()
            self.assertEqual(helper.wait(timeout=15), 130)
            helper.stdout.close()
            helper.stderr.close()
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)

    def test_empty_brief_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            process = subprocess.run([sys.executable, str(SCRIPTS / 'sidekick.py'), 'send', '--transport', 'codex-cli', '--session', 's',
                                      '--model', 'm', '--effort', 'default', '--workdir', temp], input='  ', capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn('empty', process.stderr)


if __name__ == '__main__':
    unittest.main()
