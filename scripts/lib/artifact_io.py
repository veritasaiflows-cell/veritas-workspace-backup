"""Compatibility wrappers for JSON artifact IO."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


def load_dict(path: str | Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def write_json(path: str | Path, payload: Any) -> None:
    atomic_write_json(path, payload)

