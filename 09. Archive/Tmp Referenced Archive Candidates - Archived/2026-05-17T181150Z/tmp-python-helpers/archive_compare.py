from pathlib import Path
import hashlib
root=Path.cwd()
for p in [
'Capital Deployment Readiness - Phase 0 Contract.md','Capital Deployment Readiness - Phase 1 Audit.md','Capital Deployment Readiness - Phase 2 Surface Design.md','Coverage Tier Framework.md','E17 Universe Synchronization - Earnings Block Architecture.md','E17 Universe Synchronization - Phase 0 Decision.md','Research Department Operating Model.md','Sector Coverage Expansion Plan.md','Veritas OS Automation Spine.md']:
    active=root/'06. Playbooks/Project Continuity'/p
    matches=list((root/'09. Archive').rglob(p))
    print(p)
    print(' active', active.exists(), hashlib.sha256(active.read_bytes()).hexdigest()[:12] if active.exists() else '')
    for m in matches: print(' archive', str(m.relative_to(root)).replace('\\','/'), hashlib.sha256(m.read_bytes()).hexdigest()[:12], 'same=', active.exists() and active.read_bytes()==m.read_bytes())
