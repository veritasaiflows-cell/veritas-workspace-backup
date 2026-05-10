# Tmp Helper Implementation Research

## Verdict

Do **one** durable implementation now: fold the useful model-routing drift idea from `tmp/find_disallowed_model_refs.py` / `tmp/find_disallowed_openclaw_refs.py` into `scripts/workspace_governance_truth_check.py`.

Do **not** promote the six helpers as standalone scripts. They are scratch evidence, not supported tooling. The only truth-improving capability with a durable owner is a narrow active-control-surface model-policy check. The band dump and quick market-close helper are convenience surfaces and should stay unpromoted unless repeated operator use proves a real workflow need.

## Implementation recommendation

### Capability to preserve

Add a narrow `check_model_routing_policy(findings)` to `scripts/workspace_governance_truth_check.py`.

Recommended scope:
- Scan only active doctrine/control surfaces where stale routing language can cause live operational drift, such as `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, and maybe the current queue/registry files already owned by this validator.
- Flag exact disallowed routing strings/patterns, including:
  - `openai/gpt-5.5`
  - `chatgpt-5.5`
  - `agentRuntime.id: codex` / `agentRuntime.id = codex`
  - `runtime: codex` / `runtime = codex` when used as a config claim rather than prose
- Treat the allowed model IDs as `openai-codex/gpt-5.5`, `openai-codex/gpt-5.4`, and `openai-codex/gpt-5.3-codex`, matching `TOOLS.md`.
- Emit file, line, pattern label, and a short redacted snippet. Do not dump large file contents.
- Severity recommendation:
  - `critical` for exact disallowed provider/model IDs in active control surfaces.
  - `warning` for ambiguous generic `chatgpt` references only if the pattern is included at all; otherwise leave generic prose alone to avoid false positives.

Best home:
- `scripts/workspace_governance_truth_check.py`, because the issue is governance/control-surface truth, not market data and not portfolio validation.
- Update `scripts/README.md` governance-validator notes after implementation so this remains discoverable.

### What not to implement now

- Do **not** add `dump_bands.py` as a script. If the band summary keeps being useful, add a small `--summary` mode to `scripts/validate_portfolio_config.py` later. It should read only `tmp/portfolio-config.json`, summarize completeness/staleness, and not become a market-data or note-authority surface.
- Do **not** promote `market_close_quick.py`. Its useful idea is already better owned by `scripts/market_state_refresh.py` / `scripts/technical_refresh.py`, which carry freshness fields, warnings, and provenance. If a quick tape view is later needed, add a `--summary`/`--quick` display mode to `market_state_refresh.py` that uses the same artifact contract rather than creating a second yfinance truth surface.
- Do **not** replace `find_band_refs.py` / `find_model_refs.py` with durable scripts. Use `rg`, `workspace_index.py --search` if available, or one-off commands for broad retrieval.

## Rejected alternatives

1. **Promote all six helpers into `scripts/`** — rejected. This would add clutter and make scratch diagnostics look supported.
2. **Create a new `model_policy_check.py` script** — rejected. It duplicates governance-validator ownership and adds another command to remember.
3. **Scan all of `C:\Users\Veritas\.openclaw` for model strings** — rejected for the durable validator. It risks hitting config backups, transcripts, caches, and stale archives; it also widens privacy/logging exposure. Keep this as a one-off manual diagnostic only.
4. **Make `market_close_quick.py` a supported market tape** — rejected. It would become a second market-data truth surface with weaker freshness/provenance/error semantics than the existing finance chain.
5. **Make entry-band lookup a separate script** — rejected for now. If needed, it belongs as an optional view on the existing portfolio-config validator, not as another root-level helper.

## Freshness/truth boundaries to preserve

- `tmp/` is for generated/staged artifacts, not durable tooling.
- Governance checks should validate active operating truth, not historical memory noise.
- Market data must stay in the existing artifact chain with `generated_at_utc`, `last_trading_day`, source labels, warnings, and stale-after semantics.
- Convenience views must not imply owner approval, portfolio mutation authority, deployment-state changes, or note-layer truth.
- Do not print raw OpenClaw config, owner IDs, tokens, auth material, or broad outside-workspace scan results in validator output.
- Do not use the model-policy check to rewrite files automatically. It should report drift only.

## Smallest implementation plan

1. In `scripts/workspace_governance_truth_check.py`, add model-policy constants:
   - active surfaces to scan
   - disallowed regexes with labels
   - optional exclusion/comment rule for archived/historical references if any current active file intentionally documents stale terms
2. Add a small scanner helper that returns bounded hits: `{file, line, pattern, snippet}`.
3. Add `check_model_routing_policy(findings)` and call it from `build_report()` with the existing governance checks.
4. Keep output read-only and consistent with existing report structure.
5. Update `scripts/README.md` under `workspace_governance_truth_check.py` to mention model-routing/control-surface drift.
6. Leave `validate_portfolio_config.py`, `technical_refresh.py`, and `market_state_refresh.py` unchanged in this pass.

## Proof plan

Minimum proof for the bounded main-session pass:

```powershell
python -m py_compile scripts\workspace_governance_truth_check.py
python scripts\workspace_governance_truth_check.py --write --cli-timeout 1
```

If the scanner is factored as a pure helper, add one synthetic import check without creating a new test file:

```powershell
python -c "import sys; sys.path.insert(0, 'scripts'); import workspace_governance_truth_check as w; print('model policy helper import ok')"
```

Then inspect:
- `tmp/workspace-governance-truth-check.json` contains either no model-policy findings or bounded findings with file/line/pattern/snippet only.
- Existing critical findings are not hidden or downgraded.
- `scripts/README.md` documents the expanded validator scope.

## Residue / workflow recommendation

Open one workflow residue item after the validator change is proven:

- **Residue:** archive the six `tmp/*.py` helper files with a short manifest and hashes under `09. Archive/tmp-python-helpers - Archived/`, after owner approval for the archive/move.
- **Acceptance:** `tmp/` no longer contains durable Python helpers; governance validator still runs; archive manifest records why only the model-policy idea was promoted.
- **Do not queue yet:** a band-summary mode or quick-market summary. Revisit only after repeated operator demand, and implement as a mode on the existing owner script rather than a new standalone tool.
