# Evaluation Data Contracts

This directory stores reviewed or review-pending evaluation inputs. Generated scores belong under `tmp/`; compact cross-run history belongs under `data/state-history/`.

## Retrieval evaluation split

- `wf88-retrieval-fixtures.json` supports `scripts/retrieval_quality_scorecard.py`. That scorecard measures deterministic authority, freshness, precedence, parseability, and source-selection contracts over fixture-supplied candidates. It does not query a live index or rank embedding providers.
- `retrieval-live-source-registry.json` freezes the small non-sensitive corpus and chunking/provider contract for the isolated live pilot.
- `retrieval-live-gold.json` supplies 19 draft fixtures across exact, paraphrase, named-distractor, and absent classes for `scripts/retrieval_live_eval.py`.

The live gold set remains `draft_review_required`. Provider promotion is blocked until sole-relevance labels receive human source-open review and abstention thresholds are calibrated on a separate sealed calibration set. Never tune thresholds on the four absent evaluation fixtures.

