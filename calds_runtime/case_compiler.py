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
from .review import SOURCE_TYPE_LABELS


RISK_ORDER = {"High": 0, "Medium": 1, "Data gap": 2, "Low": 3}


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
        priority_rows = self._priority_indicators(risk_matrix)
        source_counts = Counter(item.source_type for item in bundle.items)
        sentinel_items = [f"- {item}" for item in sentinel.repair_instructions] or ["- none"]
        mode = self._dossier_mode(sentinel)

        lines = [
            f"# Case Dossier: {request.title}",
            "",
            "## 1. Case Dossier Orientation",
            "",
            f"Status: `{review_decision.decision.value}` human review required",
            "",
            "This dossier compiles existing CalDS workflow artifacts into a human-readable case file. It is an internal WFA screening aid, not a finding or outside-facing conclusion.",
            "",
            "Every substantive row below is tied to a risk indicator, evidence item, source URI, checksum, or durable artifact path. Raw source documents and canonical records remain controlling.",
            "",
            f"Dossier mode: {mode}",
            "",
            "## 2. Case Summary",
            "",
            f"- Case ID: `{request.case_id}`",
            f"- Jurisdiction: {request.jurisdiction}",
            f"- Objective: {request.objective}",
            f"- Named entities: {', '.join(request.entities) or 'none specified'}",
            f"- Allowed source types: {', '.join(request.allowed_sources) or 'none specified'}",
            f"- Review packet: `{review_packet.markdown_path}`",
            "",
            "## 3. Score and Sentinel Posture",
            "",
            f"Lead statement: {lead.statement}",
            "",
            f"Score: {lead.score} / 100",
            "",
            self._score_interpretation(lead.score),
            "",
            "The score is deterministic triage priority, not a probability, not a dollar loss estimate, and not a conclusion. Higher scores mean stronger retrieved-source coverage and entity linkage after missing-data and contradiction penalties.",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Support count | {lead.score_inputs.support_count} |",
            f"| Average relevance | {lead.score_inputs.average_relevance} |",
            f"| Source diversity | {lead.score_inputs.source_diversity} |",
            f"| Hard entity links | {lead.score_inputs.hard_link_count} |",
            f"| Missing-data count | {lead.score_inputs.missing_data_count} |",
            f"| Contradiction count | {lead.score_inputs.contradiction_count} |",
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
            "## 4. Executive Briefing",
            "",
            "Read this section first. It is written as an internal briefing memo: what the organization says or is described as doing in the retrieved sources, what the records show, why CalDS flags it, and what still needs human verification.",
            "",
            *self._briefing_memo_lines(request, bundle, lead, sentinel, risk_matrix, labels),
            "",
            "## 5. Evidence Detail By Entity",
            "",
            "This section preserves the system opinion and source-fact detail behind the briefing memo. It remains an internal WFA screening opinion, not a formal allegation or outside-facing conclusion.",
            "",
            *self._entity_opinion_lines(risk_matrix, labels),
            "",
            "## 6. Flagged Review Matrix",
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
                            f"- What CalDS found: {item.observed_fact}",
                            f"- When/where: {self._when_where(item)}",
                            f"- How this triggered review: {self._trigger_text(item)}",
                            f"- Evidence refs: {refs}",
                            f"- Source URI(s): {self._format_source_uris(item.source_uris)}",
                            f"- System opinion: {self._system_opinion(item)}",
                            f"- Why this matters: {self._why_it_matters(item)}",
                            f"- What this flags: {item.reviewer_action}",
                            f"- What this does not prove: {self._not_proven_text(item)}",
                            f"- Human next step: {self._indicator_next_step(item)}",
                            *[f"- Caveat: {caveat}" for caveat in item.caveats],
                            "",
                        ]
                    )
        else:
            lines.extend(["No high, medium, or data-gap rows were generated from the current source corpus.", ""])

        lines.extend(
            [
                "## 7. Evidence Citation Ledger",
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
                        self._table_cell(SOURCE_TYPE_LABELS.get(item.source_type, item.source_type)),
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
            lines.append(f"| {self._table_cell(SOURCE_TYPE_LABELS.get(source_type, source_type))} | {count} |")

        lines.extend(
            [
                "",
                "## 8. Human-Only Next Steps",
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
                "## 9. Artifact References",
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
                "## 10. Human Review Required",
                "",
                "The workflow remains paused. A reviewer must explicitly approve, downgrade, repair, or reject this case before any outside-facing use.",
                "",
            ]
        )

        path.write_text("\n".join(lines), encoding="utf-8")
        return CompiledCaseDossier(
            dossier_id=stable_id("dossier", request.case_id, str(path)),
            case_id=request.case_id,
            markdown_path=str(path),
            source_artifact_refs=source_artifact_refs,
            sentinel_decision=sentinel.decision,
            compiler_role=AgentRole.CASE_COMPILER,
        )

    def _briefing_memo_lines(
        self,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        matrix: OversightRiskMatrix,
        labels: dict[str, str],
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

        lines = [
            f"Briefing posture: CalDS scores this lead at {lead.score} / 100 and the sentinel returned `{sentinel.decision.value}`. That means this is reviewable internal triage with caveats, not a final finding.",
            "",
            "Bottom line: this section summarizes what the records show about public-money exposure, service footprint, financial movement, outcome context, and source gaps. The briefs below answer that question entity by entity.",
            "",
        ]

        ordered = sorted(
            by_entity.items(),
            key=lambda pair: (
                min(RISK_ORDER.get(item.risk_level, 99) for item in pair[1]),
                pair[0],
            ),
        )
        if not ordered:
            lines.extend(["No entity-specific briefing could be generated from the current matrix.", ""])
        for entity, indicators in ordered:
            lines.extend(self._briefing_entity_lines(entity, indicators, bundle, labels))

        if case_wide:
            lines.extend(["### Case-wide Source Gaps", ""])
            lines.append("These are not NGO-specific findings. They are run-level blockers that limit how strongly CalDS can rank or clear the case.")
            lines.append("")
            for item in sorted(case_wide, key=lambda row: (RISK_ORDER.get(row.risk_level, 99), row.risk_area)):
                if item.risk_level not in {"Data gap", "High", "Medium"}:
                    continue
                lines.extend(
                    [
                        f"- {item.risk_area}: {item.observed_fact}",
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
    ) -> list[str]:
        priority = sorted(
            indicators,
            key=lambda item: (RISK_ORDER.get(item.risk_level, 99), item.risk_area, item.test_name),
        )
        review_rows = [item for item in priority if item.risk_level in {"High", "Medium", "Data gap"}]
        posture = self._entity_posture(Counter(item.risk_level for item in indicators))
        claim = self._entity_claim_context(entity, bundle, labels)
        facts = self._briefing_fact_bullets(review_rows, labels)
        why = self._briefing_why_flagged(review_rows)
        limits = self._briefing_limits(review_rows)
        next_step = self._briefing_next_step(review_rows)
        return [
            f"### {entity}",
            "",
            f"Briefing judgment: CalDS flags {entity} as a {posture}.",
            "",
            f"What the organization says or is described as doing: {claim}",
            "",
            "What the records show:",
            "",
            *facts,
            "",
            f"Why this is on the review list: {why}",
            "",
            f"What this does not prove: {limits}",
            "",
            f"Boss-level next step: {next_step}",
            "",
        ]

    def _briefing_fact_bullets(self, rows: list[OversightRiskIndicator], labels: dict[str, str]) -> list[str]:
        if not rows:
            return ["- No high, medium, or data-gap facts were available for this entity in the current matrix."]
        bullets: list[str] = []
        outcome_rows = [item for item in rows if item.risk_area == "Spend-versus-results"]
        selected = [item for item in rows if item.risk_area != "Spend-versus-results"]
        for item in selected[:5]:
            bullets.append(
                f"- {item.risk_area}: {item.observed_fact} ({self._when_where(item)}; evidence {self._matrix_refs(item, labels)}.)"
            )
        if outcome_rows:
            bullets.append(self._outcome_briefing_bullet(outcome_rows, labels))
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
        refs = self._matrix_refs_for_many(rows, labels)
        return (
            "- Spend-versus-results: official county/CoC outcome context worsened in the entity's matched DHCS footprint: "
            + "; ".join(segments)
            + more
            + "."
            + growth_text
            + " This is a review signal, not provider attribution. Evidence "
            + refs
            + "."
        )

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
        tokens = [token for token in re.findall(r"[a-z0-9]+", entity.lower()) if token not in {"inc", "of", "california", "the"}]
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


    def _briefing_why_flagged(self, rows: list[OversightRiskIndicator]) -> str:
        if not rows:
            return "No review-priority reason was available in the current matrix."
        areas = {item.risk_area.lower() for item in rows}
        if "spend-versus-results" in areas and any("award" in area or "public-funds" in area or "growth" in area for area in areas):
            return "CalDS sees the combination reviewers care about: material public-money exposure or financial movement, plus outcome context that moved the wrong direction in matched service geographies. That does not prove provider responsibility, but it is exactly the mismatch that should be briefed up for document review."
        if any("facility" in area for area in areas) and any("award" in area or "public-funds" in area for area in areas):
            return "CalDS sees public-money exposure next to facility-footprint stress. The reviewer should understand whether closed or changed facility rows affect service capacity, contract delivery, or merely historical licensing records."
        if any("audit" in area for area in areas):
            return "CalDS sees audit-control context that can bear directly on stewardship of public funds, especially if findings, management responses, or corrective-action status remain unresolved."
        return self._why_it_matters(rows[0])

    def _briefing_limits(self, rows: list[OversightRiskIndicator]) -> str:
        if not rows:
            return "The current matrix does not prove or disprove a substantive issue."
        limits = self._dedupe(self._not_proven_text(item) for item in rows[:4])
        return " ".join(limits[:2])

    def _briefing_next_step(self, rows: list[OversightRiskIndicator]) -> str:
        if not rows:
            return "Collect additional source material and rerun the matrix before briefing this beyond internal triage."
        for item in rows:
            if item.risk_level == "High":
                return self._indicator_next_step(item)
        return self._indicator_next_step(rows[0])

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
    def _entity_opinion_lines(self, matrix: OversightRiskMatrix, labels: dict[str, str]) -> list[str]:
        rows = [item for item in matrix.indicators if item.entity]
        by_entity: dict[str, list[OversightRiskIndicator]] = {}
        for item in rows:
            by_entity.setdefault(item.entity, []).append(item)
        lines: list[str] = []
        for entity in sorted(by_entity):
            indicators = by_entity[entity]
            priority = sorted(
                indicators,
                key=lambda item: (RISK_ORDER.get(item.risk_level, 99), item.risk_area, item.test_name),
            )
            posture = self._entity_posture(Counter(item.risk_level for item in indicators))
            lines.extend(
                [
                    f"### {entity}",
                    "",
                    f"CalDS flags {entity} as a {posture}. The entity is in this dossier because the current source bundle contains the specific source facts below.",
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
            f"{index}. {item.risk_level} - {item.risk_area}: {item.observed_fact}",
            f"   - When/where: {self._when_where(item)}",
            f"   - How it triggered: {self._trigger_text(item)}",
            f"   - Evidence: {refs}; source: {source_text}",
            f"   - Why it matters: {self._why_it_matters(item)}",
            "",
        ]

    def _entity_posture(self, counts: Counter[str]) -> str:
        if counts.get("High", 0):
            return "high-priority WFA review subject"
        if counts.get("Medium", 0):
            return "moderate-priority WFA review subject"
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
        return f"CalDS flags this as a {item.risk_level.lower()} WFA review priority because {item.observed_fact} This source fact matches the implemented {item.risk_area.lower()} screen and should stay in the active review queue."

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
            return "Rapid revenue or expense growth becomes a WFA review concern when it outpaces visible service capacity, documented outcomes, or clear grant-scope explanations."
        if "spend-versus-results" in area:
            return "Spending growth next to worsening county-level outcomes is not provider-attributable by itself, but it is exactly the mismatch CalDS should force into review."
        if "statement" in area or "scope" in area:
            return "Public claims and program language matter when they point to activities that may need contract-scope, grant-scope, or lobbying-disclosure review."
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
        return "Interpretation: insufficient retrieved support for a review lead from the current corpus."

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
        if "statement" in area or "scope" in area:
            return "It does not prove spending outside allowed scope; contract, grant, and accounting records must be checked."
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
        if "statement" in area or "scope" in area:
            return "Compare public statements to contract scopes, grant restrictions, lobbying disclosures, and accounting treatment before drawing conclusions."
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
            steps.append("Compare harvested public statements and web pages to grant scopes, contract restrictions, and accounting records; treat statements as context only.")
        if "court_docket_manifest" in source_types:
            steps.append("Verify court or docket pointers directly in the relevant docket system before treating them as meaningful context.")
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
















