from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from .contracts import (
    CanonicalRecord,
    CaseRequest,
    InvestigationProfile,
    ReviewValueScore,
    TriageFinding,
    stable_id,
)


DEFAULT_SOURCE_FAMILIES = [
    "state_awards",
    "irs_990",
    "audit",
    "enforcement_or_docket",
    "county_contract_monitoring",
    "web_and_social",
    "outcomes",
]

DEFAULT_DEEP_SOURCE_FAMILIES = [
    "raw_irs_990",
    "audit_pdf",
    "county_contracts",
    "payment_ledger",
    "litigation_docket",
    "board_files",
    "enforcement_adverse",
    "web_social_archive",
    "provider_outcomes",
]

DEFAULT_COMPLETION_GATES = [
    "profile",
    "entity_resolution",
    "target_discovery",
    "source",
    "handoff",
    "forensic_tests",
    "evidence_store",
    "citation",
    "link",
    "hallucination",
    "sentinel",
    "presentation",
    "human_action",
    "human_review",
]

DEFAULT_REVIEW_VALUE_WEIGHTS = {
    "public_money_exposure": 0.22,
    "official_adverse_record": 0.20,
    "scope_mismatch": 0.13,
    "spend_outcome_mismatch": 0.13,
    "tax_audit_financial_anomaly": 0.12,
    "source_opacity": 0.08,
    "network_centrality": 0.06,
    "verifiability": 0.06,
}


class InvestigationProfileService:
    """Loads the generic case profile that governs source gates and pruning."""

    def load_for_case(self, request: CaseRequest) -> InvestigationProfile:
        profile_path = request.metadata.get("investigation_profile_path")
        if profile_path:
            path = Path(str(profile_path))
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[1] / path
            if path.exists():
                return self._from_dict(json.loads(path.read_text(encoding="utf-8")))

        profile = request.metadata.get("investigation_profile")
        if isinstance(profile, dict):
            return self._from_dict(profile)

        return InvestigationProfile(
            profile_id=str(request.metadata.get("profile_id") or "generic_california_oversight"),
            title=str(request.metadata.get("profile_title") or request.title),
            topic=str(request.metadata.get("topic") or "public-funds oversight"),
            jurisdiction=request.jurisdiction,
            target_universe=str(request.metadata.get("target_universe") or "named entities in the case request"),
            selection_metric=str(request.metadata.get("selection_metric") or "Review Value Score"),
            required_source_families=list(request.metadata.get("required_source_families") or DEFAULT_SOURCE_FAMILIES),
            scoring_weights=dict(request.metadata.get("review_value_weights") or DEFAULT_REVIEW_VALUE_WEIGHTS),
            deep_dive_threshold=float(request.metadata.get("deep_dive_threshold") or 60.0),
            max_targets=int(request.metadata.get("max_targets") or request.max_results or 15),
            language_rules=list(request.metadata.get("language_rules") or [
                "Treat outputs as source-cited review leads, not legal findings.",
                "Preserve named-party legal distinctions and open source blockers.",
            ]),
            publication_policy=str(request.metadata.get("publication_policy") or "public_safe_after_human_review_gate"),
            completion_gates=list(request.metadata.get("completion_gates") or DEFAULT_COMPLETION_GATES),
            deep_source_families=list(request.metadata.get("deep_source_families") or DEFAULT_DEEP_SOURCE_FAMILIES),
            source_connectors=list(request.metadata.get("source_connectors") or []),
            entity_aliases=dict(request.metadata.get("entity_aliases") or {}),
            target_discovery_rules=list(request.metadata.get("target_discovery_rules") or [
                "Rank named and source-discovered entities by Review Value Score.",
                "Do not rely on public-dollar exposure alone when official adverse records or source opacity create higher review value.",
            ]),
            forensic_tests=list(request.metadata.get("forensic_tests") or []),
            evidence_store_policy=dict(request.metadata.get("evidence_store_policy") or {
                "snapshot_required_for_public_links": True,
                "hash_algorithm": "sha256",
                "parser_version_required": True,
            }),
            human_action_rules=list(request.metadata.get("human_action_rules") or [
                "Every recommended action must identify the document or authority a human must use.",
                "Do not represent a missing public source as clearance.",
            ]),
        )

    def _from_dict(self, value: dict[str, object]) -> InvestigationProfile:
        return InvestigationProfile(
            profile_id=str(value["profile_id"]),
            title=str(value.get("title") or value["profile_id"]),
            topic=str(value.get("topic") or "public-funds oversight"),
            jurisdiction=str(value.get("jurisdiction") or "California"),
            target_universe=str(value.get("target_universe") or "configured case entities"),
            selection_metric=str(value.get("selection_metric") or "Review Value Score"),
            required_source_families=list(value.get("required_source_families") or DEFAULT_SOURCE_FAMILIES),
            scoring_weights=dict(value.get("scoring_weights") or DEFAULT_REVIEW_VALUE_WEIGHTS),
            deep_dive_threshold=float(value.get("deep_dive_threshold") or 60.0),
            max_targets=int(value.get("max_targets") or 15),
            language_rules=list(value.get("language_rules") or []),
            publication_policy=str(value.get("publication_policy") or "public_safe_after_human_review_gate"),
            completion_gates=list(value.get("completion_gates") or DEFAULT_COMPLETION_GATES),
            deep_source_families=list(value.get("deep_source_families") or DEFAULT_DEEP_SOURCE_FAMILIES),
            source_connectors=list(value.get("source_connectors") or []),
            entity_aliases=dict(value.get("entity_aliases") or {}),
            target_discovery_rules=list(value.get("target_discovery_rules") or []),
            forensic_tests=list(value.get("forensic_tests") or []),
            evidence_store_policy=dict(value.get("evidence_store_policy") or {}),
            human_action_rules=list(value.get("human_action_rules") or []),
        )


class ReviewValueScoringService:
    """Deterministic target-pruning score for any investigation profile."""

    def score_entity(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        entity: str,
        records: Iterable[CanonicalRecord],
        findings: list[TriageFinding],
        missing_source_families: list[str],
    ) -> ReviewValueScore:
        entity_records = list(records)
        weights = self._normalized_weights(profile.scoring_weights)
        components = {
            "public_money_exposure": self._money_score(entity_records),
            "official_adverse_record": self._adverse_score(entity_records, findings),
            "scope_mismatch": self._scope_score(entity_records, findings),
            "spend_outcome_mismatch": self._outcome_score(entity_records, findings),
            "tax_audit_financial_anomaly": self._tax_audit_score(entity_records, findings),
            "source_opacity": self._opacity_score(profile, missing_source_families, entity_records),
            "network_centrality": self._network_score(entity_records),
            "verifiability": self._verifiability_score(entity_records, findings),
        }
        final = round(sum(components[key] * weights.get(key, 0.0) for key in components), 2)
        drivers = [
            f"{key.replace('_', ' ')} {components[key]:g}/100"
            for key in sorted(components, key=lambda item: components[item], reverse=True)
            if components[key] >= 50
        ][:4]
        rationale = (
            f"Review Value Score combines materiality, adverse-record signals, scope and outcome mismatch, "
            f"financial/audit signals, opacity, network position, and verifiability. Strongest drivers: "
            f"{'; '.join(drivers) if drivers else 'no component reached 50/100'}."
        )
        return ReviewValueScore(
            score_id=stable_id("review_value", request.case_id, entity, str(final)),
            case_id=request.case_id,
            entity=entity,
            final_score=final,
            component_scores={key: round(value, 2) for key, value in sorted(components.items())},
            weights={key: round(value, 4) for key, value in sorted(weights.items())},
            rationale=rationale,
            source_record_ids=self._dedupe(record.record_id for record in entity_records),
            source_uris=self._dedupe(
                [record.source_uri for record in entity_records]
                + [uri for finding in findings for uri in finding.source_uris]
            ),
        )

    def _normalized_weights(self, weights: dict[str, float]) -> dict[str, float]:
        merged = dict(DEFAULT_REVIEW_VALUE_WEIGHTS)
        merged.update({key: float(value) for key, value in weights.items()})
        total = sum(max(0.0, value) for value in merged.values()) or 1.0
        return {key: max(0.0, value) / total for key, value in merged.items()}

    def _money_score(self, records: list[CanonicalRecord]) -> float:
        values: list[float] = []
        for record in records:
            attrs = record.attributes
            for key in ("total_award_exposure", "completed_payments", "total_completed_payments", "contract_value"):
                value = self._number(attrs.get(key))
                if value is not None:
                    values.append(value)
            for key, value in attrs.items():
                if "payment" in key or "award" in key or "contract" in key:
                    number = self._number(value)
                    if number is not None:
                        values.append(number)
        exposure = max(values or [0.0])
        if exposure >= 100_000_000:
            return 100.0
        if exposure >= 50_000_000:
            return 85.0
        if exposure >= 25_000_000:
            return 70.0
        if exposure >= 10_000_000:
            return 55.0
        if exposure > 0:
            return 35.0
        return 0.0

    def _adverse_score(self, records: list[CanonicalRecord], findings: list[TriageFinding]) -> float:
        if any(finding.source_family == "enforcement_or_docket" and finding.risk_level == "High" for finding in findings):
            return 100.0
        if any(finding.source_family == "enforcement_or_docket" for finding in findings):
            return 75.0
        for record in records:
            signals = dict(record.attributes.get("signals", {}))
            text = f"{record.title} {record.body}".lower()
            if signals.get("official_enforcement_or_docket_flag") or signals.get("connected_party_enforcement_exposure"):
                return 100.0
            if any(term in text for term in ("debar", "suspend", "charged", "misappropriat", "violation", "falsified invoice")):
                return 85.0
            if "audit" in text and any(term in text for term in ("noncompliance", "wasteful", "unallowable", "corrective action")):
                return 70.0
        return 0.0

    def _scope_score(self, records: list[CanonicalRecord], findings: list[TriageFinding]) -> float:
        if any(finding.source_family == "web_and_social" and finding.risk_level == "High" for finding in findings):
            return 90.0
        if any(finding.source_family == "web_and_social" for finding in findings):
            return 65.0
        if any(dict(record.attributes.get("signals", {})).get("off_scope_keyword_match") for record in records):
            return 55.0
        return 0.0

    def _outcome_score(self, records: list[CanonicalRecord], findings: list[TriageFinding]) -> float:
        if any(finding.source_family == "outcomes" for finding in findings):
            return 70.0
        for record in records:
            value = f"{record.source_type} {record.body}".lower()
            if "spend-versus-results" in value or "outcome_flags" in value or "outcome context" in value:
                return 60.0
        return 0.0

    def _tax_audit_score(self, records: list[CanonicalRecord], findings: list[TriageFinding]) -> float:
        if any(finding.source_family in {"irs_990", "audit"} and finding.risk_level == "High" for finding in findings):
            return 90.0
        signals = Counter()
        for record in records:
            for key, value in dict(record.attributes.get("signals", {})).items():
                if value:
                    signals[key] += 1
        important = {
            "fac_material_weakness",
            "fac_significant_deficiency",
            "fac_questioned_costs",
            "reported_conflict_transactions",
            "schedule_l_present",
            "high_compensation",
            "rapid_growth",
            "lobbying_activities",
            "political_campaign_activity",
        }
        hits = sum(signals[key] for key in important)
        return min(100.0, hits * 25.0)

    def _opacity_score(
        self,
        profile: InvestigationProfile,
        missing_source_families: list[str],
        records: list[CanonicalRecord],
    ) -> float:
        if not profile.required_source_families:
            return 0.0
        source_gap_records = sum(1 for record in records if dict(record.attributes.get("signals", {})).get("missing_data"))
        ratio = len(missing_source_families) / len(profile.required_source_families)
        return min(100.0, ratio * 100.0 + min(30.0, source_gap_records * 5.0))

    def _network_score(self, records: list[CanonicalRecord]) -> float:
        source_types = {record.source_type for record in records}
        cross_refs = len(records)
        return min(100.0, len(source_types) * 12.0 + cross_refs * 4.0)

    def _verifiability_score(self, records: list[CanonicalRecord], findings: list[TriageFinding]) -> float:
        pointers = 0
        total = len(records) + len(findings)
        if total == 0:
            return 0.0
        for record in records:
            if record.source_uri and (record.source_uri.startswith("http") or Path(str(record.source_uri)).suffix):
                pointers += 1
        for finding in findings:
            if finding.source_uris or finding.record_ids:
                pointers += 1
        return min(100.0, (pointers / total) * 100.0)

    def _number(self, value: object) -> float | None:
        try:
            text = str(value or "").replace(",", "").replace("$", "").strip()
            if not text:
                return None
            return float(text)
        except Exception:
            return None

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
