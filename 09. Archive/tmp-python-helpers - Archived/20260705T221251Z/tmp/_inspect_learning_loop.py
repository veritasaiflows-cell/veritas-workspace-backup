import json

print("=" * 60)
print("CRON CONTROL PACKET")
print("=" * 60)
d = json.load(open("tmp/cron-control-packet.json"))
print("status:", d.get("status"))
sm = d.get("summary", {})
for k in ["total_jobs", "enabled_jobs", "healthy_jobs", "attention_jobs",
          "blocked_jobs", "fresh_within_sla", "stale_over_sla", "overdue",
          "attention", "blocked", "fresh", "stale"]:
    if k in sm:
        print(f"  {k}: {sm[k]}")
print()
print("Scorecard:")
sc = d.get("scorecard", {})
for k, v in sc.items():
    print(f"  {k}: {v}")
print()
print("Escalation keys:", list(d.get("escalation", {}).keys())[:15])

print()
print("=" * 60)
print("IMPROVEMENT LEDGER")
print("=" * 60)
d = json.load(open("tmp/improvement-ledger-current.json"))
print("status:", d.get("status"))
print("mode:", d.get("mode"))
print()
print("Summary:")
sm = d.get("summary", {})
for k, v in sm.items():
    print(f"  {k}: {v}")
print()
print("Learning Loop KPIs:")
k = d.get("learning_loop_kpis", {})
for kk, vv in k.items():
    print(f"  {kk}: {vv}")
print()
print("Open improvements (count):", len(d.get("latest_open_improvements", [])))
opens = d.get("latest_open_improvements", [])
opens_sorted = sorted(opens, key=lambda x: x.get("priority", 0), reverse=True)
print("Top 5 by priority:")
for o in opens_sorted[:5]:
    title = o.get("title", o.get("signal", "?"))
    pri = o.get("priority", "?")
    age = o.get("age_hours", "?")
    gate = o.get("proposal_gate", o.get("gate", "?"))
    sla = o.get("sla", "?")
    opened = o.get("opened_at_utc", o.get("first_seen_utc", "?"))
    print(f"  P{pri} age={age}h sla={sla} gate={gate} opened={opened}")
    print(f"    -> {title}")
print()
print("Closed latest (count):", len(d.get("latest_closed_improvements", [])))
for c in d.get("latest_closed_improvements", [])[:5]:
    print(f"  - {c.get('title', c.get('signal','?'))} | closed={c.get('closed_at_utc','?')} | reason={c.get('closure_reason','?')}")
print()
print("Recommendations:")
for r in d.get("recommendations", [])[:8]:
    if isinstance(r, str):
        print("  -", r[:200])
    else:
        print("  -", json.dumps(r, default=str)[:200])
print()
print("Next safe action:", d.get("next_safe_action", "(none)"))
