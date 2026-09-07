from pathlib import Path
p = Path('memory/2026-05-18.md')
t = p.read_text(encoding='utf-8')
start = t.find('- Completed LIN / ITA / PH missing-info closeout')
if start == -1:
    raise SystemExit('target not found')
end = t.find('\n-', start + 1)
if end == -1:
    end = len(t)
new = """- Completed LIN / ITA / PH missing-info closeout for review-only paper-readiness preparation. New packet `tmp/review-packets/lin-ita-ph-missing-info-closeout-2026-05-18.md/.json` captures: Linde official IR/Q1 2026 source proof (PDF captured; table-level extraction still manual), Parker official FY2026 Q2 release proof (sales $5.2B, organic +6.6%, adjusted EPS $7.65, adjusted EPS +17%, adjusted margin 27.1%, backlog $11.7B, aerospace backlog $8.0B), and iShares/BlackRock ITA official holdings/fact-sheet proof (expense ratio 0.38%, Dow Jones U.S. Select Aerospace & Defense Index, top holdings GE 19.01%, RTX 14.79%, BA 9.94%, LMT 3.93%, KTOS 0.82%). Integrated additive closeout sections into PH/LIN and ITA/VXUS packet JSON/MD plus combined summary. Validation: JSON tool passed for closeout, PH/LIN, and ITA/VXUS packet JSON; watcher rerun stayed warnings 0 with ETN entry candidate, VXUS/PH/ITA review candidates, LIN near-band. Boundary unchanged: no order, no owner approval inferred, no brokerage/account/money action; future paper execution still requires exact owner terms and WF67 dry-run/guard validation.
"""
t = t[:start] + new + (t[end+1:] if end < len(t) and t[end] == '\n' else t[end:])
p.write_text(t, encoding='utf-8')
print('fixed daily note entry safely')
