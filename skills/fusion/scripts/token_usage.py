#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


KEYS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'total_tokens')
CLAUDE_KEYS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
CACHE_WRITE = 'cache_creation_input_tokens'


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


def analyze_claude(path, role):
    responses = {}
    incomplete = set()
    unidentified = 0
    models = set()
    warnings = []
    sidechain = 0
    with path.open() as source:
        for number, line in enumerate(source, 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f'Ignored malformed line {number}')
                continue
            if not isinstance(item, dict) or item.get('type') != 'assistant':
                continue
            message = item.get('message')
            if not isinstance(message, dict) or message.get('model') == '<synthetic>':
                continue
            ident = message.get('id')
            usage = message.get('usage')
            if not isinstance(ident, str):
                if isinstance(usage, dict):
                    unidentified += 1
                continue
            values = [usage.get(k) for k in CLAUDE_KEYS] if isinstance(usage, dict) else []
            if len(values) != len(CLAUDE_KEYS) or not all(isinstance(v, int) and v >= 0 for v in values):
                incomplete.add(ident)
                continue
            details = usage.get('output_tokens_details')
            thinking = details.get('thinking_tokens') if isinstance(details, dict) else None
            entry = {**dict(zip(CLAUDE_KEYS, values)), 'thinking': thinking if isinstance(thinking, int) and thinking >= 0 else None}
            if message.get('model'):
                models.add(message['model'])
            sidechain += bool(item.get('isSidechain')) and role == 'lead'
            previous = responses.get(ident)
            if previous:
                entry = {k: max(previous[k], entry[k]) for k in CLAUDE_KEYS} | {'thinking': max((v for v in (previous['thinking'], entry['thinking']) if v is not None), default=None)}
            responses[ident] = entry
    tokens = None
    unresolved = incomplete - set(responses)
    if unresolved or unidentified:
        warnings.append(f'{len(unresolved) + unidentified} responses have missing or incomplete usage; totals are unknown')
    elif responses:
        rows = responses.values()
        cache_write = sum(r['cache_creation_input_tokens'] for r in rows)
        cache_read = sum(r['cache_read_input_tokens'] for r in rows)
        prompt = sum(r['input_tokens'] for r in rows) + cache_write + cache_read
        output = sum(r['output_tokens'] for r in rows)
        tokens = {'input_tokens': prompt, 'cached_input_tokens': cache_read, 'output_tokens': output,
                  'reasoning_output_tokens': sum(r['thinking'] or 0 for r in rows), 'total_tokens': prompt + output,
                  CACHE_WRITE: cache_write}
        missing = sum(r['thinking'] is None for r in rows)
        if missing:
            warnings.append(f'{missing} responses did not record thinking tokens; reasoning output may undercount')
    if not responses and not unresolved and not unidentified:
        warnings.append('No assistant usage records; usage is unknown')
    if sidechain:
        warnings.append(f'{sidechain} subagent lines are embedded in the lead transcript and counted as lead usage')
    return {'role': role, 'path': str(path.resolve()), 'models': sorted(models), 'responses': len(responses), 'tokens': tokens, 'warnings': warnings}


def summarize(rows):
    if not all(row['tokens'] is not None for row in rows):
        return None
    keys = KEYS + ((CACHE_WRITE,) if all(CACHE_WRITE in row['tokens'] for row in rows) else ())
    return {k: sum(row['tokens'][k] for row in rows) for k in keys}


def build_report(rows):
    groups = {}
    for role in dict.fromkeys(row['role'] for row in rows):
        members = [row for row in rows if row['role'] == role]
        groups[role] = {'threads': len(members), 'tokens': summarize(members)}
    return {'threads': rows, 'by_role': groups, 'total': summarize(rows),
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Full session logs, not an activation interval',
            'limitations': 'No price or plan-quota inference. Models are observed, not cost attribution. Reasoning is a subset of output; cached input is a subset of input. Claude rows also report cache writes, which are part of input. Active sessions may not yet include their current response.'}


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


def codex_entries(codex_home):
    entries = {}
    for folder in ('sessions', 'archived_sessions'):
        for path in sorted((codex_home / folder).rglob('*.jsonl')):
            meta = metadata(path)
            if meta is not None:
                entries.setdefault(meta['id'], []).append((path, meta))
    return entries


def claude_session_file(session, claude_home):
    matches = sorted((claude_home / 'projects').glob(f'*/{session}.jsonl'))
    if len(matches) > 1:
        raise ValueError(f'Multiple Claude Code transcripts for {session}; supply explicit files instead.')
    return matches[0] if matches else None


def claude_session_report(session, claude_home, sidekick_ids=()):
    if not session:
        raise ValueError('No current session ID. Supply --claude-session with an exact session ID.')
    path = claude_session_file(session, claude_home)
    if path is None:
        raise ValueError(f'No local Claude Code transcript for exact session {session}.')
    agents = {}
    for transcript in sorted((path.parent / session / 'subagents').glob('agent-*.jsonl')):
        try:
            meta = json.loads(transcript.with_suffix('.meta.json').read_text())
        except (OSError, ValueError):
            meta = {}
        agents[transcript.stem.removeprefix('agent-')] = (transcript, meta if isinstance(meta, dict) else {})
    requested = set(sidekick_ids)
    if not requested <= set(agents):
        raise ValueError('Each --sidekick-id must identify a discovered subagent of the selected session.')
    lead = analyze_claude(path, 'lead')
    lead.update(thread_id=session, agent_type=None, attribution='selected session')
    rows = [lead]
    for ident, (transcript, meta) in agents.items():
        kind = meta.get('agentType')
        role = 'sidekick' if ident in requested or kind == 'fusion-sidekick' else 'unclassified_subagent'
        row = analyze_claude(transcript, role)
        row.update(thread_id=ident, agent_type=kind, attribution='explicit selection' if ident in requested else 'subagent metadata')
        if role == 'unclassified_subagent':
            row['warnings'].append('Related subagent; metadata does not establish that it was a Fusion sidekick.')
        rows.append(row)
    result = build_report(rows)
    result['session_id'] = session
    result['harness'] = 'claude-code'
    result['discovery'] = 'Exact transcript file name and the subagents folder beside it. Project folders, cwd, and recency are not identity evidence.'
    result['coverage'] = 'Locally available transcripts only; deleted subagent transcripts cannot be enumerated. Unclassified subagents are included in total, separately from confirmed sidekicks.'
    return result


def cli_sidekick_row(ident, claude_home, codex_home):
    path = claude_session_file(ident, claude_home)
    if path is not None:
        row = analyze_claude(path, 'sidekick')
    else:
        candidates = codex_entries(codex_home).get(ident, [])
        if len(candidates) != 1:
            raise ValueError(f'No single local Claude Code or Codex session for CLI sidekick {ident}.')
        row = analyze(candidates[0][0], 'sidekick')
    row.update(thread_id=ident, agent_type='cli-session', attribution='explicit CLI sidekick')
    return row


def with_cli_sidekicks(result, idents, claude_home, codex_home):
    if not idents:
        return result
    rows = result['threads'] + [cli_sidekick_row(ident, claude_home, codex_home) for ident in idents]
    if len({row['path'] for row in rows}) != len(rows):
        raise ValueError('Each session must be counted once.')
    return {**result, **build_report(rows)}


def session_report(session, codex_home, sidekick_ids=()):
    if not session:
        raise ValueError('No current session ID. Supply --session with an exact thread ID.')
    entries = codex_entries(codex_home)
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
    parser = argparse.ArgumentParser(description='Report Codex or Claude Code session usage by lead and sidekick, or explicitly supplied Codex rollout files.')
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--session', help='Exact Codex thread ID; defaults to CODEX_THREAD_ID.')
    choice.add_argument('--claude-session', help='Exact Claude Code session ID; defaults to CLAUDE_CODE_SESSION_ID.')
    choice.add_argument('--lead', type=Path)
    parser.add_argument('--sidekick', type=Path, action='append', default=[])
    parser.add_argument('--sidekick-id', action='append', default=[], help='Confirm a discovered subagent as a sidekick.')
    parser.add_argument('--cli-sidekick', action='append', default=[], help='Add a Codex or Claude Code CLI sidekick session by its ID.')
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    parser.add_argument('--claude-home', type=Path, default=Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude'))))
    args = parser.parse_args()
    try:
        codex_home, claude_home = args.codex_home.expanduser(), args.claude_home.expanduser()
        if args.lead:
            if args.sidekick_id or args.cli_sidekick:
                raise ValueError('--sidekick-id and --cli-sidekick are only available with session discovery.')
            result = report(args.lead, args.sidekick)
        else:
            if args.sidekick:
                raise ValueError('--sidekick paths require an explicit --lead path.')
            claude = args.claude_session
            if not args.session and not claude:
                current = {name: os.environ.get(name) for name in ('CLAUDE_CODE_SESSION_ID', 'CODEX_THREAD_ID') if os.environ.get(name)}
                if len(current) > 1:
                    raise ValueError('Both CLAUDE_CODE_SESSION_ID and CODEX_THREAD_ID are set; pass --claude-session or --session.')
                claude = current.get('CLAUDE_CODE_SESSION_ID')
            if claude:
                result = claude_session_report(claude, claude_home, args.sidekick_id)
            else:
                result = session_report(args.session or os.environ.get('CODEX_THREAD_ID'), codex_home, args.sidekick_id)
            result = with_cli_sidekicks(result, args.cli_sidekick, claude_home, codex_home)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
