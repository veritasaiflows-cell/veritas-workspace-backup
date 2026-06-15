"""apply_band_update.py

Human-gated band update applier.

Reads approved entries from tmp/band-proposals.json, applies them to
tmp/portfolio-config.json, and writes a formatted plain-text update
summary to tmp/band-update-log.txt for pasting into the Execution Board.

USAGE:

  Apply all proposals marked needs_review (review and confirm interactively):
      python scripts/apply_band_update.py

  Apply specific tickers only:
      python scripts/apply_band_update.py --tickers ETN NVDA

  Preview what would change without writing anything:
      python scripts/apply_band_update.py --dry-run

  Accept all needs_review proposals non-interactively (use with caution):
      python scripts/apply_band_update.py --all

RULES:
  - Only proposals with needs_review=true are eligible for application.
  - Proposals with skip_reason set are never applied.
  - Proposals with canonical_apply_eligible=false are never applied.
  - Each eligible proposal is shown for confirmation unless --all is passed.
  - Suggested values are applied as-is. If you want different levels,
    edit portfolio-config.json directly and update band_last_set manually.
  - After applying, update the Execution Board
    using the formatted summary written to tmp/band-update-log.txt.

Writes:
  tmp/portfolio-config.json     (updated entry_bands and band_last_set dates)
  tmp/band-update-log.txt       (formatted note-layer update summary)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from market_data_utils import atomic_write_json, atomic_write_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[2]
TMP = WORKSPACE / "tmp"
PROPOSALS_PATH = TMP / "band-proposals.json"
CONFIG_PATH = TMP / "portfolio-config.json"
LOG_PATH = TMP / "band-update-log.txt"


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        print(f"ERROR: {label} not found at {path}")
        print("  Run band_refresh.py first to generate proposals.")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    atomic_write_json(path, obj, indent=2, ensure_ascii=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply approved band proposals from band_refresh.py to portfolio-config.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/apply_band_update.py
  python scripts/apply_band_update.py --tickers ETN NVDA
  python scripts/apply_band_update.py --dry-run
  python scripts/apply_band_update.py --all
        """,
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="Apply only these tickers (must still be needs_review in proposals).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing anything.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Accept all needs_review proposals non-interactively.",
    )
    return parser.parse_args()


def confirm(prompt: str) -> bool:
    """Prompt user for y/n confirmation. Returns True if confirmed."""
    while True:
        resp = input(f"{prompt} [y/n]: ").strip().lower()
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Please enter y or n.")


def format_log_entry(
    ticker: str,
    old_low: float | None,
    old_high: float | None,
    old_stop: float | None,
    new_low: float | None,
    new_high: float | None,
    new_stop: float | None,
    applied_at: str,
    reasons: list[str],
    method: str | None = None,
    band_status: str | None = None,
) -> str:
    """Format a single ticker's update for the Execution Board."""
    is_initial = old_low is None and old_high is None and old_stop is None
    prior_label = "none (initial setup)" if is_initial else f"{old_low} – {old_high}  stop {old_stop}"
    lines = [
        f"### {ticker}",
        f"  Band update applied: {applied_at}",
        f"  Prior band:    {prior_label}",
        f"  Updated band:  {new_low} – {new_high}  stop {new_stop}",
    ]
    if method or band_status:
        lines.append(f"  Engine:        {method or 'unknown'} / {band_status or 'unknown'}")
    if reasons:
        lines.append("  Reasons:")
        for r in reasons:
            lines.append(f"    - {r}")
    lines.append("")
    return "\n".join(lines)


def resolve_applied_date(proposals: list[dict]) -> str:
    dates = sorted({p.get("data_date") for p in proposals if p.get("data_date")})
    if dates:
        return dates[-1]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def split_review_proposals(all_proposals: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split proposals into review, non-applyable review, and apply-eligible review sets."""
    review_proposals = [p for p in all_proposals if p.get("needs_review") and not p.get("skip_reason")]
    ineligible = [p for p in review_proposals if not p.get("canonical_apply_eligible", True)]
    eligible = [p for p in review_proposals if p.get("canonical_apply_eligible", True)]
    return review_proposals, ineligible, eligible


def main() -> None:
    args = parse_args()

    proposals_data = load_json(PROPOSALS_PATH, "band-proposals.json")
    config = load_json(CONFIG_PATH, "portfolio-config.json")

    all_proposals: list[dict] = proposals_data.get("proposals") or []

    # Filter to eligible proposals: needs_review=True, no skip_reason, and explicitly applyable.
    review_proposals, ineligible, eligible = split_review_proposals(all_proposals)

    if not eligible:
        if review_proposals:
            print("\nNo review proposals are currently eligible for application.")
            print("The following proposal(s) are review-only / non-applyable:")
            for p in ineligible:
                print(
                    f"  - {p.get('ticker')}: {p.get('entry_band_method') or 'unknown'} / "
                    f"{p.get('band_status') or 'unknown'}"
                )
        else:
            print("\nNo proposals currently flagged as needs_review.")
            print("Run band_refresh.py to regenerate proposals with fresh data.")
        print("Nothing to apply.\n")
        sys.exit(0)

    applied_date = resolve_applied_date(eligible)

    # Further filter by --tickers if specified
    if args.tickers:
        requested = {t.upper() for t in args.tickers}
        eligible = [p for p in eligible if p["ticker"].upper() in requested]
        missing = requested - {p["ticker"].upper() for p in eligible}
        if missing:
            print(f"\nWARNING: The following tickers were not found in eligible needs_review proposals: "
                  f"{', '.join(sorted(missing))}")
            blocked_requested = [
                p for p in ineligible
                if str(p.get("ticker") or "").upper() in missing
            ]
            for p in blocked_requested:
                print(
                    f"  - {p.get('ticker')} is review-only / non-applyable: "
                    f"{p.get('entry_band_method') or 'unknown'} / {p.get('band_status') or 'unknown'}"
                )
        if not eligible:
            print("Nothing to apply for the specified tickers.\n")
            sys.exit(0)

    sep = "=" * 74
    print(f"\n{sep}")
    mode_label = "DRY RUN — " if args.dry_run else ""
    print(f"  {mode_label}APPLY BAND UPDATES  --  data date {applied_date}")
    print(sep)
    print(f"\n  {len(eligible)} proposal(s) eligible for application.")
    if ineligible:
        print(f"  {len(ineligible)} review proposal(s) are non-applyable and will be skipped:")
        for p in ineligible:
            print(
                f"    - {p.get('ticker')}: {p.get('entry_band_method') or 'unknown'} / "
                f"{p.get('band_status') or 'unknown'}"
            )
    print("")

    applied: list[dict] = []
    skipped_by_user: list[str] = []

    for proposal in eligible:
        ticker = proposal["ticker"]
        old_low   = proposal.get("current_band_low")
        old_high  = proposal.get("current_band_high")
        old_stop  = proposal.get("current_stop")
        new_low   = proposal.get("suggested_band_low")
        new_high  = proposal.get("suggested_band_high")
        new_stop  = proposal.get("suggested_stop")
        reasons   = proposal.get("reasons") or []
        atr14     = proposal.get("atr14")
        close     = proposal.get("close")
        ma20      = proposal.get("ma20")
        band_set  = proposal.get("band_last_set")
        method    = proposal.get("entry_band_method")
        status    = proposal.get("band_status")

        is_initial = old_low is None and old_high is None and old_stop is None
        print(f"  {ticker}{'  [INITIAL SETUP — no band defined yet]' if is_initial else ''}")
        if is_initial:
            print(f"    Current band:   none (first-time proposal)")
        else:
            print(f"    Current band:   {old_low} – {old_high}  stop {old_stop}  (set {band_set})")
        print(f"    Suggested band: {new_low} – {new_high}  stop {new_stop}")
        print(f"    Method/status:  {method} / {status}")
        print(f"    Close: {close}  MA20: {ma20}  ATR14: {atr14}")
        for r in reasons:
            print(f"    ⚠  {r}")

        if new_low is None or new_high is None or new_stop is None:
            print(f"    ✗ Cannot apply — suggested values are incomplete (ATR fetch may have failed).\n")
            skipped_by_user.append(ticker)
            continue

        if args.dry_run:
            print(f"    [DRY RUN] Would apply: {new_low} – {new_high}  stop {new_stop}\n")
            continue

        if not args.all:
            proceed = confirm(f"    Apply suggested band for {ticker}?")
            if not proceed:
                print(f"    Skipped by user.\n")
                skipped_by_user.append(ticker)
                continue

        # Apply to config
        if ticker in config.get("entry_bands", {}):
            band = config["entry_bands"][ticker]
            band["low"]           = new_low
            band["high"]          = new_high
            band["stop"]          = new_stop
            band["label"]         = f"{new_low}–{new_high}"
            band["stop_label"]    = str(new_stop)
            band["band_last_set"] = applied_date
        else:
            config.setdefault("entry_bands", {})[ticker] = {
                "low": new_low,
                "high": new_high,
                "stop": new_stop,
                "label": f"{new_low}–{new_high}",
                "stop_label": str(new_stop),
                "band_last_set": applied_date,
            }

        applied.append({
            "ticker": ticker,
            "old_low": old_low,
            "old_high": old_high,
            "old_stop": old_stop,
            "new_low": new_low,
            "new_high": new_high,
            "new_stop": new_stop,
            "reasons": reasons,
            "method": method,
            "band_status": status,
        })
        print(f"    ✓ Applied: {new_low} – {new_high}  stop {new_stop}\n")

    if args.dry_run:
        print(f"{sep}")
        print(f"\n  DRY RUN complete. No files were modified.\n")
        return

    if not applied:
        print(f"\n  No changes applied.\n")
        return

    # Write updated config
    write_json(CONFIG_PATH, config)

    # Write note-layer update log
    log_lines = [
        f"# Band Update Log — {applied_date}",
        f"Generated by apply_band_update.py",
        f"Applied {len(applied)} update(s). Paste the relevant sections into",
        f"03. Portfolio/Execution Board.md",
        f"and update band_last_set references in the note layer.",
        "",
        "─" * 74,
        "",
    ]
    for a in applied:
        log_lines.append(
            format_log_entry(
                ticker=a["ticker"],
                old_low=a["old_low"],
                old_high=a["old_high"],
                old_stop=a["old_stop"],
                new_low=a["new_low"],
                new_high=a["new_high"],
                new_stop=a["new_stop"],
                applied_at=applied_date,
                reasons=a["reasons"],
                method=a.get("method"),
                band_status=a.get("band_status"),
            )
        )

    log_lines += [
        "─" * 74,
        "",
        "NEXT STEP: Open 03. Portfolio/Execution Board.md",
        "and update each listed ticker's entry band, stop, and band_last_set date",
        "to match the values above.",
        "",
        "Do NOT treat this log as the canonical record. The note layer is the",
        "source of truth. This file is a formatting aid only.",
    ]
    atomic_write_text(LOG_PATH, "\n".join(log_lines), encoding="utf-8")

    print(f"{sep}")
    print(f"\n  Applied {len(applied)} band update(s): {', '.join(a['ticker'] for a in applied)}")
    if skipped_by_user:
        print(f"  Skipped {len(skipped_by_user)}: {', '.join(skipped_by_user)}")
    print(f"\n  portfolio-config.json updated.")
    print(f"  Note-layer update summary written to: {LOG_PATH}")
    print(f"\n  NEXT STEP: Open the Execution Board and")
    print(f"  paste in the updated levels from tmp/band-update-log.txt.")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    main()
