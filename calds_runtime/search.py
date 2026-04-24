from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import CanonicalRecord, SearchHit
from .truth import tokenize


@dataclass(frozen=True)
class SearchPlan:
    terms: list[str]
    allowed_sources: list[str]
    max_results: int
    required_source_types: list[str] = field(default_factory=list)


class KeywordSearchIndex:
    """Deterministic search-plane adapter over truth-plane records."""

    def __init__(self, records: list[CanonicalRecord]) -> None:
        self.records = records
        self._tokens_by_record = {
            record.record_id: set(
                tokenize(
                    " ".join(
                        [
                            record.title,
                            record.body,
                            " ".join(record.entities),
                            " ".join(str(value) for value in record.attributes.values()),
                        ]
                    )
                )
            )
            for record in records
        }

    def search(self, plan: SearchPlan) -> list[SearchHit]:
        terms = sorted(set(token.lower() for token in plan.terms if token.strip()))
        term_set = set(terms)
        if not terms:
            return []

        allowed = set(plan.allowed_sources)
        hits: list[SearchHit] = []
        for record in self.records:
            if allowed and record.source_type not in allowed:
                continue
            record_tokens = self._tokens_by_record[record.record_id]
            matched_terms = [term for term in terms if term in record_tokens]
            if not matched_terms:
                continue
            entity_bonus = 0.0
            for entity in record.entities:
                entity_terms = set(tokenize(entity))
                if entity_terms and entity_terms.issubset(term_set):
                    entity_bonus += 0.2
                elif entity_terms:
                    entity_bonus += min(0.12, 0.04 * len(entity_terms & term_set))
            if len(matched_terms) < 2 and entity_bonus < 0.1:
                continue
            coverage = len(matched_terms) / max(1, len(terms))
            score = min(1.0, coverage + min(0.35, entity_bonus))
            hits.append(
                SearchHit(
                    record_id=record.record_id,
                    relevance_score=round(score, 3),
                    matched_terms=matched_terms,
                )
            )

        ranked_hits = sorted(
            hits,
            key=lambda hit: (-hit.relevance_score, hit.record_id),
        )
        return self._diversify_by_source_type(ranked_hits, plan)

    def _diversify_by_source_type(self, ranked_hits: list[SearchHit], plan: SearchPlan) -> list[SearchHit]:
        if not plan.required_source_types or plan.max_results <= 0:
            return ranked_hits[: plan.max_results]

        records_by_id = {record.record_id: record for record in self.records}
        selected: list[SearchHit] = []
        selected_ids: set[str] = set()

        for source_type in plan.required_source_types:
            for hit in ranked_hits:
                if hit.record_id in selected_ids:
                    continue
                if records_by_id[hit.record_id].source_type == source_type:
                    selected.append(hit)
                    selected_ids.add(hit.record_id)
                    break
            if len(selected) >= plan.max_results:
                return selected

        for hit in ranked_hits:
            if hit.record_id in selected_ids:
                continue
            selected.append(hit)
            selected_ids.add(hit.record_id)
            if len(selected) >= plan.max_results:
                break
        return selected
