# Capital-base sizing proposal — review only

Generated: 2026-05-18 post-close context  
Scope: proposal packet only; no canonical mutation, no order staging, no paper/live trading authority.

## Source posture

- Portfolio Snapshot capital base assumption: roughly **$5k to $10k**.
- Target cash: **10% retained**.
- Draft weights are **model/planning weights**, not live allocations.
- No live positions have been established.
- Risk Rules: Tier 1 **8%-12%**, Tier 2 **4%-7%**, Tier 3/speculative **1%-3%**, normal single-name ceiling **15%**, sector cap **25%**, default speculative sleeve up to **5% total**.
- Current execution truth: ETN is the only deployable-now name, but still manual-only / owner-gated; GOOG, MSFT, GS, NVDA are not deployable-now; JPM and LMT are do-not-touch / below-stop; ITA is review-only ETF candidate.

## Capital scenarios

| Scenario | Total capital | Cash retained (10%) | Investable capital (90%) | Normal max single-name cap (15% of account) | Max cap as % of investable capital |
|---|---:|---:|---:|---:|---:|
| Small base | $5,000 | $500 | $4,500 | $750 | 16.7% |
| Larger base | $10,000 | $1,000 | $9,000 | $1,500 | 16.7% |

**Interpretation:** the 15% normal cap is account-level. With 10% cash retained, a full 15% single-name position consumes 16.7% of deployable capital, so concentration discipline matters more than the headline dollar amount suggests.

## Tier target dollars and tranche math

### $5,000 account / $4,500 investable

| Sizing bucket | Target % of account | Target dollars | One-tranche math | Two-tranche math |
|---|---:|---:|---:|---:|
| Tier 1 | 8%-12% | $400-$600 | $400-$600 starter/full target | $200-$300 initial + $200-$300 add |
| Tier 2 | 4%-7% | $200-$350 | $200-$350 starter/full target | $100-$175 initial + $100-$175 add |
| Tier 3 / speculative | 1%-3% | $50-$150 | $50-$150 starter/full target | $25-$75 initial + $25-$75 add |
| Normal max single name | 15% | $750 | Do not exceed without explicit stretch review | If staged, keep cumulative <= $750 |

### $10,000 account / $9,000 investable

| Sizing bucket | Target % of account | Target dollars | One-tranche math | Two-tranche math |
|---|---:|---:|---:|---:|
| Tier 1 | 8%-12% | $800-$1,200 | $800-$1,200 starter/full target | $400-$600 initial + $400-$600 add |
| Tier 2 | 4%-7% | $400-$700 | $400-$700 starter/full target | $200-$350 initial + $200-$350 add |
| Tier 3 / speculative | 1%-3% | $100-$300 | $100-$300 starter/full target | $50-$150 initial + $50-$150 add |
| Normal max single name | 15% | $1,500 | Do not exceed without explicit stretch review | If staged, keep cumulative <= $1,500 |

## Fractional-share versus whole-share-only consequences

Latest available close/band context is from 2026-05-18 artifacts unless noted.

| Name | Status / band context | Close | Relevant band / stop | Draft/tier context | Fractional-share allowed | Whole-share-only consequence at $5k | Whole-share-only consequence at $10k |
|---|---|---:|---|---|---|---|---|
| ETN | Deployable now, manual-only, first priority; in band | $381.87 | $364.48-$407.95 / stop $344.71 | Draft 7%; config Tier 1 | Can size cleanly: $350-$600 at $5k, $700-$1,200 at $10k; two-tranche possible. | 1 share = 7.6% of account and 85% of draft 7% target; a two-tranche starter needs fractions. | 2 shares = $763.74 / 7.6%, just under Tier 1 lower bound; 3 shares = $1,145.61 / 11.5%, acceptable Tier 1 but larger than 7% draft tactical weight. |
| MSFT | Wait / above-band / staged manual candidate; no live trigger | $423.54 | $389.64-$412.56 / stop $378.18 | Draft 10%; Tier 1; Tech cap sequencing required | Can plan a small starter only after band/Tech sequencing clears. | 1 share = 8.5%, inside Tier 1 but too large for a cautious two-tranche starter; cannot implement 40/60 or small starter without fractions. | 2 shares = $847.08 / 8.5%, workable Tier 1; 1-share starter = 4.2%, but action remains blocked. |
| GOOG | Almost deployable; above band / no chase | $393.11 | $354.05-$377.00 / stop $332.16 | Draft 10%; Tier 1 | Can wait for band and size gradually without forcing full shares. | 1 share = 7.9%, slightly below Tier 1 and near a full starter; two-tranche plan requires fractions. | 2 shares = $786.22 / 7.9%, slightly below Tier 1; 3 shares = $1,179.33 / 11.8%, Tier 1 but aggressive if only a starter. |
| GS | Almost deployable; above band / secondary to JPM | $946.36 | $894.64-$935.77 / stop $866.76 | Draft 7%; Tier 2 | Fractions are effectively required for intended Tier 2 sizing. | 1 share = 18.9%, above normal 15% cap and far above Tier 2; whole-share-only should defer. | 1 share = 9.5%, under normal cap but above Tier 2 7% ceiling and above 7% draft weight; use fractions or defer unless explicitly re-tiered. |
| JPM | Do not touch / below stop; trigger not live | $300.73 | Trigger $306.82-$318.12 / stop $301.17 | Draft 14%; Tier 1, but blocked | Fractions can support future staged sizing after reclaim; no action now. | 1 share = 6.0%, below Tier 1; 2 shares = 12.0%, Tier 1 but too much for initial repair/reclaim confirmation; wait. | 3 shares = $902.19 / 9.0%, clean Tier 1 if future trigger clears; 2-share starter = 6.0%, below Tier 1 but practical. |
| LMT | Do not touch / below-stop repair | $528.31 | $548.51-$582.27 / stop $531.63 | Draft 10% suspended; Tier 1 only after repair | Fractions would allow placeholder/watch sizing if ever reapproved, but current state blocks deployment. | 1 share = 10.6%, mechanically Tier 1 but invalid because below-stop repair; whole-share-only would force too much into a broken setup. | 2 shares = $1,056.62 / 10.6%, mechanically Tier 1; still blocked. |
| ITA | Review-only ETF candidate; in band, no allocation authority | $220.23 | $212.15-$223.44 / stop $205.88 | No draft weight; Defense gap candidate | Fractions helpful but less critical; ETF price permits small starters. | 1 share = 4.4%, Tier 2-sized ETF starter; 2 shares = 8.8%, Tier 1-like and likely too large before model approval. | 2 shares = 4.4%, Tier 2 starter; 4 shares = 8.8%, Tier 1-like defense ETF allocation if later approved. |
| NVDA | Wait / no chase; above band; earnings risk freeze | $222.32 | $197.01-$210.84 / stop $190.10 | Draft 5%; Tier 2 | Fractions allow correct $200-$350 / $400-$700 Tier 2 sizing; no action until event/band clears. | 1 share = 4.4%, workable Tier 2; 2 shares = 8.9%, too large for Tier 2 and Tech/AI crowding. | 2 shares = $444.64 / 4.4%, clean Tier 2; 3 shares = $666.96 / 6.7%, upper Tier 2. |

## Practical sizing framework for this capital base

1. **Minimum viable position:** prefer **$250 minimum** for single-name positions when fractional shares are available; below that, tracking and decision cost may exceed portfolio impact. For ETFs or speculative/watch sleeves, **$100-$250** can be viable if the purpose is diversification or learning, not conviction expression.
2. **Initial starter tranche:** use **about half of intended target size**. Practically: $250-$300 starters for $5k Tier 1 names, $400-$600 starters for $10k Tier 1 names; $100-$175 / $200-$350 for Tier 2 names. Add the second tranche only after the written band, stop, catalyst, and concentration gates remain clean.
3. **Fractional-share assumption:** the current draft model is most coherent if fractional shares are allowed. Without fractions, several intended Tier 1/Tier 2 weights become lumpy or impossible, especially GS at both capital bases and staged ETN/MSFT/GOOG at $5k.
4. **Whole-share-only rule of thumb:** defer any single name where one share is either above the target tier range or above the normal cap. At $5k, GS should be deferred or replaced by a cheaper ETF/fractional exposure. At $10k, GS still exceeds Tier 2 sizing as one whole share, so use fractions or re-tier explicitly before any future allocation.
5. **High-price single-name substitution:** when whole-share-only sizing distorts risk, use ETFs or lower-priced substitutes only after a separate model/sleeve approval. For the Defense gap, ITA is mechanically easier than LMT, but it remains review-only and requires look-through concentration acceptance.
6. **Effect on draft weights:** the draft weights should remain planning weights, not orderable allocations. For a $5k base, many 7%-10% weights translate into one-share-or-less positions; therefore model implementation should emphasize staged starters, fractions, and fewer simultaneous names rather than trying to populate every draft row immediately.

## Authority boundary and acceptance proof before any canonical apply

This packet does **not** authorize trades, paper orders, live orders, account actions, cash movement, brokerage actions, or canonical note edits. It is review-only sizing analysis.

Before the main session applies any Portfolio Snapshot / Risk Rules / config change, required proof should include:

- Explicit owner or standing-authority reference for the exact sizing/category change.
- Exact target files and exact old/new text or validator-backed patch material.
- Validation that the change is within workspace portfolio/canon maintenance scope only.
- Fresh source check for Portfolio Snapshot, Execution Board, Risk Rules, portfolio-config, deployment-check, and trigger-sheet.
- Concentration proof for single-name, sector, speculative sleeve, and Tech + AI-power correlated sleeve.
- Clear statement that any resulting allocation remains a model/planning allocation and does not imply execution authority.

## Bottom line recommendation

Use a **fractional-share, two-tranche framework** as the default for the $5k-$10k capital base. Treat **$250-$600** as the practical initial starter zone depending on account size and tier. Whole-share-only implementation should be narrow and selective: ETN, MSFT, GOOG, JPM, ITA, and NVDA can sometimes fit, but GS is impractical for intended Tier 2 sizing and LMT is currently blocked regardless of share math. Do not try to implement all draft weights at once; prioritize eligible names, preserve 10% cash, and keep high-price/blocked names as planning-only until authority and gates are clean.
