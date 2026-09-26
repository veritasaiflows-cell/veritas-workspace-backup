Independent review, read-only. Do not write, post, or change anything.

Read these three files in your workspace (use the read tool):
- inbox/skill-split-20260925/diffs.md
- inbox/skill-split-20260925/live-facts.md
- inbox/skill-split-20260925/workshop-only-files.md (skim only; another reviewer covers it in depth)

Background: 12 skills exist twice. The LOADED copy (workspace/skills) is what agents actually use. The WORKSHOP copy (agents/main/agent/workshop-skills) is shadowed and never loads, but owner-approved Skill Workshop applies and weekly autonomous skill reviews wrote to it. In diffs.md, "-" lines are the loaded copy and "+" lines are the Workshop copy; each file header carries its last-modified time.

For EACH of the 12 skills, decide:
1. direction: which copy should become the single source: LOADED, WORKSHOP, or MERGE (take specific parts of each).
2. For MERGE, list the exact hunks or sections to take from each side.
3. Stale claims: any line on either side contradicted by live-facts.md (quote the line and the contradicting fact).
4. Risk: LOW (wording/structure only), MEDIUM (procedure change), HIGH (changes models, authority, approval, or safety rules).
5. One-sentence reason.

Then give:
- the 3 highest-risk conflicts overall, quoted;
- anything that looks like an unattended edit changing authority, approval, or safety wording (quote it);
- anything you could not decide, marked UNDECIDED with what evidence would settle it.

Rules: quote exactly; do not guess dates or authors; if a claim is not in the files, say so. Keep the whole reply under 1,500 words. Start the reply with "QA-DIFFS RESULT".
