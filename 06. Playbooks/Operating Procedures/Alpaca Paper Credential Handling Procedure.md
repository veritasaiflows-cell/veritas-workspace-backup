# WF63 Phase 1 Credential-Handling Procedure

Purpose: define how a future read-only Alpaca paper connection may handle credentials without exposing secrets or widening authority.

## Current status

- Credential handling is **not approved yet**.
- This document contains **no secrets** and must never be used to store secrets.
- This pass did **not** inspect environment variables, credential stores, config files, or Alpaca accounts.
- No Alpaca API call is authorized by this procedure alone.

## Approved shape after explicit owner gate

A future Phase 1 connector may only proceed after Randall explicitly approves read-only paper connection testing and the kill switch permits read-only access.

Credential source rules:

1. Credentials must be paper-mode Alpaca credentials only.
2. Secrets must live outside notes, chat, generated artifacts, memory files, and committed workspace files.
3. Runtime output must redact all secret values and may only report that credentials were present/absent.
4. Ambiguous or live-looking credential names block the workflow.
5. No fallback from paper credentials to live credentials is allowed.

Preferred non-secret variable-name contract for a future connector:

- `ALPACA_PAPER_API_KEY_ID`
- `ALPACA_PAPER_API_SECRET_KEY`

Blocked credential-name classes:

- names containing `LIVE`
- generic names that omit `PAPER`, including `ALPACA_API_KEY_ID`, `ALPACA_SECRET_KEY`, `APCA_API_KEY_ID`, and `APCA_API_SECRET_KEY`
- any credential name selected for `https://api.alpaca.markets`

## Endpoint and method contract

Required endpoint:

- `https://paper-api.alpaca.markets`

Forbidden endpoint:

- `https://api.alpaca.markets`

Allowed HTTP method:

- `GET` only

Blocked HTTP methods:

- `POST`
- `PATCH`
- `PUT`
- `DELETE`

## Audit and proof rules

A future connector must produce redacted proof only:

- `tmp/alpaca-paper-readiness/read-only-connection-proof.json`
- append-only audit events in `tmp/alpaca-paper-readiness/audit-log.jsonl`

The proof must not include API keys, secret keys, account tokens, authorization headers, raw environment dumps, or request/response bodies containing sensitive account identifiers.

## Stop line

If the future connector cannot prove paper endpoint, paper credentials, GET-only behavior, redacted output, and no trade/account action authority, it must stop before making any Alpaca call.
