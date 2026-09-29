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
import model_config


LEGACY = {
    'version': 1,
    'lead': {'use_current_model': True, 'model': 'gpt-6-astra', 'reasoning_effort': 'medium'},
    'sidekick': {'model': 'gpt-6-luna', 'reasoning_effort': 'high'},
}


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'models.json'
        self.agent = Path(self.temp.name) / 'claude/agents/fusion-sidekick.md'
        self.env = patch.dict(os.environ, {'FUSION_MODELS_FILE': str(self.path), 'CLAUDE_CONFIG_DIR': str(Path(self.temp.name) / 'claude')})
        self.env.start()
        self.assertTrue(model_config.initialize()['created'])

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def edit(self, profile, key, value):
        data = json.loads(self.path.read_text())
        data['sidekicks'][profile][key] = value
        self.path.write_text(json.dumps(data))

    def active(self, harness):
        selected = model_config.resolve(harness)
        return {k: selected[k] for k in ('transport', 'model', 'reasoning_effort')}

    def test_known_harness_uses_its_profile_and_unknown_uses_default(self):
        self.assertEqual(model_config.resolve('claude-code')['profile'], 'claude-code')
        self.assertEqual(model_config.resolve('claude-code')['transport'], 'native')
        other = model_config.resolve('another-harness')
        self.assertEqual(other['profile'], 'default')
        self.assertIn(other['transport'], ('codex-cli', 'claude-cli'))

    def test_no_active_sidekick_requests_spawn(self):
        self.assertEqual(model_config.resolve('codex')['action'], 'spawn')

    def test_unchanged_settings_reuse(self):
        active = self.active('codex')
        self.assertEqual(model_config.resolve('codex', active)['action'], 'reuse')

    def test_model_effort_or_transport_change_requires_replacement(self):
        for key, value in (('model', 'gpt-6-luna'), ('reasoning_effort', 'high'), ('transport', 'codex-cli')):
            with self.subTest(key=key):
                self.path.write_text(model_config.DEFAULTS.read_text())
                active = self.active('codex')
                self.edit('codex', key, value)
                self.assertEqual(model_config.resolve('codex', active)['action'], 'replace_after_handoff')

    def test_other_profile_and_formatting_changes_preserve_sidekick(self):
        active = self.active('codex')
        revision = model_config.read()['revision']
        self.edit('claude-code', 'model', 'claude-opus-5-5')
        self.assertEqual(model_config.resolve('codex', active)['action'], 'reuse')
        self.path.write_text(json.dumps(json.loads(self.path.read_text()), indent=8))
        self.assertNotEqual(model_config.read()['revision'], revision)
        self.assertEqual(model_config.resolve('codex', active)['action'], 'reuse')

    def test_null_effort_matches_default_effort(self):
        self.edit('claude-code', 'reasoning_effort', None)
        active = self.active('claude-code')
        self.assertIsNone(active['reasoning_effort'])
        self.assertEqual(model_config.resolve('claude-code', active)['action'], 'reuse')

    def test_invalid_file_does_not_fall_back(self):
        self.path.write_text('{bad')
        with self.assertRaises(ValueError):
            model_config.resolve('codex')

    def test_missing_file_requires_init(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, 'init'):
            model_config.read()

    def test_schema_rejects_invalid_shapes(self):
        base = json.loads(self.path.read_text())
        cases = [
            LEGACY,
            {**base, 'extra': True},
            {'version': 2, 'sidekicks': {'codex': base['sidekicks']['codex']}},
            {'version': 2, 'sidekicks': {**base['sidekicks'], 'default': {'transport': 'native', 'model': 'x', 'reasoning_effort': None}}},
            {'version': 2, 'sidekicks': {**base['sidekicks'], 'codex': {'transport': 'native', 'model': 'x', 'reasoning_effort': 'huge'}}},
            {'version': 2, 'sidekicks': {**base['sidekicks'], 'codex': {'transport': 'telepathy', 'model': 'x', 'reasoning_effort': None}}},
            {'version': 2, 'sidekicks': {**base['sidekicks'], 'codex': {'transport': 'native', 'model': 'two words', 'reasoning_effort': None}}},
            {'version': 2, 'sidekicks': {**base['sidekicks'], 'codex': {'transport': 'native', 'model': 'x'}}},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                model_config.validate(case)

    def test_initializer_preserves_user_values(self):
        self.edit('codex', 'model', 'custom-model')
        result = model_config.initialize()
        self.assertFalse(result['created'])
        self.assertEqual(result['models']['sidekicks']['codex']['model'], 'custom-model')

    def test_update_changes_only_requested_fields(self):
        before = json.loads(self.path.read_text())
        model_config.update('codex', model='gpt-6-luna', effort='default')
        after = json.loads(self.path.read_text())
        self.assertEqual(after['sidekicks']['codex'], {'transport': 'native', 'model': 'gpt-6-luna', 'reasoning_effort': None})
        self.assertEqual(after['sidekicks']['claude-code'], before['sidekicks']['claude-code'])

    def test_update_rejects_invalid_candidate_without_writing(self):
        before = self.path.read_text()
        with self.assertRaises(ValueError):
            model_config.update('default', transport='native')
        with self.assertRaises(ValueError):
            model_config.update('new-harness', model='only-model')
        self.assertEqual(self.path.read_text(), before)

    def test_update_adds_profile(self):
        model_config.update('pi', transport='claude-cli', model='claude-sonnet-5-5', effort='high')
        self.assertEqual(model_config.resolve('pi')['profile'], 'pi')

    def test_printed_null_effort_is_accepted_as_active_effort(self):
        self.edit('claude-code', 'reasoning_effort', None)
        process = subprocess.run([sys.executable, str(SCRIPTS / 'model_config.py'), 'resolve', '--harness', 'claude-code',
                                  '--active-transport', 'native', '--active-model', 'claude-sonnet-5-5', '--active-effort', 'null'],
                                 capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(process.stdout)['action'], 'reuse')

    def test_init_writes_pinned_claude_agent(self):
        text = self.agent.read_text()
        self.assertIn('name: fusion-sidekick', text)
        self.assertIn('model: claude-sonnet-5-5', text)
        self.assertIn('effort: medium', text)
        self.assertIn(str(model_config.SKILL_ROOT / 'references/sidekick.md'), text)
        selected = model_config.resolve('claude-code')
        self.assertEqual((selected['agent_type'], selected['agent_file'], selected['agent_file_current']), ('fusion-sidekick', str(self.agent), True))

    def test_hand_edit_marks_agent_stale_until_sync(self):
        self.edit('claude-code', 'reasoning_effort', 'high')
        self.assertFalse(model_config.resolve('claude-code')['agent_file_current'])
        self.assertTrue(model_config.with_claude_agent(model_config.read())['claude_agent']['agent_file_written'])
        self.assertIn('effort: high', self.agent.read_text())
        self.assertTrue(model_config.resolve('claude-code')['agent_file_current'])

    def test_set_rewrites_agent_and_null_effort_omits_it(self):
        model_config.update('claude-code', model='claude-opus-5-5', effort='default')
        text = self.agent.read_text()
        self.assertIn('model: claude-opus-5-5', text)
        self.assertNotIn('effort:', text)

    def test_cli_claude_profile_needs_no_agent_file(self):
        self.agent.unlink()
        model_config.update('claude-code', transport='claude-cli')
        self.assertFalse(self.agent.exists())
        self.assertNotIn('agent_type', model_config.resolve('claude-code'))
        self.assertNotIn('agent_type', model_config.resolve('codex'))

    def test_claude_profiles_need_full_ids_and_claude_efforts(self):
        with self.assertRaisesRegex(ValueError, 'full Claude model ID'):
            model_config.update('claude-code', model='sonnet')
        with self.assertRaisesRegex(ValueError, 'for Claude'):
            model_config.update('claude-code', effort='minimal')
        with self.assertRaisesRegex(ValueError, 'full Claude model ID'):
            model_config.update('pi', transport='claude-cli', model='opus')

    def test_old_alias_file_still_loads_and_can_be_repaired(self):
        self.edit('claude-code', 'model', 'sonnet')
        self.edit('claude-code', 'reasoning_effort', None)
        self.assertEqual(model_config.resolve('codex')['profile'], 'codex')
        with self.assertRaisesRegex(ValueError, 'set --profile claude-code'):
            model_config.resolve('claude-code')
        self.assertIn('error', model_config.with_claude_agent(model_config.read())['claude_agent'])
        model_config.update('claude-code', model='claude-sonnet-5-5', effort='medium')
        self.assertTrue(model_config.resolve('claude-code')['agent_file_current'])

    def test_native_claude_change_requires_new_session(self):
        active = self.active('claude-code')
        model_config.update('claude-code', effort='high')
        self.assertEqual(model_config.resolve('claude-code', active)['action'], 'restart_session')
        model_config.update('claude-code', transport='claude-cli')
        self.assertEqual(model_config.resolve('claude-code', active)['action'], 'replace_after_handoff')

    def test_partial_active_arguments_are_rejected(self):
        process = subprocess.run([sys.executable, str(SCRIPTS / 'model_config.py'), 'resolve', '--harness', 'codex', '--active-model', 'x'],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn('--active-transport', process.stderr)


class LegacyImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.legacy = root / 'codex/plugins/fusion/models.json'
        self.legacy.parent.mkdir(parents=True)
        self.target = root / 'config/fusion-harness/models.json'
        environment = {k: v for k, v in os.environ.items() if k != 'FUSION_MODELS_FILE'}
        environment.update({'CODEX_HOME': str(root / 'codex'), 'XDG_CONFIG_HOME': str(root / 'config'), 'CLAUDE_CONFIG_DIR': str(root / 'claude')})
        self.env = patch.dict(os.environ, environment, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_default_path_follows_xdg_config_home(self):
        self.assertEqual(model_config.live_path(), self.target)

    def test_legacy_sidekick_becomes_codex_profile(self):
        self.legacy.write_text(json.dumps(LEGACY))
        result = model_config.initialize()
        self.assertEqual(result['imported_from'], str(self.legacy))
        self.assertEqual(result['models']['sidekicks']['codex'], {'transport': 'native', 'model': 'gpt-6-luna', 'reasoning_effort': 'high'})
        self.assertEqual(json.loads(self.legacy.read_text()), LEGACY)

    def test_invalid_legacy_file_uses_defaults(self):
        self.legacy.write_text('{bad')
        result = model_config.initialize()
        self.assertNotIn('imported_from', result)
        self.assertTrue(result['created'])

    def test_existing_file_is_never_replaced_by_import(self):
        self.legacy.write_text(json.dumps(LEGACY))
        self.target.parent.mkdir(parents=True)
        defaults = json.loads(model_config.DEFAULTS.read_text())
        self.target.write_text(json.dumps(defaults))
        result = model_config.initialize()
        self.assertFalse(result['created'])
        self.assertEqual(result['models'], defaults)


if __name__ == '__main__':
    unittest.main()
