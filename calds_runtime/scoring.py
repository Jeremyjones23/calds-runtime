from __future__ import annotations

from collections import Counter

from .contracts import CompletionGuardResult, EvidenceBundle, ScoreInputs


class LeadScoringService:
    """Truth-adjacent deterministic scoring inputs for reviewer triage."""

    def score(self, bundle: EvidenceBundle, completion_guard: CompletionGuardResult | None = None) -> ScoreInputs:
        support_count = len(bundle.items)
        if support_count:
            average_relevance = round(
                sum(item.relevance_score for item in bundle.items) / support_count,
                3,
            )
        else:
            average_relevance = 0.0

        source_diversity = len({item.source_type for item in bundle.items})
        hard_link_count = sum(1 for link in bundle.entity_links if link.strength >= 0.7)
        contradiction_count = sum(
            1 for item in bundle.items if bool(item.signals.get("contradiction"))
        )
        missing_data_count = sum(
            1 for item in bundle.items if bool(item.signals.get("missing_data"))
        )
        missing_data_source_types = Counter(
            item.source_type for item in bundle.items if bool(item.signals.get("missing_data"))
        )
        contradiction_source_types = Counter(
            item.source_type for item in bundle.items if bool(item.signals.get("contradiction"))
        )

        evidence_strength = (
            20.0
            + (average_relevance * 35.0)
            + min(20.0, support_count * 4.0)
            + min(15.0, source_diversity * 4.0)
            + min(20.0, hard_link_count * 5.0)
        )
        risk_severity_score = round(max(0.0, min(100.0, evidence_strength)), 2)

        guard_total = int(completion_guard.total_searches) if completion_guard else 0
        guard_blockers = int(completion_guard.blocker_count) if completion_guard else 0
        guard_misses = int(completion_guard.miss_count) if completion_guard else 0
        if guard_total > 0:
            # blocker_count is the authoritative unresolved-required-check count.
            # miss_count is retained as a diagnostic and can overlap with blockers.
            guard_unresolved = min(guard_total, guard_blockers)
            guard_resolved = max(0, guard_total - guard_unresolved)
            source_completeness_score = round((guard_resolved / guard_total) * 100.0, 2)
        else:
            guard_resolved = 0
            source_completeness_score = 0.0

        diversity_confidence = min(100.0, source_diversity * 12.5)
        if support_count:
            traceable_items = sum(
                1
                for item in bundle.items
                if item.source_uri and item.provenance.source_uri and item.provenance.checksum
            )
            traceability_confidence = (traceable_items / support_count) * 100.0
        else:
            traceability_confidence = 0.0

        gap_burden_count = missing_data_count
        caveat_penalty = min(45.0, gap_burden_count * 1.5 + contradiction_count * 8.0)
        publication_confidence_score = round(
            max(
                0.0,
                min(
                    100.0,
                    source_completeness_score * 0.55
                    + diversity_confidence * 0.25
                    + traceability_confidence * 0.20
                    - caveat_penalty,
                ),
            ),
            2,
        )
        final_score = round(
            max(
                0.0,
                min(
                    100.0,
                    risk_severity_score * 0.70
                    + source_completeness_score * 0.10
                    + publication_confidence_score * 0.20,
                ),
            ),
            2,
        )
        return ScoreInputs(
            support_count=support_count,
            average_relevance=average_relevance,
            source_diversity=source_diversity,
            hard_link_count=hard_link_count,
            contradiction_count=contradiction_count,
            missing_data_count=missing_data_count,
            final_score=final_score,
            risk_severity_score=risk_severity_score,
            source_completeness_score=source_completeness_score,
            publication_confidence_score=publication_confidence_score,
            source_diversity_confidence_score=round(diversity_confidence, 2),
            traceability_confidence_score=round(traceability_confidence, 2),
            caveat_penalty_score=round(caveat_penalty, 2),
            completion_guard_total=guard_total,
            completion_guard_resolved=guard_resolved,
            completion_guard_blocker_count=guard_blockers,
            completion_guard_miss_count=guard_misses,
            gap_burden_count=gap_burden_count,
            missing_data_source_types=dict(sorted(missing_data_source_types.items())),
            contradiction_source_types=dict(sorted(contradiction_source_types.items())),
        )
