from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class FreshnessClass(str, Enum):
    MECHANICAL_DATE_ELAPSED_EVENT = "mechanical_date_elapsed_event"
    POST_CATALYST_STATUS = "post_catalyst_status"
    CROSS_SURFACE_CONTRADICTION = "cross_surface_contradiction"
    THESIS_OR_POSTURE_CHANGE = "thesis_or_posture_change"


class JudgmentImpact(str, Enum):
    NONE = "none"
    POSSIBLE = "possible"
    MATERIAL = "material"


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


SAFE_FRESHNESS_CLASSES = {
    FreshnessClass.MECHANICAL_DATE_ELAPSED_EVENT,
    FreshnessClass.POST_CATALYST_STATUS,
}


@dataclass
class EvidenceItem:
    title: str
    source: str
    source_quality: str
    url: str | None = None
    published_at: str | None = None
    excerpt: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceItem":
        return cls(
            title=str(data.get("title", "")).strip(),
            source=str(data.get("source", "")).strip(),
            source_quality=str(data.get("source_quality", data.get("source_tier", ""))).strip(),
            url=data.get("url"),
            published_at=data.get("published_at"),
            excerpt=data.get("excerpt"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "source_quality": self.source_quality,
            "url": self.url,
            "published_at": self.published_at,
            "excerpt": self.excerpt,
        }


@dataclass
class PatchInput:
    target_note: str
    stale_claim: str
    why_stale: str
    new_evidence: list[EvidenceItem] = field(default_factory=list)
    source_quality: str = ""
    freshness_class: str = FreshnessClass.MECHANICAL_DATE_ELAPSED_EVENT.value
    patch_scope: str = ""
    proposed_replacement: str = ""
    judgment_impact: str = JudgmentImpact.NONE.value
    affected_surfaces: list[str] = field(default_factory=list)
    required_downstream_sync: list[str] = field(default_factory=list)
    rollback_note: str = ""
    verifier_signoff: str = ""
    main_approval_required: bool = True
    linked_packet_id: str | None = None
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatchInput":
        return cls(
            target_note=str(data.get("target_note", "")).strip(),
            stale_claim=str(data.get("stale_claim", "")).strip(),
            why_stale=str(data.get("why_stale", "")).strip(),
            new_evidence=[EvidenceItem.from_dict(x) for x in data.get("new_evidence", [])],
            source_quality=str(data.get("source_quality", "")).strip(),
            freshness_class=str(data.get("freshness_class", FreshnessClass.MECHANICAL_DATE_ELAPSED_EVENT.value)).strip(),
            patch_scope=str(data.get("patch_scope", "")).strip(),
            proposed_replacement=str(data.get("proposed_replacement", "")).strip(),
            judgment_impact=str(data.get("judgment_impact", JudgmentImpact.NONE.value)).strip(),
            affected_surfaces=[str(x).strip() for x in data.get("affected_surfaces", [])],
            required_downstream_sync=[str(x).strip() for x in data.get("required_downstream_sync", [])],
            rollback_note=str(data.get("rollback_note", "")).strip(),
            verifier_signoff=str(data.get("verifier_signoff", "")).strip(),
            main_approval_required=bool(data.get("main_approval_required", True)),
            linked_packet_id=data.get("linked_packet_id"),
            notes=str(data.get("notes", "")).strip(),
        )


@dataclass
class PatchProposal:
    candidate_id: str
    created_at: str
    target_note: str
    stale_claim: str
    why_stale: str
    new_evidence: list[EvidenceItem]
    source_quality: str
    freshness_class: str
    patch_scope: str
    proposed_replacement: str
    judgment_impact: str
    affected_surfaces: list[str]
    required_downstream_sync: list[str]
    rollback_note: str
    verifier_signoff: str
    main_approval_required: bool
    linked_packet_id: str | None
    apply_allowed: bool = False
    status: ProposalStatus = ProposalStatus.NEEDS_REVIEW
    rejection_reasons: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "created_at": self.created_at,
            "target_note": self.target_note,
            "stale_claim": self.stale_claim,
            "why_stale": self.why_stale,
            "new_evidence": [x.to_dict() for x in self.new_evidence],
            "source_quality": self.source_quality,
            "freshness_class": self.freshness_class,
            "patch_scope": self.patch_scope,
            "proposed_replacement": self.proposed_replacement,
            "judgment_impact": self.judgment_impact,
            "affected_surfaces": self.affected_surfaces,
            "required_downstream_sync": self.required_downstream_sync,
            "rollback_note": self.rollback_note,
            "verifier_signoff": self.verifier_signoff,
            "main_approval_required": self.main_approval_required,
            "linked_packet_id": self.linked_packet_id,
            "apply_allowed": self.apply_allowed,
            "status": self.status.value,
            "rejection_reasons": self.rejection_reasons,
            "validation_errors": self.validation_errors,
            "notes": self.notes,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_candidate_id(item: PatchInput) -> str:
    basis = json.dumps(
        {
            "target_note": item.target_note,
            "stale_claim": item.stale_claim,
            "patch_scope": item.patch_scope,
            "linked_packet_id": item.linked_packet_id,
        },
        sort_keys=True,
    )
    return "cfp_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def validate_input(item: PatchInput) -> list[str]:
    errors: list[str] = []
    if not item.target_note:
        errors.append("target_note is required")
    if not item.stale_claim:
        errors.append("stale_claim is required")
    if not item.why_stale:
        errors.append("why_stale is required")
    if not item.new_evidence:
        errors.append("new_evidence is required")
    if not item.source_quality:
        errors.append("source_quality is required")
    if not item.patch_scope:
        errors.append("patch_scope is required")
    if not item.proposed_replacement:
        errors.append("proposed_replacement is required")
    if not item.rollback_note:
        errors.append("rollback_note is required")
    if not item.main_approval_required:
        errors.append("main_approval_required must remain true")
    return errors


def rejection_reasons(item: PatchInput) -> list[str]:
    reasons: list[str] = []
    freshness_class = FreshnessClass(item.freshness_class)
    judgment_impact = JudgmentImpact(item.judgment_impact)

    if freshness_class not in SAFE_FRESHNESS_CLASSES:
        reasons.append(f"freshness_class_not_safe_for_v1:{freshness_class.value}")
    if judgment_impact == JudgmentImpact.MATERIAL:
        reasons.append("material_judgment_impact")
    if freshness_class == FreshnessClass.CROSS_SURFACE_CONTRADICTION and judgment_impact != JudgmentImpact.NONE:
        reasons.append("cross_surface_contradiction_requires_higher_review")
    if freshness_class == FreshnessClass.THESIS_OR_POSTURE_CHANGE:
        reasons.append("thesis_or_posture_change_is_out_of_bounds")
    return reasons


def build_proposal(item: PatchInput) -> PatchProposal:
    errors = validate_input(item)
    reasons = [] if errors else rejection_reasons(item)
    status = ProposalStatus.PROPOSED if not reasons and not errors else ProposalStatus.NEEDS_REVIEW
    if any(r in reasons for r in {"material_judgment_impact", "thesis_or_posture_change_is_out_of_bounds"}):
        status = ProposalStatus.REJECTED

    proposal = PatchProposal(
        candidate_id=make_candidate_id(item),
        created_at=now_iso(),
        target_note=item.target_note,
        stale_claim=item.stale_claim,
        why_stale=item.why_stale,
        new_evidence=item.new_evidence,
        source_quality=item.source_quality,
        freshness_class=item.freshness_class,
        patch_scope=item.patch_scope,
        proposed_replacement=item.proposed_replacement,
        judgment_impact=item.judgment_impact,
        affected_surfaces=item.affected_surfaces,
        required_downstream_sync=item.required_downstream_sync,
        rollback_note=item.rollback_note,
        verifier_signoff=item.verifier_signoff,
        main_approval_required=True,
        linked_packet_id=item.linked_packet_id,
        apply_allowed=False,
        status=status,
        rejection_reasons=reasons,
        validation_errors=errors,
        notes=item.notes,
    )
    return proposal


def load_inputs(path: Path) -> list[PatchInput]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "candidates" in data:
        data = data["candidates"]
    if not isinstance(data, list):
        raise ValueError("Input must be a JSON list or an object with a 'candidates' list.")
    return [PatchInput.from_dict(item) for item in data]


def write_output(proposals: list[PatchProposal], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = output_dir / f"freshness-patch-candidates-{stamp}.json"
    payload = {
        "created_at": now_iso(),
        "candidate_count": len(proposals),
        "apply_allowed": False,
        "candidates": [proposal.to_dict() for proposal in proposals],
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def write_sample_input(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = [
        {
            "target_note": "01. Dashboards/Executive Brief.md",
            "stale_claim": "The BRK.B catalyst wording still speaks as if the event is upcoming.",
            "why_stale": "BRK.B already reported on May 2, so future-tense catalyst wording is stale.",
            "new_evidence": [
                {
                    "title": "Updated event calendar review",
                    "source": "Internal verified event review",
                    "source_quality": "tier_1_primary"
                }
            ],
            "source_quality": "tier_1_primary",
            "freshness_class": "mechanical_date_elapsed_event",
            "patch_scope": "single sentence wording cleanup only",
            "proposed_replacement": "BRK.B already reported on May 2; keep the post-print state explicit instead of future-tense catalyst language.",
            "judgment_impact": "none",
            "affected_surfaces": ["01. Dashboards/Executive Brief.md", "01. Dashboards/This Week.md"],
            "required_downstream_sync": ["Check This Week wording after patch approval."],
            "rollback_note": "Restore the previous future-tense sentence if the event date was misread.",
            "verifier_signoff": "Pending main-session review",
            "main_approval_required": True,
            "linked_packet_id": "rip_example1234"
        },
        {
            "target_note": "03. Portfolio/Portfolio Snapshot.md",
            "stale_claim": "Energy sleeve stance should be upgraded immediately.",
            "why_stale": "New geopolitical chatter suggests stronger oil follow-through.",
            "new_evidence": [
                {
                    "title": "Unverified repost chain",
                    "source": "social repost chain",
                    "source_quality": "rumor_unverified"
                }
            ],
            "source_quality": "rumor_unverified",
            "freshness_class": "thesis_or_posture_change",
            "patch_scope": "energy posture rewrite",
            "proposed_replacement": "Upgrade energy posture and deployment state.",
            "judgment_impact": "material",
            "affected_surfaces": ["03. Portfolio/Portfolio Snapshot.md"],
            "required_downstream_sync": ["Would require cross-surface truth arbitration."],
            "rollback_note": "Restore prior posture wording.",
            "verifier_signoff": "Pending main-session review",
            "main_approval_required": True
        }
    ]
    path.write_text(json.dumps(sample, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-only canonical freshness patch proposals.")
    parser.add_argument("--input", type=Path, default=Path("tmp/research-automation/raw-freshness-candidates.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/research-automation"))
    parser.add_argument("--init-sample", action="store_true", help="Write a sample input file and exit.")
    args = parser.parse_args()

    if args.init_sample:
        write_sample_input(args.input)
        print(f"Sample input written: {args.input}")
        return 0

    proposals = [build_proposal(item) for item in load_inputs(args.input)]
    out_path = write_output(proposals, args.output_dir)
    summary = {
        "output": str(out_path),
        "candidate_count": len(proposals),
        "proposed": sum(1 for p in proposals if p.status == ProposalStatus.PROPOSED),
        "needs_review": sum(1 for p in proposals if p.status == ProposalStatus.NEEDS_REVIEW),
        "rejected": sum(1 for p in proposals if p.status == ProposalStatus.REJECTED),
        "apply_allowed": False,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
