from __future__ import annotations

from collections import Counter
import re
from pathlib import Path
from typing import Iterable

from .contracts import (
    AgentRole,
    CaseRequest,
    CompiledCaseDossier,
    EntityLink,
    EvidenceBundle,
    EvidenceItem,
    HumanDecision,
    LeadCandidate,
    OversightRiskIndicator,
    OversightRiskMatrix,
    Provenance,
    ReviewDecision,
    ReviewPacket,
    ScoreInputs,
    SentinelDecision,
    SentinelResult,
    read_json,
    stable_id,
    write_json,
)
from .plain_language import REVIEWER_GLOSSARY_LINES, expand_reviewer_acronyms
from .review import SOURCE_TYPE_LABELS


RISK_ORDER = {"High": 0, "Medium": 1, "Data gap": 2, "Low": 3}
GENERIC_ENTITY_TOKENS = {
    "association",
    "california",
    "center",
    "community",
    "corporation",
    "development",
    "enterprises",
    "housing",
    "humanity",
    "inc",
    "northern",
    "services",
    "service",
    "social",
    "southern",
    "supportive",
    "the",
}



class CaseDossierService:
    """Deterministic service for final human-review case dossiers."""

    def __init__(self, path_remaps: dict[str, str] | None = None) -> None:
        self.path_remaps = path_remaps or {}

    def write_dossier(
        self,
        path: Path,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        risk_matrix: OversightRiskMatrix,
        review_packet: ReviewPacket,
        review_decision: ReviewDecision,
        source_artifact_refs: list[str],
    ) -> CompiledCaseDossier:
        path.parent.mkdir(parents=True, exist_ok=True)
        labels = self._evidence_labels(bundle)
        triage_tiers = self._triage_tiers(source_artifact_refs)
        priority_rows = self._priority_indicators(risk_matrix)
        source_counts = Counter(item.source_type for item in bundle.items)
        sentinel_items = [f"- {self._plain_language(item)}" for item in sentinel.repair_instructions] or ["- none"]
        mode = self._dossier_mode(sentinel)

        lines = [
            f"# Case Dossier: {request.title}",
            "",
            "## 1. Executive Snapshot",
            "",
            *self._executive_snapshot_lines(request, bundle, lead, sentinel, review_decision, risk_matrix, labels, triage_tiers),
            "",
            "### What The Score Means",
            "",
            *self._score_plain_language_lines(lead),
            "",
            "### Decision Needed",
            "",
            f"- Human-review state: `{review_decision.decision.value}`. The workflow is paused until a reviewer approves, downgrades, repairs, or rejects the case.",
            f"- Sentinel posture: `{sentinel.decision.value}`. {sentinel.rationale}",
            f"- Immediate reviewer action: {self._supervisor_next_action(bundle, risk_matrix, sentinel)}",
            "",
            "### What This Does Not Prove",
            "",
            *self._case_limits(risk_matrix, sentinel),
            "",
            "## 2. Case In One Page",
            "",
            *self._case_one_page_lines(request, bundle, lead, sentinel, risk_matrix, labels, triage_tiers),
            "",
            "## 3. Entity Briefs",
            "",
            "These briefs assume the reader has not seen the agent work. Deep-review entities are separated from watchlist or matrix-only entities so the reader can see what CalDS selected for deeper review versus what remains contextual.",
            "",
            *self._briefing_memo_lines(request, bundle, lead, sentinel, risk_matrix, labels, triage_tiers),
            "",
            "## 4. Methodology, Guardrails, and Source Status",
            "",
            "### Triage Gate",
            "",
            *self._triage_gate_lines(source_artifact_refs),
            "",
            "### Acquisition and Completion Guard",
            "",
            *self._completion_guard_lines(source_artifact_refs),
            "",
            "### Plain-Language Source Glossary",
            "",
            *self._glossary_lines(),
            "",
            "### Score Components and Sentinel",
            "",
            f"Lead statement: {lead.statement}",
            "",
            f"Review priority score: {lead.score} / 100",
            "",
            self._score_interpretation(lead.score),
            "",
            "The score is deterministic triage priority, not a probability, not a dollar loss estimate, and not a conclusion. CalDS now splits the score into risk severity, source completeness, and publication confidence so a strong review signal is not confused with publication readiness.",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Risk severity score | {lead.score_inputs.risk_severity_score} / 100 |",
            f"| Source completeness score | {lead.score_inputs.source_completeness_score} / 100 |",
            f"| Publication confidence score | {lead.score_inputs.publication_confidence_score} / 100 |",
            f"| Support count | {lead.score_inputs.support_count} |",
            f"| Average relevance | {lead.score_inputs.average_relevance} |",
            f"| Source diversity | {lead.score_inputs.source_diversity} |",
            f"| Hard entity links | {lead.score_inputs.hard_link_count} |",
            f"| Completion guard resolved checks | {lead.score_inputs.completion_guard_resolved} of {lead.score_inputs.completion_guard_total} |",
            f"| Completion guard unresolved blockers | {lead.score_inputs.completion_guard_blocker_count} blocker(s); {lead.score_inputs.completion_guard_miss_count} miss(es) |",
            f"| Open gap burden | {lead.score_inputs.gap_burden_count} caveat signal(s) |",
            f"| Gap signal source buckets | {self._source_type_counts_text(lead.score_inputs.missing_data_source_types)} |",
            f"| Contradiction count | {lead.score_inputs.contradiction_count} caution signal(s) |",
            "",
            "### Sentinel Gate",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Decision | {sentinel.decision.value} |",
            f"| Rationale | {self._table_cell(sentinel.rationale)} |",
            f"| Flags | {self._table_cell(', '.join(sentinel.flags) if sentinel.flags else 'none')} |",
            "",
            "Sentinel repair or caution items:",
            "",
            *sentinel_items,
            "",
            "### Case Context",
            "",
            f"- Case ID: `{request.case_id}`",
            f"- Jurisdiction: {request.jurisdiction}",
            f"- Objective: {request.objective}",
            f"- Named entities: {', '.join(request.entities) or 'none specified'}",
            f"- Allowed source types: {', '.join(request.allowed_sources) or 'none specified'}",
            f"- Review packet: `{review_packet.markdown_path}`",
            "",
            "## 5. Case Dossier Orientation",
            "",
            f"Status: `{review_decision.decision.value}` human review required",
            "",
            "This dossier compiles existing CalDS workflow artifacts into a human-readable case file. It is an internal possible waste, fraud, abuse, or mismanagement screening aid, not a formal finding or outside-facing conclusion.",
            "",
            "Every substantive row below is tied to a risk indicator, evidence item, source URI, checksum, or durable artifact path. Raw source documents and canonical records remain controlling.",
            "",
            f"Dossier mode: {mode}",
            "",
            "## 6. Evidence Detail By Entity",
            "",
            "This section preserves the system opinion and source-fact detail behind the briefing memo. It remains an internal possible waste, fraud, abuse, or mismanagement screening opinion, not a formal allegation or outside-facing conclusion.",
            "",
            *self._entity_opinion_lines(risk_matrix, labels, triage_tiers),
            "",
            "## 7. Flagged Review Matrix",
            "",
            f"Methodology: {risk_matrix.methodology}",
            "",
            f"Risk scale: {risk_matrix.score_scale}",
            "",
            "| Risk level | Count |",
            "| --- | --- |",
        ]
        counts = Counter(item.risk_level for item in risk_matrix.indicators)
        for level in ["High", "Medium", "Data gap", "Low"]:
            lines.append(f"| {level} | {counts.get(level, 0)} |")

        lines.extend(
            [
                "",
                "High and medium rows are review priorities. Data-gap rows are source-collection blockers. Low rows are not expanded here unless they are needed for context.",
                "",

            ]
        )
        if priority_rows:
            for level in ["High", "Medium", "Data gap"]:
                level_rows = [item for item in priority_rows if item.risk_level == level]
                if not level_rows:
                    continue
                lines.extend([f"### {level} Rows", ""])
                for index, item in enumerate(level_rows, start=1):
                    refs = self._matrix_refs(item, labels)
                    lines.extend(
                        [
                            f"#### {level}-{index}: {item.entity} - {item.risk_area}",
                            "",
                            f"- Test: {item.test_name}",
                            f"- What CalDS found: {self._plain_language(item.observed_fact)} Evidence: {refs}.",
                            f"- When/where: {self._when_where(item)} Evidence: {refs}.",
                            f"- How this triggered review: {self._trigger_text(item)} Evidence: {refs}.",
                            f"- Evidence refs: {refs}",
                            f"- Source URI(s): {self._format_source_uris(item.source_uris)}",
                            f"- System opinion: {self._plain_language(self._system_opinion(item))} Evidence: {refs}.",
                            f"- Why this matters: {self._plain_language(self._why_it_matters(item))}",
                            f"- What this flags: {self._plain_language(item.reviewer_action)} Evidence: {refs}.",
                            f"- What this does not prove: {self._plain_language(self._not_proven_text(item))}",
                            f"- Human next step: {self._plain_language(self._indicator_next_step(item))}",
                            *[f"- Caveat: {self._plain_language(caveat)}" for caveat in item.caveats],
                            "",
                        ]
                    )
        else:
            lines.extend(["No high, medium, or data-gap rows were generated from the current source corpus.", ""])

        lines.extend(
            [
                "## 8. Evidence Citation Ledger",
                "",
                "Use this ledger to move from the readable case file back to source records. The packet-local `E##` labels are reading aids only; internal evidence IDs and checksums preserve replayability.",
                "",
                "| Ref | Internal evidence ID | Record ID | Source type | Source URI | Published | Checksum |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in bundle.items:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{labels[item.item_id]}`",
                        f"`{item.item_id}`",
                        f"`{item.record_id}`",
                        self._table_cell(self._source_type_label(item.source_type)),
                        self._table_cell(self._display_uri(item.source_uri)),
                        self._table_cell(item.published_at or "not provided"),
                        f"`{item.provenance.checksum}`",
                    ]
                )
                + " |"
            )

        lines.extend(
            [
                "",
                "### Source Coverage Snapshot",
                "",
                "| Source class | Count |",
                "| --- | --- |",
            ]
        )
        for source_type, count in sorted(source_counts.items(), key=lambda pair: (-pair[1], pair[0])):
            lines.append(f"| {self._table_cell(self._source_type_label(source_type))} | {count} |")

        lines.extend(
            [
                "",
                "## 9. Human-Only Next Steps",
                "",
                "These actions are outside the current CalDS runtime. They require a human reviewer or authorized records process before any escalation beyond internal review.",
                "",
            ]
        )
        for index, step in enumerate(self._human_next_steps(bundle, risk_matrix, sentinel), start=1):
            lines.append(f"{index}. {step}")

        lines.extend(
            [
                "",
                "## 10. Artifact References",
                "",
                "These are the durable workflow artifacts used by the compiler.",
                "",
                "| Artifact | Path |",
                "| --- | --- |",
            ]
        )
        for ref in source_artifact_refs:
            lines.append(f"| {self._table_cell(Path(ref).name)} | `{ref}` |")

        lines.extend(
            [
                "",
                "## 11. Human Review Required",
                "",
                "The workflow remains paused. A reviewer must explicitly approve, downgrade, repair, or reject this case before any outside-facing use.",
                "",
            ]
        )

        lines = [self._plain_language(line) for line in lines]
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return CompiledCaseDossier(
            dossier_id=stable_id("dossier", request.case_id, str(path)),
            case_id=request.case_id,
            markdown_path=str(path),
            source_artifact_refs=source_artifact_refs,
            sentinel_decision=sentinel.decision,
            compiler_role=AgentRole.CASE_COMPILER,
        )

    def _plain_language(self, text: object) -> str:
        return expand_reviewer_acronyms(text)

    def _source_type_label(self, source_type: str) -> str:
        return self._plain_language(SOURCE_TYPE_LABELS.get(source_type, source_type))

    def _glossary_lines(self) -> list[str]:
        return REVIEWER_GLOSSARY_LINES

    def _executive_snapshot_lines(
        self,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        review_decision: ReviewDecision,
        matrix: OversightRiskMatrix,
        labels: dict[str, str],
        triage_tiers: dict[str, object],
    ) -> list[str]:
        selected = self._selected_entities(triage_tiers, matrix)
        focus_rows = self._focus_rows(matrix, triage_tiers)
        signal_summary = self._signal_summary(focus_rows)
        selected_text = ", ".join(selected) if selected else "none selected by implemented thresholds"
        lines = [
            f"Bottom line: {self._case_bottom_line(request, bundle, lead, sentinel, matrix, labels, triage_tiers)}",
            "",
            f"- Case posture: internal possible waste, fraud, abuse, or mismanagement review lead; not a formal finding.",
            f"- Entities selected for deep review: {selected_text}.",
            f"- Main signal pattern: {signal_summary}.",
            f"- Review priority: {lead.score_inputs.final_score} / 100; risk severity: {lead.score_inputs.risk_severity_score} / 100; source completeness: {lead.score_inputs.source_completeness_score} / 100; publication confidence: {lead.score_inputs.publication_confidence_score} / 100.",
            "- Score scope: these are case-level scores for this run's evidence bundle. They are not entity-by-entity grades, not probabilities, and not a measure of how polished the report is.",
            f"- Current workflow state: `{review_decision.decision.value}` with sentinel posture `{sentinel.decision.value}`.",
            "",
            "What CalDS found first:",
            "",
            *self._top_source_findings(bundle, labels, matrix, limit=3),
            "",
            "Why this is on a reviewer's desk:",
            "",
            *self._why_on_desk_lines(matrix, labels, triage_tiers),
        ]
        return lines

    def _case_one_page_lines(
        self,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        matrix: OversightRiskMatrix,
        labels: dict[str, str],
        triage_tiers: dict[str, object],
    ) -> list[str]:
        selected = self._selected_entities(triage_tiers, matrix)
        focus_rows = self._focus_rows(matrix, triage_tiers)
        selected_text = ", ".join(selected) if selected else "no entity"
        source_phrase = self._source_family_phrase(bundle)
        why_rows = self._substantive_rows(focus_rows)[:3]
        lines = [
            (
                f"CalDS screened {self._entity_count_phrase(request)} in {request.jurisdiction} for this objective: "
                f"{str(request.objective).rstrip('.')}. The run selected {selected_text} for deeper review using deterministic triage thresholds. "
                f"The source bundle includes {source_phrase}. Evidence references below use short `E##` labels, with full source details in the citation ledger."
            ),
            "",
        ]
        if why_rows:
            lines.append("The case is not based on a row count. It is based on these source-backed review reasons:")
            lines.append("")
            for item in why_rows:
                lines.append(
                    f"- {item.entity or 'Case-wide'}: {self._plain_language(item.observed_fact)} Why it matters: {self._plain_language(self._why_it_matters(item))} Evidence: {self._compact_matrix_refs(item, labels)}."
                )
        else:
            lines.append(
                "The current matrix did not produce a high or medium source-backed finding. The case should stay in source-completion mode until official records are recovered."
            )
        gaps = self._data_gap_rows(matrix.indicators)
        if gaps:
            lines.extend(
                [
                    "",
                    f"Records still needed: {self._gap_area_summary(gaps)}. These gaps are collection blockers, not adverse findings.",
                ]
            )
        lines.extend(
            [
                "",
                (
                    f"Sentinel posture remains `{sentinel.decision.value}`. The score is a deterministic triage score, not a probability, "
                    "not a dollar-loss estimate, and not a conclusion that misconduct occurred."
                ),
            ]
        )
        return lines

    def _source_type_counts_text(self, counts: dict[str, int]) -> str:
        if not counts:
            return "none"
        parts = [
            f"{self._source_type_label(source_type)} ({count})"
            for source_type, count in sorted(counts.items(), key=lambda item: (-int(item[1]), item[0]))
        ]
        return "; ".join(parts)

    def _score_plain_language_lines(self, lead: LeadCandidate) -> list[str]:
        inputs = lead.score_inputs
        diversity_confidence = inputs.source_diversity_confidence_score or min(100.0, inputs.source_diversity * 12.5)
        traceability_confidence = inputs.traceability_confidence_score or (100.0 if inputs.support_count else 0.0)
        gap_penalty = inputs.caveat_penalty_score or min(45.0, inputs.gap_burden_count * 1.5 + inputs.contradiction_count * 8.0)
        resolved_text = (
            f"{inputs.completion_guard_resolved} of {inputs.completion_guard_total}"
            if inputs.completion_guard_total
            else "not available from a completion guard artifact"
        )
        gap_buckets = self._source_type_counts_text(inputs.missing_data_source_types)
        contradiction_buckets = self._source_type_counts_text(inputs.contradiction_source_types)
        return [
            "- What these scores apply to: the whole compiled case/run and its evidence bundle, not one nonprofit organization by itself.",
            f"- Review priority {inputs.final_score} / 100: how urgently this case should stay in the review queue after combining risk severity, source-acquisition coverage, and publication confidence.",
            f"- Risk severity {inputs.risk_severity_score} / 100: how strong the implemented source-backed risk indicators are. This is the flag-strength score; it does not say misconduct occurred.",
            f"- Source completeness {inputs.source_completeness_score} / 100: whether the required source-family acquisition checks were resolved. This run resolved {resolved_text} required check(s), with {inputs.completion_guard_blocker_count} unresolved blocker(s) and {inputs.completion_guard_miss_count} miss(es). A completed search with no public official adverse record counts as coverage, not as clearance.",
            f"- Open gap burden: {inputs.gap_burden_count} caveat signal(s). These are unresolved review questions inside the evidence bundle, not proof that source acquisition failed. Current gap buckets: {gap_buckets}.",
            f"- Contradiction burden: {inputs.contradiction_count} caution signal(s). Contradictions are never positive evidence and are not rewarded; they lower publication confidence and stay in front of the reviewer. Current contradiction buckets: {contradiction_buckets}.",
            f"- Publication confidence {inputs.publication_confidence_score} / 100: whether the record is sturdy enough for outside-facing use. The implemented model starts from source completeness (55%), source diversity (25%; this run's diversity component is {diversity_confidence:g} / 100), and citation traceability (20%; this run's traceability component is {traceability_confidence:g} / 100), then subtracts a bounded caveat penalty for open gaps and contradictions. This run's caveat penalty is {gap_penalty:g} point(s).",
            "- Meaning: a high risk-severity score with meaningful open gaps is a reason to keep the case in human review and avoid overclaiming, not a reason to bury the lead.",
            "",
            "Questions this score should raise:",
            "",
            "- Did CalDS complete the required source-family acquisition checks, or are there unresolved blockers?",
            "- Which open gap buckets would most change the decision: direct contracts and payments, raw tax-return source documents, audit source documents and finding status, facility histories, public statements, or provider-attributable outcomes?",
            "- Are the strongest risk signals concentrated in the selected deep-review entities, or spread across the full screened set?",
            "- Are the remaining gaps caused by unavailable public records, missing ingestion coverage, or records that exist but have not been pulled into this run?",
            "- Would a contradiction signal weaken the review lead, require correction, or show that the entity has a legitimate explanation that must be carried forward?",
        ]

    def _case_bottom_line(
        self,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        matrix: OversightRiskMatrix,
        labels: dict[str, str],
        triage_tiers: dict[str, object],
    ) -> str:
        entities = ", ".join(request.entities) or "the named entity set"
        selected = self._selected_entities(triage_tiers, matrix)
        substantive = self._substantive_rows(self._focus_rows(matrix, triage_tiers))
        gaps = self._data_gap_rows(matrix.indicators)
        if substantive:
            selected_text = ", ".join(selected) if selected else entities
            strongest = self._signal_summary(substantive[:6])
            top_refs = self._compact_matrix_refs_for_many(substantive[:4], labels)
            return (
                f"CalDS screened {self._entity_count_phrase(request)} and keeps {selected_text} in deep review because the strongest source-backed pattern is {strongest}. Evidence: {top_refs}. "
                f"The review priority score is {lead.score} / 100, source completeness is {lead.score_inputs.source_completeness_score} / 100, publication confidence is {lead.score_inputs.publication_confidence_score} / 100, and the sentinel posture is `{sentinel.decision.value}`; "
                "this is a review priority, not a formal conclusion."
            )
        if bundle.items:
            top_item = sorted(bundle.items, key=lambda item: item.relevance_score, reverse=True)[0]
            gap_text = self._gap_area_summary(gaps) or "required official source series"
            return (
                f"CalDS found source-backed oversight questions for {entities}, but the implemented matrix is mostly blocked by missing source series. "
                f"The strongest retrieved record is `{labels.get(top_item.item_id, top_item.item_id)}`: {self._short_excerpt(self._plain_language(top_item.excerpt), 220)} "
                f"The reviewer should treat this as a source-completion and screening dossier until {gap_text} are verified."
            )
        return (
            f"CalDS did not recover enough source-backed material to brief a possible waste, fraud, abuse, or mismanagement review for {entities}. "
            "The next step is source collection, not ranking."
        )

    def _selected_entities(self, triage_tiers: dict[str, object], matrix: OversightRiskMatrix) -> list[str]:
        selected = [str(entity) for entity in triage_tiers.get("selected_entities", []) if entity]
        if selected:
            return selected
        high_entities = []
        for item in self._substantive_rows(matrix.indicators):
            if item.entity and item.entity != "Case-wide" and item.risk_level == "High" and item.entity not in high_entities:
                high_entities.append(item.entity)
        return high_entities

    def _entity_count_phrase(self, request: CaseRequest) -> str:
        count = len(request.entities)
        if count == 1:
            return "1 entity"
        if count > 1:
            return f"{count} entities"
        return "the named entity set"

    def _focus_rows(self, matrix: OversightRiskMatrix, triage_tiers: dict[str, object]) -> list[OversightRiskIndicator]:
        selected = set(self._selected_entities(triage_tiers, matrix))
        if not selected:
            return list(matrix.indicators)
        return [item for item in matrix.indicators if item.entity in selected or item.entity == "Case-wide"]

    def _signal_summary(self, rows: Iterable[OversightRiskIndicator]) -> str:
        substantive = self._substantive_rows(rows)
        if not substantive:
            return "source gaps that prevent a defensible ranking"
        labels = []
        for item in substantive:
            label = self._risk_area_brief_label(item.risk_area)
            if label not in labels:
                labels.append(label)
        if not labels:
            return "source-backed oversight questions"
        if len(labels) == 1:
            return labels[0]
        return ", ".join(labels[:-1]) + f", and {labels[-1]}"

    def _risk_area_brief_label(self, risk_area: str) -> str:
        area = risk_area.lower()
        if "audit" in area:
            return "audit-control concerns"
        if "compensation" in area:
            return "executive-compensation or payroll-governance questions"
        if "award" in area or "public-funds" in area:
            return "material public-funding exposure"
        if "growth" in area:
            return "rapid financial growth"
        if "payroll" in area or "wages" in area:
            return "payroll or wage-growth questions"
        if "spend-versus-results" in area:
            return "spend-versus-results mismatch"
        if "facility" in area:
            return "facility-capacity or license-status stress"
        if "connected-party" in area:
            return "connected-party enforcement exposure"
        if "statement" in area or "scope" in area:
            return "possible scope-mismatch signals"
        return f"{risk_area} review signals"

    def _source_family_phrase(self, bundle: EvidenceBundle) -> str:
        counts = Counter(self._source_type_label(item.source_type) for item in bundle.items)
        if not counts:
            return "no retrieved evidence records"
        top = [f"{label} ({count})" for label, count in counts.most_common(4)]
        suffix = f" and {len(counts) - 4} other source class(es)" if len(counts) > 4 else ""
        return ", ".join(top) + suffix

    def _top_source_findings(self, bundle: EvidenceBundle, labels: dict[str, str], matrix: OversightRiskMatrix, limit: int = 4) -> list[str]:
        if not bundle.items:
            return ["- No retrieved evidence items are available in the current bundle."]
        by_id = {item.item_id: item for item in bundle.items}
        priority_ids: list[str] = []
        for row in self._substantive_rows(matrix.indicators):
            for evidence_id in row.evidence_ids:
                if evidence_id in by_id and evidence_id not in priority_ids:
                    priority_ids.append(evidence_id)
        priority_ordered = [by_id[evidence_id] for evidence_id in priority_ids]
        ordered = priority_ordered or sorted(bundle.items, key=lambda item: item.relevance_score, reverse=True)
        ordered = [
            item
            for _, item in sorted(
                enumerate(ordered),
                key=lambda pair: (self._reader_source_rank(pair[1]), pair[0]),
            )
        ]
        readable = [item for item in ordered if self._reader_source_rank(item) < 3 and "discovery" not in item.source_type.lower()]
        if len(readable) >= limit:
            ordered = readable
        lines = []
        for item in ordered[:limit]:
            ref = labels.get(item.item_id, item.item_id)
            source_label = self._source_type_label(item.source_type)
            published = item.published_at or "date not provided"
            lines.append(
                f"- `{ref}` {self._plain_language(item.title)} ({source_label}, {published}): {self._short_excerpt(self._plain_language(item.excerpt), 260)}"
            )
        if len(ordered) > limit:
            lines.append(f"- {len(ordered) - limit} additional evidence item(s) are in the citation ledger.")
        return lines

    def _reader_source_rank(self, item: EvidenceItem) -> int:
        source_type = item.source_type.lower()
        if "enforcement" in source_type or "docket" in source_type:
            return 0
        if source_type in {"org_service_page", "public_statement_source"}:
            return 1
        if "raw_artifact" in source_type or "irs_990" in source_type:
            return 2
        if source_type.startswith("source_extraction_") or source_type.startswith("parsed"):
            return 3
        return 2

    def _why_on_desk_lines(self, matrix: OversightRiskMatrix, labels: dict[str, str], triage_tiers: dict[str, object] | None = None) -> list[str]:
        focus = self._focus_rows(matrix, triage_tiers or {})
        substantive = self._substantive_rows(focus)
        gaps = self._data_gap_rows(focus)
        lines: list[str] = []
        if substantive:
            for item in substantive[:4]:
                lines.append(
                    f"- CalDS flags {item.entity or 'the case'} / {item.risk_area}: {self._plain_language(item.observed_fact)} Evidence: {self._compact_matrix_refs(item, labels)}. {self._plain_language(self._why_it_matters(item))}"
                )
        else:
            lines.append(
                "- No implemented high or medium source-backed screen fired from the current matrix. The case stays open because retrieved records raise oversight questions while required official source series are incomplete."
            )
        if gaps:
            lines.append(
                f"- Source blockers to resolve before stronger ranking: {self._gap_area_summary(gaps)}. These are collection blockers, not adverse findings."
            )
        return lines or ["- The current run did not produce a reviewable source-backed desk rationale."]

    def _triage_gate_lines(self, source_artifact_refs: list[str]) -> list[str]:
        triage = self._load_artifact_json(source_artifact_refs, "entity_triage_results.json")
        plan = self._load_artifact_json(source_artifact_refs, "forensic_investigation_plan.json")
        handoff = self._load_artifact_json(source_artifact_refs, "context_handoff_ledger.json")
        forensic = self._load_artifact_json(source_artifact_refs, "forensic_findings.json")
        if not triage:
            return ["- This run does not include the new top-15 triage artifact. Rerun the workflow to populate the triage gate."]

        results = list(triage.get("results", []))
        selected = list(plan.get("selected_entities", [])) if isinstance(plan, dict) else []
        high = [item for item in results if item.get("triage_priority") == "High"]
        medium = [item for item in results if str(item.get("triage_priority", "")).startswith("Medium")]
        lines = [
            f"- First-pass triage screened {len(results)} named entities before deep investigation.",
            f"- Deep-dive selection: {', '.join(selected) if selected else 'none selected by implemented thresholds'}.",
        ]
        if handoff:
            missing = list(handoff.get("missing_fields", []))
            lines.append(f"- Context handoff check: {handoff.get('status', 'unknown')}. Missing fields: {', '.join(missing) if missing else 'none'}.")
        for item in [*high, *medium][:8]:
            findings = [finding for finding in item.get("findings", []) if finding.get("risk_level") in {"High", "Medium"}]
            top = findings[0] if findings else {}
            entity = item.get("entity", "unknown entity")
            opinion = "selected for deep forensic review" if item.get("deep_dive_recommended") else "held in watch status pending more source coverage"
            observed = self._short_excerpt(str(top.get("observed_fact", item.get("rationale", ""))), 320)
            source = self._format_source_uris(list(top.get("source_uris", [])))
            lines.append(
                f"- {entity}: {item.get('triage_priority')} triage priority, {opinion}. Why: {item.get('rationale')} Trigger: {observed} Source: {source}"
            )
        if forensic:
            private_findings = list(forensic.get("findings", []))
            if private_findings:
                lines.append(
                    f"- Private forensic synthesis created {len(private_findings)} source-cited investigation hypothesis item(s). These stay internal and require sentinel/human review before publication."
                )
        if not high and not medium:
            lines.append("- No high or medium triage trigger fired; the case should focus on source completion rather than ranking.")
        return lines

    def _completion_guard_lines(self, source_artifact_refs: list[str]) -> list[str]:
        ledger = self._load_artifact_json(source_artifact_refs, "acquisition_ledger.json")
        guard = self._load_artifact_json(source_artifact_refs, "completion_guard.json")
        if not guard:
            return ["- This run does not include a completion guard artifact. Rerun the workflow before treating the dossier as complete."]
        searches = list(ledger.get("searches", [])) if isinstance(ledger, dict) else []
        hits = [item for item in searches if item.get("status") == "hit"]
        no_public_record = [item for item in searches if item.get("status") == "searched_no_public_official_record"]
        misses = [item for item in searches if item.get("status") not in {"hit", "searched_no_public_official_record"}]
        lines = [
            f"- Completion guard status: {guard.get('status')}.",
            f"- Required source-family checks: {guard.get('total_searches', len(searches))}; hits: {guard.get('hit_count', len(hits))}; public official no-record searches: {len(no_public_record)}; unresolved blockers: {guard.get('blocker_count', len(misses))}.",
        ]
        if no_public_record:
            lines.append("- Public official no-record coverage:")
            for item in no_public_record[:8]:
                lines.append(
                    f"  - {item.get('entity')}: {item.get('source_family')} - configured public official searches found no citation-ready adverse record; this is not legal clearance."
                )
        if misses:
            lines.append("- Top unresolved acquisition blockers:")
            for item in misses[:8]:
                lines.append(
                    f"  - {item.get('entity')}: {item.get('source_family')} - {item.get('blocker_reason') or 'No hit recorded.'}"
                )
            if len(misses) > 8:
                lines.append(f"  - +{len(misses) - 8} additional blocker(s) in `acquisition_ledger.json`.")
        else:
            lines.append("- Every required source family has a recovered citation-ready hit or a public official no-record search result for the selected entities.")
        notes = list(guard.get("notes", []))
        for note in notes[:3]:
            lines.append(f"- Guard note: {self._plain_language(note)}")
        return lines

    def _load_artifact_json(self, source_artifact_refs: list[str], filename: str) -> dict[str, object]:
        for ref in source_artifact_refs:
            path = Path(ref)
            if path.name != filename or not path.exists():
                continue
            try:
                return read_json(path)
            except Exception:
                return {}
        return {}

    def _triage_tiers(self, source_artifact_refs: list[str]) -> dict[str, object]:
        triage = self._load_artifact_json(source_artifact_refs, "entity_triage_results.json")
        plan = self._load_artifact_json(source_artifact_refs, "forensic_investigation_plan.json")
        selected = list(plan.get("selected_entities", [])) if isinstance(plan, dict) else []
        priority_by_entity: dict[str, str] = {}
        selected_lookup = set(selected)
        watchlist: list[str] = []
        for item in list(triage.get("results", [])) if isinstance(triage, dict) else []:
            entity = str(item.get("entity", ""))
            if not entity:
                continue
            priority_by_entity[entity] = str(item.get("triage_priority", "Unranked"))
            if entity not in selected_lookup:
                watchlist.append(entity)
        return {
            "selected_entities": selected,
            "watchlist_entities": watchlist,
            "priority_by_entity": priority_by_entity,
        }

    def _brief_score_meaning(self, score: float) -> str:
        if score >= 75:
            return "High triage priority from retrieval strength and entity linkage; still requires human verification."
        if score >= 50:
            return "Reviewable triage priority with open gap-burden caveats."
        if score >= 25:
            return "Limited triage priority; repair likely needed before escalation."
        return "Low deterministic score because the retrieved record is too weak, incomplete, or caveated for escalation."

    def _brief_score_summary(self, score_inputs: ScoreInputs) -> str:
        return (
            f"review priority {score_inputs.final_score} / 100; "
            f"risk severity {score_inputs.risk_severity_score} / 100; "
            f"source completeness {score_inputs.source_completeness_score} / 100; "
            f"publication confidence {score_inputs.publication_confidence_score} / 100. "
            "Risk severity answers whether the retrieved facts deserve review; source completeness answers whether required acquisition checks resolved; publication confidence answers whether the record is ready to share."
        )

    def _supervisor_next_action(
        self,
        bundle: EvidenceBundle,
        matrix: OversightRiskMatrix,
        sentinel: SentinelResult,
    ) -> str:
        for item in self._substantive_rows(matrix.indicators):
            return self._indicator_next_step(item)
        gaps = self._data_gap_rows(matrix.indicators)
        if gaps:
            return f"Complete source collection for {self._gap_area_summary(gaps)} before ranking an entity as a substantive possible waste, fraud, abuse, or mismanagement lead."
        if sentinel.repair_instructions:
            return sentinel.repair_instructions[0]
        if bundle.items:
            return "Read the top cited source records, then decide whether to collect the missing official records or close the lead as insufficient."
        return "Collect source records before continuing."

    def _case_limits(self, matrix: OversightRiskMatrix, sentinel: SentinelResult) -> list[str]:
        lines = [
            "- This dossier does not make a formal finding of waste, fraud, or abuse. It identifies possible screening questions and source blockers for human review.",
        ]
        if any(item.risk_area == "Spend-versus-results" for item in matrix.indicators):
            lines.append("- County or Continuum of Care outcomes are contextual unless provider-attributable outcome records are recovered and linked.")
        if any("connected-party" in item.risk_area.lower() for item in matrix.indicators):
            lines.append("- Connected-party enforcement exposure means an official source tied a charged person, transaction, project, or counterparty to the source chain; it does not mean the nonprofit was charged unless the cited source says that.")
        if any("scope" in item.risk_area.lower() for item in matrix.indicators):
            lines.append("- Homelessness scope-mismatch rows test whether public homelessness funds may have supported activity outside the funded scope; they do not state that the activity is categorically unlawful for a nonprofit.")
        if sentinel.flags:
            lines.append(f"- Sentinel restrictions remain active: {', '.join(sentinel.flags)}.")
        return lines

    def _substantive_rows(self, indicators: Iterable[OversightRiskIndicator]) -> list[OversightRiskIndicator]:
        rows = [item for item in indicators if item.risk_level in {"High", "Medium"}]
        return sorted(rows, key=lambda item: (RISK_ORDER.get(item.risk_level, 99), item.risk_area, item.entity, item.test_name))

    def _data_gap_rows(self, indicators: Iterable[OversightRiskIndicator]) -> list[OversightRiskIndicator]:
        rows = [item for item in indicators if item.risk_level == "Data gap"]
        return sorted(rows, key=lambda item: (item.risk_area, item.entity, item.test_name))

    def _gap_area_summary(self, rows: Iterable[OversightRiskIndicator], limit: int = 4) -> str:
        areas = []
        for item in rows:
            if item.risk_area not in areas:
                areas.append(item.risk_area)
        if not areas:
            return ""
        suffix = f"; plus {len(areas) - limit} other source area(s)" if len(areas) > limit else ""
        return ", ".join(areas[:limit]) + suffix

    def _briefing_memo_lines(
        self,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        matrix: OversightRiskMatrix,
        labels: dict[str, str],
        triage_tiers: dict[str, object],
    ) -> list[str]:
        by_entity: dict[str, list[OversightRiskIndicator]] = {}
        case_wide: list[OversightRiskIndicator] = []
        for item in matrix.indicators:
            if not item.entity:
                continue
            if item.entity == "Case-wide":
                case_wide.append(item)
            else:
                by_entity.setdefault(item.entity, []).append(item)

        lines: list[str] = []

        ordered = sorted(
            by_entity.items(),
            key=lambda pair: (
                min(RISK_ORDER.get(item.risk_level, 99) for item in pair[1]),
                pair[0],
            ),
        )
        selected = set(triage_tiers.get("selected_entities", []))
        selected_order = [pair for pair in ordered if pair[0] in selected]
        watch_order = [pair for pair in ordered if pair[0] not in selected]
        if not ordered:
            lines.extend(["No entity-specific briefing could be generated from the current matrix.", ""])
        if selected_order:
            lines.extend(["### Deep-Review Entities", ""])
            lines.append("These entities crossed the implemented triage threshold for deeper forensic review in this run.")
            lines.append("")
            for entity, indicators in selected_order:
                lines.extend(self._briefing_entity_lines(entity, indicators, bundle, labels, True, "####"))
        if watch_order:
            lines.extend(["### Watchlist And Matrix-Only Entities", ""])
            lines.append("These entities have matrix signals or source gaps, but they were not selected for deep forensic review by the implemented triage threshold in this run.")
            lines.append("")
            for entity, indicators in watch_order:
                lines.extend(self._briefing_entity_lines(entity, indicators, bundle, labels, False, "####"))

        if case_wide:
            lines.extend(["### Case-wide Source Gaps", ""])
            lines.append("These are not NGO-specific findings. They are run-level blockers that limit how strongly CalDS can rank or clear the case.")
            lines.append("")
            for item in sorted(case_wide, key=lambda row: (RISK_ORDER.get(row.risk_level, 99), row.risk_area)):
                if item.risk_level not in {"Data gap", "High", "Medium"}:
                    continue
                lines.extend(
                    [
                        f"- {item.risk_area}: {self._plain_language(item.observed_fact)}",
                        f"  Evidence: {self._matrix_refs(item, labels)}. Human action: {self._indicator_next_step(item)}",
                    ]
                )
            lines.append("")
        return lines

    def _briefing_entity_lines(
        self,
        entity: str,
        indicators: list[OversightRiskIndicator],
        bundle: EvidenceBundle,
        labels: dict[str, str],
        selected_for_deep_review: bool = True,
        heading_prefix: str = "###",
    ) -> list[str]:
        priority = sorted(
            indicators,
            key=lambda item: (RISK_ORDER.get(item.risk_level, 99), item.risk_area, item.test_name),
        )
        review_rows = [item for item in priority if item.risk_level in {"High", "Medium", "Data gap"}]
        posture = self._entity_posture(Counter(item.risk_level for item in indicators), selected_for_deep_review)
        claim = self._entity_claim_context(entity, bundle, labels)
        source_facts = self._entity_source_fact_bullets(entity, bundle, labels)
        facts = self._briefing_fact_bullets(review_rows, labels)
        why = self._briefing_why_flagged(review_rows)
        limits = self._briefing_limits(review_rows)
        next_step = self._briefing_next_step(review_rows)
        refs = self._compact_matrix_refs_for_many(review_rows, labels)
        return [
            f"{heading_prefix} {entity}",
            "",
            f"Briefing judgment: {self._entity_judgment_sentence(entity, review_rows, posture)} Evidence: {refs}.",
            "",
            f"Who they are / what they say they do: {self._plain_language(claim)}",
            "",
            "What CalDS found in the records:",
            "",
            "Key retrieved records:",
            "",
            *source_facts,
            "",
            "Why CalDS flagged it:",
            "",
            *facts,
            "",
            f"Reviewer readout: {why} Evidence: {refs}.",
            "",
            f"What this does not prove: {limits}",
            "",
            f"Recommended human next step: {next_step}",
            "",
        ]

    def _entity_judgment_sentence(
        self,
        entity: str,
        rows: list[OversightRiskIndicator],
        posture: str,
    ) -> str:
        substantive = self._substantive_rows(rows)
        if not substantive:
            gaps = self._gap_area_summary(self._data_gap_rows(rows))
            return (
                f"CalDS keeps {entity} as a {posture} because source gaps still block a clean decision"
                + (f": {gaps}." if gaps else ".")
            )
        strongest = substantive[0]
        pattern = self._signal_summary(substantive)
        return (
            f"CalDS treats {entity} as a {posture} because the records show {pattern}; "
            f"the strongest current trigger is {self._plain_language(strongest.observed_fact)}"
        )

    def _briefing_fact_bullets(self, rows: list[OversightRiskIndicator], labels: dict[str, str]) -> list[str]:
        if not rows:
            return ["- No high, medium, or data-gap facts were available for this entity in the current matrix."]
        bullets: list[str] = []
        substantive = self._substantive_rows(rows)
        data_gaps = self._data_gap_rows(rows)
        outcome_rows = [item for item in substantive if item.risk_area == "Spend-versus-results"]
        selected = [item for item in substantive if item.risk_area != "Spend-versus-results"]
        if selected:
            for item in selected[:5]:
                bullets.append(
                    f"- {item.risk_area}: {self._plain_language(item.observed_fact)} ({self._when_where(item)}; evidence {self._compact_matrix_refs(item, labels)}.)"
                )
        else:
            bullets.append("- No implemented high or medium possible waste, fraud, abuse, or mismanagement screen fired for this entity from the current matrix.")
        if outcome_rows:
            bullets.append(self._outcome_briefing_bullet(outcome_rows, labels))
        if data_gaps:
            bullets.append(
                f"- Source gaps that limit judgment: {self._gap_area_summary(data_gaps)}. These gaps explain what CalDS still cannot test; they are not adverse findings by themselves."
            )
        return bullets

    def _outcome_briefing_bullet(self, rows: list[OversightRiskIndicator], labels: dict[str, str]) -> str:
        segments = []
        for item in rows[:4]:
            county = self._geography_from_row(item) or "matched county"
            flags = self._between(item.observed_fact, "flags ", ". Parsed") or item.observed_fact
            segments.append(f"{county}: {flags}")
        more = f"; plus {len(rows) - 4} additional matched county context(s)" if len(rows) > 4 else ""
        growth = self._after(rows[0].observed_fact, "Parsed entity growth context: ")
        growth_text = f" Parsed entity growth context: {growth.rstrip('.')}." if growth else ""
        refs = self._compact_matrix_refs_for_many(rows, labels)
        return (
            "- Spend-versus-results: official county/CoC outcome context worsened in the entity's matched project geography: "
            + "; ".join(segments)
            + more
            + "."
            + growth_text
            + " This is a review signal, not provider attribution. Evidence "
            + refs
            + "."
        )

    def _entity_source_fact_bullets(
        self,
        entity: str,
        bundle: EvidenceBundle,
        labels: dict[str, str],
        limit: int = 3,
    ) -> list[str]:
        items = self._entity_related_evidence_items(entity, bundle)
        if not items:
            return [f"- No retrieved evidence excerpt directly matched {entity}; use the citation ledger for case-wide context."]
        bullets = []
        for item in items[:limit]:
            ref = labels.get(item.item_id, item.item_id)
            source_label = self._source_type_label(item.source_type)
            published = item.published_at or "date not provided"
            bullets.append(
                f"- `{ref}` {self._plain_language(item.title)} ({source_label}, {published}): {self._short_excerpt(self._plain_language(item.excerpt), 260)}"
            )
        if len(items) > limit:
            bullets.append(f"- {len(items) - limit} additional matched source item(s) appear in the citation ledger.")
        return bullets

    def _entity_related_evidence_items(self, entity: str, bundle: EvidenceBundle) -> list[EvidenceItem]:
        entity_norm = self._normalize(entity)
        tokens = self._distinctive_entity_tokens(entity)
        aliases = {
            entity_norm,
            entity_norm.removesuffix("inc"),
            entity_norm.replace("ofcalifornia", ""),
            "".join(tokens),
        }
        aliases = {alias for alias in aliases if len(alias) >= 6}
        matches: list[EvidenceItem] = []
        for item in bundle.items:
            haystack = self._normalize(" ".join([item.record_id, item.title, item.source_uri, item.excerpt]))
            if any(alias and alias in haystack for alias in aliases):
                matches.append(item)
        return sorted(matches, key=lambda item: item.relevance_score, reverse=True)

    def _entity_claim_context(self, entity: str, bundle: EvidenceBundle, labels: dict[str, str]) -> str:
        candidates = self._entity_evidence_items(entity, bundle)
        preferred_types = ["org_service_page", "public_statement_source"]
        for source_type in preferred_types:
            for item in candidates:
                if item.source_type == source_type and item.excerpt:
                    ref = f"`{labels.get(item.item_id, item.item_id)}`"
                    excerpt = item.excerpt
                    if item.source_type == "org_service_page":
                        excerpt = self._after(item.excerpt, "Service summary from official source(s):") or item.excerpt
                    return f"retrieved source `{item.title}` says or summarizes: {self._short_excerpt(excerpt)} Evidence: {ref}."
        return "this run did not recover a direct service-page or public-statement description for this entity, so CalDS does not fill that gap with an assumed mission statement."

    def _entity_evidence_items(self, entity: str, bundle: EvidenceBundle) -> list[EvidenceItem]:
        entity_norm = self._normalize(entity)
        tokens = self._distinctive_entity_tokens(entity)
        aliases = {
            entity_norm,
            entity_norm.removesuffix("inc"),
            entity_norm.replace("ofcalifornia", ""),
            "".join(tokens),
        }
        aliases = {alias for alias in aliases if len(alias) >= 6}
        matches: list[EvidenceItem] = []
        for item in bundle.items:
            if item.source_type not in {"org_service_page", "public_statement_source"}:
                continue
            haystack = self._normalize(" ".join([item.record_id, item.title, item.source_uri]))
            if any(alias and alias in haystack for alias in aliases):
                matches.append(item)
        return matches

    def _distinctive_entity_tokens(self, entity: str) -> list[str]:
        return [
            token
            for token in re.findall(r"[a-z0-9]+", entity.lower())
            if token not in GENERIC_ENTITY_TOKENS and len(token) >= 4
        ]


    def _briefing_why_flagged(self, rows: list[OversightRiskIndicator]) -> str:
        if not rows:
            return "No review-priority reason was available in the current matrix."
        substantive = self._substantive_rows(rows)
        if not substantive:
            gaps = self._gap_area_summary(self._data_gap_rows(rows))
            return (
                "CalDS is holding this item because retrieved records create an oversight question, but the current matrix cannot responsibly rank it without the missing official source series"
                + (f": {gaps}." if gaps else ".")
            )
        areas = {item.risk_area.lower() for item in substantive}
        if "spend-versus-results" in areas and any("award" in area or "public-funds" in area or "growth" in area for area in areas):
            return "CalDS sees the combination reviewers care about: material public-money exposure or financial movement, plus outcome context that moved the wrong direction in matched service geographies. That does not prove provider responsibility, but it is exactly the mismatch that should be briefed up for document review."
        if any("facility" in area for area in areas) and any("award" in area or "public-funds" in area for area in areas):
            return "CalDS sees public-money exposure next to facility-footprint stress. The reviewer should understand whether closed or changed facility rows affect service capacity, contract delivery, or merely historical licensing records."
        if any("audit" in area for area in areas):
            return "CalDS sees audit-control context that can bear directly on stewardship of public funds, especially if findings, management responses, or corrective-action status remain unresolved."
        return self._why_it_matters(substantive[0])

    def _briefing_limits(self, rows: list[OversightRiskIndicator]) -> str:
        if not rows:
            return "The current matrix does not prove or disprove a substantive issue."
        substantive = self._substantive_rows(rows)
        if not substantive:
            return "The current matrix does not prove or disprove possible waste, fraud, abuse, or mismanagement; it shows source gaps that must be resolved before stronger ranking."
        limits = self._dedupe(self._not_proven_text(item) for item in substantive[:4])
        return " ".join(limits[:2])

    def _briefing_next_step(self, rows: list[OversightRiskIndicator]) -> str:
        if not rows:
            return "Collect additional source material and rerun the matrix before briefing this beyond internal triage."
        substantive = self._substantive_rows(rows)
        if not substantive:
            gaps = self._gap_area_summary(self._data_gap_rows(rows))
            return f"Collect the missing official source series ({gaps}) and rerun the matrix before ranking this entity as a possible waste, fraud, abuse, or mismanagement lead."
        for item in substantive:
            if item.risk_level == "High":
                return self._indicator_next_step(item)
        return self._indicator_next_step(substantive[0])

    def _matrix_refs_for_many(self, rows: list[OversightRiskIndicator], labels: dict[str, str]) -> str:
        refs: list[str] = []
        for item in rows:
            for evidence_id in item.evidence_ids:
                token = f"`{labels.get(evidence_id, evidence_id)}`"
                if token not in refs:
                    refs.append(token)
            for record_id in item.record_ids:
                token = f"`{record_id}`"
                if token not in refs:
                    refs.append(token)
        return ", ".join(refs) if refs else "no direct evidence ref in these rows"

    def _short_excerpt(self, text: str, limit: int = 340) -> str:
        cleaned = " ".join(str(text).replace("...", " ").split())
        if len(cleaned) <= limit:
            return cleaned
        clipped = cleaned[:limit].rsplit(" ", 1)[0]
        return clipped + "..."

    def _between(self, text: str, start: str, end: str) -> str:
        value = str(text)
        start_at = value.find(start)
        if start_at == -1:
            return ""
        start_at += len(start)
        end_at = value.find(end, start_at)
        if end_at == -1:
            return value[start_at:].strip()
        return value[start_at:end_at].strip()

    def _after(self, text: str, marker: str) -> str:
        value = str(text)
        index = value.find(marker)
        if index == -1:
            return ""
        return value[index + len(marker):].strip().rstrip(".")

    def _normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(text).lower())
    def _entity_opinion_lines(
        self,
        matrix: OversightRiskMatrix,
        labels: dict[str, str],
        triage_tiers: dict[str, object],
    ) -> list[str]:
        rows = [item for item in matrix.indicators if item.entity]
        by_entity: dict[str, list[OversightRiskIndicator]] = {}
        for item in rows:
            by_entity.setdefault(item.entity, []).append(item)
        lines: list[str] = []
        selected = set(triage_tiers.get("selected_entities", []))
        for entity in sorted(by_entity):
            indicators = by_entity[entity]
            priority = sorted(
                indicators,
                key=lambda item: (RISK_ORDER.get(item.risk_level, 99), item.risk_area, item.test_name),
            )
            selected_for_deep_review = entity in selected
            posture = self._entity_posture(Counter(item.risk_level for item in indicators), selected_for_deep_review)
            refs = self._matrix_refs_for_many(priority[:6], labels)
            lines.extend(
                [
                    f"### {entity}",
                    "",
                    f"CalDS treats {entity} as a {posture}. The entity is in this dossier because the current source bundle contains the specific source facts below. Evidence: {refs}.",
                    "",
                    "Specific findings that drove the flag:",
                    "",
                ]
            )
            for index, item in enumerate(priority[:6], start=1):
                lines.extend(self._entity_finding_lines(index, item, labels))
            if len(priority) > 6:
                lines.append("- The full matrix contains additional lower-priority source-backed review items for this entity.")
                lines.append("")
            lines.extend(
                [
                    f"Review stance: {self._entity_review_stance(indicators)}",
                    "",
                ]
            )
        if not lines:
            return ["No entity-level opinion was generated because the matrix did not contain entity rows."]
        return lines

    def _entity_finding_lines(
        self,
        index: int,
        item: OversightRiskIndicator,
        labels: dict[str, str],
    ) -> list[str]:
        refs = self._matrix_refs(item, labels)
        source_text = self._format_source_uris(item.source_uris)
        return [
            f"{index}. {item.risk_level} - {item.risk_area}: {self._plain_language(item.observed_fact)} Evidence: {refs}.",
            f"   - When/where: {self._when_where(item)} Evidence: {refs}.",
            f"   - How it triggered: {self._trigger_text(item)} Evidence: {refs}.",
            f"   - Evidence: {refs}; source: {source_text}",
            f"   - Why it matters: {self._plain_language(self._why_it_matters(item))}",
            "",
        ]

    def _entity_posture(self, counts: Counter[str], selected_for_deep_review: bool = True) -> str:
        if not selected_for_deep_review:
            if counts.get("High", 0) or counts.get("Medium", 0):
                return "watchlist or matrix-only subject, not a deep-review target selected by this run"
            if counts.get("Data gap", 0):
                return "watchlist source-gap subject, not a deep-review target selected by this run"
            return "context-only subject, not a deep-review target selected by this run"
        if counts.get("High", 0):
            return "deep-review possible waste, fraud, abuse, or mismanagement review subject"
        if counts.get("Medium", 0):
            return "moderate-priority deep-review possible waste, fraud, abuse, or mismanagement review subject"
        if counts.get("Data gap", 0):
            return "source-gap review subject"
        return "context-only subject"

    def _entity_review_stance(self, indicators: list[OversightRiskIndicator]) -> str:
        areas = {item.risk_area.lower() for item in indicators}
        if any("spend-versus-results" in area for area in areas):
            return "The system would not close this item from summary records alone; spending and footprint need provider-attributable outcome records."
        if any("audit" in area for area in areas):
            return "The system would keep this item active until FAC findings, management responses, and corrective-action status are checked."
        if any("facility" in area for area in areas):
            return "The system would keep this item active until DHCS facility histories explain the closed or adverse-status pattern."
        if any("compensation" in area for area in areas):
            return "The system would keep this item active until compensation approval, comparability, and related-organization context are verified."
        if any("public-funds" in area or "award" in area for area in areas):
            return "The system would prioritize this item for funding-trace review because public-money exposure is material."
        return "The system would keep this item in the review queue until the cited source facts are reconciled with source documents."

    def _when_where(self, item: OversightRiskIndicator) -> str:
        years = sorted(set(re.findall(r"\b20\d{2}\b", item.observed_fact)))
        geography = self._geography_from_row(item)
        parts = []
        if years:
            parts.append("year(s): " + ", ".join(years[:8]))
        if geography:
            parts.append("place: " + geography)
        if item.entity:
            parts.append("subject: " + item.entity)
        return "; ".join(parts) if parts else "subject and timing are in the cited source row; no separate date or geography field was parsed for this indicator"

    def _geography_from_row(self, item: OversightRiskIndicator) -> str:
        if ":" in item.test_name and "county" in item.test_name.lower():
            return item.test_name.split(":", 1)[1].strip()
        matches = re.findall(r"\b(?:Los Angeles|San Francisco|Stanislaus|Orange|San Diego|Sacramento|Alameda|Fresno|Riverside|Santa Clara|Ventura|Kern|San Bernardino)\b", item.observed_fact)
        if matches:
            return ", ".join(dict.fromkeys(matches))
        if "facility" in item.risk_area.lower():
            return "DHCS facility set matched to the entity"
        return ""

    def _trigger_text(self, item: OversightRiskIndicator) -> str:
        status = f" Data status: {item.data_status}." if item.data_status else ""
        return f"{item.risk_level} {item.risk_area} screen via test '{item.test_name}'.{status}"

    def _system_opinion(self, item: OversightRiskIndicator) -> str:
        if item.risk_level == "Data gap":
            return f"CalDS flags this as a data blocker because {item.observed_fact} Without the missing source, the system cannot responsibly downgrade or clear the issue."
        return f"CalDS flags this as a {item.risk_level.lower()} possible waste, fraud, abuse, or mismanagement review priority because {item.observed_fact} This source fact matches the implemented {item.risk_area.lower()} screen and should stay in the active review queue."

    def _why_it_matters(self, item: OversightRiskIndicator) -> str:
        area = item.risk_area.lower()
        if "compensation" in area:
            return "High executive pay at a publicly funded service nonprofit is a materiality and governance question; the reviewer needs to know whether pay, approval, and outcomes line up."
        if "facility" in area:
            return "Facility closures or status changes can affect capacity, access, and contract performance; the system treats a high closed-facility ratio as a service-delivery red flag."
        if "audit" in area:
            return "Audit-control flags are direct oversight signals; repeated or unresolved findings can indicate weak controls over public funds."
        if "award" in area or "public-funds" in area:
            return "Large public-funds exposure raises the stakes of any control, deliverable, or outcome weakness because taxpayer dollars are material."
        if "growth" in area:
            return "Rapid revenue or expense growth becomes a possible waste, fraud, abuse, or mismanagement review concern when it outpaces visible service capacity, documented outcomes, or clear grant-scope explanations."
        if "spend-versus-results" in area:
            return "Spending growth next to worsening county-level outcomes is not provider-attributable by itself, but it is exactly the mismatch CalDS should force into review."
        if "connected-party" in area:
            return "An official charge or indictment connected to a public-funded project or transaction chain is a hard deep-review trigger because the reviewer must verify named parties, payment flow, controls, and whether public dollars were exposed."
        if "statement" in area or "scope" in area:
            return "Public claims and program language matter when a homelessness-funded entity appears to describe voter, citizenship, immigration, advocacy, or political work that may need contract-scope, grant-scope, funding-source, or cost-allocation review."
        if item.risk_level == "Data gap":
            return "A missing source can hide the answer either way; the system keeps the issue open until the gap is resolved."
        return "The row matters because it is a measurable source-backed proxy for public-funds oversight risk."

    def _dossier_mode(self, sentinel: SentinelResult) -> str:
        if sentinel.decision == SentinelDecision.BLOCK_REPAIR_REQUIRED:
            return "repair dossier only; not reviewable until sentinel repair is complete"
        if sentinel.decision == SentinelDecision.DOWNGRADE_FOR_REVIEW:
            return "downgraded internal review dossier with caveats preserved"
        return "internal review dossier"

    def _priority_indicators(self, matrix: OversightRiskMatrix) -> list[OversightRiskIndicator]:
        priority = [item for item in matrix.indicators if item.risk_level in {"High", "Medium", "Data gap"}]
        return sorted(priority, key=lambda item: (RISK_ORDER.get(item.risk_level, 99), item.risk_area, item.entity, item.test_name))

    def _evidence_labels(self, bundle: EvidenceBundle) -> dict[str, str]:
        return {item.item_id: f"E{index:02d}" for index, item in enumerate(bundle.items, start=1)}

    def _matrix_refs(self, indicator: OversightRiskIndicator, labels: dict[str, str]) -> str:
        refs = []
        for evidence_id in indicator.evidence_ids:
            refs.append(f"`{labels.get(evidence_id, evidence_id)}`")
        for record_id in indicator.record_ids:
            token = f"`{record_id}`"
            if token not in refs:
                refs.append(token)
        return ", ".join(refs) if refs else "no direct evidence ref in this row"

    def _compact_matrix_refs(self, indicator: OversightRiskIndicator, labels: dict[str, str]) -> str:
        refs = []
        for evidence_id in indicator.evidence_ids:
            token = f"`{labels.get(evidence_id, evidence_id)}`"
            if token not in refs:
                refs.append(token)
        if refs:
            return ", ".join(refs)
        fallback = []
        for value in [*indicator.record_ids, *indicator.source_uris]:
            token = f"`{value}`" if value else ""
            if token and token not in fallback:
                fallback.append(token)
        return ", ".join(fallback[:3]) if fallback else "no direct evidence ref in this row"

    def _compact_matrix_refs_for_many(self, rows: list[OversightRiskIndicator], labels: dict[str, str]) -> str:
        refs: list[str] = []
        fallback: list[str] = []
        for item in rows:
            for evidence_id in item.evidence_ids:
                token = f"`{labels.get(evidence_id, evidence_id)}`"
                if token not in refs:
                    refs.append(token)
            for value in [*item.record_ids, *item.source_uris]:
                token = f"`{value}`" if value else ""
                if token and token not in fallback:
                    fallback.append(token)
        if refs:
            return ", ".join(refs)
        return ", ".join(fallback[:6]) if fallback else "no direct evidence ref in these rows"

    def _format_source_uris(self, uris: Iterable[str]) -> str:
        values = [uri for uri in uris if uri]
        if not values:
            return "not listed on this row; use evidence ledger"
        clipped = values[:3]
        suffix = f"; +{len(values) - len(clipped)} more" if len(values) > len(clipped) else ""
        return "; ".join(self._display_uri(uri) for uri in clipped) + suffix

    def _display_uri(self, uri: str) -> str:
        text = str(uri)
        for original, replacement in self.path_remaps.items():
            if text.startswith(original):
                mapped = replacement + text[len(original):]
                if Path(mapped).exists():
                    return f"{text} (archived local copy: {mapped})"
        return text

    def _score_interpretation(self, score: float) -> str:
        if score >= 75:
            return "Interpretation: high-priority review lead because retrieved-source coverage and entity linkage are broad, with human verification still required."
        if score >= 50:
            return "Interpretation: reviewable triage lead with meaningful source coverage, but caveats or missing data prevent upgrade without human verification."
        if score >= 25:
            return "Interpretation: limited triage lead; source coverage or entity linkage is thin and repair may be needed before escalation."
        return "Interpretation: low deterministic score because unresolved source gaps outweigh the retrieved source coverage under the current scoring formula."

    def _not_proven_text(self, item: OversightRiskIndicator) -> str:
        area = item.risk_area.lower()
        if "compensation" in area:
            return "It does not prove compensation is improper; board approval, comparability, role scope, and peer context must be reviewed."
        if "facility" in area:
            return "It does not prove current capacity loss or adverse entity status; facility-level DHCS records must be verified."
        if "audit" in area:
            return "It does not prove a current unresolved program issue; audit year, finding status, response, and resolution must be checked."
        if "award" in area or "public-funds" in area:
            return "It does not prove poor performance or misuse; it marks funding exposure that needs source and outcome review."
        if "growth" in area:
            return "It does not prove misuse; growth can have ordinary program, accounting, merger, or grant-timing explanations."
        if "spend-versus-results" in area:
            return "It does not prove the entity caused county or CoC outcome movement; it flags a spend/outcome question for review."
        if "connected-party" in area:
            return "It does not prove the nonprofit was charged, liable, or responsible; the cited official source controls the named-party legal status."
        if "statement" in area or "scope" in area:
            return "It does not prove spending outside allowed scope or unlawful activity; contract, grant, funding-source, and accounting records must be checked."
        if item.risk_level == "Data gap":
            return "It does not prove a substantive issue; it identifies a source gap that blocks stronger review."
        return "It does not prove wrongdoing; it is a source-backed review prompt."

    def _indicator_next_step(self, item: OversightRiskIndicator) -> str:
        area = item.risk_area.lower()
        text = f"Open the cited source records for {item.entity} and compare the raw source wording to this row."
        if "compensation" in area:
            return "Verify the underlying Form 990 officer table, board approval process, comparability data, and related-organization compensation context."
        if "facility" in area:
            return "Request or retrieve DHCS facility license/status history and adverse-status records for the named facilities before entity-level use."
        if "audit" in area:
            return "Open the FAC audit PDF and finding rows; verify current finding status, agency response, corrective action, and repeat status."
        if "award" in area or "public-funds" in area:
            return "Trace award programs to contracts, grant terms, deliverables, and provider-attributable outcome reports."
        if "growth" in area:
            return "Compare raw IRS XML/PDF returns year over year, then separate program growth, grants, mergers, one-time receipts, and expense categories."
        if "spend-versus-results" in area:
            return "Request provider-attributable utilization, completion, discharge, cost-per-service, and outcome records for the same county and year window."
        if "connected-party" in area:
            return "Verify charging documents, docket status, named parties, property or project relationship, payment records, due diligence files, and internal controls before any entity-level conclusion."
        if "statement" in area or "scope" in area:
            return "Compare public statements to homelessness contract scopes, grant restrictions, funding source, lobbying disclosures, and accounting treatment before drawing conclusions."
        if item.risk_level == "Data gap":
            return "Collect the missing source named in the row and rerun the matrix before upgrading the signal."
        return text

    def _human_next_steps(
        self,
        bundle: EvidenceBundle,
        risk_matrix: OversightRiskMatrix,
        sentinel: SentinelResult,
    ) -> list[str]:
        source_types = {item.source_type for item in bundle.items}
        risk_areas = " ".join(item.risk_area.lower() for item in risk_matrix.indicators)
        steps = [
            "Open the review packet and verify each priority row against the cited evidence ledger before changing case status.",
        ]
        for instruction in sentinel.repair_instructions:
            steps.append(f"Resolve sentinel caution: {instruction}")
        if any(source_type.startswith("irs_990") or source_type == "source_extraction_irs_990_table" for source_type in source_types):
            steps.append("Verify raw IRS XML or official return images for revenue, expenses, grants, officer compensation, and year-over-year movement.")
        if any(source_type.startswith("fac") or source_type in {"source_extraction_fac_audit_table", "source_extraction_fac_award_table"} for source_type in source_types):
            steps.append("Open FAC audit PDFs and findings tables to confirm audit year, finding status, federal agency, questioned-cost fields, and management response.")
        if any(source_type.startswith("dhcs") or source_type == "source_extraction_dhcs_status_table" for source_type in source_types):
            steps.append("Pull DHCS facility license/status history and adverse-status records directly before using facility rows beyond context.")
        if "county" in risk_areas or "spend-versus-results" in risk_areas:
            steps.append("Request county contract files, monitoring letters, corrective-action status, deliverables, and provider-level outcome records for the same year window.")
        if "compensation" in risk_areas:
            steps.append("Benchmark officer and key employee compensation against comparable organizations and verify documented approval procedures.")
        if "public statement" in risk_areas or "scope" in risk_areas or "public_statement_source" in source_types:
            steps.append("Compare harvested public statements and web pages to homelessness grant scopes, contract restrictions, funding sources, and accounting records; treat statements as context until dollars and scope are linked.")
        if "court_docket_manifest" in source_types:
            steps.append("Verify court or docket pointers directly in the relevant docket system before treating them as meaningful context.")
        if "connected-party" in risk_areas:
            steps.append("For connected-party enforcement rows, verify the official charging record, docket status, named parties, nonprofit relationship, transaction documents, and public-dollar flow before any entity-level statement.")
        return self._dedupe(steps)

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        seen = set()
        output = []
        for value in values:
            if value not in seen:
                seen.add(value)
                output.append(value)
        return output

    def _table_cell(self, value: object) -> str:
        text = str(value).replace("\r", " ").replace("\n", "<br>")
        return text.replace("|", "\\|")


def compile_dossier_from_run(run_dir: Path, output_dir: Path | None = None) -> CompiledCaseDossier:
    artifacts_dir = run_dir / "artifacts"
    if not artifacts_dir.exists():
        raise FileNotFoundError(f"missing artifacts directory: {artifacts_dir}")

    output_dir = output_dir or artifacts_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    request = CaseRequest.from_dict(read_json(artifacts_dir / "case_request.json"))
    bundle = evidence_bundle_from_dict(read_json(artifacts_dir / "evidence_bundle.json"))
    lead = lead_candidate_from_dict(read_json(artifacts_dir / "lead_candidate.json"))
    sentinel = sentinel_result_from_dict(read_json(artifacts_dir / "sentinel_decision.json"))
    risk_matrix = risk_matrix_from_dict(read_json(artifacts_dir / "oversight_risk_matrix.json"))
    review_packet = review_packet_from_dict(read_json(artifacts_dir / "review_packet.json"))
    review_decision_path = artifacts_dir / "review_decision.json"
    if review_decision_path.exists():
        review_decision = review_decision_from_dict(read_json(review_decision_path))
    else:
        review_decision = ReviewDecision(
            decision_id=stable_id("review", request.case_id, "pending"),
            case_id=request.case_id,
            decision=HumanDecision.PENDING,
        )

    artifact_refs = [str(path) for path in sorted(artifacts_dir.iterdir()) if path.is_file()]
    dossier = CaseDossierService(_archive_path_remaps(run_dir)).write_dossier(
        output_dir / "case_dossier.md",
        request,
        bundle,
        lead,
        sentinel,
        risk_matrix,
        review_packet,
        review_decision,
        artifact_refs,
    )
    write_json(output_dir / "case_dossier.json", dossier)
    return dossier


def evidence_bundle_from_dict(value: dict[str, object]) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=str(value["bundle_id"]),
        case_id=str(value["case_id"]),
        query_terms=list(value.get("query_terms", [])),
        items=[evidence_item_from_dict(item) for item in value.get("items", [])],
        entity_links=[entity_link_from_dict(item) for item in value.get("entity_links", [])],
        created_at=str(value.get("created_at", "")),
    )


def evidence_item_from_dict(value: dict[str, object]) -> EvidenceItem:
    return EvidenceItem(
        item_id=str(value["item_id"]),
        record_id=str(value["record_id"]),
        title=str(value.get("title", "")),
        source_uri=str(value.get("source_uri", "")),
        source_type=str(value.get("source_type", "")),
        published_at=str(value.get("published_at", "")),
        excerpt=str(value.get("excerpt", "")),
        relevance_score=float(value.get("relevance_score", 0.0)),
        matched_terms=list(value.get("matched_terms", [])),
        provenance=provenance_from_dict(value.get("provenance", {})),
        signals=dict(value.get("signals", {})),
    )


def provenance_from_dict(value: object) -> Provenance:
    data = dict(value or {})
    return Provenance(
        record_id=str(data.get("record_id", "")),
        source_uri=str(data.get("source_uri", "")),
        source_type=str(data.get("source_type", "")),
        collected_at=str(data.get("collected_at", "")),
        checksum=str(data.get("checksum", "")),
        corpus_name=str(data.get("corpus_name", "")),
        chunk_id=str(data.get("chunk_id", "")),
    )


def entity_link_from_dict(value: dict[str, object]) -> EntityLink:
    return EntityLink(
        entity=str(value.get("entity", "")),
        record_ids=list(value.get("record_ids", [])),
        link_type=str(value.get("link_type", "")),
        strength=float(value.get("strength", 0.0)),
        rationale=str(value.get("rationale", "")),
    )


def lead_candidate_from_dict(value: dict[str, object]) -> LeadCandidate:
    return LeadCandidate(
        lead_id=str(value["lead_id"]),
        case_id=str(value["case_id"]),
        statement=str(value.get("statement", "")),
        support_summary=str(value.get("support_summary", "")),
        uncertainty=list(value.get("uncertainty", [])),
        required_review_questions=list(value.get("required_review_questions", [])),
        evidence_ids=list(value.get("evidence_ids", [])),
        score=float(value.get("score", 0.0)),
        score_inputs=ScoreInputs(**dict(value.get("score_inputs", {}))),
        status=str(value.get("status", "READY_FOR_SENTINEL")),
        created_at=str(value.get("created_at", "")),
    )


def sentinel_result_from_dict(value: dict[str, object]) -> SentinelResult:
    return SentinelResult(
        decision_id=str(value["decision_id"]),
        case_id=str(value["case_id"]),
        decision=SentinelDecision(str(value["decision"])),
        flags=list(value.get("flags", [])),
        rationale=str(value.get("rationale", "")),
        repair_instructions=list(value.get("repair_instructions", [])),
        checked_at=str(value.get("checked_at", "")),
    )


def risk_matrix_from_dict(value: dict[str, object]) -> OversightRiskMatrix:
    return OversightRiskMatrix(
        matrix_id=str(value["matrix_id"]),
        case_id=str(value["case_id"]),
        methodology=str(value.get("methodology", "")),
        score_scale=str(value.get("score_scale", "")),
        indicators=[risk_indicator_from_dict(item) for item in value.get("indicators", [])],
        created_at=str(value.get("created_at", "")),
    )


def risk_indicator_from_dict(value: dict[str, object]) -> OversightRiskIndicator:
    return OversightRiskIndicator(
        indicator_id=str(value["indicator_id"]),
        case_id=str(value["case_id"]),
        risk_area=str(value.get("risk_area", "")),
        entity=str(value.get("entity", "")),
        test_name=str(value.get("test_name", "")),
        observed_fact=str(value.get("observed_fact", "")),
        risk_level=str(value.get("risk_level", "")),
        data_status=str(value.get("data_status", "")),
        reviewer_action=str(value.get("reviewer_action", "")),
        evidence_ids=list(value.get("evidence_ids", [])),
        record_ids=list(value.get("record_ids", [])),
        source_uris=list(value.get("source_uris", [])),
        caveats=list(value.get("caveats", [])),
    )


def review_packet_from_dict(value: dict[str, object]) -> ReviewPacket:
    return ReviewPacket(
        packet_id=str(value["packet_id"]),
        case_id=str(value["case_id"]),
        markdown_path=str(value.get("markdown_path", "")),
        artifact_refs=list(value.get("artifact_refs", [])),
        created_at=str(value.get("created_at", "")),
    )


def review_decision_from_dict(value: dict[str, object]) -> ReviewDecision:
    return ReviewDecision(
        decision_id=str(value["decision_id"]),
        case_id=str(value["case_id"]),
        decision=HumanDecision(str(value.get("decision", HumanDecision.PENDING.value))),
        reviewer=str(value.get("reviewer", "unassigned")),
        rationale=str(value.get("rationale", "Pending explicit human review.")),
        created_at=str(value.get("created_at", "")),
    )




def _archive_path_remaps(run_dir: Path) -> dict[str, str]:
    project_artifacts = Path(__file__).resolve().parents[1] / "artifacts"
    for parent in [run_dir, *run_dir.parents]:
        archived_artifacts = parent / "artifacts"
        if archived_artifacts.exists() and archived_artifacts != project_artifacts and archived_artifacts != run_dir / "artifacts":
            return {str(project_artifacts): str(archived_artifacts)}
    return {}
