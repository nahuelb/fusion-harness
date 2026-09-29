import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/fusion/scripts'
sys.path.insert(0, str(SCRIPTS))
import token_usage as usage


def response(ident, output=10, thinking=2, model='claude-opus-5-5', sidechain=False):
    details = {} if thinking is None else {'output_tokens_details': {'thinking_tokens': thinking}}
    return {'type': 'assistant', 'isSidechain': sidechain, 'message': {'id': ident, 'model': model, 'usage': {
        'input_tokens': 5, 'cache_creation_input_tokens': 100, 'cache_read_input_tokens': 1000, 'output_tokens': output, **details}}}


class ClaudeUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'claude'
        self.codex = Path(self.temp.name) / 'codex'
        self.project = self.home / 'projects/-work-repo'
        self.project.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def transcript(self, session, rows, project=None):
        path = (project or self.project) / f'{session}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(json.dumps(row) for row in [{'type': 'user', 'message': {'content': 'hi'}}, *rows]) + '\n')
        return path

    def subagent(self, session, ident, agent_type, rows):
        folder = self.project / session / 'subagents'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'agent-{ident}.jsonl').write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        (folder / f'agent-{ident}.meta.json').write_text(json.dumps({'agentType': agent_type}))

    def test_streamed_repeats_count_once_with_final_usage(self):
        path = self.transcript('s1', [response('m1', output=3), response('m1', output=40), response('m2', output=10), {'type': 'assistant', 'message': {'id': 'x'}}])
        row = usage.analyze_claude(path, 'lead')
        self.assertEqual(row['responses'], 2)
        self.assertEqual(row['tokens'], {'input_tokens': 2210, 'cached_input_tokens': 2000, 'output_tokens': 50, 'reasoning_output_tokens': 4,
                                         'total_tokens': 2260, 'cache_creation_input_tokens': 200})
        self.assertEqual(row['models'], ['claude-opus-5-5'])

    def test_missing_thinking_and_empty_usage_are_reported(self):
        row = usage.analyze_claude(self.transcript('s1', [response('m1', thinking=None)]), 'lead')
        self.assertIn('thinking tokens', row['warnings'][0])
        empty = usage.analyze_claude(self.transcript('s2', []), 'lead')
        self.assertIsNone(empty['tokens'])

    def test_session_report_classifies_fusion_sidekick_and_other_subagents(self):
        self.transcript('s1', [response('m1')])
        self.subagent('s1', 'a1', 'fusion-sidekick', [response('k1', model='claude-sonnet-5-5', sidechain=True)])
        self.subagent('s1', 'a2', 'Explore', [response('e1', model='claude-haiku-4-5', sidechain=True)])
        result = usage.claude_session_report('s1', self.home)
        roles = {row['thread_id']: row['role'] for row in result['threads']}
        self.assertEqual(roles, {'s1': 'lead', 'a1': 'sidekick', 'a2': 'unclassified_subagent'})
        self.assertEqual(result['by_role']['sidekick']['tokens']['total_tokens'], 1115)
        self.assertEqual(result['total']['total_tokens'], 3 * 1115)
        self.assertEqual(result['harness'], 'claude-code')

    def test_explicit_sidekick_id_must_be_a_discovered_subagent(self):
        self.transcript('s1', [response('m1')])
        self.subagent('s1', 'a2', 'general-purpose', [response('e1')])
        result = usage.claude_session_report('s1', self.home, ['a2'])
        self.assertEqual(result['threads'][1]['role'], 'sidekick')
        with self.assertRaises(ValueError):
            usage.claude_session_report('s1', self.home, ['other'])

    def test_missing_or_ambiguous_session_fails(self):
        with self.assertRaises(ValueError):
            usage.claude_session_report('nope', self.home)
        self.transcript('s1', [response('m1')])
        self.transcript('s1', [response('m1')], self.home / 'projects/-other')
        with self.assertRaises(ValueError):
            usage.claude_session_report('s1', self.home)

    def test_embedded_sidechain_lines_are_flagged(self):
        row = usage.analyze_claude(self.transcript('s1', [response('m1', sidechain=True)]), 'lead')
        self.assertTrue(any('embedded' in warning for warning in row['warnings']))

    def test_cli_sidekicks_from_claude_and_codex_join_the_report(self):
        self.transcript('lead', [response('m1')])
        self.transcript('claude-cli', [response('c1', model='claude-sonnet-5-5')], self.home / 'projects/-scratch')
        rollout = self.codex / 'sessions/day/codex-cli.jsonl'
        rollout.parent.mkdir(parents=True)
        counts = dict(zip(usage.KEYS, (500, 400, 20, 5, 520)))
        rollout.write_text('\n'.join(json.dumps(row) for row in [{'type': 'session_meta', 'payload': {'id': 'codex-cli', 'source': 'exec'}},
                                                                   {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': counts}}}]))
        result = usage.with_cli_sidekicks(usage.claude_session_report('lead', self.home), ['claude-cli', 'codex-cli'], self.home, self.codex)
        self.assertEqual(result['by_role']['sidekick']['threads'], 2)
        self.assertEqual(result['total']['total_tokens'], 1115 * 2 + 520)
        self.assertNotIn('cache_creation_input_tokens', result['total'])
        self.assertEqual(result['session_id'], 'lead')
        with self.assertRaises(ValueError):
            usage.with_cli_sidekicks(usage.claude_session_report('lead', self.home), ['missing'], self.home, self.codex)
        with self.assertRaises(ValueError):
            usage.with_cli_sidekicks(usage.claude_session_report('lead', self.home), ['lead'], self.home, self.codex)

    def test_command_defaults_to_the_current_claude_session(self):
        self.transcript('current', [response('m1')])
        environment = {k: v for k, v in os.environ.items() if k != 'CODEX_THREAD_ID'}
        environment.update({'CLAUDE_CODE_SESSION_ID': 'current', 'CLAUDE_CONFIG_DIR': str(self.home)})
        process = subprocess.run([sys.executable, str(SCRIPTS / 'token_usage.py')], env=environment, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(process.stdout)['session_id'], 'current')
        environment['CODEX_THREAD_ID'] = 'codex-thread'
        process = subprocess.run([sys.executable, str(SCRIPTS / 'token_usage.py')], env=environment, capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn('--claude-session', process.stderr)


if __name__ == '__main__':
    unittest.main()
