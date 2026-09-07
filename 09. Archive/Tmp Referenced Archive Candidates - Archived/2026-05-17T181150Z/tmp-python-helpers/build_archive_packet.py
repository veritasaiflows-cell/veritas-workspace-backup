import json,pathlib
root=pathlib.Path.cwd()
data=json.loads((root/'tmp/archive_ref_check_raw.json').read_text(encoding='utf-16'))
keepers={
'Capital Deployment Readiness - Phase 0 Contract':'06. Playbooks/Project Continuity/Capital Deployment Readiness.md + Capital Deployment Readiness - Chain Log.md',
'Capital Deployment Readiness - Phase 1 Audit':'06. Playbooks/Project Continuity/Capital Deployment Readiness.md + Capital Deployment Readiness - Chain Log.md',
'Capital Deployment Readiness - Phase 2 Surface Design':'06. Playbooks/Project Continuity/Capital Deployment Readiness.md + Capital Deployment Readiness - Chain Log.md',
'Coverage Tier Framework':'06. Playbooks/Project Continuity/Workflow 6 - Coverage Tier Framework.md',
'E17 Universe Synchronization - Earnings Block Architecture':'06. Playbooks/Project Continuity/E17 Universe Synchronization.md + E17 Universe Synchronization - Chain Log.md',
'E17 Universe Synchronization - Phase 0 Decision':'06. Playbooks/Project Continuity/E17 Universe Synchronization.md + E17 Universe Synchronization - Chain Log.md',
'Research Department Operating Model':'06. Playbooks/Project Continuity/Workflow 9 - Research Department Operating Model.md',
'Sector Coverage Expansion Plan':'06. Playbooks/Project Continuity/Workflow 7 - Sector Coverage Expansion Plan.md',
'Veritas OS Automation Spine':'09. Archive/06. Project Continuity - Archived/Veritas OS Automation Spine.md (byte-identical archive copy already present)',
}
items=[]
for d in data:
    name=d['title']; file=d['candidate']; dest='09. Archive/06. Project Continuity - Archived/'+pathlib.Path(file).name
    live=[h for h in d['hits'] if not h['file'].startswith('tmp/') and not h['file'].startswith('migration-backups/')]
    blockers=[]
    if any(h['file']=='06. Playbooks/Active Workflows.md' for h in live): blockers.append('Listed in Active Workflows.md as review-required / owner-approval archive candidate.')
    if len(live)>5: blockers.append(f'{len(live)} non-tmp inbound reference files remain; reference updates/acceptance needed before physical removal.')
    elif live: blockers.append(f'{len(live)} non-tmp inbound reference files remain; mostly audit/chain-log/sink references.')
    # exact existing archive copy
    archives=list((root/'09. Archive').rglob(pathlib.Path(file).name))
    same=[]
    active=(root/file)
    for a in archives:
        if active.exists() and active.read_bytes()==a.read_bytes(): same.append(str(a.relative_to(root)).replace('\\','/'))
    readiness='high' if same and len(live)<=6 else 'medium'
    if not d['exists']: readiness='blocked'; blockers.append('Candidate file missing.')
    items.append({
      'candidate':file,'exists':d['exists'],'inbound_reference_files_total':d['inbound_reference_files'],'inbound_reference_files_non_tmp_non_backup':len(live),
      'readiness':readiness,'recommended_action':'archive active duplicate after owner approval; do not delete historical/audit records','recommended_destination':dest,
      'keeper_or_replacement_source':keepers.get(name,'[needs owner decision]'),'byte_identical_archive_copies':same,
      'blockers':blockers,'reference_files_non_tmp_non_backup':[h['file'] for h in live]
    })
packet={'scope':'Read-only archive-reference check for nine immediate archive candidates','stop_lines_followed':['no file moves/deletes/renames','no canonical finance edits','no config changes'],'summary':{'candidates':len(items),'exists':sum(i['exists'] for i in items),'high':sum(i['readiness']=='high' for i in items),'medium':sum(i['readiness']=='medium' for i in items),'blocked':sum(i['readiness']=='blocked' for i in items)},'items':items}
(root/'tmp/archive-candidate-owner-approval-packet.json').write_text(json.dumps(packet,indent=2),encoding='utf-8')
lines=['# Archive Candidate Owner-Approval Packet','','Scope: read-only reference check for nine immediate archive candidates. No files were moved, deleted, renamed, or canonical-finance edited.','',f"Summary: {packet['summary']['exists']}/{len(items)} candidates exist; {packet['summary']['high']} high-readiness, {packet['summary']['medium']} medium-readiness, {packet['summary']['blocked']} blocked.",'','Recommended owner decision: approve archival only after accepting that active copies are byte-identical duplicates of existing archive copies and that remaining inbound references are historical/audit/queue references or will be updated by the main archive pass.','']
for i in items:
    lines += [f"## {pathlib.Path(i['candidate']).name}",f"- Exists: {i['exists']}",f"- Inbound references: {i['inbound_reference_files_total']} total; {i['inbound_reference_files_non_tmp_non_backup']} non-tmp/non-backup.",f"- Archive readiness: **{i['readiness']}**",f"- Recommended destination: `{i['recommended_destination']}`",f"- Keeper/replacement source: `{i['keeper_or_replacement_source']}`",f"- Byte-identical archive copy: {', '.join('`'+x+'`' for x in i['byte_identical_archive_copies']) if i['byte_identical_archive_copies'] else 'none found'}",'- Blockers:']
    lines += [f"  - {b}" for b in i['blockers']] or ['  - None.']
    lines += ['- Non-tmp/non-backup reference files:']+[f"  - `{f}`" for f in i['reference_files_non_tmp_non_backup']]+['']
(root/'tmp/archive-candidate-owner-approval-packet.md').write_text('\n'.join(lines),encoding='utf-8')
print('wrote packets')
