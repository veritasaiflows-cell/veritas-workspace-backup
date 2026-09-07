import json, os
d = json.load(open('tmp/improvement-ledger-current.json','r',encoding='utf-8'))
print('--- pending_skill_proposal_count:', d['summary'].get('pending_skill_proposal_count'))
print('--- relevant_pending_skill_proposal_count:', d['summary'].get('relevant_pending_skill_proposal_count'))
print('--- skill_proposal_audit ---')
print(json.dumps(d['skill_proposal_audit'], indent=2))
print()
print('--- high_priority_overdue_open_count:', d['summary'].get('high_priority_overdue_open_count'))
print('--- followup_required_open_count:', d['summary'].get('followup_required_open_count'))
print()
print('=== HIGH-PRIORITY OVERDUE OPEN (priority >= 80, sla_status=overdue, status=open) ===')
for r in d.get('latest_open_improvements', []):
    if r.get('priority', 0) >= 80 and r.get('sla_status') == 'overdue' and r.get('status') == 'open':
        pri = r.get('priority', 0)
        cat = r.get('category', '')
        ttl = r.get('title', '')
        age = r.get('age_hours', 0)
        rec = r.get('recurrence_count', 0)
        st = r.get('distinct_state_count', 0)
        sla = r.get('sla_days')
        nxt = (r.get('next_action', '') or '')[:160]
        print('  P%3d | %-22s | %s' % (pri, cat, ttl))
        print('        age=%.1fh | recurrences=%d | states=%d | sla_days=%s' % (age, rec, st, sla))
        print('        next_action: %s' % nxt)
        print()
print()
print('=== FOLLOW-UP REQUIRED OPEN ===')
for r in d.get('latest_open_improvements', []):
    sev = r.get('severity', '')
    dec = r.get('decision', '')
    if 'follow_up_required' in sev or 'follow_up_required' in dec:
        pri = r.get('priority', 0)
        cat = r.get('category', '')
        ttl = r.get('title', '')
        fu = r.get('follow_up', {}) or {}
        nxt = (r.get('next_action', '') or '')[:160]
        print('  P%3d | %-22s | %s' % (pri, cat, ttl))
        print('        severity=%s | decision=%s' % (sev, dec))
        print('        follow_up.required=%s | status=%s' % (fu.get('required'), fu.get('status')))
        print('        next_action: %s' % nxt)
        print()
print()
print('=== SKILL WORKSHOP MANIFEST (relevant pending) ===')
mp = r'C:/Users/Veritas/.openclaw/skill-workshop/proposals.json'
if os.path.exists(mp):
    try:
        m = json.load(open(mp, 'r', encoding='utf-8'))
        print('  type:', type(m).__name__)
        if isinstance(m, dict):
            print('  top keys:', list(m.keys())[:12])
            for k in ('proposals', 'pending', 'pending_proposals', 'items'):
                if k in m:
                    v = m[k]
                    print('  has %s: %s' % (k, type(v).__name__))
                    if isinstance(v, list):
                        print('  count:', len(v))
        elif isinstance(m, list):
            print('  list length:', len(m))
            if m:
                print('  first item keys:', list(m[0].keys()) if isinstance(m[0], dict) else m[0])
    except Exception as e:
        print('  error:', e)
else:
    print('  manifest missing')