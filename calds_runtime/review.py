from __future__ import annotations

from collections import Counter
from pathlib import Path

from .contracts import (
    CaseRequest,
    EvidenceBundle,
    EvidenceItem,
    LeadCandidate,
    OversightRiskIndicator,
    OversightRiskMatrix,
    ReviewPacket,
    ScoreInputs,
    SentinelResult,
    stable_id,
)
from .plain_language import REVIEWER_GLOSSARY_LINES, expand_reviewer_acronyms


SOURCE_TYPE_LABELS = {
    "irs_990_summary": "Internal Revenue Service Form 990 summary",
    "irs_990_xml": "Downloaded Internal Revenue Service Form 990 machine-readable filing data",
    "irs_990_download_manifest": "Internal Revenue Service machine-readable filing-data availability manifest",
    "irs_990_full_text_fallback": "Rendered Form 990 fallback",
    "fac_audit_summary": "Federal Audit Clearinghouse audit summary",
    "fac_audit_pdf": "Federal Audit Clearinghouse audit source document",
    "fac_findings": "Federal Audit Clearinghouse findings table",
    "fac_federal_awards": "Federal Audit Clearinghouse federal awards table",
    "dhcs_page": "California Department of Health Care Services page",
    "dhcs_facility_status": "California Department of Health Care Services facility-status row set",
    "dhcs_adverse_status_manifest": "California Department of Health Care Services adverse-status page manifest",
    "dhcs_adverse_status_discovery": "California Department of Health Care Services adverse-status source discovery",
    "county_contract_or_monitoring": "County contract or monitoring source",
    "state_homelessness_award": "California Department of Housing and Community Development homelessness award record",
    "court_docket_manifest": "Court docket search manifest",
    "enforcement_or_docket_source": "Official enforcement or docket source",
    "social_media_source": "Social media source",
    "source_extraction_state_homeless_award_table": "Parsed California state homelessness award table",
    "source_extraction_enforcement_docket_table": "Parsed enforcement and docket source table",
    "source_extraction_irs_990_table": "Parsed Internal Revenue Service source table",
    "source_extraction_fac_audit_table": "Parsed Federal Audit Clearinghouse audit table",
    "source_extraction_fac_award_table": "Parsed Federal Audit Clearinghouse award table",
    "source_extraction_dhcs_status_table": "Parsed California Department of Health Care Services status table",
    "source_extraction_pdf_text_index": "Parsed source document text index",
    "source_extraction_official_outcome_table": "Parsed official outcome source table",
    "source_extraction_spend_vs_results_table": "Parsed spend-versus-results join",
    "source_extraction_public_statement_table": "Parsed public statement source table",
    "source_extraction_social_web_table": "Parsed social and website source table",
    "public_statement_source": "Public statement source",
    "org_service_page": "Organization service page",
}


class ReviewArtifactService:
    """Deterministic service for reviewer-facing artifacts."""

    def write_packet(
        self,
        path: Path,
        request: CaseRequest,
        bundle: EvidenceBundle,
        lead: LeadCandidate,
        sentinel: SentinelResult,
        risk_matrix: OversightRiskMatrix,
        artifact_refs: list[str],
    ) -> ReviewPacket:
        path.parent.mkdir(parents=True, exist_ok=True)
        evidence_labels = self._evidence_labels(bundle)
        entity_lookup = self._entity_lookup(bundle)
        cited_labels = [evidence_labels[item_id] for item_id in lead.evidence_ids if item_id in evidence_labels]
        score_inputs = lead.score_inputs
        formula = self._score_formula(score_inputs)

        lines = [
            f"# Review Packet: {request.title}",
            "",
            "## 1. Reviewer Orientation",
            "",
            "Status: AWAITING_HUMAN_REVIEW",
            "",
            "This packet is for internal reviewer triage only. It does not approve outside-facing use. Treat every lead as a review question until a human reviewer verifies the cited source records.",
            "",
            "This packet is formatted for public-funds oversight and misuse-risk screening. It does not assert that waste, abuse, misconduct, or a program failure occurred.",
            "",
            "### How to Use This Packet",
            "",
            "- Start with the Summary of Supported Review Signals and the Evidence Citation Map.",
            "- Evidence labels such as `E01` and `E02` are packet-local shortcuts for human review.",
            "- The stable internal evidence ID, record ID, source URI, and checksum remain in each evidence detail for audit and replay.",
            "- The `What this flags` field explains why the source was included; it is not a conclusion.",
            "- Source excerpts and parsed tables are navigation aids. Raw source documents and checksums remain controlling for audit.",
            "- The sentinel decision is a gate on wording and review posture, not a substantive approval.",
            "",
            "### Plain-Language Source Guide",
            "",
            *REVIEWER_GLOSSARY_LINES,
            "",
            "### Reviewer Decision Needed",
            "",
            "Record an explicit `APPROVE`, `DOWNGRADE`, `REPAIR`, or `REJECT` decision after checking the cited sources and missing-data notes.",
            "",
            "## 2. Case Scope",
            "",
            f"- Case ID: `{request.case_id}`",
            f"- Jurisdiction: {request.jurisdiction}",
            f"- Objective: {self._plain_language(request.objective)}",
            f"- Named entities: {', '.join(request.entities) or 'none specified'}",
            f"- Allowed source types: {self._allowed_source_labels(request.allowed_sources)}",
            "",
            *self._matrix_lines(risk_matrix, evidence_labels, bundle),
            "",
            "## 4. Summary of Supported Review Signals",
            "",
            "The following summary is derived only from retrieved evidence and recorded source signals. It is a triage summary, not a finding of wrongdoing.",
            "",
            *self._summary_bullets(bundle, evidence_labels),
            "",
            "### Evidence Coverage Snapshot",
            "",
            "| Source class | Retrieved evidence count |",
            "| --- | --- |",
        ]
        for source_type, count in self._source_counts(bundle).items():
            lines.append(f"| {self._table_cell(self._source_type_label(source_type))} | {count} |")

        lines.extend(
            [
                "",
                "## 5. Lead Candidate For Review",
                "",
                self._plain_language(lead.statement),
                "",
                "### Score Summary",
                "",
                f"Score: {lead.score} / 100",
                "",
                self._score_interpretation(lead.score),
                "",
                "The score is a deterministic triage-priority score. It is not a probability, not a dollar estimate, and not a finding. Higher scores mean stronger retrieved-source coverage and entity linkage, after penalties for missing or contradictory data.",
                "",
                "| Field | Value | Meaning |",
                "| --- | --- | --- |",
                f"| Final score | {lead.score} / 100 | Clamped to the 0-100 range |",
                f"| Support count | {score_inputs.support_count} | Number of evidence items retrieved |",
                f"| Average relevance | {score_inputs.average_relevance} | Keyword relevance across retrieved evidence |",
                f"| Source diversity | {score_inputs.source_diversity} source type(s) | Variety of independent source classes |",
                f"| Hard entity links | {score_inputs.hard_link_count} | Deterministic entity joins at strength >= 0.7 |",
                f"| Missing-data count | {score_inputs.missing_data_count} | Evidence items carrying missing-data caveats |",
                f"| Contradiction count | {score_inputs.contradiction_count} | Evidence items carrying contradiction signals |",
                "",
                "### Score Formula",
                "",
                "The implemented formula is: `20 base + average_relevance*35 + support bonus up to 20 + source-diversity bonus up to 15 + hard-link bonus up to 20 - contradiction penalties - missing-data penalties`, then clamped to `0-100`.",
                "",
                "| Component | Value | Contribution |",
                "| --- | --- | --- |",
                f"| Base | fixed | +{formula['base']:.2f} |",
                f"| Relevance | {score_inputs.average_relevance} * 35 | +{formula['relevance']:.2f} |",
                f"| Support count | min(20, {score_inputs.support_count} * 4) | +{formula['support']:.2f} |",
                f"| Source diversity | min(15, {score_inputs.source_diversity} * 4) | +{formula['diversity']:.2f} |",
                f"| Hard entity links | min(20, {score_inputs.hard_link_count} * 5) | +{formula['hard_links']:.2f} |",
                f"| Contradictions | {score_inputs.contradiction_count} * -6 | -{formula['contradiction_penalty']:.2f} |",
                f"| Missing data | {score_inputs.missing_data_count} * -5 | -{formula['missing_penalty']:.2f} |",
                f"| Raw score before clamp |  | {formula['raw']:.2f} |",
                "",
                f"Support summary: {self._plain_language(lead.support_summary)}",
                "",
                f"Cited evidence labels: {self._format_label_list(cited_labels) or 'none'}",
                "",
                "### Uncertainty and Caveats",
                "",
                *[f"- {self._plain_language(item)}" for item in lead.uncertainty],
                "",
                "## 6. Sentinel Gate",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Decision | {sentinel.decision.value} |",
                f"| Rationale | {self._table_cell(self._plain_language(sentinel.rationale))} |",
                f"| Flags | {self._table_cell(', '.join(sentinel.flags) if sentinel.flags else 'none')} |",
                "",
                "### Sentinel Repair Instructions",
                "",
                *[f"- {self._plain_language(item)}" for item in sentinel.repair_instructions],
                "",
                "## 7. Required Reviewer Questions",
                "",
                *[f"{index}. {self._plain_language(item)}" for index, item in enumerate(lead.required_review_questions, start=1)],
                "",
                "## 8. Evidence Citation Map",
                "",
                "Use this table first. It translates packet-local evidence labels into source records, explains why each item was included, and states what the reviewer should do next.",
                "",
                "| Ref | Source record | What this flags | Reviewer next step | Entity link(s) | Published |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )

        for item in bundle.items:
            label = evidence_labels[item.item_id]
            entities = entity_lookup.get(item.record_id, [])
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{label}`",
                        self._table_cell(f"{self._plain_language(item.title)} (`{item.record_id}`)"),
                        self._table_cell(self._plain_language(self._review_flag(item))),
                        self._table_cell(self._plain_language(self._reviewer_action(item))),
                        self._table_cell(", ".join(entities) if entities else "not linked"),
                        self._table_cell(item.published_at or "not provided"),
                    ]
                )
                + " |"
            )

        lines.extend(
            [
                "",
                "## 9. Evidence Details",
                "",
                "Each item below preserves the audit fields needed to replay or challenge the citation. The short label is for human reading; the internal evidence ID is retained for machine traceability.",
                "",
            ]
        )

        for item in bundle.items:
            label = evidence_labels[item.item_id]
            entities = entity_lookup.get(item.record_id, [])
            lines.extend(
                [
                    f"### {label} - {self._plain_language(item.title)}",
                    "",
                    "#### Reviewer Context",
                    "",
                    f"- What this flags: {self._plain_language(self._review_flag(item))}",
                    f"- How to use it: {self._plain_language(self._reviewer_action(item))}",
                    f"- Source posture: {self._plain_language(self._source_posture(item))}",
                    "",
                    "| Field | Value |",
                    "| --- | --- |",
                    f"| Internal evidence ID | `{item.item_id}` |",
                    f"| Record ID | `{item.record_id}` |",
                    f"| Source type | {self._table_cell(self._source_type_label(item.source_type))} |",
                    f"| Source URI | {self._table_cell(item.source_uri)} |",
                    f"| Published | {self._table_cell(item.published_at or 'not provided')} |",
                    f"| Entity link(s) | {self._table_cell(', '.join(entities) if entities else 'not linked')} |",
                    f"| Relevance score | {item.relevance_score:.3f} |",
                    f"| Matched terms | {self._table_cell(', '.join(item.matched_terms) if item.matched_terms else 'none')} |",
                    f"| Active source signals | {self._table_cell(self._active_signal_text(item))} |",
                    f"| Checksum | `{item.provenance.checksum}` |",
                    f"| Corpus | `{item.provenance.corpus_name}` |",
                    f"| Chunk | `{item.provenance.chunk_id}` |",
                    "",
                    "Excerpt or parsed output:",
                    "",
                    "```text",
                    self._code_text(item.excerpt),
                    "```",
                    "",
                ]
            )

        lines.extend(
            [
                "## 10. Artifact References",
                "",
                "These files are the durable workflow artifacts used to produce this packet.",
                "",
                "| Artifact | Path |",
                "| --- | --- |",
            ]
        )
        for ref in artifact_refs:
            lines.append(f"| {self._table_cell(Path(ref).name)} | `{ref}` |")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return ReviewPacket(
            packet_id=stable_id("packet", request.case_id, str(path)),
            case_id=request.case_id,
            markdown_path=str(path),
            artifact_refs=artifact_refs,
        )

    def _plain_language(self, text: object) -> str:
        return expand_reviewer_acronyms(text)

    def _source_type_label(self, source_type: str) -> str:
        return self._plain_language(SOURCE_TYPE_LABELS.get(source_type, source_type))

    def _allowed_source_labels(self, source_types: list[str]) -> str:
        if not source_types:
            return "none specified"
        return ", ".join(self._source_type_label(source_type) for source_type in source_types)

    def _evidence_labels(self, bundle: EvidenceBundle) -> dict[str, str]:
        return {item.item_id: f"E{index:02d}" for index, item in enumerate(bundle.items, start=1)}

    def _entity_lookup(self, bundle: EvidenceBundle) -> dict[str, list[str]]:
        lookup: dict[str, list[str]] = {}
        for link in bundle.entity_links:
            for record_id in link.record_ids:
                values = lookup.setdefault(record_id, [])
                if link.entity not in values:
                    values.append(link.entity)
        return {key: sorted(values) for key, values in lookup.items()}

    def _matrix_lines(
        self,
        risk_matrix: OversightRiskMatrix,
        labels: dict[str, str],
        bundle: EvidenceBundle,
    ) -> list[str]:
        counts = Counter(item.risk_level for item in risk_matrix.indicators)
        lines = [
            "## 3. Oversight Risk Matrix",
            "",
            "This is the reviewer-facing possible waste, fraud, abuse, or mismanagement screening matrix. It flags source-backed risk proxies and explicit data gaps; it does not allege that any entity mishandled funds or engaged in wrongdoing.",
            "",
            f"Methodology: {self._plain_language(risk_matrix.methodology)}",
            "",
            f"Risk scale: {risk_matrix.score_scale}",
            "",
            "### Matrix Summary",
            "",
            "| Risk level | Count |",
            "| --- | --- |",
        ]
        for level in ["High", "Medium", "Data gap", "Low"]:
            lines.append(f"| {level} | {counts.get(level, 0)} |")
        lines.extend(
            [
                "",
                "High and medium rows are review priorities. Data-gap rows are source-collection blockers. Low rows are retained so reviewers can see what was checked and did not trigger under the current thresholds.",
                "",
                "### Highest-Priority Rows",
                "",
            ]
        )
        priority = [item for item in risk_matrix.indicators if item.risk_level in {"High", "Medium"}][:12]
        if priority:
            for item in priority:
                lines.append(
                    f"- {item.risk_level}: {item.entity} - {item.risk_area} / {self._plain_language(item.test_name)}: {self._plain_language(item.observed_fact)}"
                )
        else:
            lines.append("- No high or medium rows were generated from the current source corpus.")
        lines.extend(
            [
                "",
                "### Full Matrix",
                "",
                "| Risk area | Entity | Level | Test | Observed fact | Evidence refs | Reviewer action |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in risk_matrix.indicators:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._table_cell(item.risk_area),
                        self._table_cell(item.entity),
                        self._table_cell(item.risk_level),
                        self._table_cell(self._plain_language(item.test_name)),
                        self._table_cell(self._plain_language(item.observed_fact)),
                        self._table_cell(self._matrix_refs(item, labels)),
                        self._table_cell(self._plain_language(item.reviewer_action)),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "### Matrix Caveats",
                "",
                "- Risk rows are screening prompts, not conclusions.",
                "- Spending, compensation, grants, audit flags, and facility closures can have ordinary explanations; the reviewer must verify source context.",
                "- Official county or Continuum of Care outcome series are now ingested for context, but the run still lacks provider-attributable treatment results, social and traffic metrics, and full facility license-history or adverse-status records.",
            ]
        )
        return lines

    def _matrix_refs(self, indicator: OversightRiskIndicator, labels: dict[str, str]) -> str:
        refs = []
        for evidence_id in indicator.evidence_ids:
            if evidence_id in labels:
                refs.append(f"`{labels[evidence_id]}`")
        for record_id in indicator.record_ids:
            if not any(record_id in ref for ref in refs):
                refs.append(f"`{record_id}`")
        return ", ".join(refs) if refs else "not applicable in retrieved evidence"

    def _source_counts(self, bundle: EvidenceBundle) -> dict[str, int]:
        counts = Counter(item.source_type for item in bundle.items)
        return dict(sorted(counts.items(), key=lambda pair: (-pair[1], SOURCE_TYPE_LABELS.get(pair[0], pair[0]))))

    def _signal_counts(self, bundle: EvidenceBundle) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in bundle.items:
            for key, value in item.signals.items():
                if value:
                    counts[key] = counts.get(key, 0) + 1
        return counts

    def _summary_bullets(self, bundle: EvidenceBundle, labels: dict[str, str]) -> list[str]:
        signals = self._signal_counts(bundle)
        source_counts = self._source_counts(bundle)
        bullets = [
            f"- Retrieved evidence volume: {len(bundle.items)} evidence item(s) across {len(source_counts)} source type(s). This supports triage prioritization only.",
        ]
        if signals.get("full_990_xml_downloaded") or signals.get("full_990_xml_parsed"):
            refs = self._refs_for(bundle, labels, "full_990_xml_downloaded", "full_990_xml_parsed")
            bullets.append(
                f"- Internal Revenue Service return coverage: downloaded machine-readable filing data or parsed Internal Revenue Service tables are present for the 2023-2025 review window where available. Review use: verify revenue, expenses, assets, grants, and schedule indicators against raw machine-readable filing data. Cited refs: {refs}."
            )
        if signals.get("full_990_xml_missing") or signals.get("irs_index_row_missing"):
            refs = self._refs_for(bundle, labels, "full_990_xml_missing", "irs_index_row_missing")
            bullets.append(
                f"- Internal Revenue Service source gaps: at least one return is represented by a missing-index or missing-object manifest. Review use: treat as a coverage gap and follow-up target, not as an adverse finding. Cited refs: {refs}."
            )
        if signals.get("irs_990_full_text_fallback"):
            refs = self._refs_for(bundle, labels, "irs_990_full_text_fallback")
            bullets.append(
                f"- Fallback return source: HealthRIGHT 360 has rendered full-text fallback fields because official Internal Revenue Service machine-readable filing data remains unresolved in this run. Review use: compare against later recovered official Internal Revenue Service machine-readable filing data or source document before relying on it. Cited refs: {refs}."
            )
        if signals.get("fac_audit_pdf_downloaded") or signals.get("fac_prior_findings") or signals.get("fac_current_year_findings"):
            refs = self._refs_for(bundle, labels, "fac_audit_pdf_downloaded", "fac_prior_findings", "fac_current_year_findings")
            bullets.append(
                f"- Federal Audit Clearinghouse audit context: audit source documents, findings rows, or prior-finding indicators are present. Review use: open the audit source document and confirm the year, finding status, agency, and management response before escalation. Cited refs: {refs}."
            )
        if signals.get("fac_federal_awards_present") or signals.get("fac_award_table_parsed"):
            refs = self._refs_for(bundle, labels, "fac_federal_awards_present", "fac_award_table_parsed")
            bullets.append(
                f"- Funding trace context: federal award rows and parsed award totals are present. Review use: identify programs and amounts for follow-up; do not infer performance from award size alone. Cited refs: {refs}."
            )
        if signals.get("dhcs_facility_closed_status") or signals.get("dhcs_status_crosscheck_incomplete"):
            refs = self._refs_for(bundle, labels, "dhcs_facility_closed_status", "dhcs_status_crosscheck_incomplete")
            bullets.append(
                f"- California Department of Health Care Services facility-status context: facility-level status rows and an incomplete adverse-status source check are present. Review use: verify facility-level meaning directly with California Department of Health Care Services records before making entity-level judgments. Cited refs: {refs}."
            )
        if signals.get("county_monitoring_report") or signals.get("county_contract_source_match"):
            refs = self._refs_for(bundle, labels, "county_monitoring_report", "county_contract_source_match")
            bullets.append(
                f"- County oversight context: monitoring or contract records are present. Review use: check agency response, corrective-action status, and current contract status. Cited refs: {refs}."
            )
        if signals.get("state_homelessness_award_exposure") or signals.get("state_homelessness_award_table"):
            refs = self._refs_for(bundle, labels, "state_homelessness_award_exposure", "state_homelessness_award_table")
            bullets.append(
                f"- State homelessness award context: California Department of Housing and Community Development Homekey or Homekey+ award rows are present. Review use: verify eligible applicant, co-applicant role, project amount, units, and any standard agreement or subrecipient allocation before treating award exposure as direct receipt. Cited refs: {refs}."
            )
        if signals.get("pdf_layout_extracted") or signals.get("pdf_text_extracted"):
            refs = self._refs_for(bundle, labels, "pdf_layout_extracted", "pdf_text_extracted")
            bullets.append(
                f"- PDF navigation support: text/layout extraction is available for downloaded PDFs. Review use: use extraction only to find pages or tables; raw PDFs remain controlling. Cited refs: {refs}."
            )
        if signals.get("missing_data"):
            refs = self._refs_for(bundle, labels, "missing_data")
            bullets.append(
                f"- Missing-data caveat: at least one item marks missing or incomplete data. Review use: resolve these gaps before any outside-facing use. Cited refs: {refs}."
            )
        return bullets

    def _refs_for(self, bundle: EvidenceBundle, labels: dict[str, str], *signal_names: str) -> str:
        refs = [labels[item.item_id] for item in bundle.items if any(item.signals.get(name) for name in signal_names)]
        if not refs:
            return "none"
        clipped = refs[:10]
        suffix = f", +{len(refs) - len(clipped)} more" if len(refs) > len(clipped) else ""
        return ", ".join(f"`{ref}`" for ref in clipped) + suffix

    def _score_formula(self, score_inputs: ScoreInputs) -> dict[str, float]:
        values = {
            "base": 20.0,
            "relevance": round(score_inputs.average_relevance * 35.0, 2),
            "support": min(20.0, score_inputs.support_count * 4.0),
            "diversity": min(15.0, score_inputs.source_diversity * 4.0),
            "hard_links": min(20.0, score_inputs.hard_link_count * 5.0),
            "contradiction_penalty": score_inputs.contradiction_count * 6.0,
            "missing_penalty": score_inputs.missing_data_count * 5.0,
        }
        values["raw"] = round(
            values["base"]
            + values["relevance"]
            + values["support"]
            + values["diversity"]
            + values["hard_links"]
            - values["contradiction_penalty"]
            - values["missing_penalty"],
            2,
        )
        return values

    def _score_interpretation(self, score: float) -> str:
        if score >= 75:
            return "Interpretation: high-priority review lead due to broad source coverage and entity linkage, still requiring human verification."
        if score >= 50:
            return "Interpretation: reviewable triage lead with meaningful source coverage, but caveats or missing data prevent upgrade without human verification."
        if score >= 25:
            return "Interpretation: limited triage lead; source coverage or entity linkage is thin and repair is likely needed before escalation."
        return "Interpretation: insufficient retrieved support for a review lead from the current corpus."

    def _source_posture(self, item: EvidenceItem) -> str:
        label = self._source_type_label(item.source_type)
        signals = item.signals or {}
        if item.source_type == "irs_990_xml":
            return f"{label}: official Internal Revenue Service machine-readable filing data preserved locally; raw machine-readable filing data controls"
        if item.source_type == "irs_990_summary":
            return f"{label}: summary context; verify against return before ranking"
        if item.source_type == "irs_990_download_manifest":
            return f"{label}: source availability gap, not a substantive finding"
        if item.source_type == "irs_990_full_text_fallback":
            return f"{label}: fallback only until official Internal Revenue Service machine-readable filing data or source document is recovered"
        if item.source_type.startswith("source_extraction_"):
            return f"{label}: deterministic parser output; raw source controls"
        if item.source_type == "state_homelessness_award":
            return f"{label}: official state project-award context; co-applicant exposure is not the same as verified direct receipt"
        if item.source_type in {"fac_audit_pdf", "fac_findings", "fac_federal_awards", "fac_audit_summary"}:
            return f"{label}: audit or award context requiring year-specific review"
        if item.source_type.startswith("dhcs"):
            return f"{label}: facility or source-status context requiring follow-up"
        if item.source_type == "county_contract_or_monitoring":
            return f"{label}: county source context requiring current-status check"
        if signals.get("missing_data"):
            return f"{label}: includes missing-data caveat"
        return f"{label}: source support for reviewer triage"

    def _review_flag(self, item: EvidenceItem) -> str:
        signals = item.signals or {}
        if item.source_type == "irs_990_xml":
            return "Official return data for year-over-year financial review and source verification."
        if item.source_type == "irs_990_summary":
            return "Financial baseline and audit-link context from a public Form 990 summary."
        if item.source_type == "irs_990_download_manifest":
            return "Missing Internal Revenue Service machine-readable filing data coverage for the specified tax period; this flags a data gap only."
        if item.source_type == "irs_990_full_text_fallback":
            return "Fallback return fields available because official XML remains unresolved for this object."
        if item.source_type == "fac_audit_pdf":
            parts = ["Federal Audit Clearinghouse audit record for year-specific review"]
            if signals.get("fac_prior_findings"):
                parts.append("prior-finding agency indicator present")
            if signals.get("fac_low_risk_no"):
                parts.append("auditee not marked low-risk for the audit year")
            if signals.get("fac_federal_awards_present"):
                parts.append("federal award rows available")
            return "; ".join(parts) + "."
        if item.source_type == "fac_findings":
            return "Filtered Federal Audit Clearinghouse findings rows exist for target reports and require row-level interpretation."
        if item.source_type == "fac_federal_awards":
            return "Federal award ledger rows exist for funding-trace review."
        if item.source_type == "dhcs_facility_status":
            return "California Department of Health Care Services facility-level status rows, including any closed statuses, require facility-level follow-up."
        if item.source_type in {"dhcs_adverse_status_manifest", "dhcs_adverse_status_discovery"}:
            return "California Department of Health Care Services adverse-status source discovery remains incomplete or machine-readability is unresolved."
        if item.source_type == "county_contract_or_monitoring":
            return "County monitoring, contract, or ledger document is available for current-status review."
        if item.source_type == "state_homelessness_award":
            return "Official state Homekey or Homekey+ award row names the entity as a project co-applicant or partner; this flags material public-funds exposure and a direct-allocation verification need."
        if item.source_type == "court_docket_manifest":
            return "Court calendar or docket-search pointer requiring direct docket verification."
        if item.source_type == "enforcement_or_docket_source":
            return "Official enforcement or docket record requiring exact legal-status review."
        if item.source_type == "social_media_source":
            return "Public social-media source context requiring timestamped scope and attribution review."
        if item.source_type == "source_extraction_irs_990_table":
            return "Parsed Internal Revenue Service financial table flags year-window coverage and missing return fields."
        if item.source_type == "source_extraction_fac_audit_table":
            return "Parsed Federal Audit Clearinghouse audit-control table flags audit years, report coverage, and control/finding indicators."
        if item.source_type == "source_extraction_fac_award_table":
            return "Parsed Federal Audit Clearinghouse award table flags program and amount concentrations for funding-trace review."
        if item.source_type == "source_extraction_dhcs_status_table":
            return "Parsed California Department of Health Care Services table flags facility counts, active/closed status counts, and counties."
        if item.source_type == "source_extraction_pdf_text_index":
            return "PDF extraction index flags where reviewer navigation aids are available."
        if item.source_type == "source_extraction_state_homeless_award_table":
            return "Parsed state homelessness award table ranks source-listed co-applicant project-award exposure and preserves direct-receipt caveats."
        if item.source_type == "source_extraction_official_outcome_table":
            return "Official outcome-source manifest flags which county or Continuum of Care datasets were ingested or blocked."
        if item.source_type == "source_extraction_spend_vs_results_table":
            return "Spend-versus-results join flags county or Continuum of Care outcome movement next to entity spending and facility footprint."
        if item.source_type == "source_extraction_public_statement_table":
            return "Public-statement source table flags harvested pages and matched review terms."
        if item.source_type == "source_extraction_enforcement_docket_table":
            return "Parsed enforcement and docket table flags official case, violation, prosecution, or legal-status source coverage."
        if item.source_type == "source_extraction_social_web_table":
            return "Parsed social and website table flags account/page coverage and source gaps."
        if item.source_type == "public_statement_source":
            return "Public statement page provides attributable context and off-scope keyword screening."
        if item.source_type == "org_service_page":
            return "Organization service page confirms service scope and operating context."
        return "Source was retrieved as support context for reviewer triage."

    def _reviewer_action(self, item: EvidenceItem) -> str:
        if item.source_type == "irs_990_xml":
            return "Open the local machine-readable filing data or Internal Revenue Service archive member and verify fields before relying on numbers."
        if item.source_type == "irs_990_summary":
            return "Use as orientation only; compare against downloaded XML or original return."
        if item.source_type == "irs_990_download_manifest":
            return "Treat as a source-coverage gap and recheck Internal Revenue Service indexes before escalation."
        if item.source_type == "irs_990_full_text_fallback":
            return "Use only as fallback; replace with official Internal Revenue Service machine-readable filing data or source document when recovered."
        if item.source_type in {"fac_audit_pdf", "fac_findings", "fac_audit_summary"}:
            return "Open the audit source document or row-level Federal Audit Clearinghouse data and verify finding status, year, agency, and response."
        if item.source_type == "fac_federal_awards":
            return "Trace programs and amounts; do not infer performance from award size alone."
        if item.source_type.startswith("dhcs"):
            return "Verify facility-level meaning directly with California Department of Health Care Services source records or an export before entity-level use."
        if item.source_type == "county_contract_or_monitoring":
            return "Check agency response, corrective-action status, and current contract status."
        if item.source_type == "state_homelessness_award":
            return "Verify the HCD award row, standard agreement, eligible applicant, co-applicant role, and any subrecipient or operating-allocation record before treating this as direct entity receipt."
        if item.source_type == "court_docket_manifest":
            return "Confirm the docket directly before treating the pointer as meaningful."
        if item.source_type == "enforcement_or_docket_source":
            return "Open the official source and verify named parties, legal status, dates, case numbers, and whether the nonprofit itself is named before escalation."
        if item.source_type == "social_media_source":
            return "Archive the page and compare claims or activity to grant scope, disclosures, and cost allocation."
        if item.source_type.startswith("source_extraction_"):
            return "Use this table as an index into source material; raw source controls."
        if item.source_type == "public_statement_source":
            return "Use only as attributable public context; do not infer spending allowability from statements alone."
        if item.source_type == "org_service_page":
            return "Use for operational context, not as an oversight signal by itself."
        return "Review the cited source and compare against the lead wording."

    def _active_signal_text(self, item: EvidenceItem) -> str:
        active = sorted(key for key, value in item.signals.items() if value)
        return ", ".join(active) if active else "none"

    def _format_label_list(self, labels: list[str]) -> str:
        if not labels:
            return ""
        chunks = [", ".join(f"`{label}`" for label in labels[index : index + 12]) for index in range(0, len(labels), 12)]
        return "<br>".join(chunks)

    def _table_cell(self, value: object) -> str:
        text = str(value)
        text = text.replace("\r", " ").replace("\n", "<br>")
        text = text.replace("|", "\\|")
        return text

    def _code_text(self, value: str) -> str:
        return value.replace("```", "` ` `").strip()
