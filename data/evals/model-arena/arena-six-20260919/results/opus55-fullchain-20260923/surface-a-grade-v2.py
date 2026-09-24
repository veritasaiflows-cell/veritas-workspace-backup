"""Grade only eligible fresh v2 attempts with the frozen arena grader/keys."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
RUN = Path(__file__).resolve().parent
ARENA = RUN.parents[1]
sys.path.insert(0, str(ARENA / 'reference'))
from grader import grade, grade_trajectory  # noqa: E402


def main():
    envelope = json.loads((ARENA / 'envelope.json').read_text(encoding='utf-8'))
    keys = json.loads((ARENA / 'reference/keys.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(json.dumps(keys, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == envelope['grading']['keys_sha256']
    responses = json.loads((RUN / 'surface-a-responses-v2-normalized.json').read_text(encoding='utf-8'))
    assert responses['schema'] == 'veritas.arena_surface_a_v2_responses.v1'
    task_map = {task['id']: task for task in envelope['tasks']}
    turns, trajectories, excluded = [], [], []
    for row in responses['trajectories']:
        case, rep = row['case'], int(row['rep'])
        task = task_map[case]
        by_number = {int(t['turn']): t for t in row['turns']}
        graded = []
        for n in range(1, len(task['turns']) + 1):
            t = by_number.get(n)
            identity = {'case': case, 'repetition': rep, 'turn': n, 'requested_model': responses['model']}
            eligible = bool(t and t['operational_status'] == 'ok')
            if eligible:
                key = keys[case][f'turn{n}'] if case in {'T2-event-revert-ambiguity', 'T5-handoff-authority-control'} else keys[case]
                g = grade(case, t['response_text'], key, tool_trace=row['tool_trace'],
                          expected_trace=task.get('expected_trace'), forbidden_reads=task.get('forbidden_reads', ()))
                if t['transport'].get('tool_violation'):
                    g['tool_findings'] = list(g.get('tool_findings') or []) + ['unexpected_tool_call']
                    g['tools'], g['strict_pass'] = False, False
                g.update({'identity': identity, 'operational_eligible': True, 'operational_status': 'ok'})
                graded.append(g)
            else:
                g = {'identity': identity, 'operational_eligible': False,
                     'operational_status': t['operational_status'] if t else 'not_dispatched',
                     'strict_pass': None, 'factual': None, 'format': None, 'tools': None,
                     'grade': None, 'reason': 'transport_invalid_or_incomplete_not_graded'}
                excluded.append(identity)
            turns.append(g)
        all_eligible = len(graded) == len(task['turns'])
        result = grade_trajectory(case, graded) if all_eligible else {'strict_pass': None, 'reason': 'operationally_ineligible_not_graded'}
        result.update({'identity': {'case': case, 'repetition': rep}, 'operational_eligible': all_eligible,
                       'operational_status': row['operational_status'], 'tool_trace': row.get('tool_trace', [])})
        trajectories.append(result)
    eligible_turns = [x for x in turns if x['operational_eligible']]
    eligible_trajectories = [x for x in trajectories if x['operational_eligible']]
    summary = {'planned_trajectories': 12, 'dispatched_trajectories': len(trajectories),
               'eligible_trajectories': len(eligible_trajectories),
               'strict_trajectories': sum(bool(x['strict_pass']) for x in eligible_trajectories),
               'planned_turns': 20, 'dispatched_turns': sum(len(row['turns']) for row in responses['trajectories']),
               'eligible_turns': len(eligible_turns), 'strict_turns': sum(bool(x['strict_pass']) for x in eligible_turns),
               'factual_turns': sum(bool(x['factual']) for x in eligible_turns),
               'format_turns': sum(bool(x['format']) for x in eligible_turns),
               'prior_invalid_unscored_turns': responses['prior_invalid_turns'],
               'v2_operational_exclusions': excluded,
               'scope': 'Surface A only, no comparative or cross-envelope score'}
    graded_doc = {'schema': 'veritas.arena_surface_a_graded_v2_normalized.v1',
                  'transport_contract': responses['transport_contract'],
                  'frozen_keys_sha256': envelope['grading']['keys_sha256'],
                  'turn_grades': turns, 'trajectory_grades': trajectories, 'summary': summary}
    graded_path = RUN / 'surface-a-graded-results-v2-normalized.json'
    with graded_path.open('x', encoding='utf-8') as f:
        json.dump(graded_doc, f, indent=2, sort_keys=True)
        f.write('\n')
    receipts = [t['transport']['receipt_file'] for row in responses['trajectories'] for t in row['turns']]
    dispatch_doc = {'schema': 'veritas.arena_surface_a_dispatch_summary_v2.v1',
                    'model': responses['model'], 'transport_contract': responses['transport_contract'],
                    'responses_path': 'surface-a-responses-v2-normalized.json',
                    'graded_results_path': graded_path.name, 'receipts': receipts,
                    'raw_transport_paths': [t['transport']['raw_transport_file'] for row in responses['trajectories'] for t in row['turns']],
                    'prior_invalid_receipts_preserved_unscored': responses['prior_invalid_turns'],
                    'zero_retries': True,
                    'effective_model_verified_all_dispatched': all(t['transport']['effective_model'] == 'claude-opus-5-5' and
                                                                   t['transport']['effective_provider'] == 'claude-cli' and
                                                                   t['transport']['fallback_used'] is False
                                                                   for row in responses['trajectories'] for t in row['turns']),
                    'summary': summary, 'per_trajectory': trajectories}
    summary_path = RUN / 'dispatch-execution-summary-v2.json'
    with summary_path.open('x', encoding='utf-8') as f:
        json.dump(dispatch_doc, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(summary, sort_keys=True))
    return 0 if len(eligible_trajectories) == 12 and len(eligible_turns) == 20 else 2

if __name__ == '__main__':
    raise SystemExit(main())
