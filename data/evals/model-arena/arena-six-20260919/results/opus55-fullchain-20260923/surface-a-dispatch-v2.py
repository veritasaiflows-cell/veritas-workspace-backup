"""Owner-authorized v2 Surface A normalized-LF Gateway dispatch. Never replay turns."""
from __future__ import annotations
import hashlib, json, re, shutil, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RUN = Path(__file__).resolve().parent
ARENA = RUN.parents[1]
ENVELOPE = json.loads((ARENA / 'envelope.json').read_text(encoding='utf-8'))
CONTRACT = json.loads((RUN / 'surface-a-transport-contract-v2-normalized-lf-20260923.json').read_text(encoding='utf-8'))
PROMPTS = RUN / 'candidate-mount/arena-six-inputs-20260919/prompts'
WORKSPACE = Path(r'C:\Users\Veritas\.openclaw\workspaces\oxalpha-lab')
NATIVE = Path(r'C:\Users\Veritas\.claude\projects\C--Users-Veritas--openclaw-workspaces-oxalpha-lab')
CLI = shutil.which('openclaw')
MODEL = 'anthropic/claude-opus-5-5'
PREFIX = 'arena-six-inputs-20260919/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def trace_native(session_id, delivered_sha):
    path = NATIVE / (session_id + '.jsonl')
    result = {'native_log': path.name, 'native_log_found': path.is_file(), 'user_provenance': None,
              'external_user_content_sha256': None, 'tool_calls': [], 'tool_results': []}
    if not path.is_file():
        return result
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get('message') if isinstance(obj.get('message'), dict) else {}
        if obj.get('type') == 'user':
            text = msg.get('content')
            if isinstance(text, str):
                h = digest(text.encode('utf-8'))
                if delivered_sha == h or result['external_user_content_sha256'] is None:
                    result['external_user_content_sha256'] = h
                    result['user_provenance'] = {'role': msg.get('role'), 'user_type': obj.get('userType'), 'entrypoint': obj.get('entrypoint')}
            if isinstance(text, list):
                for item in text:
                    if isinstance(item, dict) and item.get('type') == 'tool_result':
                        result['tool_results'].append({'tool_use_id': item.get('tool_use_id'), 'is_error': item.get('is_error')})
        elif obj.get('type') == 'assistant':
            for item in msg.get('content', []) if isinstance(msg.get('content'), list) else []:
                if not isinstance(item, dict) or item.get('type') != 'tool_use':
                    continue
                raw = item.get('input') if isinstance(item.get('input'), dict) else {}
                raw_path = raw.get('file_path') or raw.get('path') or raw.get('target_file')
                rel = None
                if isinstance(raw_path, str):
                    try:
                        rel = Path(raw_path).resolve().relative_to(WORKSPACE.resolve()).as_posix()
                        if rel.startswith(PREFIX):
                            rel = rel[len(PREFIX):]
                    except (ValueError, OSError):
                        rel = 'outside_workspace'
                result['tool_calls'].append({'name': item.get('name'), 'path': rel, 'tool_use_id': item.get('id')})
    return result


def turn(case, rep, n, prompt_rel):
    path = PROMPTS / Path(prompt_rel).name
    raw = path.read_bytes()
    assert digest(raw) == ENVELOPE['frozen_hashes'][prompt_rel], prompt_rel
    expected = raw.decode('utf-8')
    normalized = expected.rstrip('\n')
    frozen_sha, delivered_sha = digest(raw), digest(normalized.encode('utf-8'))
    stem = f'{case}-r{rep}-t{n}'
    output = RUN / f'v2-transport-{stem}.json'
    stderr = RUN / f'v2-transport-{stem}.stderr.txt'
    receipt_path = RUN / f'v2-receipt-{stem}.json'
    # Creation-exclusive guard: a valid attempt is never dispatched twice.
    marker = RUN / f'v2-started-{stem}.json'
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'case': case, 'rep': rep, 'turn': n, 'session_key': f'arena-a-v2-opus55-{case.lower()}-r{rep}',
                   'frozen_sha256': frozen_sha, 'expected_delivered_sha256': delivered_sha, 'started_at': time.time()}, f)
        f.write('\n')
    session = f'arena-a-v2-opus55-{case.lower()}-r{rep}'
    cmd = [CLI, 'agent', '--agent', 'oxalpha-lab', '--session-key', session, '--model', MODEL,
           '--thinking', 'high', '--timeout', '600', '--json', '--message-file', str(path)]
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=630, shell=False)
        stdout, err, code, timed_out = proc.stdout or '', proc.stderr or '', proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode('utf-8', errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
        err = exc.stderr.decode('utf-8', errors='replace') if isinstance(exc.stderr, bytes) else (exc.stderr or '')
        code, timed_out = None, True
    with output.open('x', encoding='utf-8') as f:
        f.write(stdout)
    with stderr.open('x', encoding='utf-8') as f:
        f.write(err)
    try:
        doc = json.loads(stdout)
    except (ValueError, TypeError):
        doc = {}
    result = doc.get('result') if isinstance(doc, dict) and isinstance(doc.get('result'), dict) else {}
    meta = result.get('meta') if isinstance(result.get('meta'), dict) else {}
    agent = meta.get('agentMeta') if isinstance(meta.get('agentMeta'), dict) else {}
    system = meta.get('systemPromptReport') if isinstance(meta.get('systemPromptReport'), dict) else {}
    execution = meta.get('executionTrace') if isinstance(meta.get('executionTrace'), dict) else {}
    final = meta.get('finalPromptText') if isinstance(meta.get('finalPromptText'), str) else ''
    match = re.fullmatch(r'\[[^\]\r\n]+\] (.*)', final, re.DOTALL)
    delivered = match.group(1) if match else None
    actual_sha = digest(delivered.encode('utf-8')) if delivered is not None else None
    native_id = agent.get('sessionId')
    native = trace_native(native_id, actual_sha) if isinstance(native_id, str) else {}
    payloads = result.get('payloads') if isinstance(result.get('payloads'), list) else []
    response = payloads[0].get('text') if payloads and isinstance(payloads[0], dict) else ''
    provider = agent.get('provider') or system.get('provider')
    effective = agent.get('model') or system.get('model')
    fallback = execution.get('fallbackUsed')
    provenance = native.get('user_provenance') or {}
    calls = native.get('tool_calls') or []
    no_tool_violation = (len(calls) == 0 if case != 'T4-multihop-read-recovery' else
                         len(calls) <= 6 and all(call['name'] == 'Read' and call['path'] != 'outside_workspace' for call in calls))
    identity_ok = provider == 'claude-cli' and effective == 'claude-opus-5-5' and fallback is False
    provenance_ok = provenance == {'role': 'user', 'user_type': 'external', 'entrypoint': 'sdk-cli'}
    transport_ok = (not timed_out and code == 0 and doc.get('status') == 'ok' and identity_ok and
                    delivered == normalized and actual_sha == delivered_sha and provenance_ok and no_tool_violation)
    status = 'ok' if transport_ok else ('timeout' if timed_out else 'transport_invalid')
    record = {'case': case, 'rep': rep, 'turn': n, 'response_text': response or '', 'operational_status': status,
              'transport': {'requested_model': MODEL, 'effective_provider': provider, 'effective_model': effective,
                            'fallback_used': fallback, 'exit_code': code, 'duration_ms': int((time.perf_counter()-started)*1000),
                            'session_key': session, 'native_session_id': native_id,
                            'frozen_prompt_sha256': frozen_sha, 'delivered_payload_sha256': actual_sha,
                            'expected_normalized_sha256': delivered_sha, 'normalization': 'strip_terminal_LF_only',
                            'delivery_match': delivered == normalized, 'user_provenance': provenance,
                            'native_external_user_content_sha256': native.get('external_user_content_sha256'),
                            'native_log': native.get('native_log'), 'tool_calls': calls, 'tool_results': native.get('tool_results', []),
                            'tool_violation': not no_tool_violation, 'raw_transport_file': output.name,
                            'stderr_file': stderr.name, 'receipt_file': receipt_path.name}}
    with receipt_path.open('x', encoding='utf-8') as f:
        json.dump(record, f, indent=2, sort_keys=True)
        f.write('\n')
    return record


def trajectory(task, rep):
    rows = []
    for n, prompt in enumerate(task['turns'], 1):
        row = turn(task['id'], rep, n, prompt)
        rows.append(row)
        print(json.dumps({'case': task['id'], 'rep': rep, 'turn': n, 'status': row['operational_status']}), flush=True)
        if row['operational_status'] != 'ok':
            break
    return {'case': task['id'], 'rep': rep, 'operational_status': 'ok' if len(rows) == len(task['turns']) and all(r['operational_status'] == 'ok' for r in rows) else 'operational_incomplete',
            'tool_trace': [c['path'] for row in rows for c in row['transport']['tool_calls'] if c['name'] == 'Read' and c['path']],
            'turns': rows}


def main():
    if not CLI or CONTRACT['schema'] != 'veritas.arena_surface_a_transport_contract.v1':
        raise SystemExit('contract_or_cli_missing')
    keys = json.loads((ARENA / 'reference/keys.json').read_text(encoding='utf-8'))
    assert digest(json.dumps(keys, sort_keys=True, separators=(',', ':')).encode()) == ENVELOPE['grading']['keys_sha256']
    assert all(digest((ARENA / rel).read_bytes()) == sha for rel, sha in ENVELOPE['frozen_hashes'].items())
    assert all(digest((PROMPTS / Path(rel).name).read_bytes()) == ENVELOPE['frozen_hashes'][rel] for rel in ENVELOPE['frozen_hashes'] if rel.startswith('prompts/'))
    assert (WORKSPACE / 'arena-six-inputs-20260919/recovery/index.json').is_file()
    tasks = ENVELOPE['tasks']
    waves = [[(tasks[0], 1), (tasks[0], 2), (tasks[1], 1), (tasks[1], 2)],
             [(tasks[2], 1), (tasks[2], 2), (tasks[3], 1), (tasks[3], 2)],
             [(tasks[4], 1), (tasks[4], 2), (tasks[5], 1), (tasks[5], 2)]]
    trajectories = []
    for i, wave in enumerate(waves, 1):
        print(json.dumps({'wave': i, 'status': 'started'}), flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(trajectory, task, rep) for task, rep in wave]
            for future in as_completed(futures):
                trajectories.append(future.result())
        if any(t['operational_status'] != 'ok' for t in trajectories):
            print(json.dumps({'wave': i, 'status': 'stop_invalid_no_further_waves'}), flush=True)
            break
        if i < len(waves):
            time.sleep(60)
    trajectories.sort(key=lambda x: (x['case'], x['rep']))
    doc = {'schema': 'veritas.arena_surface_a_v2_responses.v1', 'model': MODEL,
           'transport_contract': 'surface-a-transport-contract-v2-normalized-lf-20260923.json',
           'prior_invalid_turns': CONTRACT['prior_invalid_turns']['turns'], 'retry_policy': 'zero',
           'trajectories': trajectories}
    path = RUN / 'surface-a-responses-v2-normalized.json'
    with path.open('x', encoding='utf-8') as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'trajectories': len(trajectories), 'complete': sum(t['operational_status'] == 'ok' for t in trajectories), 'response_file': path.name}), flush=True)
    return 0 if len(trajectories) == 12 and all(t['operational_status'] == 'ok' for t in trajectories) else 2

if __name__ == '__main__':
    raise SystemExit(main())
