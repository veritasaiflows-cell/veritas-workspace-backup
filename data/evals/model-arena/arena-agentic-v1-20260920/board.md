# Board B - new-bank benchmark scoreboard

- Envelope: `arena-agentic-v1-20260920` (status: frozen)
- Keys sha256: `b663fb5351cfb006bd13462094c8527c4b44b0055665e42236edd96f04f881a5`
- Scope: 12 cases / 6 families / 2 structures per family / 600s per turn / 0 retries
- Recomputed by Veritas Main from the five archived `graded-results.json` files.

## Scoreboard

| model | strict | eligible | answered | timeouts | source sha256 |
|---|---|---|---|---|---|
| deepseek41flash | 1 | 11 | 11 | 1 | `e4d838d160ce2de84483210c8e4a266cc082ec1e87e4d0dbe3da4fec0c3d08e5` |
| glm53flash | 0 | 11 | 11 | 1 | `674ea66e2192fcd762b89560d899007ab52b4bf84161d5b8bed512feef4d1c7d` |
| sol | 0 | 12 | 12 | 0 | `885a5c53695fc203f54d7580bb8ce2f708ad19264fe66a3c5379a700d0bbc98f` |
| astra | 0 | 12 | 12 | 0 | `965ab7f2fc489e4e15228aca550b8c9a31a7c9f4fbfba6136bfefe2e5460ff7b` |
| spark13 | 1 | 11 | 11 | 1 | `7410e049c2c8993c0c6f599a2052a9b8e89bd0eaa3a0d025f593c68c2aa06475` |

Model ids requested:
- deepseek41flash: `ollama-cloud/deepseek-v4.1-flash:cloud`
- glm53flash: `ollama-cloud/glm-5.3-flash:cloud`
- sol: `openai/gpt-5.6-sol`
- astra: `openai/gpt-6-astra`
- spark13: `meta/muse-spark-1.3-contributor`

## Notes

- Eligibility canon: a trajectory is eligible iff its response is non-empty; parse_error json_empty denotes the operational timeout and is excluded from factual denominators.
- T4 ruling: T4 cases are solvable by derivation from the prompt; fixture-gated abstention scores zero by design.
- Timeouts are operational outcomes, never factual failures. Each timeout is a
  trajectory whose response was empty (`parse_error == "json_empty"`).

Timeout cases:
- deepseek41flash: `ad2161157921538089853178cdb459bbaed40f96fa77329a69e4be635c5af0bc`
- glm53flash: `ad2161157921538089853178cdb459bbaed40f96fa77329a69e4be635c5af0bc`
- sol: none (all 12 answered)
- astra: none (all 12 answered)
- spark13: `75c25de61ca18168d846f86e84e40de6b807213f547029876cb6ca2bcc99c2b4`

## Reproducibility

- Grading primitive: strict JSON parse + whole-object `strict_equal` against the frozen key.
- Grading runner: `reference/grader-frozen.py`
  (sha256 `ea14f559f022b1d9f438b62590bc0392e292139ad8503a5186da13320eb7241f`) - the lineage that produced these archived results.
- Rerunning the frozen grader over the archived responses reproduces every field except
  the top-level `timestamp_utc`, which is wall-clock by construction.

## Evidence

- `data/evals/model-arena/results/arena-agentic-v1-20260920/deepseek41flash-20260920/graded-results.json`
- `data/evals/model-arena/results/arena-agentic-v1-20260920/glm53flash-20260920/graded-results.json`
- `data/evals/model-arena/results/arena-agentic-v1-20260920/sol-20260920/graded-results.json`
- `data/evals/model-arena/results/arena-agentic-v1-20260920/astra-20260920/graded-results.json`
- `data/evals/model-arena/results/arena-agentic-v1-20260920/spark13-20260920/graded-results.json`
- `responses.json` per model (verbatim raw responses)
- `envelope.json`, `reference/keys.json`, `evidence-manifest.json`
