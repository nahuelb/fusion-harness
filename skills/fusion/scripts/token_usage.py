#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


KEYS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'total_tokens')


def analyze(path, role):
    totals = None
    models = set()
    warnings = []
    with path.open() as source:
        for number, line in enumerate(source, 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f'Ignored malformed line {number}')
                continue
            if not isinstance(item, dict):
                continue
            payload = item.get('payload') or {}
            if not isinstance(payload, dict):
                continue
            if item.get('type') == 'turn_context' and payload.get('model'):
                models.add(payload['model'])
            if item.get('type') != 'event_msg' or payload.get('type') != 'token_count':
                continue
            info = payload.get('info') or {}
            usage = info.get('total_token_usage') if isinstance(info, dict) else None
            if isinstance(usage, dict) and all(isinstance(usage.get(k), int) and usage[k] >= 0 for k in KEYS):
                if totals and usage['total_tokens'] < totals['total_tokens']:
                    warnings.append('Cumulative counter decreased; final snapshot may undercount this rollout')
                totals = {k: usage[k] for k in KEYS}
    if totals is None:
        warnings.append('No complete cumulative token snapshot; usage is unknown')
    return {'role': role, 'path': str(path.resolve()), 'models': sorted(models), 'tokens': totals, 'warnings': warnings}


def summarize(rows):
    known = all(row['tokens'] is not None for row in rows)
    return {k: sum(row['tokens'][k] for row in rows) for k in KEYS} if known else None


def build_report(rows):
    groups = {}
    for role in dict.fromkeys(row['role'] for row in rows):
        members = [row for row in rows if row['role'] == role]
        groups[role] = {'threads': len(members), 'tokens': summarize(members)}
    return {'threads': rows, 'by_role': groups, 'total': summarize(rows),
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Full supplied rollouts, not an activation interval',
            'limitations': 'Final cumulative snapshots; no price or plan-quota inference. Models are observed, not cost attribution. Reasoning is a subset of output; cached input is a subset of input. Active sessions may not yet include their current response.'}


def report(lead, sidekicks):
    paths = [lead, *sidekicks]
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError('Each rollout must be listed once.')
    return build_report([analyze(lead, 'lead'), *(analyze(path, 'sidekick') for path in sidekicks)])


def metadata(path):
    try:
        with path.open() as source:
            item = json.loads(source.readline(1024 * 1024))
    except (OSError, ValueError):
        return None
    if not isinstance(item, dict) or item.get('type') != 'session_meta':
        return None
    data = item.get('payload')
    return data if isinstance(data, dict) and isinstance(data.get('id'), str) else None


def spawn_metadata(meta):
    source = meta.get('source')
    sub = source.get('subagent') if isinstance(source, dict) else None
    spawn = sub.get('thread_spawn') if isinstance(sub, dict) else None
    return spawn if isinstance(spawn, dict) else {}


def session_report(session, codex_home, sidekick_ids=()):
    if not session:
        raise ValueError('No current session ID. Supply --session with an exact thread ID.')
    entries = {}
    for folder in ('sessions', 'archived_sessions'):
        for path in sorted((codex_home / folder).rglob('*.jsonl')):
            meta = metadata(path)
            if meta is not None:
                entries.setdefault(meta['id'], []).append((path, meta))
    if session not in entries:
        raise ValueError(f'No local rollout for exact session {session}. Ephemeral, remote, or unavailable logs cannot be measured here.')
    selected = {session}
    while True:
        related = set()
        for ident, candidates in entries.items():
            for _, meta in candidates:
                spawn = spawn_metadata(meta)
                parent = spawn.get('parent_thread_id')
                if isinstance(parent, str) and parent in selected and meta.get('parent_thread_id', parent) == parent:
                    related.add(ident)
        new = related - selected
        if not new:
            break
        selected.update(new)
    requested = set(sidekick_ids)
    if not requested <= selected - {session}:
        raise ValueError('Each --sidekick-id must identify a discovered subagent of the selected session.')
    rows = []
    for ident in [session, *sorted(selected - {session})]:
        candidates = entries[ident]
        if len(candidates) != 1:
            raise ValueError(f'Multiple rollouts for {ident}; use explicit --lead/--sidekick paths to select one copy.')
        path, meta = candidates[0]
        spawn = spawn_metadata(meta)
        role = 'lead' if ident == session else 'sidekick' if ident in requested or spawn.get('agent_role') == 'fusion-sidekick' else 'unclassified_subagent'
        row = analyze(path, role)
        row.update(thread_id=ident, parent_thread_id=spawn.get('parent_thread_id'), agent_type=spawn.get('agent_role'),
                   attribution='selected session' if ident == session else 'explicit selection' if ident in requested else 'native metadata')
        if role == 'unclassified_subagent':
            row['warnings'].append('Related subagent; metadata does not establish that it was a Fusion sidekick.')
        if meta.get('forked_from_id'):
            row['warnings'].append('Forked session: counters may include inherited history; no baseline subtraction is available.')
        rows.append(row)
    result = build_report(rows)
    result['session_id'] = session
    result['discovery'] = 'Exact metadata ID and native subagent ancestry. Shared session IDs, filenames, cwd, and recency are not identity evidence.'
    result['coverage'] = 'Locally available rollouts only; missing/deleted subagents cannot be enumerated. Unclassified subagents are included in total, separately from confirmed sidekicks.'
    return result


def main():
    parser = argparse.ArgumentParser(description='Report current or selected session usage, or explicitly supplied rollout files.')
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--session', help='Exact thread ID; defaults to CODEX_THREAD_ID.')
    choice.add_argument('--lead', type=Path)
    parser.add_argument('--sidekick', type=Path, action='append', default=[])
    parser.add_argument('--sidekick-id', action='append', default=[], help='Confirm a discovered subagent as a sidekick.')
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    args = parser.parse_args()
    try:
        if args.lead:
            if args.sidekick_id:
                raise ValueError('--sidekick-id is only available with session discovery.')
            result = report(args.lead, args.sidekick)
        else:
            if args.sidekick:
                raise ValueError('--sidekick paths require an explicit --lead path.')
            result = session_report(args.session or os.environ.get('CODEX_THREAD_ID'), args.codex_home.expanduser(), args.sidekick_id)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
