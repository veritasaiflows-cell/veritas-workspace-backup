# Session: 2026-04-26 08:55 UTC — Generalized entry-band tool

- **Source**: Cowork desktop, Claude (audit/advisory layer per CLAUDE.md)
- **Trigger**: Randall uploaded `etn_entry_band_1.jsx` (an ETN-only React component with hardcoded monthly OHLC and ETN-specific macro regimes) and asked to make it a program for any ticker that fits the workspace.

## What was built

Two-file pair following the existing `scripts/` conventions and matching the same yfinance + JSON + portfolio-config pattern used by `band_refresh.py` and `technical_refresh.py`:

- `scripts/entry_band_fetch.py` — CLI fetcher. `python scripts/entry_band_fetch.py TICKER [--interval 1d|1wk|1mo] [--years N] [--start YYYY-MM-DD] [--html] [--open] [--quiet]`. Pulls OHLC from yfinance, tags each bar with the workspace macro-regime catalogue, looks up the vault preferred band from `tmp/portfolio-config.json` (`entry_bands.{TICKER}` schema as written by `apply_band_update.py`), writes JSON to `tmp/entry-band-data/{TICKER}.json`, and with `--html` produces a self-contained interactive viewer at `generated documents/entry-bands/{TICKER}_entry_band.html`. Ticker symbol is regex-validated; rejected with rc=2 on suspicious input.
- `scripts/entry_band_viewer.jsx` — Generalized React component, ticker-agnostic. Reads from `props.data` or `window.__ENTRY_BAND_DATA__`. Same three band methods as the original (SMA Envelope, Keltner Channel, Dual MA Band), same backtest engine (1/3/6 month forward returns, drawdowns, win-rate by regime), same dark-theme UI. Adds: vault preferred-band overlay (purple ReferenceLines for low/high and red for stop, from portfolio-config), graceful header for stop-only or label-only bands (e.g. LMT "Post-earnings rebuild only"), forward-period scaling for daily/weekly intervals (21/63/126 trading days for daily, 4/13/26 weeks for weekly), regime tagging that handles daily YYYY-MM-DD bars by month-prefix matching.

## How the HTML viewer renders without a build step

Fetcher inlines the JSX into the HTML inside a `<script type="text/babel" data-type="module" data-presets="react">` block. The `export default function EntryBandViewer` declaration is stripped to `function EntryBandViewer` so the bootstrap render call at the end can reference it as a module-level identifier. React 18, react-dom, react/jsx-runtime, and recharts 2.12 resolve through a `<script type="importmap">` that points at esm.sh (recharts uses `?external=react,react-dom` so it shares the importmap-resolved React). Babel-standalone 7.24 handles JSX → JS at load time. No npm, no bundler, no localhost — opens by double-click in any modern browser.

## Macro regime catalogue

Periods extended through 2026-12 to match the current Portfolio Snapshot read of late-cycle, restrictive, resilient, selective risk-on (tagged as continued tightening bias). The catalogue lives at module level in `entry_band_fetch.py` and is embedded into each per-ticker JSON bundle so the viewer renders the regime timeline strip and regime filter pills without any second round-trip.

## Verification

End-to-end run inside the sandbox (with stubbed yfinance, since the sandbox has no network egress for pip):

- ETN with full vault band: JSON contains `preferred_band={low:383.41, high:406.93, stop:371.65, set:'2026-04-26'}`. HTML embeds the band, references esm.sh CDN, contains `function EntryBandViewer` with no `export default` leakage. (47.6 KB output.)
- LMT with stop-only band (`low/high` null): preferred_band correctly carries `stop=581.5` and `label='Post-earnings rebuild only'`; HTML header falls back to the label form rather than rendering "$—–$—".
- UNKN (not in vault): `preferred_band=null`, no overlay drawn.
- Regime tagging spot-checks: 2015-03→low_rate_low_vol, 2018-11→vol_spike_crisis, 2020-03→vol_spike_crisis, 2023-08→peak_hold, 2026-02→tightening.
- Bad ticker (`abc/../etc/passwd`) rejected with rc=2 before any fetch.

## File-truncation incident

While editing, the Edit tool reported success on `entry_band_fetch.py` but the on-disk file was actually truncated mid-statement at `json_path.wr` (414 → would-have-been 430+ lines). Same pattern Randall already documented in 2026-04-25 memory note, and the same workaround applied: rewrote the full file via bash heredoc (`cat > file << 'EOF'`), which has no such limit. Worth re-flagging that for any rewrite of a script file > ~14 KB, bash heredoc is the safer path; Edit/Write are fine for small targeted changes.

## Authority

Acted on standing authority per CLAUDE.md (workspace enhancement layer). Two new files added under `scripts/`. No existing files modified. No portfolio-config or note-layer files touched. Outputs of test runs left at `tmp/entry-band-data/{ETN,LMT,UNKN}.json` and `generated documents/entry-bands/{ETN,LMT}_entry_band.html` as a working sample — these can be deleted any time without affecting the tool itself.

## How Randall uses this

```
# JPM, daily bars over 5 years, with vault-band overlay, open in browser
python scripts/entry_band_fetch.py JPM --interval 1d --years 5 --html --open

# Watchlist sweep
for sym in MSFT JPM GOOG ETN NVDA LMT BRK-B XOM; do
  python scripts/entry_band_fetch.py "$sym" --html --quiet
done
```

## Recommended follow-ups (not done this session)

- A 5-line wrapper `scripts/entry_band_sweep.py` that walks the tracked-universe list from `portfolio-config.json` and renders an HTML for each, so the morning chain can produce a fresh batch.
- Index symbols (`^GSPC`, `^VIX`) work via the validator regex, but yfinance index data through `Ticker(...).info` has limited fields; the JSON's `name` may fall back to the symbol — acceptable, not a defect.
- Optional second pass: emit a one-line summary row per ticker (current band position pct, distance to vault low, distance to vault stop) into a sweep CSV at `tmp/entry-band-summary.csv` for the daily executive brief.
