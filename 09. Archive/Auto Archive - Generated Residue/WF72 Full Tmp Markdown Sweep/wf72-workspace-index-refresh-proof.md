# WF72 workspace-index refresh proof

- Generated: `2026-05-24T04:59:24Z`
- Status: `ok`
- Workspace index report: `tmp/workspace-index-report.json`
- Workspace index generated: `2026-05-24T04:57:55Z`
- Artifact index validate: `status=ok checks=27 failed=0`
- Note drift: `review_only candidates=18 review_needed=12`

## Counts

- documents: 735
- headings: 10011
- links: 360
- aliases: 407
- owners: 10
- artifacts: 366
- artifact_metadata: 1216
- freshness: 1101
- runs: 1

## Retrieval smokes

- WF72: ok
- Phase 4A SQL canon: ok
- note drift workspace index: ok_after_hyphenless_retry

## Boundary

workspace index and SQL cockpit remain retrieval/proof/index only, not canon/apply/approval/trade/account/paper authority

## Residue

- workspace_index FTS query with hyphenated note-drift failed as sqlite parsed hyphen as operator; hyphenless retry succeeded
- WF74 QA residue remains: stray scripts/go/tmp/go-build binary should be cleaned or ignored before commit/package hygiene
