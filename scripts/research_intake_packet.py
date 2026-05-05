from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class SourceTier(str, Enum):
    TIER_1_PRIMARY = "tier_1_primary"
    TIER_2_TRUSTED = "tier_2_trusted"
    TIER_3_SECONDARY = "tier_3_secondary"
    RUMOR_UNVERIFIED = "rumor_unverified"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, value: str | None) -> "SourceTier":
        if not value:
            return cls.UNKNOWN
        key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "tier_1": cls.TIER_1_PRIMARY,
            "primary": cls.TIER_1_PRIMARY,
            "company_primary": cls.TIER_1_PRIMARY,
            "filing": cls.TIER_1_PRIMARY,
            "ir": cls.TIER_1_PRIMARY,
            "transcript": cls.TIER_1_PRIMARY,
            "official": cls.TIER_1_PRIMARY,
            "tier_2": cls.TIER_2_TRUSTED,
            "trusted": cls.TIER_2_TRUSTED,
            "trusted_financial_media": cls.TIER_2_TRUSTED,
            "trusted_macro_geopolitical": cls.TIER_2_TRUSTED,
            "tier_3": cls.TIER_3_SECONDARY,
            "secondary": cls.TIER_3_SECONDARY,
            "analysis": cls.TIER_3_SECONDARY,
            "rumor": cls.RUMOR_UNVERIFIED,
            "unverified": cls.RUMOR_UNVERIFIED,
            "unknown": cls.UNKNOWN,
        }
        return aliases.get(key, cls._value2member_map_.get(key, cls.UNKNOWN))


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MaterialityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Route(str, Enum):
    IGNORE = "ignore"
    ARCHIVE_WEEKLY_DIGEST = "archive_weekly_digest"
    WEEKLY_INTELLIGENCE = "weekly_intelligence"
    DASHBOARD_WATCH_ITEM = "dashboard_watch_item"
    THESIS_REVIEW_QUEUE = "thesis_review_queue"
    CANONICAL_FRESHNESS_PATCH_CANDIDATE = "canonical_freshness_patch_candidate"
    STOP_LINE_NO_PROMOTION = "stop_line_no_promotion"


class AgentRole(str, Enum):
    EVENT_DETECTOR = "event_detector"
    MATERIALITY_SCORER = "materiality_scorer"
    THESIS_DRIFT_AGENT = "thesis_drift_agent"
    EVIDENCE_QA_AGENT = "evidence_qa_agent"
    ROUTING_AGENT = "routing_agent"


DAILY_EXECUTION = {"JPM", "ETN", "NVDA", "GOOG", "MSFT", "BRK.B", "XOM", "LMT", "VRT", "GS"}
EVENT_WATCH = {"CVX", "AMD", "LNG", "PLTR", "AMZN", "RTX", "CAT"}
MACRO_CONTEXT = {"SLV", "TLT", "RATES", "FED", "OIL", "CREDIT", "INFLATION", "HORMUZ", "MIDDLE EAST"}
SPECULATIVE_MONITOR = {"KTOS", "SMCI"}

HIGH_MATERIALITY_TAGS = {
    "earnings",
    "guidance",
    "guidance_cut",
    "guidance_raise",
    "restatement",
    "regulatory",
    "lawsuit",
    "sanctions",
    "war",
    "production_disruption",
    "major_contract",
    "management_response",
    "thesis_impairment",
    "timing_confirmation",
    "dividend_cut",
    "credit_event",
    "fed_decision",
    "oil_shock",
}

MEDIUM_MATERIALITY_TAGS = {
    "analyst_day",
    "sector_readthrough",
    "macro",
    "policy",
    "valuation_reset",
    "technical_base",
    "earnings_date",
    "product_update",
    "capital_return",
}

NO_ROUTE_TAGS = {"duplicate", "immaterial", "minor_price_move", "background_noise"}


@dataclass
class EvidenceItem:
    title: str
    source: str
    source_tier: str = SourceTier.UNKNOWN.value
    url: str | None = None
    published_at: str | None = None
    excerpt: str | None = None
    retrieved_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceItem":
        return cls(
            title=str(data.get("title", "")).strip(),
            source=str(data.get("source", "")).strip(),
            source_tier=SourceTier.parse(data.get("source_tier")).value,
            url=data.get("url"),
            published_at=data.get("published_at"),
            excerpt=data.get("excerpt"),
            retrieved_at=data.get("retrieved_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "source_tier": SourceTier.parse(self.source_tier).value,
            "url": self.url,
            "published_at": self.published_at,
            "excerpt": self.excerpt,
            "retrieved_at": self.retrieved_at,
        }


@dataclass
class RawResearchEvent:
    event_title: str
    event_datetime: str
    affected: list[str] = field(default_factory=list)
    source_tier: str = SourceTier.UNKNOWN.value
    event_class: str = "general_event"
    verification_status: str = "confirmed"
    primary_evidence: list[EvidenceItem] = field(default_factory=list)
    secondary_evidence: list[EvidenceItem] = field(default_factory=list)
    event_summary: str = ""
    tags: list[str] = field(default_factory=list)
    stale_canonical_note: bool = False
    rumor_heavy: bool = False
    requires_primary_confirmation: bool = False
    duplicate_of_packet_id: str | None = None
    contradiction_notes: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    manual_notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawResearchEvent":
        return cls(
            event_title=str(data.get("event_title", data.get("title", ""))).strip(),
            event_datetime=str(data.get("event_datetime", data.get("date_time", ""))).strip(),
            affected=[str(x).strip().upper() for x in data.get("affected", data.get("affected_tickers_or_themes", []))],
            source_tier=SourceTier.parse(data.get("source_tier")).value,
            event_class=normalize_tag(data.get("event_class", "general_event")) or "general_event",
            verification_status=normalize_tag(data.get("verification_status", "confirmed")) or "confirmed",
            primary_evidence=[EvidenceItem.from_dict(x) for x in data.get("primary_evidence", [])],
            secondary_evidence=[EvidenceItem.from_dict(x) for x in data.get("secondary_evidence", [])],
            event_summary=str(data.get("event_summary", data.get("summary", ""))).strip(),
            tags=[normalize_tag(x) for x in data.get("tags", [])],
            stale_canonical_note=bool(data.get("stale_canonical_note", False)),
            rumor_heavy=bool(data.get("rumor_heavy", False)),
            requires_primary_confirmation=bool(data.get("requires_primary_confirmation", False)),
            duplicate_of_packet_id=data.get("duplicate_of_packet_id"),
            contradiction_notes=[str(x).strip() for x in data.get("contradiction_notes", [])],
            open_questions=[str(x).strip() for x in data.get("open_questions", [])],
            manual_notes=str(data.get("manual_notes", "")).strip(),
        )


@dataclass
class AgentFinding:
    role: str
    summary: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    materiality: MaterialityLevel | None = None
    flags: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    uncertainty: list[str] = field(default_factory=list)
    recommended_route: Route | None = None
    requires_human_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "summary": self.summary,
            "confidence": self.confidence.value,
            "materiality": self.materiality.value if self.materiality else None,
            "flags": self.flags,
            "contradictions": self.contradictions,
            "uncertainty": self.uncertainty,
            "recommended_route": self.recommended_route.value if self.recommended_route else None,
            "requires_human_review": self.requires_human_review,
        }


@dataclass
class IntakePacket:
    packet_id: str
    created_at: str
    event_title: str
    event_datetime: str
    affected_tickers_or_themes: list[str]
    source_tier: str
    event_class: str
    verification_status: str
    open_questions: list[str]
    primary_evidence: list[EvidenceItem]
    secondary_evidence: list[EvidenceItem]
    confidence_level: ConfidenceLevel
    materiality_level: MaterialityLevel
    thesis_impact: str
    portfolio_posture_impact: str
    contradictions_uncertainty: list[str]
    recommended_routing: Route
    canonical_mutation_allowed: bool = False
    stop_line_triggered: bool = False
    next_required_review: str = ""
    stale_canonical_note: bool = False
    agent_findings: list[AgentFinding] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    routing_reason: str = ""

    def enforce_fail_closed(self) -> None:
        self.canonical_mutation_allowed = False
        if self.recommended_routing == Route.CANONICAL_FRESHNESS_PATCH_CANDIDATE:
            self.next_required_review = (
                self.next_required_review
                or "Human review required: exact freshness patch proposal only; no auto-apply."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "created_at": self.created_at,
            "event_title": self.event_title,
            "event_datetime": self.event_datetime,
            "affected_tickers_or_themes": self.affected_tickers_or_themes,
            "source_tier": self.source_tier,
            "event_class": self.event_class,
            "verification_status": self.verification_status,
            "open_questions": self.open_questions,
            "primary_evidence": [x.to_dict() for x in self.primary_evidence],
            "secondary_evidence": [x.to_dict() for x in self.secondary_evidence],
            "confidence_level": self.confidence_level.value,
            "materiality_level": self.materiality_level.value,
            "thesis_impact": self.thesis_impact,
            "portfolio_posture_impact": self.portfolio_posture_impact,
            "contradictions_uncertainty": self.contradictions_uncertainty,
            "recommended_routing": self.recommended_routing.value,
            "canonical_mutation_allowed": self.canonical_mutation_allowed,
            "stop_line_triggered": self.stop_line_triggered,
            "next_required_review": self.next_required_review,
            "stale_canonical_note": self.stale_canonical_note,
            "routing_reason": self.routing_reason,
            "validation_errors": self.validation_errors,
            "agent_findings": [x.to_dict() for x in self.agent_findings],
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_tag(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower()).strip("_")


def make_packet_id(raw: RawResearchEvent) -> str:
    basis = json.dumps(
        {
            "title": raw.event_title,
            "dt": raw.event_datetime,
            "affected": sorted(raw.affected),
            "primary": [x.title for x in raw.primary_evidence],
        },
        sort_keys=True,
    )
    return "rip_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def highest_source_tier(raw: RawResearchEvent) -> SourceTier:
    tiers = [SourceTier.parse(raw.source_tier)]
    tiers.extend(SourceTier.parse(x.source_tier) for x in raw.primary_evidence)
    tiers.extend(SourceTier.parse(x.source_tier) for x in raw.secondary_evidence)

    order = [
        SourceTier.TIER_1_PRIMARY,
        SourceTier.TIER_2_TRUSTED,
        SourceTier.TIER_3_SECONDARY,
        SourceTier.RUMOR_UNVERIFIED,
        SourceTier.UNKNOWN,
    ]
    for tier in order:
        if tier in tiers:
            return tier
    return SourceTier.UNKNOWN


def event_scope(raw: RawResearchEvent) -> dict[str, bool]:
    affected = {x.upper() for x in raw.affected}
    return {
        "has_daily_execution": bool(affected & DAILY_EXECUTION),
        "has_event_watch": bool(affected & EVENT_WATCH),
        "has_macro_context": bool(affected & MACRO_CONTEXT),
        "has_speculative_monitor": bool(affected & SPECULATIVE_MONITOR),
    }


def estimate_confidence(raw: RawResearchEvent) -> ConfidenceLevel:
    tier = highest_source_tier(raw)

    if raw.rumor_heavy or tier in {SourceTier.RUMOR_UNVERIFIED, SourceTier.UNKNOWN}:
        return ConfidenceLevel.LOW
    if raw.contradiction_notes:
        return ConfidenceLevel.MEDIUM
    if raw.primary_evidence and tier in {SourceTier.TIER_1_PRIMARY, SourceTier.TIER_2_TRUSTED}:
        return ConfidenceLevel.HIGH
    if raw.primary_evidence or raw.secondary_evidence:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def score_materiality(raw: RawResearchEvent) -> MaterialityLevel:
    tags = set(raw.tags)
    scope = event_scope(raw)

    if tags & NO_ROUTE_TAGS and not (tags & HIGH_MATERIALITY_TAGS):
        return MaterialityLevel.LOW

    if tags & HIGH_MATERIALITY_TAGS:
        return MaterialityLevel.HIGH

    if scope["has_daily_execution"] and (tags & MEDIUM_MATERIALITY_TAGS or raw.stale_canonical_note):
        return MaterialityLevel.MEDIUM

    if scope["has_event_watch"] and tags & {"earnings", "earnings_date", "sector_readthrough", "valuation_reset", "technical_base"}:
        return MaterialityLevel.MEDIUM

    if scope["has_macro_context"] and tags & {"macro", "policy", "fed_decision", "oil_shock", "inflation", "credit_event"}:
        return MaterialityLevel.MEDIUM

    if scope["has_speculative_monitor"] and tags & {"major_contract", "regulatory", "earnings", "thesis_impairment"}:
        return MaterialityLevel.MEDIUM

    return MaterialityLevel.LOW


def detect_stop_line(raw: RawResearchEvent, confidence: ConfidenceLevel, materiality: MaterialityLevel) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    tier = highest_source_tier(raw)

    if confidence == ConfidenceLevel.LOW:
        reasons.append("low_confidence")
    if raw.rumor_heavy or tier == SourceTier.RUMOR_UNVERIFIED:
        reasons.append("rumor_or_unverified_source")
    if not raw.primary_evidence and materiality in {MaterialityLevel.MEDIUM, MaterialityLevel.HIGH}:
        reasons.append("material_event_without_primary_evidence")
    if raw.requires_primary_confirmation and not raw.primary_evidence:
        reasons.append("requires_primary_confirmation_without_primary_evidence")
    if raw.verification_status in {"unresolved", "contradicted"}:
        reasons.append(f"verification_status:{raw.verification_status}")
    if raw.duplicate_of_packet_id:
        reasons.append(f"duplicate_of:{raw.duplicate_of_packet_id}")
    if raw.contradiction_notes and not raw.primary_evidence:
        reasons.append("unresolved_contradiction_without_primary_evidence")

    return bool(reasons), reasons


def determine_route(
    *,
    materiality: MaterialityLevel,
    confidence: ConfidenceLevel,
    stale_canonical_note: bool,
    stop_line: bool,
    scope: dict[str, bool],
) -> tuple[Route, str]:
    if stop_line or confidence == ConfidenceLevel.LOW:
        return Route.STOP_LINE_NO_PROMOTION, "Low confidence, rumor-heavy, duplicate, or unresolved evidence gap: no promotion."

    if materiality == MaterialityLevel.LOW and confidence == ConfidenceLevel.HIGH:
        return Route.ARCHIVE_WEEKLY_DIGEST, "Low materiality with high confidence: archive or weekly digest only."

    if materiality == MaterialityLevel.HIGH and stale_canonical_note:
        return Route.CANONICAL_FRESHNESS_PATCH_CANDIDATE, "High materiality and stale canonical note risk: draft patch candidate for human review."

    if materiality == MaterialityLevel.HIGH:
        return Route.THESIS_REVIEW_QUEUE, "High materiality: route to thesis-review queue."

    if materiality == MaterialityLevel.MEDIUM:
        if scope["has_daily_execution"] or scope["has_macro_context"]:
            return Route.DASHBOARD_WATCH_ITEM, "Medium materiality tied to daily/macro coverage: dashboard watch item."
        return Route.WEEKLY_INTELLIGENCE, "Medium materiality: weekly intelligence item."

    return Route.IGNORE, "No meaningful route found."


def thesis_impact_text(raw: RawResearchEvent, materiality: MaterialityLevel) -> str:
    tags = set(raw.tags)
    if materiality == MaterialityLevel.HIGH:
        return "Potential thesis-drift item. Compare against current thesis assumptions before any note or posture change."
    if raw.stale_canonical_note:
        return "Possible freshness issue in canonical or mirror surface. Patch proposal may be drafted, but not applied automatically."
    if tags & {"earnings_date", "technical_base", "valuation_reset"}:
        return "May affect timing/setup language, but no autonomous thesis change is allowed."
    return "No clear thesis-drift impact detected."


def portfolio_impact_text(raw: RawResearchEvent, materiality: MaterialityLevel) -> str:
    scope = event_scope(raw)
    if materiality == MaterialityLevel.HIGH and scope["has_daily_execution"]:
        return "May affect deployment timing or active capital competition. Human review required; no action language is authorized."
    if scope["has_event_watch"]:
        return "May affect watch-lane freshness or future promotion candidacy. Human gate required for promotion."
    if scope["has_macro_context"]:
        return "May affect macro/regime context. Human review required before changing macro gate or portfolio posture."
    if scope["has_speculative_monitor"]:
        return "May affect speculative monitor relevance. Human review required before any sleeve or tier change."
    return "No immediate portfolio posture impact identified."


def next_review_text(route: Route) -> str:
    if route == Route.STOP_LINE_NO_PROMOTION:
        return "Human evidence review required. Do not promote, patch, or surface as action-ready."
    if route == Route.CANONICAL_FRESHNESS_PATCH_CANDIDATE:
        return "Human canonical freshness review required. Draft exact patch only; no auto-apply."
    if route == Route.THESIS_REVIEW_QUEUE:
        return "Human thesis-review queue. Compare against existing thesis before any canonical or posture change."
    if route == Route.DASHBOARD_WATCH_ITEM:
        return "Operator review for dashboard watch item. No deployment or canonical mutation."
    if route == Route.WEEKLY_INTELLIGENCE:
        return "Weekly intelligence review. Monitor for repeat signal or escalation."
    if route == Route.ARCHIVE_WEEKLY_DIGEST:
        return "Archive or include in weekly digest only."
    return "No follow-up required unless repeated or contradicted."


def event_detector(raw: RawResearchEvent) -> AgentFinding:
    flags = []
    if not raw.event_title:
        flags.append("missing_event_title")
    if not raw.event_datetime:
        flags.append("missing_event_datetime")
    if not raw.affected:
        flags.append("missing_affected_ticker_or_theme")

    summary = raw.event_summary or f"Detected event: {raw.event_title}"
    return AgentFinding(
        role=AgentRole.EVENT_DETECTOR.value,
        summary=summary,
        confidence=ConfidenceLevel.HIGH if not flags else ConfidenceLevel.MEDIUM,
        flags=flags,
        requires_human_review=bool(flags),
    )


def materiality_scorer(raw: RawResearchEvent) -> AgentFinding:
    materiality = score_materiality(raw)
    scope = event_scope(raw)
    flags = [key for key, value in scope.items() if value]

    return AgentFinding(
        role=AgentRole.MATERIALITY_SCORER.value,
        summary=f"Materiality scored as {materiality.value} for affected scope: {', '.join(flags) or 'unmapped'}.",
        confidence=estimate_confidence(raw),
        materiality=materiality,
        flags=flags,
        requires_human_review=materiality in {MaterialityLevel.MEDIUM, MaterialityLevel.HIGH},
    )


def thesis_drift_agent(raw: RawResearchEvent) -> AgentFinding:
    materiality = score_materiality(raw)
    tags = set(raw.tags)
    flags = []
    if raw.stale_canonical_note:
        flags.append("stale_canonical_note_candidate")
    if tags & {"thesis_impairment", "guidance_cut", "management_response", "restatement"}:
        flags.append("possible_thesis_drift")
    if tags & {"earnings_date", "timing_confirmation"}:
        flags.append("timing_freshness_check")

    return AgentFinding(
        role=AgentRole.THESIS_DRIFT_AGENT.value,
        summary=thesis_impact_text(raw, materiality),
        confidence=estimate_confidence(raw),
        materiality=materiality,
        flags=flags,
        uncertainty=list(raw.contradiction_notes),
        requires_human_review=bool(flags) or materiality == MaterialityLevel.HIGH,
    )


def evidence_qa_agent(raw: RawResearchEvent) -> AgentFinding:
    confidence = estimate_confidence(raw)
    materiality = score_materiality(raw)
    stop_line, reasons = detect_stop_line(raw, confidence, materiality)
    contradictions = list(raw.contradiction_notes)

    flags = []
    if not raw.primary_evidence:
        flags.append("missing_primary_evidence")
    if not raw.secondary_evidence:
        flags.append("missing_secondary_evidence")
    if highest_source_tier(raw) in {SourceTier.RUMOR_UNVERIFIED, SourceTier.UNKNOWN}:
        flags.append("weak_source_tier")
    flags.extend(reasons)

    return AgentFinding(
        role=AgentRole.EVIDENCE_QA_AGENT.value,
        summary=f"Evidence QA confidence is {confidence.value}. Stop-line: {stop_line}.",
        confidence=confidence,
        materiality=materiality,
        flags=sorted(set(flags)),
        contradictions=contradictions,
        uncertainty=[] if confidence == ConfidenceLevel.HIGH else ["Evidence quality does not support autonomous routing beyond review."],
        recommended_route=Route.STOP_LINE_NO_PROMOTION if stop_line else None,
        requires_human_review=stop_line or confidence != ConfidenceLevel.HIGH,
    )


def routing_agent(raw: RawResearchEvent) -> AgentFinding:
    confidence = estimate_confidence(raw)
    materiality = score_materiality(raw)
    stop_line, reasons = detect_stop_line(raw, confidence, materiality)
    route, reason = determine_route(
        materiality=materiality,
        confidence=confidence,
        stale_canonical_note=raw.stale_canonical_note,
        stop_line=stop_line,
        scope=event_scope(raw),
    )
    return AgentFinding(
        role=AgentRole.ROUTING_AGENT.value,
        summary=reason,
        confidence=confidence,
        materiality=materiality,
        flags=reasons,
        recommended_route=route,
        requires_human_review=route in {
            Route.STOP_LINE_NO_PROMOTION,
            Route.CANONICAL_FRESHNESS_PATCH_CANDIDATE,
            Route.THESIS_REVIEW_QUEUE,
            Route.DASHBOARD_WATCH_ITEM,
        },
    )


ROLE_FUNCTIONS: list[tuple[AgentRole, Callable[[RawResearchEvent], AgentFinding]]] = [
    (AgentRole.EVENT_DETECTOR, event_detector),
    (AgentRole.MATERIALITY_SCORER, materiality_scorer),
    (AgentRole.THESIS_DRIFT_AGENT, thesis_drift_agent),
    (AgentRole.EVIDENCE_QA_AGENT, evidence_qa_agent),
    (AgentRole.ROUTING_AGENT, routing_agent),
]


def run_parallel_agents(raw: RawResearchEvent) -> list[AgentFinding]:
    results: dict[str, AgentFinding] = {}
    with futures.ThreadPoolExecutor(max_workers=len(ROLE_FUNCTIONS)) as pool:
        pending = {pool.submit(fn, raw): role.value for role, fn in ROLE_FUNCTIONS}
        for future in futures.as_completed(pending):
            role = pending[future]
            try:
                results[role] = future.result()
            except Exception as exc:
                results[role] = AgentFinding(
                    role=role,
                    summary=f"Agent lane failed: {exc}",
                    confidence=ConfidenceLevel.LOW,
                    flags=["agent_lane_failed"],
                    recommended_route=Route.STOP_LINE_NO_PROMOTION,
                    requires_human_review=True,
                )

    return [results[role.value] for role, _ in ROLE_FUNCTIONS]


def build_packet(raw: RawResearchEvent) -> IntakePacket:
    findings = run_parallel_agents(raw)
    confidence = estimate_confidence(raw)
    materiality = score_materiality(raw)
    stop_line, stop_reasons = detect_stop_line(raw, confidence, materiality)
    route, route_reason = determine_route(
        materiality=materiality,
        confidence=confidence,
        stale_canonical_note=raw.stale_canonical_note,
        stop_line=stop_line,
        scope=event_scope(raw),
    )

    contradictions_uncertainty: list[str] = []
    contradictions_uncertainty.extend(raw.contradiction_notes)
    contradictions_uncertainty.extend(raw.open_questions)
    contradictions_uncertainty.extend(stop_reasons)
    for finding in findings:
        contradictions_uncertainty.extend(finding.contradictions)
        contradictions_uncertainty.extend(finding.uncertainty)
    contradictions_uncertainty = sorted({x for x in contradictions_uncertainty if x})

    packet = IntakePacket(
        packet_id=make_packet_id(raw),
        created_at=now_iso(),
        event_title=raw.event_title,
        event_datetime=raw.event_datetime,
        affected_tickers_or_themes=raw.affected,
        source_tier=highest_source_tier(raw).value,
        event_class=raw.event_class,
        verification_status=raw.verification_status,
        open_questions=raw.open_questions,
        primary_evidence=raw.primary_evidence,
        secondary_evidence=raw.secondary_evidence,
        confidence_level=confidence,
        materiality_level=materiality,
        thesis_impact=thesis_impact_text(raw, materiality),
        portfolio_posture_impact=portfolio_impact_text(raw, materiality),
        contradictions_uncertainty=contradictions_uncertainty,
        recommended_routing=route,
        canonical_mutation_allowed=False,
        stop_line_triggered=stop_line,
        next_required_review=next_review_text(route),
        stale_canonical_note=raw.stale_canonical_note,
        agent_findings=findings,
        routing_reason=route_reason,
    )
    packet.enforce_fail_closed()
    packet.validation_errors = validate_packet(packet)

    if packet.validation_errors:
        packet.stop_line_triggered = True
        packet.recommended_routing = Route.STOP_LINE_NO_PROMOTION
        packet.routing_reason = "Validation failed: packet is fail-closed."
        packet.next_required_review = "Human review required to repair packet validation errors."
        packet.enforce_fail_closed()

    return packet


def validate_packet(packet: IntakePacket) -> list[str]:
    errors: list[str] = []
    if not packet.event_title:
        errors.append("event_title is required")
    if not packet.event_datetime:
        errors.append("event_datetime is required")
    if not packet.affected_tickers_or_themes:
        errors.append("affected_tickers_or_themes is required")
    if not packet.source_tier or packet.source_tier == SourceTier.UNKNOWN.value:
        errors.append("source_tier must be explicit")
    if not packet.event_class:
        errors.append("event_class is required")
    if not packet.verification_status:
        errors.append("verification_status is required")
    if packet.canonical_mutation_allowed:
        errors.append("canonical_mutation_allowed must remain false in intake packet v1")
    if packet.materiality_level in {MaterialityLevel.MEDIUM, MaterialityLevel.HIGH} and not packet.primary_evidence:
        errors.append("medium/high materiality packet requires primary_evidence or must stop-line")
    if packet.recommended_routing == Route.CANONICAL_FRESHNESS_PATCH_CANDIDATE and not packet.stale_canonical_note:
        errors.append("patch candidate route requires stale_canonical_note=true")
    return errors


def load_events(path: Path) -> list[RawResearchEvent]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "events" in data:
        data = data["events"]
    if not isinstance(data, list):
        raise ValueError("Input must be a JSON list or an object with an 'events' list.")
    return [RawResearchEvent.from_dict(item) for item in data]


def write_packets(packets: list[IntakePacket], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = output_dir / f"intake-packets-{stamp}.json"
    payload = {
        "created_at": now_iso(),
        "packet_count": len(packets),
        "canonical_mutation_allowed": False,
        "packets": [packet.to_dict() for packet in packets],
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def write_sample_input(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = [
        {
            "event_title": "NVDA timing confirmation remains unresolved after fresh calendar check",
            "event_datetime": "2026-05-03T16:30:00-07:00",
            "affected": ["NVDA"],
            "source_tier": "tier_2_trusted",
            "event_class": "company_event",
            "verification_status": "unresolved",
            "event_summary": "Fresh timing information suggests the note layer should remain cautious until primary confirmation is available.",
            "tags": ["earnings_date", "timing_confirmation"],
            "stale_canonical_note": True,
            "rumor_heavy": False,
            "requires_primary_confirmation": True,
            "primary_evidence": [
                {
                    "title": "Company investor relations calendar",
                    "source": "Company IR",
                    "source_tier": "tier_1_primary",
                    "url": "https://example.com/ir-calendar",
                    "published_at": "2026-05-03T09:00:00-07:00",
                    "excerpt": "Calendar item requires manual confirmation before note mutation.",
                }
            ],
            "secondary_evidence": [
                {
                    "title": "Trusted market calendar update",
                    "source": "Trusted financial media",
                    "source_tier": "tier_2_trusted",
                    "url": "https://example.com/calendar-update",
                    "published_at": "2026-05-03T08:00:00-07:00",
                }
            ],
            "contradiction_notes": [],
            "open_questions": ["Has NVDA primary investor-relations timing confirmation been updated directly?"],
        },
        {
            "event_title": "Unverified social post claims major XOM production disruption",
            "event_datetime": "2026-05-03T15:10:00-07:00",
            "affected": ["XOM", "OIL", "HORMUZ"],
            "source_tier": "rumor",
            "event_class": "geopolitical_event",
            "verification_status": "unresolved",
            "event_summary": "Unverified claim without primary confirmation.",
            "tags": ["oil_shock", "production_disruption"],
            "stale_canonical_note": False,
            "rumor_heavy": True,
            "requires_primary_confirmation": True,
            "primary_evidence": [],
            "secondary_evidence": [],
            "contradiction_notes": ["No company, exchange, or trusted wire confirmation."],
            "open_questions": ["Is there any primary confirmation from company, exchange, regulator, or trusted wire?", "Is the event operationally material or a repost chain?"],
        },
    ]
    path.write_text(json.dumps(sample, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-only research intake packets from raw research events.")
    parser.add_argument("--input", type=Path, default=Path("tmp/research-automation/raw-events.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/research-automation"))
    parser.add_argument("--init-sample", action="store_true", help="Write a sample input file and exit.")
    args = parser.parse_args()

    if args.init_sample:
        write_sample_input(args.input)
        print(f"Sample input written: {args.input}")
        return 0

    events = load_events(args.input)
    packets = [build_packet(event) for event in events]
    out_path = write_packets(packets, args.output_dir)

    summary = {
        "output": str(out_path),
        "packet_count": len(packets),
        "stop_lines": sum(1 for p in packets if p.stop_line_triggered),
        "patch_candidates": sum(1 for p in packets if p.recommended_routing == Route.CANONICAL_FRESHNESS_PATCH_CANDIDATE),
        "canonical_mutation_allowed": False,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
