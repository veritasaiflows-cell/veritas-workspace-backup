from pathlib import Path
import re,json
root=Path.cwd()
cands=[
'06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 0 Contract.md',
'06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 1 Audit.md',
'06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 2 Surface Design.md',
'06. Playbooks/Project Continuity/Coverage Tier Framework.md',
'06. Playbooks/Project Continuity/E17 Universe Synchronization - Earnings Block Architecture.md',
'06. Playbooks/Project Continuity/E17 Universe Synchronization - Phase 0 Decision.md',
'06. Playbooks/Project Continuity/Research Department Operating Model.md',
'06. Playbooks/Project Continuity/Sector Coverage Expansion Plan.md',
'06. Playbooks/Project Continuity/Veritas OS Automation Spine.md',
]
skip_parts={'.git','node_modules','.venv','venv'}
files=[]
for p in root.rglob('*'):
    if p.is_file() and not any(part in skip_parts for part in p.parts):
        if p.suffix.lower() in ['.md','.txt','.json','.yaml','.yml','.csv','.py','.js','.ps1']:
            try: txt=p.read_text(encoding='utf-8',errors='ignore')
            except Exception: continue
            files.append((p,txt))
res=[]
for c in cands:
    cp=root/c
    title=cp.stem
    rel=c.replace('\\','/')
    rel_enc=rel.replace(' ','%20')
    variants=[
        ('wikilink', re.compile(r'\[\[[^\]]*?'+re.escape(title)+r'(?:#[^\]|]+)?(?:\|[^\]]*)?\]\]', re.I)),
        ('markdown_path', re.compile(r'\]\((?:\.\./|\./)?'+re.escape(rel)+r'(?:#[^)]+)?\)', re.I)),
        ('markdown_path_encoded', re.compile(r'\]\((?:\.\./|\./)?'+re.escape(rel_enc)+r'(?:#[^)]+)?\)', re.I)),
        ('plain_path', re.compile(re.escape(rel), re.I)),
        ('plain_title', re.compile(r'(?<![\w-])'+re.escape(title)+r'(?![\w-])', re.I)),
    ]
    hits=[]
    for p,txt in files:
        if cp.exists() and p.resolve()==cp.resolve(): continue
        relp=str(p.relative_to(root)).replace('\\','/')
        if relp in ['tmp/archive-candidate-owner-approval-packet.md','tmp/archive-candidate-owner-approval-packet.json','tmp/archive_ref_check.py']:
            continue
        kinds=[]; snippets=[]
        for kind,pat in variants:
            ms=list(pat.finditer(txt))
            if ms:
                kinds.append(kind)
                for m in ms[:3]:
                    line=txt.count('\n',0,m.start())+1
                    s=txt[max(0,m.start()-80):min(len(txt),m.end()+80)].replace('\n',' ')
                    snippets.append({'line':line,'kind':kind,'snippet':s})
        if kinds: hits.append({'file':relp,'kinds':sorted(set(kinds)),'snippets':snippets[:4]})
    res.append({'candidate':c,'exists':cp.exists(),'title':title,'inbound_reference_files':len(hits),'hits':hits})
print(json.dumps(res,indent=2))
