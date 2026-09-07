# Retired — Alpaca Paper Credential Handling Procedure

Status: Retired deny-only safety record as of 2026-08-29.

The alerts-and-recommendations OS has no operational paper connector, credential route, account/position/order read path, request-card path, reconciliation path, or simulated execution authority. Earlier endpoint, environment-variable, and connector instructions are superseded and must not be reconstructed or used.

The only surviving principles are:

- never expose or persist secrets;
- never infer authority from the presence of credentials;
- fail closed on any brokerage, account, order, or execution path;
- preserve immutable historical audit evidence without reactivating it.

This tombstone grants no config, auth, credential, network, channel, service, runtime, capital, account, brokerage, paper/live, delivery, or execution authority.
