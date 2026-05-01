from __future__ import annotations

from dataclasses import dataclass

from .contracts import CaseRequest, CompletionGuardResult, EvidenceBundle, LeadCandidate, stable_id
from .scoring import LeadScoringService
from .search import SearchPlan
from .sentinel import PROHIBITED_TERMS, PUBLICATION_PRESSURE_TERMS
from .truth import tokenize


STOP_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "whether",
    "while",
    "request",
    "requested",
    "records",
    "record",
    "review",
    "reviewable",
    "california",
}


@dataclass(frozen=True)
class BoundedCase:
    case_id: str
    scope_note: str
    jurisdiction: str
    entities: list[str]
    allowed_sources: list[str]
    guardrails: list[str]


class LocalProviderAdapter:
    """Provider SDK placeholder; no model output is system of record."""

    name = "local-rule-adapter"

    def describe_role_call(self, role: str) -> dict[str, str]:
        return {
            "adapter": self.name,
            "mode": "deterministic-local-stub",
            "role": role,
        }


class CaseDirector:
    def bound(self, request: CaseRequest) -> BoundedCase:
        scope = (
            f"{request.jurisdiction} internal triage case limited to "
            f"{len(request.allowed_sources)} source types and {len(request.entities)} named entities."
        )
        return BoundedCase(
            case_id=request.case_id,
            scope_note=scope,
            jurisdiction=request.jurisdiction,
            entities=request.entities,
            allowed_sources=request.allowed_sources,
            guardrails=[
                "Use retrieved evidence only.",
                "Keep all outputs internal until explicit human review.",
                "Preserve uncertainty and missing data.",
            ],
        )


class RetrievalStrategist:
    def plan(self, request: CaseRequest, bounded_case: BoundedCase) -> SearchPlan:
        # Entity names are contract-critical in broad cases; keep them ahead of generic objective terms.
        raw_terms = tokenize(" ".join([*bounded_case.entities, request.title, request.objective]))
        blocked = STOP_TERMS | set(PROHIBITED_TERMS)
        for phrase in PUBLICATION_PRESSURE_TERMS:
            blocked.update(tokenize(phrase))
        terms = []
        for term in raw_terms:
            if len(term) <= 2 or term in blocked:
                continue
            if term not in terms:
                terms.append(term)
        return SearchPlan(
            terms=terms[:48],
            allowed_sources=bounded_case.allowed_sources,
            max_results=request.max_results,
            required_source_types=bounded_case.allowed_sources,
        )

class EntityNetworkAnalyst:
    def summarize_links(self, bundle: EvidenceBundle) -> dict[str, object]:
        hard_links = [link for link in bundle.entity_links if link.strength >= 0.7]
        soft_links = [link for link in bundle.entity_links if link.strength < 0.7]
        return {
            "hard_link_count": len(hard_links),
            "soft_link_count": len(soft_links),
            "links": [
                {
                    "entity": link.entity,
                    "record_ids": link.record_ids,
                    "link_type": link.link_type,
                    "strength": link.strength,
                    "rationale": link.rationale,
                }
                for link in bundle.entity_links
            ],
        }


class EvidenceAnalyst:
    def summarize_bundle(self, bundle: EvidenceBundle) -> dict[str, object]:
        return {
            "evidence_count": len(bundle.items),
            "evidence_ids": [item.item_id for item in bundle.items],
            "source_uris": [item.source_uri for item in bundle.items],
            "notes": [
                "Evidence bundle is source-cited and provenance-bearing.",
                "No source summary should be used without the linked evidence item.",
            ],
        }


class LeadScorerAgent:
    def __init__(self, scoring_service: LeadScoringService) -> None:
        self.scoring_service = scoring_service

    def create_candidate(
        self,
        request: CaseRequest,
        bundle: EvidenceBundle,
        completion_guard: CompletionGuardResult | None = None,
        selected_entities: list[str] | None = None,
    ) -> LeadCandidate:
        score_inputs = self.scoring_service.score(bundle, completion_guard)
        evidence_ids = [item.item_id for item in bundle.items]
        focus_entities = list(selected_entities or request.entities)
        entity_phrase = ", ".join(focus_entities[:3]) if focus_entities else "the requested subject"
        theme = self._theme(bundle)
        low_linkage = len(focus_entities) > 1 and score_inputs.hard_link_count == 0

        if not bundle.items:
            statement = f"No reviewable lead candidate is supported for {entity_phrase} from the allowed corpus."
            support_summary = "No retrieved record met the local search threshold."
        elif score_inputs.support_count < 2 or low_linkage:
            statement = (
                f"Retrieved records show a limited review signal for {entity_phrase} "
                f"focused on {theme}."
            )
            if low_linkage and score_inputs.support_count >= 2:
                support_summary = (
                    f"Supported by {score_inputs.support_count} retrieved records, but entity linkage remains below upgrade threshold."
                )
            else:
                support_summary = (
                    f"Supported by {score_inputs.support_count} retrieved record; source count is below upgrade threshold."
                )
        else:
            statement = (
                f"Retrieved records show a reviewable oversight signal for {entity_phrase} "
                f"focused on {theme}."
            )
            support_summary = (
                f"Supported by {score_inputs.support_count} retrieved records across "
                f"{score_inputs.source_diversity} source type(s)."
            )

        uncertainty = []
        signal_counts = self._signal_counts(bundle)
        if score_inputs.support_count < 2:
            uncertainty.append("Support is thin and requires more source coverage.")
        if low_linkage:
            uncertainty.append("Entity linkage remains low and should not be upgraded without corroboration.")
        if signal_counts.get("going_concern_flag"):
            uncertainty.append("At least one retrieved record includes a going-concern audit flag; verify the audit document before any escalation.")
        if signal_counts.get("material_weakness_internal_controls"):
            uncertainty.append("At least one retrieved record includes an internal-control audit flag; preserve the original audit context.")
        if signal_counts.get("reported_conflict_transactions"):
            uncertainty.append("At least one retrieved Form 990 reports Schedule L transactions; this is a disclosure that requires document review, not an adverse conclusion.")
        if signal_counts.get("schedule_l_present"):
            uncertainty.append("At least one downloaded Form 990 XML includes Schedule L content; review the original XML before using related-party language.")
        if signal_counts.get("full_990_xml_downloaded"):
            uncertainty.append("The IRS XML is now locally preserved; summary fields should be checked against the raw XML before ranking.")
        if signal_counts.get("irs_990_pdf_unavailable"):
            uncertainty.append("The IRS bulk source exposed XML for the target returns; an official bulk return PDF was not available in this run.")
        if signal_counts.get("irs_990_full_text_fallback"):
            uncertainty.append("A rendered Form 990 full-text fallback is present for HealthRIGHT 360 because the official IRS XML object remains unresolved.")
        if signal_counts.get("fac_material_weakness") or signal_counts.get("fac_significant_deficiency"):
            uncertainty.append("At least one FAC record carries an audit-control review signal; use the downloaded audit PDF for context.")
        if signal_counts.get("fac_low_risk_no"):
            uncertainty.append("At least one FAC record marks the auditee as not low-risk for that audit year; preserve the year-specific context.")
        if signal_counts.get("fac_prior_findings"):
            uncertainty.append("At least one FAC record references prior finding agencies; verify the finding chain before escalation.")
        if signal_counts.get("fac_questioned_costs") or signal_counts.get("fac_repeat_finding"):
            uncertainty.append("At least one FAC finding row requires reviewer interpretation; do not treat it as an entity-level conclusion.")
        if signal_counts.get("dhcs_facility_closed_status"):
            uncertainty.append("DHCS facility rows include closed facility statuses; closure status is facility-level context and not an adverse entity finding.")
        if signal_counts.get("dhcs_status_crosscheck_incomplete"):
            uncertainty.append("The DHCS adverse-status page was checked, but a machine-readable table was not available in the fetched page.")
        if signal_counts.get("dhcs_adverse_source_probe_complete"):
            uncertainty.append("DHCS adverse-source discovery attempts are documented; absence of a recovered machine-readable table is not an adverse-status clearance.")
        if signal_counts.get("county_monitoring_report") or signal_counts.get("county_contract_source_match"):
            uncertainty.append("County contract or monitoring records are source context; reviewer must confirm current resolution and contract status.")
        if signal_counts.get("county_grant_ledger_present") or signal_counts.get("fac_federal_awards_present"):
            uncertainty.append("Grant and award ledger rows support funding-trace review, not standalone performance conclusions.")
        if signal_counts.get("pdf_layout_extracted"):
            uncertainty.append("PDF layout/table extraction provides navigation aids only; raw PDFs remain controlling source documents.")
        if signal_counts.get("court_docket_manifest"):
            uncertainty.append("A court-calendar or docket-search manifest is present; treat it only as a pointer for docket follow-up.")
        if signal_counts.get("official_enforcement_or_docket_flag"):
            uncertainty.append("At least one official enforcement or docket source is present; verify named parties, legal status, and whether the source names the nonprofit before escalation.")
        if signal_counts.get("social_media_source_checked"):
            uncertainty.append("Social or public web context is present; treat it as attributable context only until spending, scope, or disclosure records are checked.")
        if score_inputs.contradiction_count:
            uncertainty.append("At least one record preserves a conflicting or corrective signal.")
        if score_inputs.missing_data_count:
            uncertainty.append("At least one record carries an open gap-burden caveat that must be resolved before stronger outside-facing use.")
        if not uncertainty:
            uncertainty.append("This remains an internal triage lead pending human review.")

        review_questions = [
            "Do the cited records support the lead wording without adding external claims?",
            "Are any missing records needed before escalation?",
            "Should the lead be approved, downgraded, repaired, or rejected?",
        ]
        if signal_counts.get("federal_audit_available"):
            review_questions.append("Open the referenced audit documents and confirm whether any audit notes remain current.")
        if signal_counts.get("fac_audit_pdf_downloaded"):
            review_questions.append("Open the downloaded FAC audit PDF and compare it with the filtered FAC rows.")
        if signal_counts.get("full_990_xml_downloaded"):
            review_questions.append("Open the downloaded IRS XML and verify financial fields before using any revenue-based ranking.")
        if signal_counts.get("irs_990_full_text_fallback"):
            review_questions.append("Compare the HealthRIGHT 360 rendered full-text fallback against any later recovered official IRS XML or PDF before relying on it.")
        if signal_counts.get("reported_conflict_transactions"):
            review_questions.append("Review the relevant Schedule L disclosures before treating related-party transaction language as meaningful.")
        if signal_counts.get("dhcs_facility_status_crosscheck"):
            review_questions.append("Confirm whether any DHCS facility status requires facility-level follow-up before entity-level triage.")
        if signal_counts.get("dhcs_adverse_source_probe_complete"):
            review_questions.append("Treat the DHCS adverse-status source discovery as incomplete unless DHCS provides a directly verifiable row export or record response.")
        if signal_counts.get("county_monitoring_report"):
            review_questions.append("Check county monitoring records for agency responses, corrective-action status, and current contract context.")
        if signal_counts.get("court_docket_manifest"):
            review_questions.append("Confirm the docket directly before treating any court-calendar pointer as meaningful.")
        if signal_counts.get("official_enforcement_or_docket_flag"):
            review_questions.append("Open the official enforcement or docket source and separate third-party charges from any entity-level findings.")
        if signal_counts.get("social_media_source_checked"):
            review_questions.append("Compare social or public web claims to contract scope, grant restrictions, disclosures, and cost allocation.")

        return LeadCandidate(
            lead_id=stable_id("lead", request.case_id, *evidence_ids),
            case_id=request.case_id,
            statement=statement,
            support_summary=support_summary,
            uncertainty=uncertainty,
            required_review_questions=review_questions,
            evidence_ids=evidence_ids,
            score=score_inputs.final_score,
            score_inputs=score_inputs,
        )

    def _theme(self, bundle: EvidenceBundle) -> str:
        ranked_terms: dict[str, int] = {}
        for item in bundle.items:
            for term in item.matched_terms:
                if term in STOP_TERMS or term in PROHIBITED_TERMS:
                    continue
                ranked_terms[term] = ranked_terms.get(term, 0) + 1
        if not ranked_terms:
            return "source consistency and missing context"
        return ", ".join(
            term for term, _ in sorted(ranked_terms.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
        )


    def _signal_counts(self, bundle: EvidenceBundle) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in bundle.items:
            for key, value in item.signals.items():
                if value:
                    counts[key] = counts.get(key, 0) + 1
        return counts

