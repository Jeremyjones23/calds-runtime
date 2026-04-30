from __future__ import annotations

from .contracts import EvidenceBundle, ScoreInputs


class LeadScoringService:
    """Truth-adjacent deterministic scoring inputs for reviewer triage."""

    def score(self, bundle: EvidenceBundle) -> ScoreInputs:
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

        evidence_strength = (
            20.0
            + (average_relevance * 35.0)
            + min(20.0, support_count * 4.0)
            + min(15.0, source_diversity * 4.0)
            + min(20.0, hard_link_count * 5.0)
        )
        risk_severity_score = round(max(0.0, min(100.0, evidence_strength)), 2)
        source_completeness_score = round(
            max(0.0, min(100.0, 100.0 - contradiction_count * 6.0 - missing_data_count * 5.0)),
            2,
        )
        diversity_confidence = min(100.0, source_diversity * 12.5)
        publication_confidence_score = round(
            max(0.0, min(100.0, source_completeness_score * 0.7 + diversity_confidence * 0.3)),
            2,
        )
        final_score = round(
            max(
                0.0,
                min(
                    100.0,
                    risk_severity_score * 0.65
                    + source_completeness_score * 0.25
                    + publication_confidence_score * 0.10,
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
        )
