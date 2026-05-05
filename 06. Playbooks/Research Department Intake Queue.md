# Research Department Intake Queue

## Purpose
Live operator queue for Workflow 25.

This is the intake and review board for names that need:
- new-name admission
- promotion review
- demotion review
- removal / bench review

Do not treat this as a deployment board.

## Queue states
- **Queued** - candidate identified, but review packet not assembled
- **Ready for review** - minimum evidence set is named and owner files are known
- **In review** - admission / promotion object is actively being filled out
- **Decided** - admit, defer, hold, promote, demote, remove, or bench decision is explicit

## Active pilot cases (WF25)

| Case | Review type | Candidate | Current state | Why this is the right pilot now | Owner surfaces | Honest no-go condition | Next action |
|---|---|---|---|---|---|---|---|
| WF25-P1 | New-name admission | **EOG** | Queued | Real near-term catalyst from the current cluster, not already in the tracked universe, and forces an honest decision on whether the energy sleeve needs a new high-quality upstream name instead of vague sector curiosity. | `04. Research/Coverage Universe.md`, `02. Markets/Watchlist.md`, `tmp/portfolio-config.json` | If EOG is only interesting because it is in the earnings cluster, or if it offers no cleaner role than XOM/CVX/LNG, defer instead of admitting. | Build the admission object and decide admit-to-watch, defer, or reject. |
| WF25-P2 | Promotion review | **GS** | Queued | Already live on the board as deployable-now tactical secondary to JPM, so this is a real lane question: should GS remain tactical, or has the evidence earned a promotion review toward a stronger standing? | `04. Research/Coverage Universe.md`, `02. Markets/Watchlist.md`, `03. Portfolio/Deployment Trigger Sheet.md`, `03. Portfolio/Technical Entry and Invalidation Sheet.md` | If GS is still just a tactical alternative to JPM without a distinct portfolio role, keep it tactical and say so plainly. | Build the promotion review object and decide promote, hold tactical, or demote. |

## Not chosen yet
- **LDOS** - credible alternate new-name defense admission case, but second-priority behind EOG for now
- **XOM** - credible demotion / requalification case, but more useful as a follow-on review after the cleaner GS lane question is resolved

## Rule
A pilot case is allowed to end in **defer** or **hold**. The point is honest desk procedure, not forced additions.
