"""Command safety helpers for review-only proof runners."""
from __future__ import annotations

import shlex


FORBIDDEN_REVIEW_ONLY_TOKENS = (
    "--execute",
    "--apply",
    "--promote",
    "--import",
    "--submit",
    "--cancel",
    "--sell",
    "--buy",
    "--archive",
    "--delete",
    "--live",
    "order_card_request",
    "autonomous_paper_manager",
    "alpaca",
    "paper-position",
    "paper_position",
    "gateway",
    "openclaw.json",
    "db_lifecycle_archive_apply",
    "finance_sql_canon",
    " -c ",
    " ; ",
    "|",
    ">",
    "<",
    " rm ",
    " del ",
    "remove-item",
)


def command_is_review_only_safe(command: str, forbidden_tokens: tuple[str, ...] = FORBIDDEN_REVIEW_ONLY_TOKENS) -> bool:
    lowered = f" {command.lower()} "
    return not any(token in lowered for token in forbidden_tokens)


def parse_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=False)
    cleaned: list[str] = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in ("'", '"'):
            cleaned.append(part[1:-1])
        else:
            cleaned.append(part)
    return cleaned

