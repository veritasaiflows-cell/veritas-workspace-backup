#!/usr/bin/env python3
"""Shared WF78 scaleout batch manifest helpers.

The helpers centralize batch labels, rank windows, source-pool ordering, and
artifact paths so WF78 scaleout can use one repeatable pipeline instead of
per-batch cloned scripts.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"
STATE = ROOT / "state"

DEFAULT_MANIFEST = STATE / "workflows" / "wf78-scaleout-batch-manifest.json"
DEFAULT_SOURCE_POOL = DATA / "finance" / "wf78-101-200-candidate-source-v1.json"
DEFAULT_UNIVERSE = DATA / "finance" / "universe-v1.json"
DEFAULT_READINESS_INDEX = TMP / "wf78-sql-readiness-index.json"

SCHEMA = "veritas.wf78_scaleout_batch_manifest.v1"
BATCH_RE = re.compile(r"^(\d+)-(\d+)$")

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


@dataclass(frozen=True)
class BatchSpec:
    batch_label: str
    rank_start: int
    rank_end: int
    candidate_rank_start: int
    candidate_rank_end: int
    source_artifact: Path
    provider_validation: Path
    owner_decision_packet: Path
    import_gate: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def symbol(value: Any) -> str:
    return str(value or "").upper().strip().replace(".", "-")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_batch_label(label: str) -> tuple[int, int]:
    match = BATCH_RE.match(str(label or "").strip())
    if not match:
        raise ValueError(f"invalid batch label: {label!r}")
    start = int(match.group(1))
    end = int(match.group(2))
    if end < start:
        raise ValueError(f"batch end before start: {label}")
    if end - start + 1 != 100:
        raise ValueError(f"batch must contain exactly 100 ranks: {label}")
    if start < 201 or end > 500:
        raise ValueError(f"batch outside WF78 201-500 scaleout range: {label}")
    if start % 100 != 1 or end % 100 != 0:
        raise ValueError(f"batch must align to 100-name boundaries: {label}")
    return start, end


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = load_dict(path)
    if not payload:
        raise FileNotFoundError(rel(path))
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"unexpected WF78 batch manifest schema: {payload.get('schema')}")
    return payload


def batch_specs(manifest: dict[str, Any] | None = None) -> list[BatchSpec]:
    payload = manifest or load_manifest()
    specs: list[BatchSpec] = []
    baseline = int(payload.get("baseline_count") or 200)
    for raw in as_list(payload.get("batches")):
        row = as_dict(raw)
        label = str(row.get("batch_label") or "")
        start, end = parse_batch_label(label)
        candidate_start = int(row.get("candidate_rank_start") or (start - baseline))
        candidate_end = int(row.get("candidate_rank_end") or (end - baseline))
        if candidate_end - candidate_start + 1 != 100:
            raise ValueError(f"candidate rank window must contain 100 rows: {label}")
        specs.append(
            BatchSpec(
                batch_label=label,
                rank_start=start,
                rank_end=end,
                candidate_rank_start=candidate_start,
                candidate_rank_end=candidate_end,
                source_artifact=resolve(row["source_artifact"]),
                provider_validation=resolve(row["provider_validation"]),
                owner_decision_packet=resolve(row["owner_decision_packet"]),
                import_gate=resolve(row["import_gate"]),
            )
        )
    return specs


def batch_spec(label: str, manifest: dict[str, Any] | None = None) -> BatchSpec:
    parse_batch_label(label)
    for spec in batch_specs(manifest):
        if spec.batch_label == label:
            return spec
    raise KeyError(f"batch {label} is not registered in {rel(DEFAULT_MANIFEST)}")


def active_universe_tickers(universe_path: Path = DEFAULT_UNIVERSE) -> set[str]:
    universe = load_dict(universe_path)
    return {
        symbol(row.get("ticker"))
        for row in as_list(universe.get("entries"))
        if isinstance(row, dict) and row.get("active") is not False and row.get("ticker")
    }


def ordered_scaleout_candidates(source_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the stable 201-500 candidate order.

    The first 100 rows use the already-vetted selected seed. Remaining rows use
    the durable source-pool order. Current-universe duplicates stay excluded by
    the source registry's `already_in_current_100` flag so future imports do
    not shift later batch windows.
    """
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    selected = [
        row for row in as_list(source_payload.get("selected_101_200"))
        if isinstance(row, dict) and row.get("ticker")
    ]
    selected.sort(key=lambda row: int(row.get("selected_rank") or 999999))
    for row in selected:
        ticker = symbol(row.get("yfinance_symbol") or row.get("ticker"))
        if ticker and ticker not in seen:
            seen.add(ticker)
            enriched = dict(row)
            enriched["scaleout_candidate_rank"] = len(ordered) + 1
            ordered.append(enriched)

    for row in as_list(source_payload.get("candidates")):
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        ticker = symbol(row.get("yfinance_symbol") or row.get("ticker"))
        if not ticker or ticker in seen:
            continue
        if row.get("already_in_current_100") is True:
            continue
        if row.get("candidate_group") == "duplicate_or_current_100":
            continue
        if row.get("identity_complete") is not True:
            continue
        seen.add(ticker)
        enriched = dict(row)
        enriched["scaleout_candidate_rank"] = len(ordered) + 1
        ordered.append(enriched)
    return ordered


def batch_candidates(spec: BatchSpec, source_payload: dict[str, Any], active_tickers: set[str] | None = None) -> list[dict[str, Any]]:
    active = active_tickers or active_universe_tickers()
    rows = ordered_scaleout_candidates(source_payload)
    selected: list[dict[str, Any]] = []
    for row in rows:
        rank = int(row.get("scaleout_candidate_rank") or 0)
        if spec.candidate_rank_start <= rank <= spec.candidate_rank_end:
            ticker = symbol(row.get("yfinance_symbol") or row.get("ticker"))
            enriched = dict(row)
            enriched["batch_label"] = spec.batch_label
            enriched["batch_rank_start"] = spec.rank_start
            enriched["batch_rank_end"] = spec.rank_end
            enriched["scaleout_candidate_rank"] = rank
            enriched["target_rank"] = spec.rank_start + (rank - spec.candidate_rank_start)
            enriched["already_active_in_universe"] = ticker in active
            selected.append(enriched)
    return selected


def artifact_meta(path: Path, artifact_type: str, required: bool = True) -> dict[str, Any]:
    payload = load_dict(path) if path.suffix.lower() == ".json" and path.exists() else {}
    stat = path.stat() if path.exists() else None
    return {
        "artifact_type": artifact_type,
        "path": rel(path),
        "exists": path.exists(),
        "required": required,
        "sha256": sha256_file(path),
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "size_bytes": stat.st_size if stat else None,
    }


def batch_artifacts(spec: BatchSpec) -> dict[str, str]:
    return {
        "source_artifact": rel(spec.source_artifact),
        "provider_validation": rel(spec.provider_validation),
        "owner_decision_packet": rel(spec.owner_decision_packet),
        "import_gate": rel(spec.import_gate),
    }
