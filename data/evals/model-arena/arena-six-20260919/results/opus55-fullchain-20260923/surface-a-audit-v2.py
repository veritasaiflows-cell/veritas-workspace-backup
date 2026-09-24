"""Post-dispatch native transcript and T4 fixture-tool proof; no new model calls."""
import hashlib, json
from pathlib import Path
RUN = Path(__file__).resolve().parent
NATIVE = Path(r'C:\Users\Veritas\.claude\projects\C--Users-Veritas--openclaw-workspaces-oxalpha-lab')
PREFIX = 'arena-six-inputs-20260919/'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main():
    responses = json.loads((RUN / 'surface-a-responses-v2-normalized.json').read_text(encoding='utf-8'))
    audit = []
    t4 = []
    for row in responses['trajectories']:
        case, rep = row['case'], row['rep']
        session_ids = [t['transport']['native_session_id'] for t in row['turns']]
        assert all(s == session_ids[0] for s in session_ids), (case, rep, 'session_continuity')
        transcript = NATIVE / (session_ids[0] + '.jsonl')
        assert transcript.is_file()
        events = []
        for line in transcript.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        user_messages = [e for e in events if e.get('type') == 'user' and e.get('userType') == 'external' and e.get('entrypoint') == 'sdk-cli'
                         and isinstance(e.get('message', {}).get('content'), str)]
        for turn in row['turns']:
            n = turn['turn']
            raw_doc = json.loads((RUN / turn['transport']['raw_transport_file']).read_text(encoding='utf-8'))
            delivered_final = raw_doc['result']['meta']['finalPromptText']
            actual_user = user_messages[n - 1] if len(user_messages) >= n else {}
            text = actual_user.get('message', {}).get('content')
            ok = text == delivered_final and actual_user.get('message', {}).get('role') == 'user'
            audit.append({'case': case, 'rep': rep, 'turn': n, 'native_user_equals_gateway_final_prompt': ok,
                          'native_user_sha256': sha(text) if isinstance(text, str) else None,
                          'gateway_final_prompt_sha256': sha(delivered_final),
                          'native_user_messages_in_trajectory': len(user_messages), 'session_id': session_ids[0]})
        if case != 'T4-multihop-read-recovery':
            continue
        pending = {}
        calls = []
        for event in events:
            msg = event.get('message') if isinstance(event.get('message'), dict) else {}
            content = msg.get('content')
            if event.get('type') == 'assistant' and isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict) or item.get('type') != 'tool_use':
                        continue
                    raw = item.get('input') if isinstance(item.get('input'), dict) else {}
                    path = raw.get('file_path') or raw.get('path') or raw.get('target_file')
                    normalized = str(path).replace('\\', '/') if path is not None else None
                    if normalized and PREFIX in normalized:
                        normalized = normalized.split(PREFIX, 1)[1]
                    rec = {'name': item.get('name'), 'path': normalized, 'tool_use_id': item.get('id'),
                           'result_found': False}
                    pending[item.get('id')] = rec
                    calls.append(rec)
            if event.get('type') == 'user' and isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict) or item.get('type') != 'tool_result':
                        continue
                    rec = pending.get(item.get('tool_use_id'))
                    if rec is None:
                        continue
                    val = item.get('content')
                    raw_result = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False, sort_keys=True)
                    rec.update({'result_found': True, 'is_error': item.get('is_error', False),
                                'result_sha256': sha(raw_result), 'result_visible_content': raw_result})
        t4.append({'case': case, 'rep': rep, 'native_log': transcript.name, 'calls_and_results': calls,
                   'expected_read_trace': row['tool_trace']})
    document = {'schema': 'veritas.arena_surface_a_native_audit_v2.v1', 'turns': audit,
                'all_native_prompts_match_gateway': all(r['native_user_equals_gateway_final_prompt'] for r in audit),
                'T4_tool_trace': t4}
    with (RUN / 'surface-a-native-and-t4-tool-trace-v2.json').open('x', encoding='utf-8') as f:
        json.dump(document, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'turns': len(audit), 'native_prompt_matches': sum(x['native_user_equals_gateway_final_prompt'] for x in audit),
                      't4_read_counts': [len(x['calls_and_results']) for x in t4],
                      't4_result_counts': [sum(c['result_found'] for c in x['calls_and_results']) for x in t4]}, sort_keys=True))
    return 0 if len(audit) == 20 and document['all_native_prompts_match_gateway'] and len(t4) == 2 and all(all(c['result_found'] for c in x['calls_and_results']) for x in t4) else 2

if __name__ == '__main__':
    raise SystemExit(main())
