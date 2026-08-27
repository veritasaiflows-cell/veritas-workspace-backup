# SEC Skill Venv Footprint Plan - 2026-07-02

## Conclusion

Keep `skills/sec/.venv` in place for now.

The venv is large, but it is not dead residue. Current SEC evidence tooling still documents and uses `skills\sec\.venv\Scripts\python.exe` for review-only SEC/EDGAR packet generation. Deleting, moving, or rebuilding it now would risk breaking the official-source evidence path for WF65/WF66 without a proven replacement.

Recommended action: harden documentation and proof first, then consider relocation only through a separate owner-approved apply lane with backup, rollback, and post-move smoke proof.

## Scope

This P2 pass was reference-reviewed and proposal-only.

Reviewed:
- `skills/sec/SKILL.md`
- `skills/sec/requirements.txt`
- `skills/sec/scripts/sec_finance_ai.py`
- `skills/sec/_meta.json`
- `skills/sec/agents/openai.yaml`
- `08. Audits/ClawHub SEC Tooling Adoption Audit - 2026-05-17.md`
- `08. Audits/Skill Consolidation Matrix - 2026-07-02.md`
- SEC-related `scripts/README.md` section
- current `.venv` footprint and import behavior

Out of scope:
- no `.venv` deletion, move, rebuild, or package update
- no live SEC network retrieval
- no skill body edits
- no Skill Workshop proposal lifecycle action
- no finance canon, portfolio, capital, paper/live/account, config/runtime, external-delivery, or archive/delete action

## Evidence

| Check | Result |
|---|---|
| Footprint | `skills/sec/.venv` has 4,591 total entries; file-length sum is 103,176,099 bytes. |
| Python runtime | `.venv` is Python 3.13.13, created from `C:\Users\Veritas\AppData\Local\Programs\Python\Python313\python.exe`. |
| Installed direct deps | `pandas`, `pydantic`, `requests`, `beautifulsoup4`, `lxml`, `python-dateutil`, plus transitive deps. |
| Pip | `pip 26.0.1` inside `skills/sec/.venv`. |
| Import proof | Local venv import succeeded; `Tools` exposes 17 callable methods. |
| User-Agent | `SEC_HEADERS["User-Agent"]` is `Veritas OpenClaw Research veritasaiflows@gmail.com`, not the packaged placeholder. |
| Static risk scan | No hits for subprocess/shell/delete patterns or non-GET request methods in `skills/sec/scripts/sec_finance_ai.py`. |
| Compile proof | `python -m py_compile skills\sec\scripts\sec_finance_ai.py` passed. |
| Current coupling | `scripts/README.md` still instructs `skills\sec\.venv\Scripts\python.exe scripts\sec_evidence_packet.py ...`. |
| Git behavior | The venv has its own `.gitignore` with `*`, so the dependency tree is ignored locally. |

## Findings

1. `skills/sec/.venv` is currently required by the documented SEC evidence path. The strongest live coupling is `scripts/README.md`, which uses the venv interpreter for `sec_evidence_packet.py`.
2. The security posture is acceptable for review-only official-source evidence. Static scan found GET-style SEC retrieval and no obvious subprocess, shell, delete, or non-GET request behavior.
3. The dependency footprint is real bloat but bounded. It is about 103 MB and stays ignored by the venv-local `.gitignore`.
4. The current docs are stale in two ways: `skills/sec/SKILL.md` still uses Linux-first path examples, and the SEC section of `scripts/README.md` contains tombstoned legacy JSON-path placeholders in some proof commands.
5. `skills/sec/SKILL.md` has an odd number of Markdown code fences. The final quick-validation block appears unclosed.
6. The dependency set is old enough to deserve a rebuild/lockfile review later, but not urgent enough to justify immediate mutation while the evidence path is live and functioning.

## Decision

Do not delete, move, or rebuild `skills/sec/.venv` now.

Treat the current state as `keep active, document, and harden`. The venv should remain classified as a review watchlist item, not a cleanup target, until a replacement invocation path is proven.

## Recommended Next Actions

P2A - Skill Workshop hygiene proposal, owner-gated before apply:
- close the unclosed code fence in `skills/sec/SKILL.md`
- replace Linux-only invocation examples with Windows-first workspace commands
- preserve the SEC User-Agent safety gate
- preserve review-only/no portfolio-canon-trade authority boundaries

P2B - Documentation repair, safe after explicit approval:
- fix the SEC `scripts/README.md` proof commands that currently contain tombstoned legacy JSON placeholder text
- keep the bounded smoke-test command as the preferred validation example

P2C - Add a small SEC env audit validator:
- verify venv interpreter exists
- verify required packages import
- verify `SEC_HEADERS` is not placeholder
- verify `Tools` method count is at least 17
- verify `skills/sec/SKILL.md` code fences are balanced
- write proof under `tmp/`

P2D - Relocation/rebuild plan, owner-gated and not recommended yet:
- dry-run a new external venv path outside `skills/sec`
- prove `sec_evidence_packet.py` works through the replacement interpreter
- update docs and any hard-coded references
- keep backup/rollback instructions
- only then remove the old venv after exact approval

## Stop Lines

Stop before any:
- `.venv` deletion, move, rebuild, dependency update, or archive
- live SEC retrieval without User-Agent confirmation
- skill-body mutation outside Skill Workshop
- finance canon, portfolio, sizing, capital, paper/live/account, brokerage, config/runtime, credential, startup, channel, or external action

## Acceptance Proof For Any Future Apply

Before a future SEC `.venv` cleanup apply can be called complete:

1. `openclaw skills check --json`
2. `python scripts\skill_workshop_body_guard.py --write --validate`
3. SEC env validator, if implemented
4. `python -m py_compile skills\sec\scripts\sec_finance_ai.py`
5. local import/function listing from the selected interpreter
6. bounded SEC smoke-test packet and validator proof, only after User-Agent is confirmed
7. `git diff --check`
8. lane register closed with proof and active lanes back to zero

## Authority

This audit is review-only. It is not approval to delete, move, rebuild, archive, or externally publish anything. SEC evidence remains official-source input only; it does not authorize portfolio/canon mutation, owner approval, sizing/allocation, capital deployment, paper/live execution, brokerage/account action, money movement, config/runtime mutation, or external delivery.
