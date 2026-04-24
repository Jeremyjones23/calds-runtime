from __future__ import annotations

import re

from .contracts import CaseRequest, LeadCandidate, SentinelDecision, SentinelResult, stable_id, utc_now


PROHIBITED_TERMS = ["corruption", "illegality", "intent"]
ESCALATED_LANGUAGE_PATTERNS = [
    r"\b(fraudulent|defrauded|defraud)\b",
    r"\b(committed|commits|engaged in|engages in|proved|proves|found|finding of|evidence of)\s+(fraud|corruption|illegality|illegal)\b",
    r"\b(fraud|corruption|illegality)\s+(occurred|scheme|finding|proven|proved)\b",
]
PUBLICATION_PRESSURE_TERMS = [
    "public claim",
    "press release",
    "publish",
    "headline",
    "prove",
    "guilty",
]


def find_escalated_language(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for term in PROHIBITED_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            matches.append(term)
    for pattern in ESCALATED_LANGUAGE_PATTERNS:
        if re.search(pattern, lowered):
            matches.append(pattern)
    return matches


class SentinelPolicy:
    """Deterministic sentinel gate for language safety and review posture."""

    def review(self, request: CaseRequest, lead: LeadCandidate) -> SentinelResult:
        flags: list[str] = []
        repair_instructions: list[str] = []
        combined_output = " ".join(
            [
                lead.statement,
                lead.support_summary,
                " ".join(lead.uncertainty),
                " ".join(lead.required_review_questions),
            ]
        ).lower()

        if find_escalated_language(combined_output):
            flags.append("escalated_language_in_output")
            repair_instructions.append(
                "Replace accusatory wording with neutral WFA screening language unless a formal threshold policy is implemented."
            )

        if (
            "audit flag" in combined_output
            or "schedule l" in combined_output
            or "fac record" in combined_output
            or "audit-control review signal" in combined_output
        ):
            flags.append("audit_review_signal")
            repair_instructions.append("Keep audit and Schedule L references as review questions until source documents are checked.")
        if "dhcs facility" in combined_output or "facility-level context" in combined_output:
            flags.append("facility_status_context_required")
            repair_instructions.append("Keep DHCS status records at facility-level context unless a reviewer confirms entity-level meaning.")
        if "county contract" in combined_output or "county monitoring" in combined_output:
            flags.append("county_source_context_required")
            repair_instructions.append("Require reviewer confirmation of current county contract or monitoring status.")
        if "court-calendar" in combined_output or "docket-search" in combined_output:
            flags.append("docket_context_required")
            repair_instructions.append("Treat docket pointers as follow-up tasks until the docket is directly verified.")
        objective = request.objective.lower()
        if any(term in objective for term in PUBLICATION_PRESSURE_TERMS):
            flags.append("publication_pressure_in_request")
            repair_instructions.append(
                "Keep the lead internal-only and require reviewer approval before any outside-facing use."
            )

        if lead.score_inputs.support_count < 2:
            flags.append("thin_support")
            repair_instructions.append("Collect at least one additional independent source before upgrade.")

        if lead.score_inputs.support_count >= 2 and lead.score_inputs.hard_link_count == 0:
            flags.append("low_entity_linkage")
            repair_instructions.append("Keep the lead downgraded until entity linkage is corroborated.")

        if lead.score_inputs.missing_data_count:
            flags.append("missing_data")
            repair_instructions.append("Preserve missing-data caveats in the review packet.")

        if lead.score_inputs.contradiction_count:
            flags.append("unresolved_contradiction")
            repair_instructions.append("Resolve or clearly preserve contradictory source material.")

        if "escalated_language_in_output" in flags:
            decision = SentinelDecision.BLOCK_REPAIR_REQUIRED
            rationale = "Output uses language that exceeds the implemented evidence policy."
        elif flags:
            decision = SentinelDecision.DOWNGRADE_FOR_REVIEW
            rationale = "Lead can proceed only as an internal reviewer-safe candidate with caveats."
        else:
            decision = SentinelDecision.ALLOW_FOR_REVIEW
            rationale = "Lead preserves source-cited, internal review posture."

        return SentinelResult(
            decision_id=stable_id("sentinel", request.case_id, lead.lead_id, utc_now()),
            case_id=request.case_id,
            decision=decision,
            flags=flags,
            rationale=rationale,
            repair_instructions=repair_instructions,
            checked_at=utc_now(),
        )
