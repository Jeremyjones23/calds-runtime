from __future__ import annotations

from collections import Counter
import re
from typing import Iterable

from .contracts import InvestigationProfile, SourceConnectorSpec


class CaliforniaSourceCatalogService:
    """Deterministic source catalog for California public-funds investigations.

    The catalog does not retrieve records. It declares the official or public
    source families each investigation should try before the workflow treats a
    gap as a hard blocker or records-request item.
    """

    def connector_specs_for_profile(self, profile: InvestigationProfile) -> list[SourceConnectorSpec]:
        specs = [
            *self.statewide_connector_specs(),
            *self.local_connector_specs(profile.jurisdiction),
            *self.profile_connector_specs(profile),
        ]
        return self._dedupe_specs(specs)

    def coverage_summary(self, profile: InvestigationProfile) -> dict[str, object]:
        specs = self.connector_specs_for_profile(profile)
        access_modes = Counter(spec.access_mode for spec in specs)
        families = Counter(spec.source_family for spec in specs)
        return {
            "jurisdiction": profile.jurisdiction,
            "connector_count": len(specs),
            "source_families": sorted(families),
            "access_modes": dict(sorted(access_modes.items())),
            "public_http_connector_count": access_modes.get("public_http", 0),
            "manual_or_records_request_connector_count": sum(
                count
                for mode, count in access_modes.items()
                if mode in {"public_or_records_request", "credentialed_or_manual", "manual_records_request"}
            ),
            "credentialed_connector_count": sum(1 for spec in specs if spec.credentials_required),
        }

    def statewide_connector_specs(self) -> list[SourceConnectorSpec]:
        return [
            SourceConnectorSpec(
                "irs_teos_bulk_xml",
                "raw_irs_990",
                "Internal Revenue Service tax-exempt organization search, raw XML, and return images",
                "public_http",
                ["raw Form 990 XML", "return image or rendered filing", "tax-exempt organization search result"],
                [
                    "https://www.irs.gov/charities-non-profits/search-for-tax-exempt-organizations",
                    "https://www.irs.gov/charities-non-profits/exempt-organizations-public-disclosure-obtaining-copies-of-documents-from-irs",
                ],
            ),
            SourceConnectorSpec(
                "propublica_nonprofit_api",
                "raw_irs_990",
                "ProPublica Nonprofit Explorer API summary tied to IRS filings",
                "public_http",
                ["organization filing summary", "filing-year index", "IRS filing pointer"],
                ["https://projects.propublica.org/nonprofits/api"],
            ),
            SourceConnectorSpec(
                "fac_public_api",
                "audit_pdf",
                "Federal Audit Clearinghouse public audit API and reporting packages",
                "public_http",
                ["single audit metadata", "audit finding rows", "federal award rows", "reporting package or audit PDF"],
                ["https://www.fac.gov/api", "https://fac.gov/"],
            ),
            SourceConnectorSpec(
                "ca_ag_charity_registry",
                "state_charity_registry",
                "California Attorney General Registry of Charities and Fundraisers",
                "public_http",
                ["registry status", "public charity filings", "registrant details"],
                ["https://oag.ca.gov/charities"],
            ),
            SourceConnectorSpec(
                "ca_sos_business_search",
                "state_entity_registry",
                "California Secretary of State business search and filing images",
                "public_http",
                ["entity status", "formation record", "statement of information", "agent and address record"],
                [
                    "https://bizfileonline.sos.ca.gov/search/business",
                    "https://www.sos.ca.gov/business-programs/bizfile/search-online",
                ],
            ),
            SourceConnectorSpec(
                "ca_state_auditor_reports",
                "audit_pdf",
                "California State Auditor reports and recommendations",
                "public_http",
                ["audit report", "recommendation status", "finding excerpt"],
                ["https://www.auditor.ca.gov/reports/"],
            ),
            SourceConnectorSpec(
                "ca_grants_portal",
                "state_awards",
                "California Grants Portal opportunities and awardee data",
                "public_http",
                ["grant opportunity", "awardee record", "program purpose"],
                ["https://www.grants.ca.gov/", "https://lab.data.ca.gov/dataset/california-grants-portal"],
            ),
            SourceConnectorSpec(
                "open_fiscal_vendor_payments",
                "payment_ledger",
                "Open FI$Cal state expenditure and vendor transaction reports",
                "public_http",
                ["vendor transaction", "state expenditure row", "department and fund detail"],
                ["https://open.fiscal.ca.gov/"],
            ),
            SourceConnectorSpec(
                "ca_hdis_outcomes",
                "provider_outcomes",
                "California Homeless Data Integration System and system performance measures",
                "public_http",
                ["Continuum of Care performance measure", "statewide homelessness outcome context"],
                ["https://bcsh.ca.gov/calich/hdis.html"],
            ),
            SourceConnectorSpec(
                "ca_dhcs_license_adverse",
                "enforcement_adverse",
                "California Department of Health Care Services license, status, and adverse-action sources",
                "public_http",
                ["license status", "adverse action", "probation, suspension, or revocation record"],
                ["https://www.dhcs.ca.gov/"],
            ),
            SourceConnectorSpec(
                "ca_cal_access_power_search",
                "campaign_finance",
                "California Secretary of State CAL-ACCESS and Power Search campaign/lobbying disclosures",
                "public_http",
                ["committee, contribution, independent expenditure, or lobbying disclosure"],
                ["https://powersearch.sos.ca.gov/", "https://www.sos.ca.gov/campaign-lobbying"],
            ),
            SourceConnectorSpec(
                "ca_fppc_lobbying_guidance",
                "campaign_finance",
                "California Fair Political Practices Commission campaign, lobbying, and ethics sources",
                "public_http",
                ["lobbying guidance", "ethics disclosure context", "enforcement status if cited"],
                ["https://www.fppc.ca.gov/"],
            ),
            SourceConnectorSpec(
                "pacer_case_locator",
                "litigation_docket",
                "Federal PACER case locator and court dockets",
                "credentialed_or_manual",
                ["case docket", "complaint", "settlement", "judgment or charging document"],
                ["https://pacer.uscourts.gov/"],
                True,
                "PACER and some federal court materials may require credentials, fees, or manual retrieval.",
            ),
            SourceConnectorSpec(
                "ca_superior_court_portals",
                "litigation_docket",
                "California superior court case portals",
                "public_or_records_request",
                ["county court docket", "complaint", "settlement", "judgment or charging document"],
                ["https://www.courts.ca.gov/find-my-court.htm"],
                False,
                "California court portals vary by county and may require manual search, fees, or courthouse requests.",
            ),
            SourceConnectorSpec(
                "organization_web_archive",
                "web_social_archive",
                "Organization website, public statement, and web archive capture",
                "public_http",
                ["current service page", "archived page", "public statement excerpt", "social post URL if public"],
                ["https://web.archive.org/"],
            ),
        ]

    def local_connector_specs(self, jurisdiction: str) -> list[SourceConnectorSpec]:
        specs = list(self._generic_county_specs())
        if "san francisco" in self._norm(jurisdiction):
            specs.extend(self._san_francisco_specs())
        return specs

    def profile_connector_specs(self, profile: InvestigationProfile) -> list[SourceConnectorSpec]:
        specs: list[SourceConnectorSpec] = []
        for item in profile.source_connectors:
            specs.append(
                SourceConnectorSpec(
                    connector_id=str(item.get("connector_id") or "profile_connector"),
                    source_family=str(item.get("source_family") or ""),
                    name=str(item.get("name") or item.get("connector_id") or "profile connector"),
                    access_mode=str(item.get("access_mode") or "public_http"),
                    required_artifacts=list(item.get("required_artifacts") or []),
                    source_uris=list(item.get("source_uris") or []),
                    credentials_required=bool(item.get("credentials_required") or False),
                    manual_access_reason=str(item.get("manual_access_reason") or ""),
                    parser_version=str(item.get("parser_version") or "profile-v1"),
                )
            )
        return specs

    def _generic_county_specs(self) -> list[SourceConnectorSpec]:
        return [
            SourceConnectorSpec(
                "county_contract_monitoring_records",
                "county_contracts",
                "County contract, amendment, invoice, monitoring, and corrective-action records",
                "public_or_records_request",
                ["contract", "amendment", "invoice", "monitoring letter", "corrective action"],
                [],
                False,
                "No single California county portal covers all counties; use the relevant county portal or public-records request.",
            ),
            SourceConnectorSpec(
                "county_payment_ledger",
                "payment_ledger",
                "County payment and vendor ledger",
                "public_or_records_request",
                ["payment row", "invoice ledger", "vendor payment export"],
                [],
                False,
                "County payment portals vary and may require a records request for row-level vendor payments.",
            ),
            SourceConnectorSpec(
                "county_board_files",
                "board_files",
                "County board, committee, procurement, and legislative approval files",
                "public_or_records_request",
                ["agenda item", "staff report", "resolution", "contract approval file"],
                [],
                False,
                "County board-file systems vary by county and may require manual or records-request retrieval.",
            ),
            SourceConnectorSpec(
                "county_provider_outcomes",
                "provider_outcomes",
                "County provider deliverable, capacity, and outcome reports",
                "public_or_records_request",
                ["deliverable report", "capacity report", "program outcome report"],
                [],
                False,
                "Provider-attributable outcomes are often not posted publicly and may require county contract-monitoring records.",
            ),
        ]

    def _san_francisco_specs(self) -> list[SourceConnectorSpec]:
        return [
            SourceConnectorSpec(
                "sf_open_data_payments",
                "payment_ledger",
                "San Francisco Open Data nonprofit spending payment rows",
                "public_http",
                ["supplier payment aggregation", "row-level payment export"],
                ["https://data.sfgov.org/resource/qkex-vh98.json"],
            ),
            SourceConnectorSpec(
                "sf_legislative_research_center",
                "board_files",
                "San Francisco Legislative Research Center and board files",
                "public_http",
                ["legislative file", "board or committee agenda item", "resolution or ordinance", "contract approval attachment"],
                ["https://www.sf.gov/legislative-research-center-lrc", "https://sfgov.legistar.com/Legislation.aspx"],
            ),
            SourceConnectorSpec(
                "sf_ethics_lobbying_data",
                "campaign_finance",
                "San Francisco Ethics Commission lobbying disclosure data",
                "public_http",
                ["lobbyist client record", "contacts", "payments", "subject matter disclosure"],
                ["https://sfethics.org/disclosures/lobbyist-disclosure/lobbyist-disclosure-data"],
            ),
            SourceConnectorSpec(
                "sf_controller_reports",
                "audit_pdf",
                "San Francisco Controller audits, performance reports, and recommendations",
                "public_http",
                ["controller report", "audit finding", "recommendation status"],
                ["https://www.sf.gov/departments/city-administrator/office-controller"],
            ),
            SourceConnectorSpec(
                "sf_hsh_data_hub",
                "provider_outcomes",
                "San Francisco homelessness and supportive housing data and archived reports",
                "public_http",
                ["HSH report", "capacity measure", "system outcome context"],
                ["https://hsh.archive.sf.gov/"],
            ),
            SourceConnectorSpec(
                "sf_hsh_contract_monitoring",
                "county_contracts",
                "San Francisco HSH contract, monitoring, and corrective-action files",
                "public_or_records_request",
                ["contract", "amendment", "invoice", "monitoring letter", "corrective action"],
                ["https://www.sf.gov/departments/homelessness-and-supportive-housing"],
                False,
                "Some San Francisco HSH contract-monitoring files may require targeted public-records requests.",
            ),
        ]

    def _dedupe_specs(self, specs: Iterable[SourceConnectorSpec]) -> list[SourceConnectorSpec]:
        seen: dict[str, SourceConnectorSpec] = {}
        for spec in specs:
            if not spec.connector_id:
                continue
            existing = seen.get(spec.connector_id)
            if existing is None:
                seen[spec.connector_id] = spec
                continue
            seen[spec.connector_id] = SourceConnectorSpec(
                connector_id=existing.connector_id,
                source_family=existing.source_family or spec.source_family,
                name=existing.name or spec.name,
                access_mode=existing.access_mode or spec.access_mode,
                required_artifacts=self._dedupe([*existing.required_artifacts, *spec.required_artifacts]),
                source_uris=self._dedupe([*existing.source_uris, *spec.source_uris]),
                credentials_required=existing.credentials_required or spec.credentials_required,
                manual_access_reason=existing.manual_access_reason or spec.manual_access_reason,
                parser_version=existing.parser_version,
            )
        return list(seen.values())

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                output.append(value)
        return output

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
