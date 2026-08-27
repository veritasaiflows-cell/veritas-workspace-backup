#!/usr/bin/env python3
"""Central WF78/WF85/WF86/WF87 artifact and schema registry."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
DATA = ROOT / "data"

SCHEMA_WF78_DAILY_FRESHNESS_LOOP = "veritas.wf78_daily_freshness_loop.v1"
SCHEMA_WF78_INTELLIGENCE_ROUTING_V2 = "veritas.wf78_intelligence_routing_v2.v1"
SCHEMA_WF78_PIPELINE_SMOKE = "veritas.wf78_pipeline_smoke.v1"
SCHEMA_WF78_SCALEOUT_PACKET = "veritas.wf78_scaleout_packet.v1"

WF78_DAILY_FRESHNESS_LOOP = TMP / "wf78-daily-freshness-loop.json"
WF78_INTELLIGENCE_ROUTING_V2 = TMP / "wf78-intelligence-routing-v2.json"
WF78_AUTO_TIER_ROUTING = TMP / "wf78-auto-tier-routing.json"
WF78_TIER_C_ATTENTION_TRIGGER = TMP / "wf78-tier-c-attention-trigger.json"
WF78_ROUTING_DELTA = TMP / "wf78-routing-delta.json"
WF78_TIER_WEIGHTED_FRESHNESS_RESOLUTION = TMP / "wf78-tier-weighted-freshness-resolution.json"
WF78_REPAIR_DEBT_SCOREBOARD = TMP / "wf78-repair-debt-scoreboard.json"
WF78_REPAIR_PRIORITY_QUEUE = TMP / "wf78-repair-priority-queue.json"
WF78_DAILY_MOVEMENT_LEDGER = TMP / "wf78-daily-movement-ledger.json"
WF78_TIER_ROUTING_EVENT_LEDGER = TMP / "wf78-tier-routing-event-ledger.json"
WF78_TIER_ROUTING_EVENT_LEDGER_MD = TMP / "wf78-tier-routing-event-ledger.md"
WF78_DAILY_MOVEMENT_LEDGER_MD = TMP / "wf78-daily-movement-ledger.md"
WF78_TIER_ROUTING_EVENTS = STATE / "workflows" / "wf78-tier-routing-events.jsonl"

AUTONOMOUS_ROUTING_DEPLOYMENT_CARDS = TMP / "autonomous-routing-deployment-cards.json"
CRON_CONTRACT_VALIDATOR = TMP / "cron-contract-validator.json"
CRON_FRESHNESS_SPINE = TMP / "cron-freshness-spine.json"
ARTIFACT_INDEX_DB = TMP / "veritas-artifact-index.sqlite"
CANONICAL_FINANCE_DATA_PLANE = TMP / "canonical-finance-data-plane.json"
TRADE_GRADE_DECISION_CARDS = TMP / "trade-grade-decision-cards.json"

FINANCE_UNIVERSE = DATA / "finance" / "universe-v1.json"
WF78_100_TICKER_IMPORT_GATE = TMP / "wf78-100-ticker-import-gate.json"
WF78_101_200_TIER_C_IMPORT_GATE = TMP / "wf78-101-200-tier-c-import-gate.json"
WF78_SCALEOUT_PACKET = TMP / "wf78-scaleout-packet.json"

WF86_SHADOW_DECISIONS = TMP / "paper-autotrader" / "shadow-decisions.json"
WF86_SHADOW_ELIGIBILITY = TMP / "paper-autotrader" / "shadow-eligibility.json"
WF87_MARKET_HOURS_GATE_PROBE = TMP / "wf87-market-hours-gate-probe.json"
WF87_AUTONOMY_COMMAND_CENTER = TMP / "wf87-autonomy-command-center.json"
WF87_V2_READINESS_ROLLUP = TMP / "wf87-v2-readiness-rollup.json"

CRON_WF78_DAILY_FRESHNESS = STATE / "cron-contracts" / "finance-wf78-daily-freshness-and-promotion-proof.json"
CRON_WF87_MARKET_HOURS = STATE / "cron-contracts" / "finance-wf87-market-hours-fresh-gate-probe.json"
CRON_WF87_COMMAND_CENTER = STATE / "cron-contracts" / "finance-wf87-autonomy-command-center-refresh.json"
