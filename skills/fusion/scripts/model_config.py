#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


DEFAULTS = Path(__file__).resolve().parents[1] / 'config/models.default.json'
EFFORTS = {'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'}
TRANSPORTS = {'native', 'codex-cli', 'claude-cli'}
FALLBACK_PROFILE = 'default'
DEFAULT_EFFORT_NAMES = {'default', 'null'}


def effort_argument(value):
    return None if value in DEFAULT_EFFORT_NAMES else value


def live_path():
    explicit = os.environ.get('FUSION_MODELS_FILE')
    if explicit:
        return Path(explicit).expanduser()
    config_home = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config').expanduser()
    return config_home / 'fusion-harness/models.json'


def legacy_path():
    codex_home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').expanduser()
    return codex_home / 'plugins/fusion/models.json'


def validate(data):
    if not isinstance(data, dict) or set(data) != {'version', 'sidekicks'} or type(data['version']) is not int or data['version'] != 2:
        raise ValueError('Expected version 2 and exactly the version and sidekicks keys.')
    profiles = data['sidekicks']
    if not isinstance(profiles, dict) or FALLBACK_PROFILE not in profiles:
        raise ValueError(f'sidekicks must be an object with a "{FALLBACK_PROFILE}" profile.')
    for name, settings in profiles.items():
        if not name or name != name.strip() or any(c.isspace() for c in name):
            raise ValueError('Profile names must be nonempty and contain no whitespace.')
        if not isinstance(settings, dict) or set(settings) != {'transport', 'model', 'reasoning_effort'}:
            raise ValueError(f'sidekicks.{name} must contain exactly transport, model, and reasoning_effort.')
        if settings['transport'] not in TRANSPORTS:
            raise ValueError(f'sidekicks.{name}.transport must be one of {sorted(TRANSPORTS)}.')
        model = settings['model']
        if not isinstance(model, str) or not model or any(c.isspace() for c in model):
            raise ValueError(f'sidekicks.{name}.model must be a nonempty model identifier without whitespace.')
        effort = settings['reasoning_effort']
        if effort is not None and effort not in EFFORTS:
            raise ValueError(f'sidekicks.{name}.reasoning_effort must be null or one of {sorted(EFFORTS)}.')
    if profiles[FALLBACK_PROFILE]['transport'] == 'native':
        raise ValueError(f'The "{FALLBACK_PROFILE}" profile must use a CLI transport so it works in any harness.')
    return data


def read():
    path = live_path()
    try:
        data = validate(json.loads(path.read_text()))
    except FileNotFoundError as exc:
        raise ValueError(f'No model file at {path}. Run model_config.py init.') from exc
    revision = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
    return {'path': str(path.resolve()), 'revision': revision, 'models': data}


def settings_of(item):
    return (item['transport'], item['model'], item['reasoning_effort'])


def resolve_loaded(loaded, harness, active=None):
    profiles = loaded['models']['sidekicks']
    profile = harness if harness in profiles else FALLBACK_PROFILE
    selected = dict(profiles[profile])
    action = 'spawn' if active is None else 'reuse' if settings_of(active) == settings_of(selected) else 'replace_after_handoff'
    return {'path': loaded['path'], 'revision': loaded['revision'], 'harness': harness, 'profile': profile, 'action': action, **selected}


def resolve(harness, active=None):
    return resolve_loaded(read(), harness, active)


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, suffix='.tmp') as output:
        output.write(json.dumps(data, indent=2) + '\n')
    os.replace(output.name, path)


def imported_defaults():
    defaults = validate(json.loads(DEFAULTS.read_text()))
    source = legacy_path()
    if os.environ.get('FUSION_MODELS_FILE') or not source.is_file():
        return defaults, None
    try:
        legacy = json.loads(source.read_text())
        sidekick = legacy['sidekick']
        candidate = json.loads(json.dumps(defaults))
        candidate['sidekicks']['codex'] = {'transport': 'native', 'model': sidekick['model'], 'reasoning_effort': sidekick['reasoning_effort']}
        return validate(candidate), str(source)
    except (OSError, ValueError, KeyError, TypeError):
        return defaults, None


def initialize():
    path = live_path()
    if path.exists():
        return {**read(), 'created': False}
    data, source = imported_defaults()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x') as output:
            output.write(json.dumps(data, indent=2) + '\n')
    except FileExistsError:
        return {**read(), 'created': False}
    result = {**read(), 'created': True}
    if source:
        result['imported_from'] = source
    return result


def update(profile, transport=None, model=None, effort=None):
    loaded = read()
    data = json.loads(json.dumps(loaded['models']))
    current = data['sidekicks'].get(profile)
    if current is None and not (transport and model):
        raise ValueError(f'New profile {profile} needs --transport and --model.')
    candidate = dict(current or {'reasoning_effort': None})
    if transport:
        candidate['transport'] = transport
    if model:
        candidate['model'] = model
    if effort:
        candidate['reasoning_effort'] = effort_argument(effort)
    data['sidekicks'][profile] = candidate
    write_atomic(Path(loaded['path']), validate(data))
    return read()


def main():
    parser = argparse.ArgumentParser(description='Read and update live Fusion sidekick settings.')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    commands.add_parser('show')
    sub = commands.add_parser('resolve')
    sub.add_argument('--harness', required=True)
    sub.add_argument('--active-transport', choices=sorted(TRANSPORTS))
    sub.add_argument('--active-model')
    sub.add_argument('--active-effort', help='Use "default" or "null" when the active sidekick has no explicit effort.')
    sub = commands.add_parser('set')
    sub.add_argument('--profile', required=True)
    sub.add_argument('--transport', choices=sorted(TRANSPORTS))
    sub.add_argument('--model')
    sub.add_argument('--effort', choices=sorted(EFFORTS | DEFAULT_EFFORT_NAMES))
    args = parser.parse_args()
    try:
        if args.command == 'init':
            result = initialize()
        elif args.command == 'show':
            result = read()
        elif args.command == 'set':
            result = update(args.profile, args.transport, args.model, args.effort)
        else:
            given = [args.active_transport, args.active_model, args.active_effort]
            if any(given) and not all(given):
                raise ValueError('Pass all of --active-transport, --active-model, and --active-effort, or none.')
            active = None
            if all(given):
                active = {'transport': args.active_transport, 'model': args.active_model, 'reasoning_effort': effort_argument(args.active_effort)}
            result = resolve(args.harness, active)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Fusion model configuration: {exc}\n')


if __name__ == '__main__':
    main()
