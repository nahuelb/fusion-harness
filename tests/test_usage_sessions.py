import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/fusion/scripts'))
import token_usage as usage


class SessionUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def rollout(self, ident, parent=None, role='default', archive=False, folder='day', count=100, native=True):
        directory = self.home / ('archived_sessions' if archive else 'sessions') / folder
        directory.mkdir(parents=True, exist_ok=True)
        meta = {'id': ident, 'session_id': parent or ident, 'parent_thread_id': parent, 'source': 'cli'}
        if parent and native:
            meta['source'] = {'subagent': {'thread_spawn': {'parent_thread_id': parent, 'agent_role': role}}}
        rows = [{'type': 'session_meta', 'payload': meta}]
        if count is not None:
            rows.append({'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': dict(zip(usage.KEYS, (count, count // 2, 10, 2, count + 10)))}}})
        path = directory / f'{ident}.jsonl'
        path.write_text('\n'.join(map(json.dumps, rows)))
        return path

    def test_exact_identity_no_prefix_or_latest_fallback(self):
        self.rollout('root-123')
        with self.assertRaises(ValueError):
            usage.session_report('root', self.home)
        with self.assertRaises(ValueError):
            usage.session_report(None, self.home)

    def test_ancestry_includes_archived_replacements_and_nested_agents(self):
        self.rollout('root')
        self.rollout('first', 'root', role='fusion-sidekick', archive=True)
        self.rollout('second', 'root')
        self.rollout('nested', 'second')
        self.rollout('unrelated')
        result = usage.session_report('root', self.home)
        self.assertEqual({r['thread_id'] for r in result['threads']}, {'root', 'first', 'second', 'nested'})
        self.assertEqual(result['by_role']['sidekick']['threads'], 1)
        self.assertEqual(result['by_role']['unclassified_subagent']['threads'], 2)
        self.assertEqual(result['total']['input_tokens'], 400)

    def test_shared_group_id_and_user_fork_do_not_imply_subagent(self):
        self.rollout('root')
        self.rollout('fork', 'root', native=False)
        result = usage.session_report('root', self.home)
        self.assertEqual(len(result['threads']), 1)

    def test_explicit_sidekick_attribution(self):
        self.rollout('root')
        self.rollout('worker', 'root')
        result = usage.session_report('root', self.home, ['worker'])
        self.assertEqual(result['by_role']['sidekick']['tokens']['input_tokens'], 100)
        with self.assertRaises(ValueError):
            usage.session_report('root', self.home, ['other'])
        with self.assertRaises(ValueError):
            usage.session_report('root', self.home, ['root'])

    def test_selecting_subagent_does_not_include_caller_or_siblings(self):
        self.rollout('root')
        self.rollout('a', 'root')
        self.rollout('b', 'root')
        result = usage.session_report('a', self.home)
        self.assertEqual([r['thread_id'] for r in result['threads']], ['a'])

    def test_duplicate_selected_identity_fails_instead_of_double_counting(self):
        self.rollout('root')
        self.rollout('root', archive=True)
        with self.assertRaises(ValueError):
            usage.session_report('root', self.home)

    def test_unknown_group_does_not_hide_known_lead(self):
        self.rollout('root')
        self.rollout('worker', 'root', count=None)
        result = usage.session_report('root', self.home)
        self.assertIsNone(result['total'])
        self.assertEqual(result['by_role']['lead']['tokens']['input_tokens'], 100)
        self.assertIsNone(result['by_role']['unclassified_subagent']['tokens'])

    def test_metadata_identity_over_filename(self):
        path = self.rollout('real')
        path.rename(path.with_name('wrong-id.jsonl'))
        self.assertEqual(usage.session_report('real', self.home)['session_id'], 'real')
        with self.assertRaises(ValueError):
            usage.session_report('wrong-id', self.home)


class RolloutUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'rollout.jsonl'

    def tearDown(self):
        self.temp.cleanup()

    def write_counts(self, counts):
        lines = []
        for n in counts:
            tokens = dict(zip(usage.KEYS, (n, n // 2, n // 10, 0, n + n // 10)))
            lines.append(json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': tokens}}}))
        self.path.write_text('\n'.join(lines))

    def test_cumulative_snapshots_are_not_summed(self):
        self.write_counts([100, 200, 200])
        result = usage.report(self.path, [])
        self.assertEqual(result['total']['input_tokens'], 200)
        self.assertEqual(result['total']['total_tokens'], 220)

    def test_unknown_usage_stays_unknown(self):
        self.path.write_text('{bad\n{}\n')
        result = usage.report(self.path, [])
        self.assertIsNone(result['total'])
        self.assertEqual(len(result['threads'][0]['warnings']), 2)

    def test_duplicate_rollout_is_rejected(self):
        self.write_counts([100])
        with self.assertRaises(ValueError):
            usage.report(self.path, [self.path])

    def test_reset_is_reported(self):
        self.write_counts([200, 100])
        self.assertIn('decreased', usage.analyze(self.path, 'lead')['warnings'][0])


if __name__ == '__main__':
    unittest.main()
