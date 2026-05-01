from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Iterable

from .contracts import (
    CanonicalRecord,
    CaseRequest,
    EntityLink,
    EvidenceBundle,
    EvidenceItem,
    Provenance,
    SearchHit,
    sha256_text,
    stable_id,
    utc_now,
)


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]*", re.IGNORECASE)


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


class JsonCorpusTruthStore:
    """Deterministic truth-plane adapter backed by local JSON records."""

    def __init__(self, corpus_dir: Path, corpus_name: str = "local-fixture-corpus") -> None:
        self.corpus_dir = corpus_dir
        self.corpus_name = corpus_name
        self._records = self._load_records()

    @property
    def records(self) -> list[CanonicalRecord]:
        return list(self._records.values())

    def get_record(self, record_id: str) -> CanonicalRecord:
        return self._records[record_id]

    def _load_records(self) -> dict[str, CanonicalRecord]:
        if not self.corpus_dir.exists():
            raise FileNotFoundError(f"Corpus directory does not exist: {self.corpus_dir}")

        loaded: dict[str, CanonicalRecord] = {}
        for path in sorted(self.corpus_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            body = str(data.get("body", ""))
            record_id = str(data["record_id"])
            source_uri = str(data["source_uri"])
            source_type = str(data["source_type"])
            collected_at = str(data.get("collected_at", "2026-04-24T00:00:00+00:00"))
            checksum = sha256_text(
                "|".join(
                    [
                        record_id,
                        str(data.get("title", "")),
                        body,
                        source_uri,
                        source_type,
                    ]
                )
            )
            provenance = Provenance(
                record_id=record_id,
                source_uri=source_uri,
                source_type=source_type,
                collected_at=collected_at,
                checksum=checksum,
                corpus_name=self.corpus_name,
                chunk_id=str(data.get("chunk_id", f"{record_id}#body")),
            )
            loaded[record_id] = CanonicalRecord(
                record_id=record_id,
                title=str(data.get("title", record_id)),
                body=body,
                source_uri=source_uri,
                source_type=source_type,
                published_at=str(data.get("published_at", "unknown")),
                entities=[str(entity) for entity in data.get("entities", [])],
                attributes=dict(data.get("attributes", {})),
                provenance=provenance,
            )
        if not loaded:
            raise ValueError(f"No JSON records found in corpus directory: {self.corpus_dir}")
        return loaded

    def build_evidence_bundle(
        self,
        request: CaseRequest,
        query_terms: list[str],
        hits: Iterable[SearchHit],
    ) -> EvidenceBundle:
        items: list[EvidenceItem] = []
        for hit in hits:
            record = self.get_record(hit.record_id)
            item = EvidenceItem(
                item_id=stable_id("evidence", request.case_id, record.record_id),
                record_id=record.record_id,
                title=record.title,
                source_uri=record.source_uri,
                source_type=record.source_type,
                published_at=record.published_at,
                excerpt=self._excerpt(
                    record.body,
                    hit.matched_terms,
                    radius=900
                    if record.source_type.startswith("source_extraction_")
            or record.source_type in {"irs_990_rendered_secondary_source", "irs_990_full_text_fallback", "irs_990_raw_artifact", "irs_990_raw_artifact_discovery", "contract_payment_discovery", "enforcement_docket_discovery", "dhcs_adverse_status_discovery", "org_service_page", "public_statement_source", "enforcement_or_docket_source", "social_media_source"}
                    else 190,
                    prefer_start=record.source_type.startswith("source_extraction_")
                    or record.source_type in {"irs_990_raw_artifact", "irs_990_raw_artifact_discovery", "contract_payment_discovery", "enforcement_docket_discovery", "org_service_page", "public_statement_source", "enforcement_or_docket_source", "social_media_source"},
                ),
                relevance_score=round(hit.relevance_score, 3),
                matched_terms=hit.matched_terms,
                provenance=record.provenance,
                signals=dict(record.attributes.get("signals", {})),
            )
            items.append(item)

        return EvidenceBundle(
            bundle_id=stable_id("bundle", request.case_id, "evidence", *[item.record_id for item in items]),
            case_id=request.case_id,
            query_terms=query_terms,
            items=items,
            entity_links=self.build_entity_links(items),
            created_at=utc_now(),
        )

    def build_entity_links(self, items: list[EvidenceItem]) -> list[EntityLink]:
        records_by_id = {record.record_id: record for record in self.records}
        record_ids_by_entity: dict[str, list[str]] = {}
        for item in items:
            for entity in records_by_id[item.record_id].entities:
                record_ids_by_entity.setdefault(entity, []).append(item.record_id)

        links: list[EntityLink] = []
        for entity, record_ids in sorted(record_ids_by_entity.items()):
            unique_ids = sorted(set(record_ids))
            if len(unique_ids) < 2:
                strength = 0.35
                link_type = "single-record-mention"
                rationale = "Entity appears in one retrieved record only."
            else:
                source_types = {
                    records_by_id[record_id].source_type for record_id in unique_ids
                }
                strength = min(1.0, 0.45 + 0.15 * len(unique_ids) + 0.1 * len(source_types))
                link_type = "cross-source-link" if len(source_types) > 1 else "same-source-link"
                rationale = "Entity appears across multiple retrieved records."
            links.append(
                EntityLink(
                    entity=entity,
                    record_ids=unique_ids,
                    link_type=link_type,
                    strength=round(strength, 2),
                    rationale=rationale,
                )
            )
        return links

    def _excerpt(self, body: str, terms: list[str], radius: int = 190, prefer_start: bool = False) -> str:
        if not body:
            return ""
        if prefer_start:
            excerpt = body[: radius * 2].strip()
            if len(body) > radius * 2:
                excerpt = excerpt + "..."
            return excerpt
        lowered = body.lower()
        match_index = -1
        for term in terms:
            match_index = lowered.find(term.lower())
            if match_index >= 0:
                break
        if match_index < 0:
            return body[: radius * 2].strip()
        start = max(0, match_index - radius)
        end = min(len(body), match_index + radius)
        excerpt = body[start:end].strip()
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(body):
            excerpt = excerpt + "..."
        return excerpt

