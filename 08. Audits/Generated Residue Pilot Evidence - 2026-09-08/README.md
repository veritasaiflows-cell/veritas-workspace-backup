# Generated Residue Pilot Evidence — 2026-09-08

Tracked, non-deletable home for the paperwork of the 17-file generated-residue pilot (607,330 bytes). The 2026-09-22 temp cleanup moved the originals into `09. Archive/Scripts and Tmp Cleanup - Archived/2026-09-22-tmp-cleanup/`, which is git-ignored and inside the 30-day archive-deletion horizon. These are byte-identical copies made on 2026-09-22 at 21:58 Phoenix. The originals were left in place.

| File | Original location (before 2026-09-22 cleanup) | SHA-256 |
|---|---|---|
| `archive-pilot-input.json` (frozen list) | `tmp/cleanup-infrastructure-20260908/` | `c1f5586c7ad4bfb1f030a0b93c6eb215eb51bb1c1e088de6731d7619fd51dacc` |
| `pilot-verification.json` | `tmp/cleanup-infrastructure-20260908/` | `2c0d264107d72e1aef7402650ae06f7b85d3f6f1cafc7953ee3779603c4f6aa7` |
| `generated-residue-17-retention-approval-20260908.json` | `tmp/` | `90e1004ce8ad1b3bb312c30c965933f7448dd90b6ee19dcfc204481553380b2e` |
| `generated-residue-microbatch-retention-packet-20260908.json` | `tmp/` | `a2f55e61d8ce4b45ce41544b4d4c0d794ee595619f82e7196fa130bf82aee5d4` |
| `generated-residue-delete-readiness-packet-20260908.json` | `tmp/` | `6e86be3130b33a8a7cc1b5bbe9ab3b99e072da052b85cb42df063e8d94af7887` |
| `generated-residue-delete-readiness-packet-20260908.md` | `tmp/` | `cd612e3f4824a5e2f1bf68c578ec91d7d80fecde45176e3d9ce5d4728d0fbb9e` |
| `cleanup-archive-pilot-manifest-20260908.md` | `tmp/` | `f5d071147380129f5c2c283ff58819971ed33d4d5ba68391e7c3e3098138338d` |
| `bounded-auto-archive-last-report.json` (move receipt) | `tmp/` | `b1b5845814f7faedc802e05405ccfe2c01505f0f635062097c83aafdab2f98f6` |

## Delete tool

`scripts/generated_residue_delete_apply.py` reads its scope from this folder only (approval + frozen list, hash-bound). Tests: `scripts/test_generated_residue_delete_apply.py`.

- `build` — after the retention window, re-verifies all 17 archived files and writes `generated-residue-delete-manifest-<UTC>.json` here, valid 24 hours. Never deletes.
- `apply --manifest <path> --approved-sha256 <sha>` — read-only preflight.
- `apply ... --approval-reference "<owner approval>" --apply` — deletes only if every gate passes; writes `generated-residue-delete-receipt-<UTC>.json` here.

Permanent deletion requires Randall's second exact approval naming the manifest SHA-256. Nothing in this folder grants it.
