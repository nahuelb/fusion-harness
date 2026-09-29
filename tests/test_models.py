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


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.path = root / 'config/fusion-harness/models.json'
        self.agents = root / 'claude/agents'
        self.agents.mkdir(parents=True)
        self.agent = self.agents / 'fusion-sidekick.md'
        environment = {k: v for k, v in os.environ.items() if k != 'FUSION_MODELS_FILE'}
        environment.update({'XDG_CONFIG_HOME': str(root / 'config'), 'CLAUDE_CONFIG_DIR': str(root / 'claude')})
        self.env = patch.dict(os.environ, environment, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def write_overrides(self, sidekicks):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({'version': 2, 'sidekicks': sidekicks}))

    def active(self, harness):
        selected = model_config.resolve(harness)
        return {k: selected[k] for k in model_config.FIELDS}

    def test_defaults_work_without_a_user_file(self):
        self.assertEqual(model_config.user_path(), self.path)
        selected = model_config.resolve('claude-code')
        self.assertEqual((selected['transport'], selected['model'], selected['reasoning_effort']), ('native', 'claude-sonnet-5-5', 'medium'))
        self.assertEqual(model_config.resolve('codex')['model'], 'gpt-6-sol')
        other = model_config.resolve('another-harness')
        self.assertEqual(other['profile'], 'default')
        self.assertIn(other['transport'], ('codex-cli', 'claude-cli'))
        self.assertFalse(self.path.exists())

    def test_set_saves_only_the_override_for_future_sessions(self):
        model_config.update('claude-code', model='claude-sonnet-5', effort='high')
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved, {'version': 2, 'sidekicks': {'claude-code': {'model': 'claude-sonnet-5', 'reasoning_effort': 'high'}}})
        selected = model_config.resolve('claude-code')
        self.assertEqual((selected['transport'], selected['model'], selected['reasoning_effort']), ('native', 'claude-sonnet-5', 'high'))

    def test_overrides_keep_later_default_changes_for_other_fields(self):
        self.write_overrides({'codex': {'reasoning_effort': 'high'}})
        defaults = json.loads(model_config.DEFAULTS.read_text())
        defaults['sidekicks']['codex']['model'] = 'gpt-7-sol'
        with patch.object(model_config, 'DEFAULTS', Path(self.temp.name) / 'defaults.json'):
            model_config.DEFAULTS.write_text(json.dumps(defaults))
            self.assertEqual(self.active('codex'), {'transport': 'native', 'model': 'gpt-7-sol', 'reasoning_effort': 'high'})

    def test_reset_returns_to_defaults(self):
        model_config.update('codex', effort='high')
        model_config.update('claude-code', effort='low')
        model_config.reset('codex')
        self.assertEqual(json.loads(self.path.read_text())['sidekicks'], {'claude-code': {'reasoning_effort': 'low'}})
        self.assertEqual(model_config.resolve('codex')['reasoning_effort'], 'medium')

    def test_new_profile_inherits_missing_fields_from_default(self):
        model_config.update('default', effort='low')
        model_config.update('pi', effort='high')
        self.assertEqual(json.loads(self.path.read_text())['sidekicks']['pi'], {'reasoning_effort': 'high'})
        selected = model_config.resolve('pi')
        self.assertEqual((selected['profile'], selected['transport'], selected['model'], selected['reasoning_effort']), ('pi', 'codex-cli', 'gpt-6-sol', 'high'))
        model_config.update('pi', transport='claude-cli', model='claude-sonnet-5-5')
        self.assertEqual(self.active('pi'), {'transport': 'claude-cli', 'model': 'claude-sonnet-5-5', 'reasoning_effort': 'high'})

    def test_no_active_sidekick_requests_spawn(self):
        self.assertEqual(model_config.resolve('codex')['action'], 'spawn')

    def test_unchanged_settings_reuse(self):
        active = self.active('codex')
        self.assertEqual(model_config.resolve('codex', active)['action'], 'reuse')

    def test_model_effort_or_transport_change_requires_replacement(self):
        for key, value in (('model', 'gpt-6-luna'), ('effort', 'high'), ('transport', 'codex-cli')):
            with self.subTest(key=key):
                model_config.reset('codex')
                active = self.active('codex')
                model_config.update('codex', **{key: value})
                self.assertEqual(model_config.resolve('codex', active)['action'], 'replace_after_handoff')

    def test_other_profile_changes_preserve_sidekick(self):
        active = self.active('codex')
        model_config.update('claude-code', model='claude-opus-5-5')
        self.assertEqual(model_config.resolve('codex', active)['action'], 'reuse')

    def test_null_effort_matches_default_effort(self):
        model_config.update('claude-code', effort='default')
        active = self.active('claude-code')
        self.assertIsNone(active['reasoning_effort'])
        self.assertEqual(model_config.resolve('claude-code', active)['action'], 'reuse')

    def test_invalid_user_file_does_not_fall_back(self):
        self.path.parent.mkdir(parents=True)
        for text in ('{bad', json.dumps({'version': 1, 'sidekicks': {}}), json.dumps({'version': 2, 'sidekicks': {'codex': {'extra': 1}}}),
                     json.dumps({'version': 2, 'sidekicks': {'codex': {'reasoning_effort': 'huge'}}})):
            with self.subTest(text=text):
                self.path.write_text(text)
                with self.assertRaises(ValueError):
                    model_config.resolve('codex')

    def test_default_profile_must_stay_cli(self):
        with self.assertRaises(ValueError):
            model_config.update('default', transport='native')
        self.assertFalse(self.path.exists())

    def test_claude_profiles_need_full_ids_and_claude_efforts(self):
        with self.assertRaisesRegex(ValueError, 'full Claude model ID'):
            model_config.update('claude-code', model='sonnet')
        with self.assertRaisesRegex(ValueError, 'for Claude'):
            model_config.update('claude-code', effort='minimal')
        with self.assertRaisesRegex(ValueError, 'full Claude model ID'):
            model_config.update('pi', transport='claude-cli', model='opus')
        self.assertFalse(self.path.exists())

    def test_hand_written_alias_blocks_only_its_profile(self):
        self.write_overrides({'claude-code': {'model': 'sonnet'}})
        self.assertEqual(model_config.resolve('codex')['profile'], 'codex')
        with self.assertRaisesRegex(ValueError, 'set --profile claude-code'):
            model_config.resolve('claude-code')
        model_config.update('claude-code', model='claude-sonnet-5-5')
        self.assertEqual(model_config.resolve('claude-code')['model'], 'claude-sonnet-5-5')

    def test_resolve_writes_claude_agent_and_requests_reload(self):
        first = model_config.resolve('claude-code')
        self.assertEqual((first['agent_type'], first['agent_file'], first['reload_required'], first['restart_required']),
                         ('fusion-sidekick', str(self.agent), True, False))
        text = self.agent.read_text()
        self.assertIn('model: claude-sonnet-5-5', text)
        self.assertIn('effort: medium', text)
        self.assertIn(str(model_config.SKILL_ROOT / 'references/sidekick.md'), text)
        self.assertFalse(model_config.resolve('claude-code')['reload_required'])

    def test_changed_claude_settings_rewrite_agent_and_request_reload(self):
        active = self.active('claude-code')
        model_config.update('claude-code', model='claude-opus-5-5', effort='default')
        selected = model_config.resolve('claude-code', active)
        self.assertEqual((selected['action'], selected['reload_required']), ('replace_after_handoff', True))
        self.assertIn('model: claude-opus-5-5', self.agent.read_text())
        self.assertNotIn('effort:', self.agent.read_text())

    def test_missing_agents_folder_requires_restart(self):
        self.agents.rmdir()
        selected = model_config.resolve('claude-code')
        self.assertTrue(selected['restart_required'])
        self.assertTrue(self.agent.exists())

    def test_user_owned_agent_file_is_never_replaced(self):
        self.agent.write_text('---\nname: fusion-sidekick\nmodel: claude-opus-5-5\n---\nMine.\n')
        selected = model_config.resolve('claude-code')
        self.assertIn('not generated', selected['error'])
        self.assertEqual(self.agent.read_text(), '---\nname: fusion-sidekick\nmodel: claude-opus-5-5\n---\nMine.\n')

    def test_cli_claude_profile_needs_no_agent_file(self):
        model_config.update('claude-code', transport='claude-cli')
        self.assertNotIn('agent_type', model_config.resolve('claude-code'))
        self.assertNotIn('agent_type', model_config.resolve('codex'))
        self.assertFalse(self.agent.exists())

    def test_printed_null_effort_is_accepted_as_active_effort(self):
        model_config.update('codex', effort='default')
        process = subprocess.run([sys.executable, str(SCRIPTS / 'model_config.py'), 'resolve', '--harness', 'codex',
                                  '--active-transport', 'native', '--active-model', 'gpt-6-sol', '--active-effort', 'null'],
                                 capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(process.stdout)['action'], 'reuse')

    def test_partial_active_arguments_are_rejected(self):
        process = subprocess.run([sys.executable, str(SCRIPTS / 'model_config.py'), 'resolve', '--harness', 'codex', '--active-model', 'x'],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn('--active-transport', process.stderr)


if __name__ == '__main__':
    unittest.main()
