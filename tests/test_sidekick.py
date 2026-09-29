import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/fusion/scripts'
sys.path.insert(0, str(SCRIPTS))
import sidekick


CODEX = {'transport': 'codex-cli', 'model': 'gpt-6-sol', 'reasoning_effort': 'medium'}
CLAUDE = {'transport': 'claude-cli', 'model': 'sonnet', 'reasoning_effort': None}


def completed(command, stdout='', returncode=0, stderr=''):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class CodexTransportTests(unittest.TestCase):
    def fake_codex(self, command, **kwargs):
        self.calls.append((command, kwargs))
        Path(command[command.index('-o') + 1]).write_text('Report text\n')
        events = [{'type': 'thread.started', 'thread_id': 'thread-1'}, {'type': 'turn.completed'}]
        return completed(command, '\n'.join(map(json.dumps, events)))

    def setUp(self):
        self.calls = []

    def test_start_sets_model_effort_sandbox_and_captures_session(self):
        with patch.object(sidekick.subprocess, 'run', side_effect=self.fake_codex):
            result = sidekick.run(CODEX, 'brief', '/work')
        command, kwargs = self.calls[0]
        self.assertEqual(command[:3], ['codex', 'exec', '--json'])
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertEqual(command[command.index('-s') + 1], 'workspace-write')
        self.assertEqual(command[command.index('-C') + 1], '/work')
        self.assertEqual(kwargs['input'], 'brief')
        self.assertEqual((result['session'], result['report'], result['exit_code']), ('thread-1', 'Report text', 0))
        self.assertNotIn('error', result)

    def test_send_resumes_the_recorded_session(self):
        with patch.object(sidekick.subprocess, 'run', side_effect=self.fake_codex):
            result = sidekick.run(CODEX, 'next brief', '/work', 'thread-1')
        command, kwargs = self.calls[0]
        self.assertEqual(command[:4], ['codex', 'exec', 'resume', 'thread-1'])
        self.assertEqual(kwargs['cwd'], '/work')
        self.assertEqual(result['session'], 'thread-1')

    def test_missing_session_is_an_error(self):
        with patch.object(sidekick.subprocess, 'run', return_value=completed([], '')):
            result = sidekick.run(CODEX, 'brief', '/work')
        self.assertIn('session', result['error'])

    def test_failure_reports_stderr(self):
        with patch.object(sidekick.subprocess, 'run', return_value=completed([], '', 2, 'model not available')):
            result = sidekick.run(CODEX, 'brief', '/work', 'thread-1')
        self.assertEqual(result['exit_code'], 2)
        self.assertIn('model not available', result['error'])


class ClaudeTransportTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def fake_claude(self, command, **kwargs):
        self.calls.append((command, kwargs))
        session = command[command.index('--resume') + 1] if '--resume' in command else command[command.index('--session-id') + 1]
        return completed(command, json.dumps({'type': 'result', 'is_error': False, 'result': 'Done', 'session_id': session}))

    def test_start_uses_new_session_and_accept_edits_without_bypass(self):
        with patch.dict(os.environ, {'CLAUDECODE': '1'}), patch.object(sidekick.subprocess, 'run', side_effect=self.fake_claude):
            result = sidekick.run(CLAUDE, 'brief', '/work')
        command, kwargs = self.calls[0]
        self.assertIn('--session-id', command)
        self.assertEqual(command[command.index('--permission-mode') + 1], 'acceptEdits')
        self.assertNotIn('--effort', command)
        self.assertFalse(any('dangerously' in part or 'bypass' in part for part in command))
        self.assertNotIn('CLAUDECODE', kwargs['env'])
        self.assertEqual(result['report'], 'Done')
        self.assertEqual(result['session'], command[command.index('--session-id') + 1])

    def test_send_resumes_with_recorded_effort(self):
        settings = {**CLAUDE, 'reasoning_effort': 'high'}
        with patch.object(sidekick.subprocess, 'run', side_effect=self.fake_claude):
            result = sidekick.run(settings, 'brief', '/work', 'session-1')
        command, _ = self.calls[0]
        self.assertEqual(command[command.index('--resume') + 1], 'session-1')
        self.assertEqual(command[command.index('--effort') + 1], 'high')
        self.assertEqual(result['session'], 'session-1')

    def test_cli_error_result_is_reported(self):
        payload = json.dumps({'is_error': True, 'result': 'Permission denied', 'session_id': 's'})
        with patch.object(sidekick.subprocess, 'run', return_value=completed([], payload, 1)):
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

    def test_empty_brief_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            process = subprocess.run([sys.executable, str(SCRIPTS / 'sidekick.py'), 'send', '--transport', 'codex-cli', '--session', 's',
                                      '--model', 'm', '--effort', 'default', '--workdir', temp], input='  ', capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn('empty', process.stderr)


if __name__ == '__main__':
    unittest.main()
