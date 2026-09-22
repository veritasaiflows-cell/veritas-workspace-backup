# Board B - superseding scoreboard (2026-09-21)

- Envelope: `arena-agentic-v1-20260920`, overlay `arena-agentic-v1-20260920-overlay-r2`
- **Supersedes** `arena-agentic-v1-20260920/board.md`, which is sealed and hash-pinned in
  `evidence-manifest.json` and was therefore left byte-identical rather than edited.
- Withdrawal record: `pre-overlay-withdrawal-20260921.json`

## Live board - overlay-r2 only

Only these runs are citable as capability evidence on this bank.

| run | transport | strict | answered | timeouts |
|---|---|---|---|---|
| `spark13-overlay-r2-20260920` | collectors | **12/12** | 12 | 0 |
| `deepseek41flash-overlay-r2-20260920` | collectors | **11/12** | n/r | n/r |
| `deepseek41flash-overlay-r2-cli-chain-20260920` | CLI-lab-pipe | **10/12** | 10 | 2 |
| `glm53flash-overlay-r2-cli-20260920` | CLI-lab-pipe | **10/12** | 11 | 1 |
| `minimax-m3-overlay-r2-20260920` | collectors | **10/12** | 12 | 0 |
| `glm53flash-chain-overlay-r2-cli-20260920` | CLI-lab-pipe | **9/12** | 10 | 2 |
| `glm53flash-overlay-r2-20260920` | collectors | **4/12** | 11 | 1 |

Strict range: [4, 9, 10, 11, 12] — the bank discriminates.

## Withdrawn - pre-overlay, NOT capability evidence

These runs predate `overlay/key-shapes.json`. The required JSON key names were never
published to candidates, so a correct answer under a different field name scored zero.
**Do not cite these as model scores or quote them as differentiators.**

| run | strict | answered | status |
|---|---|---|---|
| `astra-20260920` | ~~0/12~~ | n/r | WITHDRAWN |
| `deepseek41flash-20260920` | ~~1/12~~ | n/r | WITHDRAWN |
| `deepseek41flash-chain-20260920` | ~~0/12~~ | 12 | WITHDRAWN |
| `glm53flash-20260920` | ~~0/12~~ | n/r | WITHDRAWN |
| `glm53flash-chain-20260920` | ~~0/12~~ | 12 | WITHDRAWN |
| `minimax-m3-20260920` | ~~0/12~~ | 12 | WITHDRAWN |
| `sol-20260920` | ~~0/12~~ | n/r | WITHDRAWN |
| `spark13-20260920` | ~~1/12~~ | n/r | WITHDRAWN |

Strict range: [0, 1] — no range, ranks nothing.

## Why the grader is exonerated

Two free controls were run against the frozen grader on 2026-09-21:

- **Oracle** (each hidden key serialized verbatim): **12/12** strict, 12/12 clean, 0 contaminated, 0 invented.
- **Null** (empty response every case): **0/12** strict, 12 operational timeouts — correctly classified operational, not factual.

The grader passes its own key and floors an empty subject. The pre-overlay floor was an
envelope-publication defect, already fixed by overlay-r2 — not a grader defect.

## Known gaps

- **Astra and Sol have no valid score on this bank.** Their only runs are pre-overlay and
  withdrawn. Owner declined re-dispatch on 2026-09-21 (OpenAI usage low). They are absent
  from the live board, not scored zero.
- `calibration-board-enh-20260920.json` mixes pre-overlay and overlay-r2 rows in one table
  with no envelope column. It is a dated seal and was not edited; treat it as superseded.

No routing, configuration, role, capital, or execution authority follows from this board.
