# Cleanup archive pilot manifest — 2026-09-08 Phoenix

**Status:** review-only; no archive or deletion authorized by this manifest.

## Source inventory

- Dry-run report: `tmp/tmp-cleanup-report.json`
- Candidate digest: `c3b3afb7f4f7dd3f3be8caa3b74ee90362ffeadd38b95a0f15bf19d6f8e20824`
- Candidate count: 1,980
- Generated mode: `dry-run`; moved count: 0; delete authority: false.

## Narrow reversible pilot

This is a 17-file subset of old transient `.err`, `.out`, and `.log` outputs in `tmp/`.  Its names have no non-`tmp`/non-archive references other than the hash cache; files with explicit runtime, test, audit, or memory references were excluded.  The prospective action is **archive move only** through the existing `tmp_cleanup.py` route, after a fresh digest match.  It is not a deletion set.

| Path | SHA-256 |
|---|---|
| `tmp/_canon.log` | `3602ed102bb72e178d4d3c3b984394635602cffdd13341d9f26b1a299d506bfb` |
| `tmp/_cronlist.err` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tmp/_fsep.log` | `cd89c46f4f0cf64ec9930148d6bec5699fe1fc2aeb822294cee13a298647a8fe` |
| `tmp/_newjob.err` | `b903d348b29d4cce503178d8543e6cb3dc2393d16a65f35b44e2c2bb0ba19bec` |
| `tmp/_s2_guard2.out` | `782f0247ee409796dcb13118d514440219c69efed2ff7eae2ae8eea7101a45f9` |
| `tmp/_s2_roster.out` | `af3a71e35bfa29ab8b41f45c32a48fffcd96770fc3d9a92771d3ef2fdbe32f4c` |
| `tmp/_s2_sqlguard.out` | `3602ed102bb72e178d4d3c3b984394635602cffdd13341d9f26b1a299d506bfb` |
| `tmp/_s2_sqlrefresh_apply.out` | `d4f3efe2ea0c796739e6bfc03bca147909d290b259c5f0d2bb362a53b08d7dca` |
| `tmp/_s2_sqlrefresh_dry.out` | `c74b0d1266da2d9517315e192ae6b8c4ab3353e51123809cc8377d46f103380f` |
| `tmp/_s2_tlm.out` | `809a44203a1f6c688cbb4a978afc50765f659ff42592a1812e8a9879ab521b3f` |
| `tmp/_s2_wf78_legacy_label_retirement_guard.out` | `c054d90508373a8fb04ff9f5f630cc6400087603767a33fe1b8734b2b33dfe30` |
| `tmp/_s2_wf78_tier_capacity_policy_gate.out` | `8e5f3209a8a18c82536c014f09ce4c62d18f181ba22ce046712fc3d9dffb5e3d` |
| `tmp/_s2_wf78_tier_semantics_guard.out` | `fa350321bdb739f129709dd543d02bc0811633598a8c5ebeef76f8b539c76dc9` |
| `tmp/_s2_wf85.out` | `ff9ea3e953128d0b8bbe9393a3ad152092ca19ad2afe12dc64e2b3d60a60e4f8` |
| `tmp/gatefix-run.log` | `109c935cc6d3ee65f9d88050c1cf3bee870948462403f24b587130092ac3bc11` |
| `tmp/memory-compounding-probe.err` | `8f006ae9fbcf2bec95b74174aa8bf3d5c195824684b9735f39a3e4cd30dd17c4` |
| `tmp/rb-apply.out` | `5aeb95b9d08f04c753e20a4c93e264c439ce35b32cd7bcb766544c247e56f151` |

## Required apply-time checks

1. Rerun the dry-run and require the source digest to match; otherwise regenerate this manifest.
2. Re-hash each listed file and require the hash to match exactly.
3. Confirm the files still have no active code/config/runtime reference outside the hash cache.
4. Archive move only, then verify destination hashes and the rollback manifest.
5. Run the affected workspace/cron validators; do not delete the archive copy.

## Explicit exclusions

- Any candidate with a live runtime/test reference, or a documented audit/memory reference.
- All 3,905 files in `09. Archive`: current readiness is `manual_review_required`, with zero deletion-ready.
- Databases, journal sidecars, directories, generated packets, and all active/state/canon surfaces.
