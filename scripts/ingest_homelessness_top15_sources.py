from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import ssl
import struct
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "live_ca_homelessness_top15_2026_04_29"
COLLECTED_AT = "2026-04-29T00:00:00+00:00"
DEFAULT_ARTIFACT_BASE_DIR = PROJECT_ROOT / "artifacts" / "homelessness_top15_sources_2026_04_29"
ARTIFACT_BASE_DIR = DEFAULT_ARTIFACT_BASE_DIR
RAW_DIR = ARTIFACT_BASE_DIR / "raw"
OUTCOME_DIR = ARTIFACT_BASE_DIR / "outcomes"
WEB_DIR = ARTIFACT_BASE_DIR / "web"
PROPUBLICA_DIR = ARTIFACT_BASE_DIR / "propublica"
IRS_RAW_DIR = ARTIFACT_BASE_DIR / "irs_raw"
FAC_DIR = ARTIFACT_BASE_DIR / "fac"
CONTRACT_DIR = ARTIFACT_BASE_DIR / "contracts"
DOCKET_DIR = ARTIFACT_BASE_DIR / "enforcement_dockets"
DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "live_corpus" / f"{CASE_ID}_stage1"
ACTIVE_PROFILE = "statewide_homekey"
ACTIVE_TARGET_LIMIT = 15

HCD_ROUND3_URL = "https://www.hcd.ca.gov/sites/default/files/docs/grants-and-funding/homekey/homekey-round-3-awardee-list.pdf"
HCD_PLUS_URL = "https://www.hcd.ca.gov/sites/default/files/docs/grants-and-funding/homekey/hk-plus-awardee-list.pdf"
HCD_ROUND3_ELIGIBILITY_URL = "https://www.hcd.ca.gov/grants-and-funding/homekey/eligibility"
HCD_PLUS_ELIGIBILITY_URL = "https://www.hcd.ca.gov/grants-and-funding/homekey-plus/timeline-and-eligibility"
HCD_HOMEKEY_FUNDING_URL = "https://www.hcd.ca.gov/funding/homekey/funding-overview"
CA_SPM_SOURCE_URL = "https://lab.data.ca.gov/dataset/ca-system-performance-measures-statewide-and-by-coc"
CA_SPM_RESOURCE_ID = "e02178d9-1d34-4798-9979-f50af9f1742e"
CA_SPM_API = "https://data.ca.gov/api/3/action/datastore_search"
HDIS_URL = "https://bcsh.ca.gov/calich/hdis.html"
FHFA_OIG_HOMELESSNESS_FUNDS_PRESS_RELEASE_URL = "https://www.fhfaoig.gov/sites/default/files/Beverly-Hills-Man-Arrested%2C-Brentwood-Man-Charged-in-Separate-Criminal-Cases-Linked-to-Fraud-in-Public-Homelessness-Funds.pdf"
LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL = "https://cityclerk.lacity.org/onlinedocs/2021/21-0112-S3_misc_6-16-23.pdf"
LA_CITY_SHELBY_2026_OPERATIONS_URL = "https://cityclerk.lacity.org/onlinedocs/2023/23-1022-s27_rpt_cao_2-10-26.pdf"
PROPUBLICA_API_BASE = "https://projects.propublica.org/nonprofits/api/v2"
PROPUBLICA_API_DOC_URL = "https://projects.propublica.org/nonprofits/api/"
PROPUBLICA_EXPLORER_BASE = "https://projects.propublica.org/nonprofits/organizations"
IRS_FORM_990_DOWNLOADS_URL = "https://www.irs.gov/charities-non-profits/form-990-series-downloads"
IRS_TEOS_BULK_URL = "https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads"
FAC_DATA_URL = "https://www.fac.gov/data/"
FAC_API_URL = "https://www.fac.gov/api"
FAC_DOWNLOAD_CURRENT_URL = "https://www.fac.gov/data/download/current/"
FAC_GENERAL_CSV_URL = "https://app.fac.gov/dissemination/public-data/gsa/full/general.csv"
FAC_AWARDS_CSV_URL = "https://app.fac.gov/dissemination/public-data/gsa/full/federal_awards.csv"
FAC_FINDINGS_CSV_URL = "https://app.fac.gov/dissemination/public-data/gsa/full/findings.csv"
FAC_FINDINGS_TEXT_CSV_URL = "https://app.fac.gov/dissemination/public-data/gsa/full/findings_text.csv"
FAC_CORRECTIVE_ACTION_CSV_URL = "https://app.fac.gov/dissemination/public-data/gsa/full/corrective_action_plans.csv"
LA_CITY_CLERK_BASE_URL = "https://cityclerk.lacity.org/"
US_DOJ_BASE_URL = "https://www.justice.gov/"
US_DOJ_SEARCH_URL = "https://search.justice.gov/search"
US_COURTS_PACER_URL = "https://pcl.uscourts.gov/pcl/index.jsf"
CA_COURTS_URL = "https://www.courts.ca.gov/"
PACER_FIND_CASE_URL = "https://pacer.uscourts.gov/find-case"
CA_COURTS_LOOKUP_GUIDE_URL = "https://selfhelp.courts.ca.gov/court-basics/look-up-case"
CA_DOJ_CHARITY_REGISTRY_URL = "https://rct.doj.ca.gov/"
FHFA_OIG_SEARCH_URL = "https://www.fhfaoig.gov/search"
LA_SUPERIOR_COURT_CASE_ACCESS_URL = "https://www.lacourt.org/casesummary/ui/"
ALAMEDA_SUPERIOR_COURT_DOMAIN_URL = "https://www.alameda.courts.ca.gov/"
SAN_BERNARDINO_SUPERIOR_COURT_DOMAIN_URL = "https://www.sb-court.org/"
VENTURA_SUPERIOR_COURT_DOMAIN_URL = "https://www.ventura.courts.ca.gov/"
SACRAMENTO_SUPERIOR_COURT_DOMAIN_URL = "https://www.saccourt.ca.gov/"
OAKLAND_HOMEKEY_R2H2_URL = "https://www.oaklandca.gov/Business/For-Developers%E2%80%8B/City-Homekey-Rapid-Response-Homeless-Housing-R2H2-Program"
OAKLAND_DIGNITY_VILLAGE_URL = "https://www.oaklandca.gov/News-Releases/HCD/Oakland-awarded-14.3-million-in-Homekey-funds-to-create-40-new-permanent-supportive-housing-units"
OAKLAND_QUALITY_INN_URL = "https://www.oaklandca.gov/News-Releases/HCD/Oakland-awarded-20.4-million-in-Homekey-Round-3-funds-for-the-Quality-Inn"
LA_HOMEKEY_PLUS_SAFE_HARBOR_REPORT_URL = "https://cityclerk.lacity.org/onlinedocs/2025/25-0269_rpt_hci_3-6-25.pdf"
LA_HOMEKEY_PLUS_SAFE_HARBOR_I_RESOLUTION_URL = "https://cityclerk.lacity.org/onlinedocs/2025/25-0269_misc_05-28-25.pdf"
LA_HOMEKEY_PLUS_SAFE_HARBOR_II_RESOLUTION_URL = "https://cityclerk.lacity.org/onlinedocs/2025/25-0269_misc_07-22-25.pdf"
SF_NONPROFIT_SPENDING_DATASET_URL = "https://catalog.data.gov/dataset/citywide-nonprofit-spending"
SF_NONPROFIT_SPENDING_API = "https://data.sfgov.org/resource/qkex-vh98.json"
SF_NONPROFIT_SPENDING_COLUMNS_URL = "https://data.sfgov.org/api/views/qkex-vh98/columns.json"
SF_NONPROFIT_SPENDING_DASHBOARD_URL = "https://www.sf.gov/data/san-francisco-nonprofit-contracts-and-spending"
SF_HOMELESSNESS_DATA_URL = "https://www.sf.gov/resource/2024/homelessness-response-system-data"
SF_HOMELESSNESS_OVERSIGHT_PDF_URL = "https://sfbos.org/sites/default/files/Policy_Analysis.GF_Vacancies.Contract_Oversight.Dept_Restructures.Final_.01.13.25.pdf"
SF_HOMERISE_AUDIT_PRESS_URL = "https://www.sf.gov/news--audit-finds-one-citys-providers-housing-unhoused-residents-had-serious-financial-shortfalls"
SF_HOMERISE_AUDIT_PDF_URL = "https://www.sf.gov/sites/default/files/2024-04/HSH-MOHCD%20HomeRise%20Audit%20Report%2004.02.24.pdf"
SF_UCHS_VIOLATION_PRESS_URL = "https://www.sf.gov/news--united-council-human-services-found-be-violation-city-agreements"
SF_DA_UCHS_CHARGES_URL = "https://sfdistrictattorney.org/former-nonprofit-ceo-charged-with-stealing-and-misappropriating-public-funds/"
SF_SUSPENDED_DEBARRED_URL = "https://www.sf.gov/resource--2022--suspended-and-debarred-contractors"

HOMELESSNESS_SCOPE_HIGH_TERMS = [
    "voter registration",
    "get out the vote",
    "voter engagement",
    "citizenship",
    "naturalization",
    "immigration legal services",
    "ice enforcement",
    "block ice",
    "deportation defense",
    "immigration enforcement",
    "power building",
    "political action",
    "campaign contribution",
    "ballot measure",
    "electioneering",
]

HOMELESSNESS_SCOPE_MEDIUM_TERMS = [
    "policy advocacy",
    "community organizing",
    "lobbying",
    "lobbyist",
    "public affairs",
    "know your rights",
    "asylum",
    "refugee resettlement",
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return normalize_space(" ".join(self.parts))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def money(value: float) -> str:
    return "$" + f"{value:,.0f}"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def configure_artifact_dirs(base_dir: Path) -> Path:
    """Point source acquisition artifacts at a run-scoped directory."""

    global ARTIFACT_BASE_DIR, RAW_DIR, OUTCOME_DIR, WEB_DIR, PROPUBLICA_DIR, IRS_RAW_DIR, FAC_DIR, CONTRACT_DIR, DOCKET_DIR
    ARTIFACT_BASE_DIR = Path(base_dir)
    RAW_DIR = ARTIFACT_BASE_DIR / "raw"
    OUTCOME_DIR = ARTIFACT_BASE_DIR / "outcomes"
    WEB_DIR = ARTIFACT_BASE_DIR / "web"
    PROPUBLICA_DIR = ARTIFACT_BASE_DIR / "propublica"
    IRS_RAW_DIR = ARTIFACT_BASE_DIR / "irs_raw"
    FAC_DIR = ARTIFACT_BASE_DIR / "fac"
    CONTRACT_DIR = ARTIFACT_BASE_DIR / "contracts"
    DOCKET_DIR = ARTIFACT_BASE_DIR / "enforcement_dockets"
    return ARTIFACT_BASE_DIR


def reset_run_scoped_artifact_dir(corpus_dir: Path, artifacts_dir: Path) -> None:
    resolved_corpus = corpus_dir.resolve()
    resolved_artifacts = artifacts_dir.resolve()
    if resolved_artifacts == resolved_corpus or resolved_artifacts == PROJECT_ROOT.resolve():
        raise ValueError(f"refusing to clear unsafe artifacts directory: {resolved_artifacts}")
    if resolved_artifacts.parent == resolved_corpus and resolved_artifacts.name == "_source_artifacts":
        shutil.rmtree(resolved_artifacts, ignore_errors=True)


def fetch_bytes(url: str, timeout: int = 60, attempts: int = 3) -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "text/html,application/pdf,application/json,text/plain,*/*",
        },
    )
    context = ssl.create_default_context()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return response.read(), response.geturl(), response.headers.get("content-type", "")
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    assert last_error is not None
    raise last_error


def fetch_json_url(url: str, timeout: int = 60) -> tuple[Any, str, str]:
    raw, final_url, content_type = fetch_bytes(url, timeout=timeout)
    return json.loads(raw.decode("utf-8", "replace")), final_url, content_type


def html_to_text(raw: bytes) -> str:
    parser = TextExtractor()
    parser.feed(raw.decode("utf-8", "replace"))
    return repair_mojibake(parser.text())


def repair_mojibake(text: str) -> str:
    replacements = {
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€\u009d": '"',
        "â€“": "-",
        "â€”": "-",
        "â€¢": "-",
        "Â ": " ",
    }
    repaired = text
    for bad, good in replacements.items():
        repaired = repaired.replace(bad, good)
    return repaired


def snippet(text: str, terms: list[str], radius: int = 260) -> str:
    lowered = text.lower()
    for term in terms:
        index = lowered.find(term.lower())
        if index >= 0:
            start = max(0, index - radius)
            end = min(len(text), index + len(term) + radius)
            return ("..." if start else "") + text[start:end].strip() + ("..." if end < len(text) else "")
    return text[: radius * 2].strip()


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def compact_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def first_number(*values: Any) -> float | None:
    for value in values:
        number_value = number(value)
        if number_value is not None:
            return number_value
    return None


def sum_numbers(*values: Any) -> float | None:
    numbers = [number(value) for value in values]
    present = [value for value in numbers if value is not None]
    if not present:
        return None
    return float(sum(present))


def build_record(
    record_id: str,
    title: str,
    source_uri: str,
    source_type: str,
    published_at: str,
    entities: list[str],
    body: str,
    signals: dict[str, Any],
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attrs = dict(attributes or {})
    attrs["signals"] = signals
    return {
        "record_id": record_id,
        "title": title,
        "source_uri": source_uri,
        "source_type": source_type,
        "published_at": published_at,
        "collected_at": COLLECTED_AT,
        "entities": entities,
        "attributes": attrs,
        "body": body,
    }


SF_ENTITY_METADATA: dict[str, dict[str, Any]] = {
    "Tenderloin Housing Clinic Inc": {"aliases": ["Tenderloin Housing Clinic", "THC"], "service_urls": ["https://www.thclinic.org/en/what-we-do/"], "statement_urls": ["https://www.thclinic.org/"]},
    "Episcopal Community Svcs of SF Inc": {"aliases": ["Episcopal Community Services of San Francisco", "ECS"], "service_urls": ["https://ecs-sf.org/programs/"], "statement_urls": ["https://ecs-sf.org/"]},
    "Five Keys Schools And Programs": {"aliases": ["Five Keys Schools and Programs", "Five Keys"], "service_urls": ["https://www.fivekeys.org/programs"], "statement_urls": ["https://www.fivekeys.org/"]},
    "St Vincent De Paul Society of SF": {"aliases": ["St. Vincent de Paul Society of San Francisco", "Society Of St Vincent De Paul District Council Of San Francisco", "SVDP-SF"], "service_urls": ["https://svdp-sf.org/what-we-do/"], "statement_urls": ["https://svdp-sf.org/"]},
    "Larkin Street Youth Services": {"aliases": ["Larkin Street"], "service_urls": ["https://larkinstreetyouth.org/how-we-help/"], "statement_urls": ["https://larkinstreetyouth.org/"]},
    "Heluna Health": {"aliases": ["Heluna", "Public Health Foundation Enterprises", "Public Health Foundation Enterprises Inc"], "service_urls": ["https://www.helunahealth.org/our-work/"], "statement_urls": ["https://www.helunahealth.org/"]},
    "Tides Center": {"aliases": ["Tides"], "service_urls": ["https://www.tides.org/services/fiscal-sponsorship/"], "statement_urls": ["https://www.tides.org/"]},
    "Compass Family Services": {"aliases": ["Compass Families", "Compass SF"], "service_urls": ["https://www.compass-sf.org/our-programs"], "statement_urls": ["https://www.compass-sf.org/"]},
    "Catholic Charities": {"aliases": ["Catholic Charities San Francisco"], "service_urls": ["https://www.catholiccharitiessf.org/what-we-do/homelessness-housing/"], "statement_urls": ["https://www.catholiccharitiessf.org/"]},
    "Brilliant Corners": {"aliases": [], "service_urls": ["https://brilliantcorners.org/what-we-do/"], "statement_urls": ["https://brilliantcorners.org/"]},
    "Community Housing Partnership": {"aliases": ["HomeRise", "Community Housing Partnership Corporation"], "service_urls": ["https://homerisesf.org/what-we-do/"], "statement_urls": ["https://homerisesf.org/"]},
    "Tenderloin Neighborhood Development Corp": {"aliases": ["Tenderloin Neighborhood Development Corporation", "TNDC"], "service_urls": ["https://www.tndc.org/our-work/"], "statement_urls": ["https://www.tndc.org/"]},
    "Hamilton Families": {"aliases": ["Hamilton Family Center"], "service_urls": ["https://hamiltonfamilies.org/programs"], "statement_urls": ["https://hamiltonfamilies.org/"]},
    "Urban Alchemy": {"aliases": [], "service_urls": ["https://urban-alchemy.us/services/"], "statement_urls": ["https://urban-alchemy.us/"]},
    "Bayview Hunters Pt Fndtn For Comm Improv": {"aliases": ["Bayview Hunters Point Foundation", "Bayview Hunters Point Foundation for Community Improvement"], "service_urls": ["https://bayviewci.org/"], "statement_urls": ["https://bayviewci.org/"]},
    "Abode Services": {"aliases": ["Abode"], "service_urls": ["https://abodeservices.org/how-we-help/"], "statement_urls": ["https://abodeservices.org/"]},
    "Conard House Inc": {"aliases": ["Conard House"], "service_urls": ["https://conardhouse.org/programs/"], "statement_urls": ["https://conardhouse.org/"]},
    "Providence Foundation of San Francisco": {"aliases": ["Providence Foundation"], "service_urls": [SF_SUSPENDED_DEBARRED_URL], "statement_urls": [SF_SUSPENDED_DEBARRED_URL]},
    "Homeless Prenatal Program": {"aliases": ["HPP"], "service_urls": ["https://homelessprenatal.org/what-we-do/"], "statement_urls": ["https://homelessprenatal.org/"]},
    "Felton Institute": {"aliases": ["Felton"], "service_urls": ["https://felton.org/social-services/"], "statement_urls": ["https://felton.org/"]},
    "United Council of Human Services": {"aliases": ["UCHS", "United Council for Human Services"], "service_urls": [SF_UCHS_VIOLATION_PRESS_URL], "statement_urls": [SF_DA_UCHS_CHARGES_URL]},
}


SF_ADVERSE_ENTITY_BOOSTS = {
    "United Council of Human Services": 125_000_000,
    "Community Housing Partnership": 110_000_000,
    "Providence Foundation of San Francisco": 100_000_000,
}

SF_PROPUBLICA_EIN_OVERRIDES = {
    "Heluna Health": "952557063",
    "St Vincent De Paul Society of SF": "994698655",
}


TARGETS: list[dict[str, Any]] = [
    {
        "rank": 1,
        "name": "Hope the Mission",
        "slug": "hope_the_mission",
        "aliases": ["Hope The Mission", "Hope of the Valley Rescue Mission"],
        "service_urls": ["https://hopethemission.org/our-programs/"],
        "statement_urls": ["https://hopethemission.org/"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2023-11-01", "eligible_applicant": "County of Los Angeles", "project": "Sierra Highway PSH Portfolio", "city": "Lancaster", "county": "Los Angeles", "amount": 19789357, "units": 60, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 44-45"},
            {"program": "Homekey Round 3", "award_date": "2023-11-01", "eligible_applicant": "City of Los Angeles", "project": "Motel 6 North Hills", "city": "North Hills", "county": "Los Angeles", "amount": 32068000, "units": 111, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 74-75"},
            {"program": "Homekey Round 3", "award_date": "2023-11-21", "eligible_applicant": "County of Los Angeles", "project": "Knight's Inn Palmdale", "city": "Palmdale", "county": "Los Angeles", "amount": 28662113, "units": 100, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 96-97"},
            {"program": "Homekey Round 3", "award_date": "2023-11-22", "eligible_applicant": "County of Los Angeles", "project": "Lancaster Pathway Home", "city": "Lancaster", "county": "Los Angeles", "amount": 27659747, "units": 102, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 103-105"},
            {"program": "Homekey Round 3", "award_date": "2024-02-06", "eligible_applicant": "City of Los Angeles", "project": "Oak Tree Inn", "city": "Los Angeles", "county": "Los Angeles", "amount": 7158774, "units": 22, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 176-177"},
        ],
    },
    {
        "rank": 2,
        "name": "Weingart Center Association",
        "slug": "weingart_center",
        "aliases": ["Weingart Center"],
        "service_urls": ["https://www.weingart.org/programs"],
        "statement_urls": ["https://www.weingart.org/", "https://www.weingart.org/history"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2023-09-26", "eligible_applicant": "County of Los Angeles", "project": "The Weingart Sycamore", "city": "Baldwin Park", "county": "Los Angeles", "amount": 34629600, "units": 109, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 31-33"},
            {"program": "Homekey Round 3", "award_date": "2023-11-21", "eligible_applicant": "County of Los Angeles", "project": "The Weingart Primrose", "city": "Carson", "county": "Los Angeles", "amount": 34356700, "units": 107, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 90-95"},
            {"program": "Homekey Round 3", "award_date": "2023-11-21", "eligible_applicant": "City of Los Angeles", "project": "The Weingart Shelby", "city": "Los Angeles", "county": "Los Angeles", "amount": 26579000, "units": 78, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 132-137"},
        ],
    },
    {
        "rank": 3,
        "name": "DignityMoves",
        "slug": "dignitymoves",
        "aliases": ["Dignity Moves"],
        "service_urls": ["https://dignitymoves.org/interim-supportive-housing/"],
        "statement_urls": ["https://dignitymoves.org/"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2023-12-19", "eligible_applicant": "City of San Bernardino", "project": "San Bernardino Community Wellness Campus", "city": "San Bernardino", "county": "San Bernardino", "amount": 34944702, "units": 140, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 140-148"},
            {"program": "Homekey Round 3", "award_date": "2024-02-06", "eligible_applicant": "City of Oakland", "project": "Dignity Village", "city": "Oakland", "county": "Alameda", "amount": 14266000, "units": 41, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 178-179"},
            {"program": "Homekey+", "award_date": "2025-07-15", "eligible_applicant": "County of Ventura", "project": "Homekey+ Lewis Road", "city": "Camarillo", "county": "Ventura", "amount": 27970000, "units": 89, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 line 36"},
        ],
    },
    {
        "rank": 4,
        "name": "The People Concern",
        "slug": "the_people_concern",
        "aliases": ["People Concern"],
        "service_urls": ["https://www.thepeopleconcern.org/homeless-services/"],
        "statement_urls": ["https://www.thepeopleconcern.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-05-20", "eligible_applicant": "City of Los Angeles", "project": "Safe Harbor I", "city": "Wilmington", "county": "Los Angeles", "amount": 14935650, "units": 34, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 19-23"},
            {"program": "Homekey+", "award_date": "2026-02-13", "eligible_applicant": "County of Los Angeles", "project": "St.Vincent Supportive Community", "city": "Los Angeles", "county": "Los Angeles", "amount": 38500000, "units": 98, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 2 lines 181-187"},
        ],
    },
    {
        "rank": 5,
        "name": "California Supportive Housing",
        "slug": "california_supportive_housing",
        "aliases": ["CSH Enterprise Housing", "CSH Elsie Housing"],
        "service_urls": ["https://www.cshousing.org/"],
        "statement_urls": ["https://www.cshousing.org/"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2023-12-19", "eligible_applicant": "City of Oakland", "project": "CSH Enterprise Housing", "city": "Oakland", "county": "Alameda", "amount": 20368264, "units": 104, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 156-157"},
            {"program": "Homekey+", "award_date": "2025-12-16", "eligible_applicant": "Housing Authority of the County of Sacramento", "project": "CSH Elsie Housing", "city": "Sacramento", "county": "Sacramento", "amount": 31523590, "units": 60, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 2 lines 151-154"},
        ],
    },
    {
        "rank": 6,
        "name": "Self-Help Enterprises",
        "slug": "self_help_enterprises",
        "aliases": ["SHE"],
        "service_urls": ["https://www.selfhelpenterprises.org/", "https://www.selfhelpenterprises.org/about-us/"],
        "statement_urls": ["https://www.selfhelpenterprises.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-09-19", "eligible_applicant": "City of Visalia", "project": "Crescent Meadows", "city": "Visalia", "county": "Tulare", "amount": 11970000, "units": 25, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 82-83"},
            {"program": "Homekey+", "award_date": "2025-09-19", "eligible_applicant": "City of Fresno", "project": "La Hacienda Estates", "city": "Fresno", "county": "Fresno", "amount": 4966896, "units": 18, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 84-85"},
            {"program": "Homekey+", "award_date": "2025-11-13", "eligible_applicant": "City of Merced", "project": "Mercy Village", "city": "Merced", "county": "Merced", "amount": 28257013, "units": 66, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 2 lines 144-146"},
        ],
    },
    {
        "rank": 7,
        "name": "PATH Ventures",
        "slug": "path_ventures",
        "aliases": ["Path Ventures", "PATH"],
        "service_urls": ["https://epath.org/path-ventures/"],
        "statement_urls": ["https://epath.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-10-13", "eligible_applicant": "Los Angeles County Development Authority", "project": "Path Villas East LA", "city": "Los Angeles", "county": "Los Angeles", "amount": 27000000, "units": 60, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 96-97"},
            {"program": "Homekey+", "award_date": "2026-02-13", "eligible_applicant": "County of Los Angeles", "project": "PATH Villas South Park", "city": "Los Angeles", "county": "Los Angeles", "amount": 15672927, "units": 52, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 2 lines 171-172"},
        ],
    },
    {
        "rank": 8,
        "name": "Abode Housing Development",
        "slug": "abode_housing_development",
        "aliases": ["Abode"],
        "service_urls": ["https://abode.org/housing-development", "https://abode.org/services"],
        "statement_urls": ["https://abode.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-07-15", "eligible_applicant": "County of Santa Clara", "project": "Algarve Community Apartments", "city": "San Jose", "county": "Santa Clara", "amount": 41220000, "units": 91, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 30-35"},
        ],
    },
    {
        "rank": 9,
        "name": "TLCS, Inc.",
        "slug": "tlcs_inc",
        "aliases": ["TLCS", "Hope Cooperative"],
        "service_urls": ["https://hopecoop.org/"],
        "statement_urls": ["https://hopecoop.org/"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2023-09-26", "eligible_applicant": "Housing Authority of the City of Sacramento", "project": "Arden Star Hotel Homekey Conversion", "city": "Unincorporated Sacramento County", "county": "Sacramento", "amount": 20000000, "units": 124, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 16-23"},
            {"program": "Homekey Round 3", "award_date": "2023-09-26", "eligible_applicant": "Housing Authority of the City of Sacramento", "project": "Rodeway Inn Homekey Conversion", "city": "Sacramento", "county": "Sacramento", "amount": 20386000, "units": 70, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 1 lines 24-25"},
        ],
    },
    {
        "rank": 10,
        "name": "Swords to Plowshares",
        "slug": "swords_to_plowshares",
        "aliases": ["Swords"],
        "service_urls": ["https://www.swords-to-plowshares.org/"],
        "statement_urls": ["https://www.swords-to-plowshares.org/about/vision-for-impact/care/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-09-19", "eligible_applicant": "City and County of San Francisco", "project": "1034 Van Ness", "city": "San Francisco", "county": "San Francisco", "amount": 39044030, "units": 124, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 76-79"},
        ],
    },
    {
        "rank": 11,
        "name": "Community Revitalization and Development Corporation",
        "slug": "community_revitalization_development",
        "aliases": ["CRDC"],
        "service_urls": ["https://crdc.org/"],
        "statement_urls": ["https://crdc.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-09-19", "eligible_applicant": "City of Fairfield", "project": "Vista Ridge", "city": "Fairfield", "county": "Solano", "amount": 21535540, "units": 51, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 70-75"},
            {"program": "Homekey+", "award_date": "2025-10-13", "eligible_applicant": "County of Amador", "project": "Valley View Commons", "city": "Sutter Creek", "county": "Amador", "amount": 14999956, "units": 36, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 98-103"},
        ],
    },
    {
        "rank": 12,
        "name": "Burbank Housing Development Corporation",
        "slug": "burbank_housing_development",
        "aliases": ["Burbank Housing"],
        "service_urls": ["https://burbankhousing.org/our-story/"],
        "statement_urls": ["https://burbankhousing.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2025-08-14", "eligible_applicant": "City of Napa", "project": "4th and Division Apartments", "city": "Napa", "county": "Napa", "amount": 7627399, "units": 24, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 42-45"},
            {"program": "Homekey+", "award_date": "2025-09-19", "eligible_applicant": "City of Rohnert Park", "project": "6500 Redwood Drive", "city": "Rohnert Park", "county": "Sonoma", "amount": 28758453, "units": 71, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 68-69"},
        ],
    },
    {
        "rank": 13,
        "name": "Service First Northern California",
        "slug": "service_first_northern_california",
        "aliases": ["Service First of Northern California", "Service First NC"],
        "service_urls": ["https://servicefirstnc.org/"],
        "statement_urls": ["https://servicefirstnc.org/"],
        "awards": [
            {"program": "Homekey+", "award_date": "2026-01-27", "eligible_applicant": "City of Stockton", "project": "The Hunter House", "city": "Stockton", "county": "San Joaquin", "amount": 35579520, "units": 78, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 2 lines 162-163"},
        ],
    },
    {
        "rank": 14,
        "name": "Habitat for Humanity Yuba/Sutter, Inc.",
        "slug": "habitat_yuba_sutter",
        "aliases": ["Habitat for Humanity Yuba/Sutter", "Habitat for Humanity Yuba-Sutter", "Habitat For Humanity International Inc Yuba Sutter"],
        "service_urls": ["https://www.habitatca.org/affiliate/habitat-for-humanity-yubasutter/", "https://yuba-sutterhabitat.org/"],
        "statement_urls": ["https://www.habitatca.org/affiliate/habitat-for-humanity-yubasutter/"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2024-02-13", "eligible_applicant": "City of Yuba City", "project": "Merriment Village Apartments", "city": "Yuba City", "county": "Sutter", "amount": 24632331, "units": 80, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 180-183"},
            {"program": "Homekey+", "award_date": "2025-08-14", "eligible_applicant": "County of Glenn", "project": "Purpose Place Apartments Phase III", "city": "Orland", "county": "Glenn", "amount": 5228847, "units": 18, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 1 lines 46-49"},
            {"program": "Homekey+", "award_date": "2026-02-13", "eligible_applicant": "County of Yuba", "project": "Innovation Housing Estates", "city": "Olivehurst", "county": "Yuba", "amount": 5225218, "units": 17, "source_url": HCD_PLUS_URL, "source_note": "Homekey+ PDF page 2 lines 188-191"},
        ],
    },
    {
        "rank": 15,
        "name": "Lutheran Social Services of Southern California",
        "slug": "lutheran_social_services_socal",
        "aliases": ["LSSSC"],
        "service_urls": ["https://www.lsssc.org/sbd-main", "https://www.lsssc.org/"],
        "statement_urls": ["https://www.lsssc.org/articles/get-out-there-n9t2h-wk9tc-mfxze"],
        "awards": [
            {"program": "Homekey Round 3", "award_date": "2023-12-19", "eligible_applicant": "City of San Bernardino", "project": "San Bernardino Community Wellness Campus", "city": "San Bernardino", "county": "San Bernardino", "amount": 34944702, "units": 140, "source_url": HCD_ROUND3_URL, "source_note": "Round 3 PDF page 2 lines 140-148"},
        ],
    },
]


COUNTY_COC_HINTS = {
    "Alameda": ["Alameda", "Oakland"],
    "Amador": ["Amador"],
    "Fresno": ["Fresno"],
    "Glenn": ["Glenn"],
    "Los Angeles": ["Los Angeles City & County", "Los Angeles County"],
    "Merced": ["Merced"],
    "Napa": ["Napa"],
    "Sacramento": ["Sacramento"],
    "San Bernardino": ["San Bernardino"],
    "San Francisco": ["San Francisco"],
    "San Joaquin": ["San Joaquin", "Stockton"],
    "Santa Clara": ["Santa Clara", "San Jose"],
    "Solano": ["Solano", "Vallejo"],
    "Sonoma": ["Sonoma", "Santa Rosa"],
    "Sutter": ["Sutter", "Yuba City"],
    "Tulare": ["Tulare", "Visalia"],
    "Ventura": ["Ventura", "Oxnard"],
    "Yuba": ["Sutter", "Yuba City"],
}


def award_total(target: dict[str, Any]) -> float:
    return float(sum(float(item["amount"]) for item in target["awards"]))


def award_summary_rows() -> list[dict[str, Any]]:
    rows = []
    for target in TARGETS:
        awards = target["awards"]
        rows.append(
            {
                "rank": target["rank"],
                "entity": target["name"],
                "total_award_exposure": award_total(target),
                "project_count": len(awards),
                "programs": sorted({item["program"] for item in awards}),
                "award_years": sorted({str(item["award_date"])[:4] for item in awards}),
                "counties": sorted({item["county"] for item in awards}),
                "cities": sorted({item["city"] for item in awards}),
                "projects": [item["project"] for item in awards],
                "source_urls": sorted({item["source_url"] for item in awards}),
                "caveat": "Full project-award amount is assigned to each source-listed co-applicant for exposure ranking; allocation among co-applicants is not stated in HCD award lists.",
            }
        )
    return rows


def sf_hsh_payment_rows(limit: int = 80) -> list[dict[str, Any]]:
    query = {
        "$select": "supplier_name,sum(completed_payments)",
        "$where": "department='Homelessness and Supportive Housing' AND completed_payments IS NOT NULL",
        "$group": "supplier_name",
        "$order": "sum_completed_payments DESC",
        "$limit": str(limit),
    }
    url = SF_NONPROFIT_SPENDING_API + "?" + urllib.parse.urlencode(query)
    payload, final_url, content_type = fetch_json_url(url, timeout=90)
    rows = payload if isinstance(payload, list) else list(payload.get("rows", []))
    table = {
        "created_at": now(),
        "source_url": SF_NONPROFIT_SPENDING_DATASET_URL,
        "api_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "rows": rows,
        "methodology": "Aggregate San Francisco Open Data nonprofit payment rows for the Department of Homelessness and Supportive Housing by supplier name.",
    }
    write_json(RAW_DIR / "sf_hsh_payment_target_rows.json", table)
    return list(rows)


def sf_targets_from_payments(target_limit: int = 15) -> list[dict[str, Any]]:
    rows = sf_hsh_payment_rows(limit=80)
    by_name: dict[str, float] = {}
    for row in rows:
        name = normalize_space(row.get("supplier_name"))
        amount = number(row.get("sum_completed_payments")) or 0.0
        if name:
            by_name[name] = max(by_name.get(name, 0.0), amount)
    for name, boost in SF_ADVERSE_ENTITY_BOOSTS.items():
        by_name.setdefault(name, 0.0)
    ranked = sorted(
        by_name.items(),
        key=lambda item: item[1] + SF_ADVERSE_ENTITY_BOOSTS.get(item[0], 0.0),
        reverse=True,
    )[:target_limit]
    targets = []
    for rank, (name, amount) in enumerate(ranked, start=1):
        metadata = SF_ENTITY_METADATA.get(name, {})
        aliases = list(metadata.get("aliases", []))
        targets.append(
            {
                "rank": rank,
                "name": name,
                "slug": slugify(name),
                "aliases": aliases,
                "service_urls": list(metadata.get("service_urls") or [SF_NONPROFIT_SPENDING_DASHBOARD_URL]),
                "statement_urls": list(metadata.get("statement_urls") or list(metadata.get("service_urls") or [SF_NONPROFIT_SPENDING_DASHBOARD_URL])),
                "awards": [
                    {
                        "program": "San Francisco HSH nonprofit payments",
                        "award_date": "2019-2025",
                        "eligible_applicant": "City and County of San Francisco",
                        "project": "Aggregated HSH payments by supplier name",
                        "city": "San Francisco",
                        "county": "San Francisco",
                        "amount": amount,
                        "units": "",
                        "source_url": SF_NONPROFIT_SPENDING_DATASET_URL,
                        "source_note": "SF Open Data dataset qkex-vh98 aggregated by supplier_name for Homelessness and Supportive Housing.",
                    }
                ],
                "target_selection": {
                    "selection_metric": "Review Value Score intake proxy",
                    "sf_hsh_completed_payments_2019_2025": amount,
                    "official_adverse_record_boost": SF_ADVERSE_ENTITY_BOOSTS.get(name, 0),
                },
            }
        )
    return targets


def configure_profile(profile: str, target_limit: int = 15) -> None:
    global CASE_ID, DEFAULT_ARTIFACT_BASE_DIR, DEFAULT_CORPUS_DIR, ACTIVE_PROFILE, ACTIVE_TARGET_LIMIT
    ACTIVE_PROFILE = profile
    ACTIVE_TARGET_LIMIT = target_limit
    if profile in {"statewide_homekey", "ca_statewide_homelessness"}:
        CASE_ID = "live_ca_homelessness_top15_2026_04_29"
        DEFAULT_ARTIFACT_BASE_DIR = PROJECT_ROOT / "artifacts" / "homelessness_top15_sources_2026_04_29"
        DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "live_corpus" / f"{CASE_ID}_stage1"
        return
    if profile != "sf_homelessness":
        raise ValueError(f"unknown homelessness ingestion profile: {profile}")
    CASE_ID = "live_ca_sf_homelessness_complex"
    DEFAULT_ARTIFACT_BASE_DIR = PROJECT_ROOT / "artifacts" / "sf_homelessness_sources"
    DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "live_corpus" / f"{CASE_ID}_fresh"


def download_source_docs() -> dict[str, dict[str, Any]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    source_urls = {
        "homekey_round3_awardee_list": HCD_ROUND3_URL,
        "homekey_plus_awardee_list": HCD_PLUS_URL,
        "fhfa_oig_homelessness_funds_press_release": FHFA_OIG_HOMELESSNESS_FUNDS_PRESS_RELEASE_URL,
        "la_city_homekey3_shelby_authorization": LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL,
        "la_city_shelby_2026_operations": LA_CITY_SHELBY_2026_OPERATIONS_URL,
    }
    if ACTIVE_PROFILE == "sf_homelessness":
        source_urls.update(
            {
                "sf_hsh_nonprofit_spending_dashboard": SF_NONPROFIT_SPENDING_DASHBOARD_URL,
                "sf_hsh_nonprofit_spending_columns": SF_NONPROFIT_SPENDING_COLUMNS_URL,
                "sf_homelessness_response_data": SF_HOMELESSNESS_DATA_URL,
                "sf_homelessness_contract_oversight_report": SF_HOMELESSNESS_OVERSIGHT_PDF_URL,
                "sf_homerise_controller_audit_announcement": SF_HOMERISE_AUDIT_PRESS_URL,
                "sf_homerise_controller_audit_pdf": SF_HOMERISE_AUDIT_PDF_URL,
                "sf_uchs_city_violation_notice": SF_UCHS_VIOLATION_PRESS_URL,
                "sf_uchs_da_charging_announcement": SF_DA_UCHS_CHARGES_URL,
                "sf_suspended_debarred_contractors": SF_SUSPENDED_DEBARRED_URL,
            }
        )
    manifest = {}
    for name, url in source_urls.items():
        suffix = ".json" if url.endswith(".json") else ".pdf" if ".pdf" in url.lower() else ".html"
        path = RAW_DIR / f"{name}{suffix}"
        try:
            raw, final_url, content_type = fetch_bytes(url, timeout=120)
            path.write_bytes(raw)
            manifest[name] = {
                "source_url": url,
                "final_url": final_url,
                "content_type": content_type,
                "local_path": str(path),
                "byte_count": len(raw),
                "sha256": sha256_bytes(raw),
                "fetched": True,
                "error": "",
            }
        except Exception as exc:
            manifest[name] = {
                "source_url": url,
                "final_url": "",
                "content_type": "",
                "local_path": str(path),
                "byte_count": 0,
                "sha256": "",
                "fetched": False,
                "error": repr(exc),
            }
    write_json(RAW_DIR / "download_manifest.json", manifest)
    return manifest


def enforcement_docket_artifacts() -> dict[str, Any]:
    """Curated official-source rows for enforcement/docket triage.

    This is not a live docket parser yet. It is a deterministic official-source
    table for known high-value records recovered during source review.
    """

    rows = [
        {
            "entity": "Weingart Center Association",
            "risk_level": "High",
            "test_name": "Official federal criminal-case source and City project linkage screen",
            "legal_status": "third_party_charged_presumption_of_innocence",
            "official_source": True,
            "observed_fact": (
                "An official federal press release dated October 16, 2025 says Steven Taylor was charged with seven counts of bank fraud, "
                "one count of aggravated identity theft, and one count of money laundering, and describes a Cheviot Hills property originally "
                "acquired for $11.2 million and contracted to sell to a homeless housing developer using City of Los Angeles and State of California "
                "public funds for $27.3 million in a double-escrow transaction hidden from the lender. Los Angeles City Clerk records identify "
                "the Cheviot Hills/Shelby Homekey 3 project as Weingart-related and later describe The Weingart Shelby at 3340 Shelby Drive."
            ),
            "reviewer_action": (
                "Open the federal press release, City Clerk Homekey authorization, and 2026 operations report; verify case number, named parties, "
                "property address, project agreements, payment flows, due diligence records, and whether any official source names Weingart as charged or only as transaction counterparty/operator."
            ),
            "source_urls": [
                FHFA_OIG_HOMELESSNESS_FUNDS_PRESS_RELEASE_URL,
                LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL,
                LA_CITY_SHELBY_2026_OPERATIONS_URL,
            ],
            "caveats": [
                "The official federal source charges Taylor, not Weingart Center Association.",
                "The row is a deep-dive trigger because public homelessness funds and a Weingart-linked project appear in the official-source chain.",
                "A criminal charge is an allegation; every defendant is presumed innocent unless and until proven guilty in court.",
            ],
            "connected_party_entity_trigger": True,
            "relationship_type": "public-funded project transaction counterparty/operator context",
            "trigger_confidence": "High",
        }
    ]
    if ACTIVE_PROFILE == "sf_homelessness":
        rows.extend(
            [
                {
                    "entity": "Community Housing Partnership",
                    "risk_level": "High",
                    "test_name": "Official Controller audit finding for HomeRise",
                    "legal_status": "official_audit_financial_shortfalls",
                    "official_source": True,
                    "observed_fact": (
                        "A San Francisco Controller announcement and audit report identify HomeRise, formerly Community Housing Partnership, "
                        "as the provider in an audit of City-funded housing for unhoused residents. The Controller announcement says the audit "
                        "found serious financial shortfalls. This is an entity-level official audit trigger for deeper review, not a legal finding."
                    ),
                    "reviewer_action": (
                        "Open the Controller announcement and audit PDF; verify the audit period, contracts reviewed, fiscal findings, corrective-action status, "
                        "current HSH payment exposure, and whether subsequent monitoring records show remediation."
                    ),
                    "source_urls": [SF_HOMERISE_AUDIT_PRESS_URL, SF_HOMERISE_AUDIT_PDF_URL],
                    "caveats": [
                        "CalDS uses the official audit as a deep-review trigger, not as proof of fraud or intent.",
                        "The run must preserve the distinction between financial-control findings, operational shortfalls, and legal conclusions.",
                    ],
                    "connected_party_entity_trigger": False,
                    "relationship_type": "official entity audit",
                    "trigger_confidence": "High",
                },
                {
                    "entity": "United Council of Human Services",
                    "risk_level": "High",
                    "test_name": "Official City violation and District Attorney charging-source screen",
                    "legal_status": "former_ceo_charged_presumption_of_innocence",
                    "official_source": True,
                    "observed_fact": (
                        "San Francisco issued an official notice that United Council of Human Services was found to be in violation of City agreements. "
                        "The San Francisco District Attorney separately announced that a former nonprofit CEO was charged with stealing and misappropriating "
                        "public funds. This combination is a mandatory deep-review trigger for the entity and its public-funding controls."
                    ),
                    "reviewer_action": (
                        "Open the City violation notice and District Attorney announcement; verify the agreements, named parties, charging document, "
                        "payment controls, board oversight, current vendor status, and whether any official source names the entity itself as charged."
                    ),
                    "source_urls": [SF_UCHS_VIOLATION_PRESS_URL, SF_DA_UCHS_CHARGES_URL],
                    "caveats": [
                        "Charges against an individual are allegations unless proven in court.",
                        "The former-CEO charge is a connected-party trigger; the source chain must not be rewritten as a final entity legal conclusion.",
                    ],
                    "connected_party_entity_trigger": True,
                    "relationship_type": "entity agreement violation plus former-executive charging context",
                    "trigger_confidence": "High",
                },
            ]
        )
    table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": (
            "Official enforcement and docket triage rows are manually curated from official federal and municipal sources when live docket parsing is not yet implemented. "
            "Rows trigger deep review only; they do not create legal conclusions."
        ),
        "rows": rows,
        "source_family": "enforcement_or_docket",
        "source_gap_policy": "Targets without an official row remain un-cleared; the run must record that official enforcement and docket acquisition is incomplete.",
    }
    path = RAW_DIR / "enforcement_docket_source_summary.json"
    write_json(path, table)
    return table


def fetch_page_rows(target: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    base_dir = WEB_DIR / kind
    base_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    urls = target.get(f"{kind}_urls", [])
    for index, url in enumerate(urls, start=1):
        row: dict[str, Any] = {"entity": target["name"], "slug": target["slug"], "url": url, "kind": kind}
        try:
            raw, final_url, content_type = fetch_bytes(url, timeout=75)
            text = html_to_text(raw)
            stem = f"{target['slug']}_{kind}_{index}"
            (base_dir / f"{stem}.html").write_bytes(raw)
            (base_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
            terms = [
                "homeless",
                "housing",
                "supportive",
                "services",
                "policy",
                *HOMELESSNESS_SCOPE_HIGH_TERMS,
                *HOMELESSNESS_SCOPE_MEDIUM_TERMS,
            ]
            text_lower = text.lower()
            row.update(
                {
                    "fetched": True,
                    "final_url": final_url,
                    "content_type": content_type,
                    "text_chars": len(text),
                    "local_text_path": str(base_dir / f"{stem}.txt"),
                    "summary": snippet(text, terms, radius=420),
                    "matched_terms": [term for term in terms if term in text_lower],
                    "error": "",
                }
            )
        except Exception as exc:
            row.update({"fetched": False, "final_url": "", "content_type": "", "text_chars": 0, "summary": "", "matched_terms": [], "error": repr(exc)})
        rows.append(row)
    return rows


def fetch_all_pages() -> dict[str, list[dict[str, Any]]]:
    result = {"service": [], "statement": []}
    for target in TARGETS:
        result["service"].extend(fetch_page_rows(target, "service"))
        result["statement"].extend(fetch_page_rows(target, "statement"))
    write_json(WEB_DIR / "page_harvest_manifest.json", result)
    return result


def propublica_org_page(ein: object) -> str:
    return f"{PROPUBLICA_EXPLORER_BASE}/{ein}"


def propublica_search_url(query: str) -> str:
    return f"{PROPUBLICA_API_BASE}/search.json?{urllib.parse.urlencode({'q': query, 'state[id]': 'CA', 'c_code[id]': '3'})}"


def propublica_org_api_url(ein: object) -> str:
    return f"{PROPUBLICA_API_BASE}/organizations/{ein}.json"


def select_propublica_org(target: dict[str, Any], organizations: list[dict[str, Any]]) -> dict[str, Any] | None:
    aliases = [target["name"], *target.get("aliases", [])]
    compact_aliases = {compact_name(alias) for alias in aliases}
    best: tuple[int, dict[str, Any]] | None = None
    for org in organizations:
        org_name = compact_name(org.get("name", ""))
        sub_name = compact_name(org.get("sub_name", ""))
        state = str(org.get("state") or "").upper()
        score = 0
        if state == "CA":
            score += 25
        if int(org.get("subseccd") or 0) == 3:
            score += 10
        if org_name in compact_aliases or sub_name in compact_aliases:
            score += 100
        elif any(alias and (alias in org_name or org_name in alias or alias in sub_name) for alias in compact_aliases):
            score += 70
        score += int(float(org.get("score") or 0) // 10)
        if score >= 70 and (best is None or score > best[0]):
            best = (score, org)
    return best[1] if best else None


def propublica_search_queries(target: dict[str, Any]) -> list[str]:
    queries: list[str] = []
    for candidate in [target["name"], *target.get("aliases", [])]:
        cleaned = normalize_space(candidate)
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    compact = compact_name(target["name"])
    if "inc" in compact:
        cleaned = re.sub(r"\binc(?:orporated)?\b\.?", "", target["name"], flags=re.IGNORECASE).strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    if "svcs" in target["name"].lower():
        expanded = target["name"].replace("Svcs", "Services")
        if expanded not in queries:
            queries.append(expanded)
    return queries[:6]


def propublica_artifacts() -> dict[str, Any]:
    """Fetch browseable ProPublica nonprofit profile and filing summaries.

    ProPublica is not the system of record for IRS filings, but it provides a
    useful public API and viewer that link back to IRS-source Form 990 material.
    """

    PROPUBLICA_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for target in TARGETS:
        search_path = PROPUBLICA_DIR / f"{target['slug']}_search.json"
        org_path = PROPUBLICA_DIR / f"{target['slug']}_organization.json"
        search_errors: list[dict[str, str]] = []
        selected: dict[str, Any] | None = None
        search_data: dict[str, Any] = {}
        search_url = ""
        search_final_url = ""
        search_content_type = ""
        try:
            override_ein = SF_PROPUBLICA_EIN_OVERRIDES.get(target["name"]) if ACTIVE_PROFILE == "sf_homelessness" else None
            if override_ein:
                selected = {"ein": override_ein, "name": target["name"], "subseccd": 3, "state": "CA"}
                search_url = propublica_org_api_url(override_ein)
                search_final_url = search_url
                search_content_type = "application/json override"
                search_errors.append({"query": target["name"], "search_url": search_url, "error": "matched_by_profile_ein_override"})
                write_json(search_path, {"selected_query": target["name"], "selected_search_url": search_url, "organizations": [selected]})
            else:
                for query in propublica_search_queries(target):
                    search_url = propublica_search_url(query)
                    try:
                        payload, search_final_url, search_content_type = fetch_json_url(search_url, timeout=75)
                        search_data = payload if isinstance(payload, dict) else {"organizations": payload}
                        write_json(PROPUBLICA_DIR / f"{target['slug']}_search_{slugify(query)}.json", search_data)
                        selected = select_propublica_org(target, list(search_data.get("organizations", [])))
                        if selected:
                            write_json(search_path, {"selected_query": query, "selected_search_url": search_url, **search_data})
                            break
                        search_errors.append({"query": query, "search_url": search_url, "error": "not_matched"})
                    except Exception as exc:
                        search_errors.append({"query": query, "search_url": search_url, "error": repr(exc)})
            if not selected:
                matches.append(
                    {
                        "entity": target["name"],
                        "status": "not_matched",
                        "search_url": search_url,
                        "search_final_url": search_final_url,
                        "search_content_type": search_content_type,
                        "candidate_count": len(search_data.get("organizations", [])),
                        "search_attempts": search_errors,
                        "error": "",
                    }
                )
                continue
            ein = selected["ein"]
            org_url = propublica_org_api_url(ein)
            org_data, org_final_url, org_content_type = fetch_json_url(org_url, timeout=75)
            write_json(org_path, org_data)
            org = dict(org_data.get("organization") or {})
            filings = list(org_data.get("filings_with_data") or [])
            filings_without_data = list(org_data.get("filings_without_data") or [])
            matches.append(
                {
                    "entity": target["name"],
                    "status": "matched",
                    "ein": ein,
                    "strein": selected.get("strein") or org.get("strein"),
                    "matched_name": selected.get("name") or org.get("name"),
                    "city": selected.get("city") or org.get("city"),
                    "state": selected.get("state") or org.get("state"),
                    "ntee_code": selected.get("ntee_code") or org.get("ntee_code"),
                    "subsection_code": selected.get("subseccd") or org.get("subsection_code"),
                    "search_url": search_url,
                    "search_attempts": search_errors,
                    "organization_api_url": org_url,
                    "organization_page_url": propublica_org_page(ein),
                    "organization_final_url": org_final_url,
                    "organization_content_type": org_content_type,
                    "filings_with_data_count": len(filings),
                    "filings_without_data_count": len(filings_without_data),
                    "latest_object_id": org.get("latest_object_id"),
                    "data_source": org_data.get("data_source") or search_data.get("data_source"),
                    "error": "",
                }
            )
            for filing in filings:
                tax_year = int(filing.get("tax_prd_yr") or 0)
                if not tax_year:
                    continue
                officer_comp = first_number(filing.get("compnsatncurrofcr"))
                salary_comp = sum_numbers(filing.get("compnsatncurrofcr"), filing.get("othrsalwages"), filing.get("payrolltx"))
                rows.append(
                    {
                        "entity": target["name"],
                        "ein": ein,
                        "tax_period": filing.get("tax_prd"),
                        "tax_period_year": tax_year,
                        "form_type": filing.get("formtype"),
                        "downloaded": True,
                        "source": "ProPublica Nonprofit Explorer API backed by IRS extract data",
                        "propublica_organization_url": propublica_org_page(ein),
                        "propublica_api_url": org_url,
                        "pdf_url": filing.get("pdf_url") or "",
                        "irs_form_990_downloads_url": IRS_FORM_990_DOWNLOADS_URL,
                        "total_revenue": first_number(filing.get("totrevenue")),
                        "total_expenses": first_number(filing.get("totfuncexpns")),
                        "total_assets_end": first_number(filing.get("totassetsend")),
                        "total_liabilities_end": first_number(filing.get("totliabend")),
                        "contributions_gifts_grants": first_number(filing.get("totcntrbgfts")),
                        "public_support_170": first_number(filing.get("gftgrntsrcvd170")),
                        "government_grants": None,
                        "officer_compensation_total": officer_comp,
                        "top_compensation_total": officer_comp,
                        "top_compensation_person": "aggregate current officers/directors/trustees",
                        "top_compensation_title": "aggregate officer compensation from ProPublica/IRS extract",
                        "compensation_is_aggregate": True,
                        "salaries_comp_benefits_current_year": salary_comp,
                        "total_employee_count": None,
                        "political_campaign_activity": None,
                        "lobbying_activities": None,
                        "updated": filing.get("updated") or "",
                    }
                )
        except Exception as exc:
            matches.append(
                {
                    "entity": target["name"],
                    "status": "error",
                    "search_url": search_url,
                    "error": repr(exc),
                }
            )

    table = {
        "case_id": CASE_ID,
        "created_at": now(),
        "methodology": (
            "Resolve top-15 entity names through the ProPublica Nonprofit Explorer API, then extract available IRS Form 990 filing summary fields. "
            "ProPublica is a browseable/API access layer; official IRS filings remain controlling source documents."
        ),
        "official_source_policy": {
            "irs_form_990_downloads": IRS_FORM_990_DOWNLOADS_URL,
            "irs_teos_bulk": IRS_TEOS_BULK_URL,
            "fac_data": FAC_DATA_URL,
            "fac_api": FAC_API_URL,
        },
        "matches": matches,
        "rows": sorted(rows, key=lambda row: (str(row["entity"]), int(row["tax_period_year"]))),
        "row_count": len(rows),
        "profile_matched_entity_count": len({match["entity"] for match in matches if match.get("status") == "matched"}),
        "filing_row_entity_count": len({row["entity"] for row in rows}),
        "source_family": "irs_990",
        "caveats": [
            "ProPublica summary fields are not a substitute for raw IRS XML/PDF review.",
            "Current-officer compensation from the API is aggregate unless a raw return parser identifies individual officers.",
            "Government-grant fields may require raw XML/PDF parsing and are not inferred from total contributions.",
        ],
    }
    write_json(PROPUBLICA_DIR / "propublica_irs_990_summary.json", table)
    return table


def extract_object_id_from_pdf_url(pdf_url: str) -> str:
    parsed = urllib.parse.urlparse(pdf_url or "")
    path_values = urllib.parse.parse_qs(parsed.query).get("path", [])
    path = path_values[0] if path_values else parsed.path
    match = re.search(r"([0-9]{12,})\.pdf", path)
    return match.group(1) if match else ""


def irs_xml_candidate_urls(row: dict[str, Any]) -> list[str]:
    object_id = extract_object_id_from_pdf_url(str(row.get("pdf_url") or ""))
    if not object_id:
        return []
    filing_year = object_id[:4]
    ein = re.sub(r"[^0-9]", "", str(row.get("ein") or ""))
    tax_period = re.sub(r"[^0-9]", "", str(row.get("tax_period") or ""))
    candidates = [f"https://apps.irs.gov/pub/epostcard/990/xml/{filing_year}/{object_id}_public.xml"]
    if ein and tax_period:
        candidates.append(f"https://apps.irs.gov/pub/epostcard/990/xml/{filing_year}/{ein}_{tax_period}_990_{object_id}_public.xml")
    return candidates


def irs_index_url(year: str) -> str:
    return f"https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv"


def irs_xml_zip_url(year: str, batch_id: str) -> str:
    return f"https://apps.irs.gov/pub/epostcard/990/xml/{year}/{batch_id.upper()}.zip"


def irs_index_entries_for_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    target_object_ids = {extract_object_id_from_pdf_url(str(row.get("pdf_url") or "")) for row in rows}
    target_object_ids.discard("")
    target_pairs = {
        (re.sub(r"[^0-9]", "", str(row.get("ein") or "")), re.sub(r"[^0-9]", "", str(row.get("tax_period") or "")))
        for row in rows
        if row.get("ein") and row.get("tax_period")
    }
    years = sorted({object_id[:4] for object_id in target_object_ids if len(object_id) >= 4})
    matches: dict[str, dict[str, Any]] = {}
    for year in years:
        index_path = IRS_RAW_DIR / f"index_{year}.csv"
        source_url = irs_index_url(year)
        try:
            if not index_path.exists():
                raw, final_url, content_type = fetch_bytes(source_url, timeout=180, attempts=2)
                index_path.write_bytes(raw)
                write_json(
                    IRS_RAW_DIR / f"index_{year}_manifest.json",
                    {
                        "source_url": source_url,
                        "final_url": final_url,
                        "content_type": content_type,
                        "byte_count": len(raw),
                        "sha256": sha256_bytes(raw),
                    },
                )
            with index_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for index_row in reader:
                    object_id = str(index_row.get("OBJECT_ID") or "")
                    pair = (str(index_row.get("EIN") or ""), str(index_row.get("TAX_PERIOD") or ""))
                    if object_id in target_object_ids or pair in target_pairs:
                        batch_id = str(index_row.get("XML_BATCH_ID") or "")
                        normalized = {
                            "return_id": index_row.get("RETURN_ID"),
                            "ein": index_row.get("EIN"),
                            "tax_period": index_row.get("TAX_PERIOD"),
                            "taxpayer_name": index_row.get("TAXPAYER_NAME"),
                            "return_type": index_row.get("RETURN_TYPE"),
                            "object_id": object_id,
                            "xml_batch_id": batch_id,
                            "index_url": source_url,
                            "index_local_path": str(index_path),
                            "xml_zip_url": irs_xml_zip_url(year, batch_id) if batch_id else "",
                        }
                        if object_id:
                            matches[object_id] = normalized
                        matches[f"{pair[0]}:{pair[1]}"] = normalized
        except Exception as exc:
            write_json(
                IRS_RAW_DIR / f"index_{year}_error.json",
                {"source_url": source_url, "error": repr(exc), "target_object_ids": sorted(target_object_ids)},
            )
    return matches


def probe_url(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CalDS source acquisition checker/1.0", "Accept": "application/xml,text/xml,*/*"},
        method="HEAD",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return {
                "url": url,
                "reachable": 200 <= int(response.status) < 400,
                "http_status": int(response.status),
                "content_type": response.headers.get("content-type", ""),
                "final_url": response.geturl(),
                "error": "",
            }
    except Exception as exc:
        return {
            "url": url,
            "reachable": False,
            "http_status": getattr(exc, "code", None),
            "content_type": "",
            "final_url": "",
            "error": repr(exc),
        }


def fetch_range(url: str, start: int, end: int, timeout: int = 120) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CalDS official source acquisition/1.0",
            "Accept": "application/zip,application/octet-stream,*/*",
            "Range": f"bytes={start}-{end}",
        },
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        status = int(getattr(response, "status", response.getcode()))
        if status != 206:
            raise RuntimeError(f"Server did not honor byte range for {url}: HTTP {status}")
        return response.read()


def remote_content_length(url: str, timeout: int = 45) -> int:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CalDS official source acquisition/1.0", "Accept": "application/zip,*/*"},
        method="HEAD",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return int(response.headers["Content-Length"])


def remote_zip_entries(zip_url: str) -> list[dict[str, Any]]:
    size = remote_content_length(zip_url)
    tail_size = min(size, 131072)
    tail = fetch_range(zip_url, size - tail_size, size - 1)
    eocd_index = tail.rfind(b"PK\x05\x06")
    if eocd_index < 0:
        raise RuntimeError(f"ZIP end-of-central-directory record not found for {zip_url}")
    eocd = tail[eocd_index : eocd_index + 22]
    if len(eocd) < 22:
        raise RuntimeError(f"Incomplete ZIP end-of-central-directory record for {zip_url}")
    (
        _signature,
        _disk_number,
        _central_disk,
        _disk_entries,
        total_entries,
        central_size,
        central_offset,
        _comment_length,
    ) = struct.unpack("<4s4H2IH", eocd)
    if total_entries == 0xFFFF or central_size == 0xFFFFFFFF or central_offset == 0xFFFFFFFF:
        locator_index = tail.rfind(b"PK\x06\x07", 0, eocd_index)
        if locator_index < 0 or locator_index + 20 > len(tail):
            raise RuntimeError(f"ZIP64 locator not found for {zip_url}")
        locator = tail[locator_index : locator_index + 20]
        _locator_sig, _locator_disk, zip64_eocd_offset, _locator_disks = struct.unpack("<4sIQI", locator)
        zip64 = fetch_range(zip_url, zip64_eocd_offset, zip64_eocd_offset + 55)
        if len(zip64) < 56 or zip64[:4] != b"PK\x06\x06":
            raise RuntimeError(f"ZIP64 end-of-central-directory record not found for {zip_url}")
        (
            _zip64_sig,
            _zip64_size,
            _made_by,
            _needed,
            _disk_num,
            _central_disk_num,
            _entries_on_disk,
            zip64_total_entries,
            zip64_central_size,
            zip64_central_offset,
        ) = struct.unpack("<4sQ2H2I4Q", zip64[:56])
        total_entries = int(zip64_total_entries)
        central_size = int(zip64_central_size)
        central_offset = int(zip64_central_offset)
    central = fetch_range(zip_url, central_offset, central_offset + central_size - 1)
    entries: list[dict[str, Any]] = []
    offset = 0
    for _ in range(total_entries):
        header = central[offset : offset + 46]
        if len(header) < 46 or header[:4] != b"PK\x01\x02":
            raise RuntimeError(f"Malformed ZIP central directory for {zip_url} at offset {offset}")
        (
            _sig,
            _version_made,
            _version_needed,
            flags,
            compression_method,
            _mod_time,
            _mod_date,
            crc32,
            compressed_size,
            uncompressed_size,
            filename_len,
            extra_len,
            comment_len,
            _disk_start,
            _internal_attrs,
            _external_attrs,
            local_header_offset,
        ) = struct.unpack("<4s6H3I5H2I", header)
        filename_start = offset + 46
        filename_end = filename_start + filename_len
        filename = central[filename_start:filename_end].decode("utf-8", "replace")
        entries.append(
            {
                "filename": filename,
                "flags": flags,
                "compression_method": compression_method,
                "crc32": crc32,
                "compressed_size": compressed_size,
                "uncompressed_size": uncompressed_size,
                "local_header_offset": local_header_offset,
                "zip_url": zip_url,
            }
        )
        offset = filename_end + extra_len + comment_len
    return entries


def remote_zip_extract_entry(zip_url: str, entry: dict[str, Any]) -> bytes:
    local_offset = int(entry["local_header_offset"])
    local = fetch_range(zip_url, local_offset, local_offset + 64)
    if len(local) < 30 or local[:4] != b"PK\x03\x04":
        raise RuntimeError(f"Malformed local ZIP header for {entry.get('filename')}")
    (
        _sig,
        _version_needed,
        _flags,
        compression_method,
        _mod_time,
        _mod_date,
        _crc32,
        _compressed_size,
        _uncompressed_size,
        filename_len,
        extra_len,
    ) = struct.unpack("<4s5H3I2H", local[:30])
    data_start = local_offset + 30 + filename_len + extra_len
    compressed_size = int(entry["compressed_size"])
    compressed = fetch_range(zip_url, data_start, data_start + compressed_size - 1)
    if compression_method == 0:
        return compressed
    if compression_method == 8:
        return zlib.decompress(compressed, -15)
    raise RuntimeError(f"Unsupported ZIP compression method {compression_method} for {entry.get('filename')}")


def remote_zip_extract_irs_xml(zip_url: str, object_id: str, cache: dict[str, list[dict[str, Any]]]) -> tuple[bytes, dict[str, Any]]:
    entries = cache.get(zip_url)
    if entries is None:
        entries = remote_zip_entries(zip_url)
        cache[zip_url] = entries
    candidates = [entry for entry in entries if object_id and object_id in str(entry.get("filename") or "")]
    if not candidates:
        raise RuntimeError(f"Object ID {object_id} not found in IRS XML ZIP {zip_url}")
    entry = candidates[0]
    raw = remote_zip_extract_entry(zip_url, entry)
    return raw, entry


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def xml_first_text(root: ET.Element, names: set[str]) -> str:
    for element in root.iter():
        if xml_local_name(element.tag) in names and element.text and element.text.strip():
            return normalize_space(element.text)
    return ""


def xml_first_number(root: ET.Element, names: set[str]) -> float | None:
    value = xml_first_text(root, names)
    return number(value)


def xml_boolish(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "x"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def parse_irs_990_xml(raw: bytes) -> dict[str, Any]:
    root = ET.fromstring(raw)
    fields: dict[str, Any] = {
        "activity_or_mission": xml_first_text(root, {"ActivityOrMissionDesc", "MissionDesc", "Desc"}),
        "total_revenue": xml_first_number(root, {"CYTotalRevenueAmt", "TotalRevenueAmt"}),
        "previous_total_revenue": xml_first_number(root, {"PYTotalRevenueAmt"}),
        "total_expenses": xml_first_number(root, {"CYTotalExpensesAmt", "TotalFunctionalExpensesAmt"}),
        "previous_total_expenses": xml_first_number(root, {"PYTotalExpensesAmt"}),
        "contributions_gifts_grants": xml_first_number(root, {"CYContributionsGrantsAmt", "ContriRptFundraisingEventAmt"}),
        "previous_contributions_gifts_grants": xml_first_number(root, {"PYContributionsGrantsAmt"}),
        "government_grants": xml_first_number(root, {"GovernmentGrantsAmt"}),
        "salaries_comp_benefits_current_year": xml_first_number(
            root,
            {
                "CYSalariesCompEmpBnftPaidAmt",
                "CYSalariesCompEmpBnftAmt",
                "TotalCompGreaterThan100KGrp",
                "CompCurrentOfcrDirectorsGrp",
            },
        ),
        "total_employee_count": xml_first_number(root, {"TotalEmployeeCnt", "EmployeeCnt"}),
        "political_campaign_activity": xml_boolish(xml_first_text(root, {"PoliticalCampaignActyInd"})),
        "lobbying_activities": xml_boolish(xml_first_text(root, {"LobbyingActivitiesInd"})),
        "federal_grant_audit_required": xml_boolish(xml_first_text(root, {"FederalGrantAuditRequiredInd"})),
        "federal_grant_audit_performed": xml_boolish(xml_first_text(root, {"FederalGrantAuditPerformedInd"})),
        "grant_records_maintained": xml_boolish(xml_first_text(root, {"GrantRecordsMaintainedInd"})),
    }

    compensation_people: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float]] = set()
    for parent in root.iter():
        child_values: dict[str, str] = {}
        for child in list(parent):
            name = xml_local_name(child.tag)
            text = normalize_space(child.text or "")
            if text:
                child_values[name] = text
        person = child_values.get("PersonNm") or child_values.get("BusinessNameLine1Txt") or child_values.get("BusinessNameLine1")
        if not person:
            continue
        title = child_values.get("TitleTxt") or child_values.get("Title") or ""
        org_comp = number(child_values.get("ReportableCompFromOrgAmt")) or 0.0
        related_comp = number(child_values.get("ReportableCompFromRltdOrgAmt")) or 0.0
        other_comp = number(child_values.get("OtherCompensationAmt")) or 0.0
        total_comp = number(child_values.get("TotalCompensationFilingOrgAmt"))
        if total_comp is None:
            total_comp = org_comp + related_comp + other_comp
        if not total_comp:
            continue
        key = (person, title, float(total_comp))
        if key in seen:
            continue
        seen.add(key)
        compensation_people.append(
            {
                "person": person,
                "title": title,
                "reportable_comp_from_org": org_comp or None,
                "reportable_comp_from_related_orgs": related_comp or None,
                "other_compensation": other_comp or None,
                "total_compensation": float(total_comp),
            }
        )
    compensation_people = sorted(compensation_people, key=lambda item: float(item.get("total_compensation") or 0), reverse=True)
    fields["compensation_people"] = compensation_people[:10]
    if compensation_people:
        top = compensation_people[0]
        fields["top_compensation_total"] = top.get("total_compensation")
        fields["top_compensation_person"] = top.get("person")
        fields["top_compensation_title"] = top.get("title")
        fields["compensation_is_aggregate"] = False
    return fields


def raw_irs_990_artifacts(tax_table: dict[str, Any]) -> dict[str, Any]:
    """Acquire raw filing artifacts where public URLs are available.

    This keeps the raw-return work in deterministic source acquisition. It
    archives the latest ProPublica-linked full 990 PDF per entity when possible
    and extracts the official IRS XML object from the TEOS bulk ZIP when the
    IRS index identifies the batch. Large ZIPs are read by byte range so source
    acquisition stays deterministic without downloading entire yearly archives.
    """

    IRS_RAW_DIR.mkdir(parents=True, exist_ok=True)
    latest_by_entity: dict[str, dict[str, Any]] = {}
    for row in tax_table.get("rows", []):
        entity = str(row.get("entity") or "")
        if not entity:
            continue
        year = int(row.get("tax_period_year") or 0)
        existing = latest_by_entity.get(entity)
        if existing is None or year > int(existing.get("tax_period_year") or 0):
            latest_by_entity[entity] = dict(row)

    rows: list[dict[str, Any]] = []
    index_entries = irs_index_entries_for_rows(list(latest_by_entity.values()))
    zip_entry_cache: dict[str, list[dict[str, Any]]] = {}
    for entity, row in sorted(latest_by_entity.items()):
        slug = slugify(entity)
        year = int(row.get("tax_period_year") or 0)
        ein = str(row.get("ein") or "")
        tax_period = re.sub(r"[^0-9]", "", str(row.get("tax_period") or ""))
        pdf_url = str(row.get("pdf_url") or "")
        object_id = extract_object_id_from_pdf_url(pdf_url)
        index_entry = index_entries.get(object_id) or index_entries.get(f"{re.sub(r'[^0-9]', '', ein)}:{tax_period}") or {}
        xml_index_confirmed = bool(index_entry)
        xml_zip_url = str(index_entry.get("xml_zip_url") or "")
        pdf_path = IRS_RAW_DIR / f"{slug}_{ein}_{year}_form_990.pdf"
        pdf_downloaded = False
        pdf_error = ""
        pdf_sha256 = ""
        pdf_byte_count = 0
        pdf_content_type = ""
        pdf_final_url = ""
        if pdf_url:
            try:
                raw, pdf_final_url, pdf_content_type = fetch_bytes(pdf_url, timeout=120, attempts=2)
                pdf_path.write_bytes(raw)
                pdf_downloaded = True
                pdf_sha256 = sha256_bytes(raw)
                pdf_byte_count = len(raw)
            except Exception as exc:
                pdf_error = repr(exc)

        xml_candidates = irs_xml_candidate_urls(row)
        xml_checks = [probe_url(url) for url in xml_candidates[:2]]
        xml_downloaded = False
        xml_path = IRS_RAW_DIR / f"{slug}_{ein}_{year}_form_990.xml"
        xml_sha256 = ""
        xml_final_url = ""
        xml_content_type = ""
        xml_error = ""
        xml_zip_entry: dict[str, Any] = {}
        parsed_detail_fields = {
            "total_revenue": row.get("total_revenue"),
            "total_expenses": row.get("total_expenses"),
            "officer_compensation_total": row.get("officer_compensation_total"),
            "top_compensation_total": row.get("top_compensation_total"),
            "top_compensation_person": row.get("top_compensation_person"),
            "top_compensation_title": row.get("top_compensation_title"),
            "compensation_is_aggregate": row.get("compensation_is_aggregate"),
            "salaries_comp_benefits_current_year": row.get("salaries_comp_benefits_current_year"),
            "contributions_gifts_grants": row.get("contributions_gifts_grants"),
            "government_grants": row.get("government_grants"),
            "total_employee_count": row.get("total_employee_count"),
            "political_campaign_activity": row.get("political_campaign_activity"),
            "lobbying_activities": row.get("lobbying_activities"),
        }
        for check in xml_checks:
            if not check.get("reachable"):
                continue
            try:
                raw, final_url, content_type = fetch_bytes(str(check["url"]), timeout=60, attempts=1)
                xml_path.write_bytes(raw)
                check.update({"downloaded": True, "final_url": final_url, "content_type": content_type})
                xml_downloaded = True
                xml_sha256 = sha256_bytes(raw)
                xml_final_url = final_url
                xml_content_type = content_type
                parsed_detail_fields.update({key: value for key, value in parse_irs_990_xml(raw).items() if value is not None and value != ""})
                break
            except Exception as exc:
                check["download_error"] = repr(exc)
                xml_error = repr(exc)
        if not xml_downloaded and xml_zip_url and str(index_entry.get("object_id") or ""):
            try:
                raw, xml_zip_entry = remote_zip_extract_irs_xml(xml_zip_url, str(index_entry["object_id"]), zip_entry_cache)
                xml_path.write_bytes(raw)
                xml_downloaded = True
                xml_sha256 = sha256_bytes(raw)
                xml_final_url = xml_zip_url
                xml_content_type = "application/xml"
                parsed_detail_fields.update({key: value for key, value in parse_irs_990_xml(raw).items() if value is not None and value != ""})
            except Exception as exc:
                xml_error = repr(exc)

        rows.append(
            {
                "entity": entity,
                "ein": ein,
                "tax_period": row.get("tax_period"),
                "tax_period_year": year,
                "irs_object_id": object_id,
                "irs_index_confirmed": xml_index_confirmed,
                "irs_index_entry": index_entry,
                "irs_xml_zip_url": xml_zip_url,
                "pdf_url": pdf_url,
                "pdf_downloaded": pdf_downloaded,
                "pdf_final_url": pdf_final_url,
                "pdf_local_path": str(pdf_path) if pdf_downloaded else "",
                "pdf_content_type": pdf_content_type,
                "pdf_byte_count": pdf_byte_count,
                "pdf_sha256": pdf_sha256,
                "pdf_error": pdf_error,
                "xml_candidate_urls": xml_candidates,
                "xml_probe_results": xml_checks,
                "xml_downloaded": xml_downloaded,
                "xml_local_path": str(xml_path) if xml_downloaded else "",
                "xml_sha256": xml_sha256,
                "xml_final_url": xml_final_url,
                "xml_content_type": xml_content_type,
                "xml_zip_entry": xml_zip_entry,
                "xml_error": xml_error,
                "raw_source_status": (
                    "pdf_and_xml_downloaded"
                    if pdf_downloaded and xml_downloaded
                    else "official_irs_xml_extracted"
                    if xml_downloaded
                    else "pdf_downloaded_xml_index_confirmed"
                    if pdf_downloaded and xml_index_confirmed
                    else "xml_index_confirmed_zip_not_downloaded"
                    if xml_index_confirmed
                    else "pdf_downloaded_xml_missing"
                    if pdf_downloaded
                    else "raw_artifact_missing"
                ),
                "parsed_detail_fields": parsed_detail_fields,
                "caveats": [
                    "PDF acquisition archives the public filing for human or downstream parser review; it is not itself a parsed line-item extraction.",
                    "IRS XML byte-range extraction uses the official IRS index and bulk ZIP entry; parsed line items remain parser outputs that should be checked against the raw XML/PDF for high-stakes conclusions.",
                ],
            }
        )

    table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": "Archive latest full Form 990 PDF per matched entity when a public filing URL is available; use official IRS TEOS index rows and byte-range ZIP extraction to recover the raw XML object where available.",
        "rows": rows,
        "row_count": len(rows),
        "pdf_downloaded_count": len([row for row in rows if row["pdf_downloaded"]]),
        "xml_index_confirmed_count": len([row for row in rows if row["irs_index_confirmed"]]),
        "xml_downloaded_count": len([row for row in rows if row["xml_downloaded"]]),
        "source_family": "irs_990",
        "source_urls": [PROPUBLICA_API_DOC_URL, IRS_FORM_990_DOWNLOADS_URL, IRS_TEOS_BULK_URL],
    }
    write_json(IRS_RAW_DIR / "raw_irs_990_artifact_summary.json", table)
    return table


def normalize_ein(value: object) -> str:
    return re.sub(r"[^0-9]", "", str(value or "")).lstrip("0")


def stream_fac_csv(url: str, timeout: int = 240):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 CalDS official source acquisition/1.0",
            "Accept": "text/csv,*/*",
        },
    )
    context = ssl.create_default_context()
    response = urllib.request.urlopen(request, timeout=timeout, context=context)
    return response, csv.DictReader(io.TextIOWrapper(response, encoding="utf-8", newline=""))


def fac_audit_artifacts(tax_table: dict[str, Any]) -> dict[str, Any]:
    """Filter official Federal Audit Clearinghouse data for matched target EINs."""

    FAC_DIR.mkdir(parents=True, exist_ok=True)
    target_by_ein: dict[str, str] = {}
    for match in tax_table.get("matches", []):
        ein = normalize_ein(match.get("ein"))
        entity = str(match.get("entity") or "")
        if ein and entity:
            target_by_ein[ein] = entity
    for row in tax_table.get("rows", []):
        ein = normalize_ein(row.get("ein"))
        entity = str(row.get("entity") or "")
        if ein and entity:
            target_by_ein[ein] = entity

    matched_general: list[dict[str, Any]] = []
    report_to_entity: dict[str, str] = {}
    report_to_ein: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    try:
        response, reader = stream_fac_csv(FAC_GENERAL_CSV_URL)
        with response:
            for row in reader:
                ein = normalize_ein(row.get("auditee_ein"))
                entity = target_by_ein.get(ein)
                if not entity:
                    continue
                normalized = dict(row)
                normalized["entity"] = entity
                normalized["matched_ein"] = ein
                matched_general.append(normalized)
                report_id = str(row.get("report_id") or "")
                if report_id:
                    report_to_entity[report_id] = entity
                    report_to_ein[report_id] = ein
    except Exception as exc:
        errors.append({"source_url": FAC_GENERAL_CSV_URL, "error": repr(exc)})

    report_ids = set(report_to_entity)
    finding_rows: list[dict[str, Any]] = []
    finding_text_rows: list[dict[str, Any]] = []
    corrective_rows: list[dict[str, Any]] = []
    award_rows: list[dict[str, Any]] = []

    def collect_by_report(url: str, target: list[dict[str, Any]], kind: str) -> None:
        if not report_ids:
            return
        try:
            response, reader = stream_fac_csv(url)
            with response:
                for row in reader:
                    report_id = str(row.get("report_id") or "")
                    if report_id not in report_ids:
                        continue
                    normalized = dict(row)
                    normalized["entity"] = report_to_entity[report_id]
                    normalized["matched_ein"] = report_to_ein.get(report_id, "")
                    normalized["source_kind"] = kind
                    target.append(normalized)
        except Exception as exc:
            errors.append({"source_url": url, "error": repr(exc)})

    collect_by_report(FAC_FINDINGS_CSV_URL, finding_rows, "findings")
    collect_by_report(FAC_FINDINGS_TEXT_CSV_URL, finding_text_rows, "findings_text")
    collect_by_report(FAC_CORRECTIVE_ACTION_CSV_URL, corrective_rows, "corrective_action_plans")
    collect_by_report(FAC_AWARDS_CSV_URL, award_rows, "federal_awards")

    by_entity: dict[str, dict[str, Any]] = {}
    for entity in target_by_ein.values():
        by_entity.setdefault(
            entity,
            {
                "entity": entity,
                "matched_eins": sorted({ein for ein, candidate in target_by_ein.items() if candidate == entity}),
                "report_ids": [],
                "audit_years": [],
                "fac_report_count": 0,
                "fac_findings_row_count": 0,
                "material_weakness_years": [],
                "internal_control_deficiency_years": [],
                "material_noncompliance_years": [],
                "not_low_risk_years": [],
                "fac_award_amount_total": 0.0,
                "status": "no_fac_report_found_for_matched_ein",
            },
        )
    for row in matched_general:
        entity = str(row["entity"])
        summary = by_entity.setdefault(entity, {"entity": entity})
        report_id = str(row.get("report_id") or "")
        audit_year = str(row.get("audit_year") or "")
        summary.setdefault("matched_eins", [])
        summary.setdefault("report_ids", [])
        summary.setdefault("audit_years", [])
        summary.setdefault("material_weakness_years", [])
        summary.setdefault("internal_control_deficiency_years", [])
        summary.setdefault("material_noncompliance_years", [])
        summary.setdefault("not_low_risk_years", [])
        if report_id and report_id not in summary["report_ids"]:
            summary["report_ids"].append(report_id)
        if audit_year and audit_year not in summary["audit_years"]:
            summary["audit_years"].append(audit_year)
        if xml_boolish(row.get("is_internal_control_material_weakness_disclosed")) and audit_year not in summary["material_weakness_years"]:
            summary["material_weakness_years"].append(audit_year)
        if xml_boolish(row.get("is_internal_control_deficiency_disclosed")) and audit_year not in summary["internal_control_deficiency_years"]:
            summary["internal_control_deficiency_years"].append(audit_year)
        if xml_boolish(row.get("is_material_noncompliance_disclosed")) and audit_year not in summary["material_noncompliance_years"]:
            summary["material_noncompliance_years"].append(audit_year)
        if xml_boolish(row.get("is_low_risk_auditee")) is False and audit_year not in summary["not_low_risk_years"]:
            summary["not_low_risk_years"].append(audit_year)
        summary["fac_report_count"] = len(summary["report_ids"])
        summary["status"] = "fac_report_found"

    findings_by_entity: dict[str, int] = {}
    for row in finding_rows:
        entity = str(row.get("entity") or "")
        findings_by_entity[entity] = findings_by_entity.get(entity, 0) + 1
    award_total_by_entity: dict[str, float] = {}
    award_top_by_entity: dict[str, dict[str, Any]] = {}
    for row in award_rows:
        entity = str(row.get("entity") or "")
        amount = number(row.get("amount_expended")) or number(row.get("amount_expended_total")) or 0.0
        award_total_by_entity[entity] = award_total_by_entity.get(entity, 0.0) + amount
        existing = award_top_by_entity.get(entity)
        if existing is None or amount > float(existing.get("amount_expended_total") or 0):
            award_top_by_entity[entity] = {
                "entity": entity,
                "report_id": row.get("report_id"),
                "federal_program_name": row.get("federal_program_name") or row.get("program_name") or row.get("cluster_name") or "",
                "amount_expended_total": amount,
                "assistance_listing": row.get("assistance_listing_number") or row.get("federal_award_reference_number") or "",
            }
    for entity, summary in by_entity.items():
        summary["fac_findings_row_count"] = findings_by_entity.get(entity, 0)
        summary["fac_award_amount_total"] = award_total_by_entity.get(entity, 0.0)
        for key in ["report_ids", "audit_years", "material_weakness_years", "internal_control_deficiency_years", "material_noncompliance_years", "not_low_risk_years"]:
            summary[key] = sorted(summary.get(key, []))

    write_json(FAC_DIR / "fac_general_filtered.json", {"source_url": FAC_GENERAL_CSV_URL, "rows": matched_general, "row_count": len(matched_general)})
    write_json(FAC_DIR / "fac_findings_filtered.json", {"source_url": FAC_FINDINGS_CSV_URL, "rows": finding_rows, "row_count": len(finding_rows)})
    write_json(FAC_DIR / "fac_findings_text_filtered.json", {"source_url": FAC_FINDINGS_TEXT_CSV_URL, "rows": finding_text_rows, "row_count": len(finding_text_rows)})
    write_json(FAC_DIR / "fac_corrective_actions_filtered.json", {"source_url": FAC_CORRECTIVE_ACTION_CSV_URL, "rows": corrective_rows, "row_count": len(corrective_rows)})
    write_json(FAC_DIR / "fac_federal_awards_filtered.json", {"source_url": FAC_AWARDS_CSV_URL, "rows": award_rows, "row_count": len(award_rows)})

    table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": "Filter official Federal Audit Clearinghouse public CSV extracts by matched ProPublica/IRS EINs only; preserve no-report rows as coverage results rather than adverse findings. Name fallback is intentionally disabled to avoid broad false positives on common nonprofit words.",
        "source_urls": [
            FAC_DOWNLOAD_CURRENT_URL,
            FAC_DATA_URL,
            FAC_API_URL,
            FAC_GENERAL_CSV_URL,
            FAC_AWARDS_CSV_URL,
            FAC_FINDINGS_CSV_URL,
            FAC_FINDINGS_TEXT_CSV_URL,
            FAC_CORRECTIVE_ACTION_CSV_URL,
        ],
        "target_eins": target_by_ein,
        "audit_summary": sorted(by_entity.values(), key=lambda item: str(item.get("entity", ""))),
        "award_summary": sorted(award_top_by_entity.values(), key=lambda item: str(item.get("entity", ""))),
        "general_rows": matched_general[:200],
        "findings_rows": finding_rows[:200],
        "findings_text_rows": finding_text_rows[:200],
        "corrective_action_rows": corrective_rows[:200],
        "errors": errors,
        "row_count": len(by_entity),
        "source_family": "audit",
    }
    write_json(FAC_DIR / "fac_audit_summary.json", table)
    return table


LOCAL_CONTRACT_MONITORING_SOURCES: list[dict[str, Any]] = [
    {
        "entity": "Hope the Mission",
        "source_url": LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL,
        "source_title": "Los Angeles City Administrative Officer Homekey Round 3 recommendations",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": (
            "Los Angeles City records authorize Homekey Round 3 applications and funding actions for Motel 6 North Hills and Oak Tree Inn, "
            "two source-listed projects where Hope the Mission appears in the HCD award exposure table."
        ),
        "project_context": "Motel 6 North Hills; Oak Tree Inn",
        "money_context": "City report table lists Homekey request and City match amounts by project; direct nonprofit receipt still requires agreement/payment records.",
    },
    {
        "entity": "Weingart Center Association",
        "source_url": LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL,
        "source_title": "Los Angeles City Administrative Officer Homekey Round 3 recommendations",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": (
            "Los Angeles City records identify Cheviot Hills/Shelby as a Homekey Round 3 site and include an authorizing resolution for joint application with Weingart Center Association."
        ),
        "project_context": "Cheviot Hills/Shelby; 3340 Shelby Drive",
        "money_context": "City report table lists Homekey request and City match amounts for the Shelby project; direct payment tracing still requires agreements, escrow, draw, and operating records.",
    },
    {
        "entity": "Weingart Center Association",
        "source_url": LA_CITY_SHELBY_2026_OPERATIONS_URL,
        "source_title": "Los Angeles FY 2025-26 Third Homelessness Funding Report",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": "Los Angeles City records state the Weingart Shelby at 3340 Shelby Drive was expected to begin operations on March 26, 2026.",
        "project_context": "The Weingart Shelby operations",
        "money_context": "Operations report context; exact draw and operating-cost ledger remains a source request.",
    },
    {
        "entity": "DignityMoves",
        "source_url": OAKLAND_DIGNITY_VILLAGE_URL,
        "source_title": "Oakland awarded $14.3 million in Homekey funds for Dignity Village",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": (
            "City of Oakland records state the Dignity Village Oakland project received $14.266 million in State Homekey funds and that DignityMoves and Housing Consortium of the East Bay are co-developing the site."
        ),
        "project_context": "Dignity Village Oakland, 9418 Edes Ave/606 Clara St.",
        "money_context": "Official local project award and partner role; direct nonprofit receipts and operating ledgers remain unresolved.",
    },
    {
        "entity": "The People Concern",
        "source_url": LA_HOMEKEY_PLUS_SAFE_HARBOR_REPORT_URL,
        "source_title": "Los Angeles Homekey+ Program Recommendations",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": (
            "Los Angeles City records describe Safe Harbor I and Safe Harbor II as collaborative ventures with The People Concern serving as lead service provider."
        ),
        "project_context": "Safe Harbor I at 828 W Anaheim Street; Safe Harbor II at 728 N Lagoon Avenue",
        "money_context": "Report identifies approximate Homekey+ capital funding requests; final standard agreements and payments remain unresolved.",
    },
    {
        "entity": "The People Concern",
        "source_url": LA_HOMEKEY_PLUS_SAFE_HARBOR_I_RESOLUTION_URL,
        "source_title": "Los Angeles Safe Harbor I authorizing resolution",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": "The Safe Harbor I resolution names The People Concern as a co-applicant for Homekey+ funds and states an application amount not to exceed $17.5 million.",
        "project_context": "Safe Harbor I, 828 W Anaheim Street",
        "money_context": "Application authority only; standard agreement, allowability, and draw records remain unresolved.",
    },
    {
        "entity": "The People Concern",
        "source_url": LA_HOMEKEY_PLUS_SAFE_HARBOR_II_RESOLUTION_URL,
        "source_title": "Los Angeles Safe Harbor II authorizing resolution",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": "The Safe Harbor II resolution names The People Concern as a co-applicant for Homekey+ funds and states an application amount not to exceed $17.04 million.",
        "project_context": "Safe Harbor II, 728 N Lagoon Avenue",
        "money_context": "Application authority only; standard agreement, allowability, and draw records remain unresolved.",
    },
    {
        "entity": "California Supportive Housing",
        "source_url": OAKLAND_QUALITY_INN_URL,
        "source_title": "Oakland awarded $20.4 million in Homekey Round 3 funds for Quality Inn",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": (
            "City of Oakland records state Oakland received $20.368 million in State Homekey funds for the Quality Inn and that California Supportive Housing will develop and own the property."
        ),
        "project_context": "Quality Inn, 8471 Enterprise Way, Oakland",
        "money_context": "Official local project award and owner/developer role; direct receipts, draws, and performance records remain unresolved.",
    },
    {
        "entity": "California Supportive Housing",
        "source_url": OAKLAND_HOMEKEY_R2H2_URL,
        "source_title": "Oakland City Homekey and Rapid Response Homeless Housing Program",
        "source_type": "city_contract_monitoring_source",
        "observed_fact": "Oakland's Homekey program page identifies Quality Inn as a Round 3 project in partnership with California Supportive Housing.",
        "project_context": "Oakland Homekey/R2H2 project index",
        "money_context": "Program index context; agreement/payment records remain unresolved.",
    },
]


def contract_payment_discovery_artifacts(summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a contract/payment-ledger acquisition scaffold without counting it as proof."""

    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    by_entity = {row["entity"]: row for row in summary_rows}
    recovered_by_entity: dict[str, list[dict[str, Any]]] = {}
    for source in LOCAL_CONTRACT_MONITORING_SOURCES:
        recovered_by_entity.setdefault(str(source["entity"]), []).append(dict(source))
    for target in TARGETS:
        summary = by_entity.get(target["name"], {})
        official_sources = sorted({award["source_url"] for award in target["awards"]})
        recovered_sources = recovered_by_entity.get(target["name"], [])
        query_terms = [
            f"{target['name']} standard agreement",
            f"{target['name']} payment ledger",
            f"{target['name']} monitoring letter",
            f"{target['name']} corrective action Homekey",
        ]
        if ACTIVE_PROFILE == "sf_homelessness":
            query_terms = [
                f"{target['name']} SF HSH contract",
                f"{target['name']} San Francisco payment ledger",
                f"{target['name']} HSH monitoring letter",
                f"{target['name']} corrective action San Francisco homelessness",
            ]
        if any(award.get("county") == "Los Angeles" for award in target["awards"]):
            official_sources.extend([LA_CITY_CLERK_BASE_URL, LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL, LA_CITY_SHELBY_2026_OPERATIONS_URL])
        official_sources.extend(source["source_url"] for source in recovered_sources)
        if ACTIVE_PROFILE == "sf_homelessness":
            official_sources.extend([SF_NONPROFIT_SPENDING_DATASET_URL, SF_NONPROFIT_SPENDING_DASHBOARD_URL, SF_NONPROFIT_SPENDING_API])
        citation_ready_payment = ACTIVE_PROFILE == "sf_homelessness"
        rows.append(
            {
                "entity": target["name"],
                "rank": summary.get("rank"),
                "state_award_exposure": summary.get("total_award_exposure"),
                "project_count": summary.get("project_count"),
                "counties": summary.get("counties", []),
                "contract_or_payment_record_recovered": bool(recovered_sources) or citation_ready_payment,
                "standard_agreement_status": "not_recovered",
                "payment_ledger_status": "official_sf_open_data_completed_payment_aggregation_recovered" if citation_ready_payment else "not_recovered",
                "monitoring_or_corrective_action_status": "local_project_or_application_source_recovered" if recovered_sources else "not_recovered",
                "recovered_source_count": len(recovered_sources),
                "recovered_sources": recovered_sources,
                "official_sources_to_search": sorted(
                    set(
                        official_sources
                        + (
                            [SF_NONPROFIT_SPENDING_DATASET_URL, SF_NONPROFIT_SPENDING_DASHBOARD_URL, SF_HOMELESSNESS_DATA_URL]
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else [HCD_ROUND3_ELIGIBILITY_URL, HCD_PLUS_ELIGIBILITY_URL, HCD_HOMEKEY_FUNDING_URL]
                        )
                    )
                ),
                "query_terms": query_terms,
                "source_gap": not citation_ready_payment,
                "reviewer_action": (
                    "Use the SF Open Data payment aggregation as citation-ready payment exposure, then request exact contracts, invoices, deliverables, monitoring letters, corrective actions, and program outcome records before making entity-level findings."
                    if citation_ready_payment
                    else "Request or retrieve standard agreements, amendments, payment ledgers, monitoring letters, corrective actions, and deliverable records before making entity-level findings."
                ),
            }
        )
    table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": (
            "Systematic San Francisco contract/payment acquisition table. Official SF Open Data completed-payment aggregation counts as citation-ready payment exposure; exact contracts, invoices, monitoring, corrective actions, and deliverables remain follow-up records."
            if ACTIVE_PROFILE == "sf_homelessness"
            else "Systematic contract/payment-ledger discovery scaffold for every top-15 entity. Rows preserve acquisition gaps and do not count as citation-ready contract evidence."
        ),
        "rows": rows,
        "row_count": len(rows),
        "recovered_local_source_count": sum(len(row.get("recovered_sources") or []) for row in rows),
        "source_family": "county_contract_monitoring",
    }
    write_json(CONTRACT_DIR / "contract_payment_discovery_summary.json", table)
    return table


ENFORCEMENT_SEARCH_TERMS = [
    "indictment",
    "charged",
    "prosecution",
    "settlement",
    "violation",
    "fraud",
    "corrective action",
    "monitoring letter",
]

PUBLIC_ENFORCEMENT_SEARCH_SOURCES = [
    {
        "source_id": "us_doj_searchgov",
        "name": "U.S. Department of Justice official Search.gov index",
        "base_url": US_DOJ_SEARCH_URL,
        "query_param": "query",
        "extra_params": {"affiliate": "justice"},
        "no_results_markers": ["No results found", "Your search did not match any documents"],
    },
    {
        "source_id": "fhfa_oig_site_search",
        "name": "Federal Housing Finance Agency Office of Inspector General site search",
        "base_url": FHFA_OIG_SEARCH_URL,
        "query_param": "search",
        "extra_params": {},
        "no_results_markers": ["No results found", "no results"],
    },
]

MANUAL_ENFORCEMENT_SEARCH_SOURCES = [
    {"source_id": "pacer_case_locator", "name": "PACER Case Locator", "source_url": PACER_FIND_CASE_URL, "reason": "Requires PACER account and controlled export for docket-level federal search."},
    {"source_id": "california_trial_courts", "name": "California trial court portals", "source_url": CA_COURTS_LOOKUP_GUIDE_URL, "reason": "California trial-court records are accessed through local court portals or clerk offices."},
    {"source_id": "california_doj_charity_registry", "name": "California DOJ Registry of Charities and Fundraisers", "source_url": CA_DOJ_CHARITY_REGISTRY_URL, "reason": "Interactive registry search should be captured as a saved result or official export."},
]

ENTITY_COURT_PORTALS = {
    "Hope the Mission": [LA_SUPERIOR_COURT_CASE_ACCESS_URL],
    "Weingart Center Association": [LA_SUPERIOR_COURT_CASE_ACCESS_URL],
    "DignityMoves": [ALAMEDA_SUPERIOR_COURT_DOMAIN_URL, SAN_BERNARDINO_SUPERIOR_COURT_DOMAIN_URL, VENTURA_SUPERIOR_COURT_DOMAIN_URL],
    "The People Concern": [LA_SUPERIOR_COURT_CASE_ACCESS_URL],
    "California Supportive Housing": [ALAMEDA_SUPERIOR_COURT_DOMAIN_URL, SACRAMENTO_SUPERIOR_COURT_DOMAIN_URL],
}


def enforcement_search_url(source: dict[str, Any], query: str) -> str:
    params = dict(source.get("extra_params") or {})
    params[str(source["query_param"])] = query
    return f"{source['base_url']}?{urllib.parse.urlencode(params)}"


def public_enforcement_search_runs(target: dict[str, Any]) -> list[dict[str, Any]]:
    search_dir = DOCKET_DIR / "public_searches"
    search_dir.mkdir(parents=True, exist_ok=True)
    aliases = [target["name"], *target.get("aliases", [])]
    query_names = []
    for alias in aliases:
        cleaned = normalize_space(alias)
        if cleaned and cleaned not in query_names:
            query_names.append(cleaned)
    query_names = query_names[:2]
    rows: list[dict[str, Any]] = []
    for source in PUBLIC_ENFORCEMENT_SEARCH_SOURCES:
        for query_name in query_names:
            query = f'"{query_name}" ({ " OR ".join(ENFORCEMENT_SEARCH_TERMS[:6]) })'
            search_url = enforcement_search_url(source, query)
            stem = f"{target['slug']}_{source['source_id']}_{len(rows) + 1}"
            row: dict[str, Any] = {
                "entity": target["name"],
                "source_id": source["source_id"],
                "source_name": source["name"],
                "query": query,
                "query_name": query_name,
                "search_url": search_url,
                "status": "error",
                "completed": False,
                "possible_public_adverse_hit": False,
                "result_interpretation": "not_completed",
                "local_html_path": "",
                "local_text_path": "",
                "error": "",
            }
            try:
                raw, final_url, content_type = fetch_bytes(search_url, timeout=45, attempts=1)
                text = html_to_text(raw)
                lower = text.lower()
                marker_text = f"{raw.decode('utf-8', 'replace')}\n{text}".lower()
                no_results = any(marker.lower() in marker_text for marker in source.get("no_results_markers", []))
                legal_terms_present = any(term in lower for term in ENFORCEMENT_SEARCH_TERMS)
                query_name_present = normalize_name(query_name) in normalize_name(text)
                if no_results:
                    status = "searched_no_public_official_record"
                    interpretation = "official_search_returned_no_results"
                    possible_hit = False
                elif query_name_present and legal_terms_present:
                    status = "possible_public_search_hit_needs_review"
                    interpretation = "search_page_contains_entity_and_legal_terms"
                    possible_hit = True
                else:
                    status = "searched_no_obvious_public_official_record"
                    interpretation = "search_page_fetched_without_entity_legal_hit"
                    possible_hit = False
                html_path = search_dir / f"{stem}.html"
                text_path = search_dir / f"{stem}.txt"
                html_path.write_bytes(raw)
                text_path.write_text(text[:20000], encoding="utf-8")
                row.update(
                    {
                        "status": status,
                        "completed": True,
                        "possible_public_adverse_hit": possible_hit,
                        "result_interpretation": interpretation,
                        "final_url": final_url,
                        "content_type": content_type,
                        "text_chars": len(text),
                        "local_html_path": str(html_path),
                        "local_text_path": str(text_path),
                        "summary": snippet(text, [query_name, "No results", "results"], radius=240),
                    }
                )
            except Exception as exc:
                row.update({"status": "source_error", "error": repr(exc)})
            rows.append(row)
    return rows


def enforcement_docket_discovery_artifacts(enforcement_table: dict[str, Any]) -> dict[str, Any]:
    """Record systematic official-source enforcement/docket search targets for all entities."""

    DOCKET_DIR.mkdir(parents=True, exist_ok=True)
    official_entities = {str(row.get("entity")) for row in enforcement_table.get("rows", [])}
    rows: list[dict[str, Any]] = []
    public_search_rows: list[dict[str, Any]] = []
    for target in TARGETS:
        entity = target["name"]
        has_official_row = entity in official_entities
        searches = public_enforcement_search_runs(target)
        public_search_rows.extend(searches)
        completed = [row for row in searches if row.get("completed")]
        possible_hits = [row for row in completed if row.get("possible_public_adverse_hit")]
        manual_sources = [*MANUAL_ENFORCEMENT_SEARCH_SOURCES]
        for portal in ENTITY_COURT_PORTALS.get(entity, []):
            manual_sources.append({"source_id": "local_trial_court_portal", "name": "Local trial court portal", "source_url": portal, "reason": "Requires local court search workflow, saved results, or clerk-office access."})
        if has_official_row:
            status = "citation_ready_official_row_present"
            source_gap = False
        elif completed and not possible_hits:
            status = "searched_no_public_official_record"
            source_gap = False
        elif possible_hits:
            status = "possible_public_search_hit_needs_manual_review"
            source_gap = True
        else:
            status = "systematic_search_gap"
            source_gap = True
        rows.append(
            {
                "entity": entity,
                "official_enforcement_row_recovered": has_official_row,
                "status": status,
                "source_gap": source_gap,
                "public_official_search_completed_count": len(completed),
                "public_official_search_possible_hit_count": len(possible_hits),
                "public_official_searches": searches,
                "manual_sources_remaining": manual_sources,
                "official_sources_to_search": [
                    US_DOJ_BASE_URL,
                    FHFA_OIG_HOMELESSNESS_FUNDS_PRESS_RELEASE_URL,
                    US_COURTS_PACER_URL,
                    CA_COURTS_URL,
                    LA_CITY_CLERK_BASE_URL,
                    CA_DOJ_CHARITY_REGISTRY_URL,
                    *[source["source_url"] for source in manual_sources],
                ],
                "query_terms": [
                    f'"{entity}" indictment',
                    f'"{entity}" prosecution',
                    f'"{entity}" settlement',
                    f'"{entity}" violation',
                    f'"{entity}" corrective action',
                    f'"{entity}" monitoring letter',
                ],
                "reviewer_action": "Search official agency, court, inspector-general, and municipal records; preserve named-party distinctions and presumption-of-innocence caveats. Public no-result search is not legal clearance; PACER/local-court/manual registry searches may still be required.",
            }
        )
    table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": "Every top-15 entity receives official public enforcement search attempts plus manual-source instructions. Recovered official adverse rows remain hits; completed public official searches with no public adverse result remain source-access blockers, not clearance.",
        "rows": rows,
        "public_search_rows": public_search_rows,
        "row_count": len(rows),
        "public_search_row_count": len(public_search_rows),
        "source_family": "enforcement_or_docket",
    }
    write_json(DOCKET_DIR / "enforcement_docket_discovery_summary.json", table)
    return table


def fetch_spm_rows() -> list[dict[str, Any]]:
    OUTCOME_DIR.mkdir(parents=True, exist_ok=True)
    params = urllib.parse.urlencode({"resource_id": CA_SPM_RESOURCE_ID, "limit": 1000})
    raw, final_url, content_type = fetch_bytes(f"{CA_SPM_API}?{params}", timeout=90)
    data = json.loads(raw.decode("utf-8", "replace"))
    if not data.get("success"):
        raise RuntimeError(f"CA SPM datastore request failed: {data}")
    rows = data.get("result", {}).get("records", [])
    write_json(
        OUTCOME_DIR / "ca_spm_raw_records.json",
        {
            "source_url": CA_SPM_SOURCE_URL,
            "api_url": f"{CA_SPM_API}?{params}",
            "final_url": final_url,
            "content_type": content_type,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def number(value: Any) -> float | None:
    try:
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def pct_change(previous: float, current: float) -> float:
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return ((current - previous) / abs(previous)) * 100.0


def match_spm_location(county: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    metric_rows = [row for row in rows if row.get("Metric") == "M1a"]
    hints = COUNTY_COC_HINTS.get(county, [county])
    for hint in hints:
        hint_lower = hint.lower()
        for row in metric_rows:
            if hint_lower in str(row.get("Location", "")).lower():
                return row
    return None


def spm_change_for_county(county: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    row = match_spm_location(county, rows)
    if not row:
        return None
    previous_period = "Jan 2023 - Dec 2023"
    current_period = "Jul 2024 - Jun 2025"
    previous = number(row.get(previous_period))
    current = number(row.get(current_period))
    if previous is None or current is None:
        return None
    return {
        "location": row.get("Location"),
        "metric": "M1a",
        "metric_description": "People who accessed homelessness services and housing in the official Continuum of Care geography.",
        "previous_period": previous_period,
        "previous_value": previous,
        "current_period": current_period,
        "current_value": current,
        "change_pct": pct_change(previous, current),
    }


def outcome_artifacts(summary_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    spm_rows = fetch_spm_rows()
    manifest = {
        "created_at": now(),
        "sources": {
            "ca_spm": {
                "title": "CA System Performance Measures, Statewide and by CoC",
                "source_url": CA_SPM_SOURCE_URL,
                "api_base": CA_SPM_API,
                "resource_id": CA_SPM_RESOURCE_ID,
                "row_count": len(spm_rows),
                "fetched": True,
                "join_grain": "Continuum of Care/year-period/metric",
            },
            "hdis_context": {
                "title": "California Homeless Data Integration System context",
                "source_url": HDIS_URL,
                "fetched": True,
                "join_grain": "statewide and Continuum of Care context",
            },
        },
        "methodology": (
            "Official CA SPM M1a rows are matched by San Francisco geography to the SF HSH completed-payment supplier list. This is contextual screening and not provider attribution."
            if ACTIVE_PROFILE == "sf_homelessness"
            else "Official CA SPM M1a rows are matched by county-name text to the counties listed in HCD Homekey/Homekey+ award rows. This is contextual screening and not provider attribution."
        ),
    }
    entity_rows = []
    for row in summary_rows:
        county_changes = []
        flags = []
        for county in row["counties"]:
            change = spm_change_for_county(county, spm_rows)
            if not change:
                continue
            county_changes.append({"county": county, **change})
            if change["change_pct"] > 0:
                flags.append(
                    f"{county} Continuum of Care M1a service-system volume increased from {change['previous_value']:,.0f} in {change['previous_period']} to {change['current_value']:,.0f} in {change['current_period']} ({change['change_pct']:+.1f}%)"
                )
        risk_level = "High" if row["total_award_exposure"] >= 50_000_000 and flags else "Medium" if flags else "Low"
        if flags:
            entity_rows.append(
                {
                    "entity": row["entity"],
                    "county": ", ".join(row["counties"]),
                    "risk_level": risk_level,
                    "outcome_flags": flags,
                    "state_award_exposure": row["total_award_exposure"],
                    "public_funding_exposure": row["total_award_exposure"],
                    "state_project_count": row["project_count"],
                    "spending_growth_pct": None,
                    "revenue_growth_pct": None,
                    "government_grant_growth_pct": None,
                    "homelessness_spm_change": county_changes,
                    "join_caveats": [
                        "County and Continuum of Care outcomes are not provider-attributable without direct program outcome records.",
                        (
                            "This join compares SF HSH completed-payment exposure to official geography-level homelessness service-system movement, not audited program performance or client outcomes."
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else "This join compares state project-award exposure to official geography-level homelessness service-system movement, not audited spend or client outcomes."
                        ),
                        (
                            "The completed-payment exposure total is a supplier-name aggregation; exact contract scope, allowability, deliverables, and outcomes still require contract-file review."
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else "The award-list exposure total is not a verified direct-payment total to the nonprofit."
                        ),
                    ],
                }
            )
    join = {
        "created_at": now(),
        "methodology": manifest["methodology"],
        "entity_outcome_rows": entity_rows,
        "row_count": len(entity_rows),
    }
    write_json(OUTCOME_DIR / "official_outcome_source_manifest.json", manifest)
    write_json(OUTCOME_DIR / "outcome_join_summary.json", join)
    return manifest, join


def markdown_table(rows: list[dict[str, Any]], columns: list[str], limit: int = 60) -> str:
    shown = rows[:limit]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in shown:
        values = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                value = money(value) if "award" in column or "amount" in column else f"{value:.1f}"
            values.append(normalize_space(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    if len(rows) > limit:
        lines.append("| " + " | ".join([f"+{len(rows) - limit} additional row(s)", *("" for _ in columns[1:])]) + " |")
    return "\n".join(lines)


def top_award_summary_lines(summary_rows: list[dict[str, Any]], limit: int = 15) -> str:
    if ACTIVE_PROFILE == "sf_homelessness":
        lines = ["Top source-ranked San Francisco HSH completed-payment exposures from official SF Open Data:"]
    else:
        lines = ["Top source-ranked co-applicant project-award exposures from official HCD tables:"]
    for row in summary_rows[:limit]:
        if ACTIVE_PROFILE == "sf_homelessness":
            lines.append(
                "- Rank {rank}: {entity} appears in SF HSH completed-payment aggregation with {exposure} in payment exposure across {counties}.".format(
                    rank=row["rank"],
                    entity=row["entity"],
                    exposure=money(float(row["total_award_exposure"])),
                    counties=row["counties"],
                )
            )
        else:
            lines.append(
                "- Rank {rank}: {entity} appears on {project_count} Homekey/Homekey+ project-award row(s), "
                "with {exposure} in attached project-award exposure across {counties}.".format(
                    rank=row["rank"],
                    entity=row["entity"],
                    project_count=row["project_count"],
                    exposure=money(float(row["total_award_exposure"])),
                    counties=row["counties"],
                )
            )
    return "\n".join(lines)


def write_corpus(corpus_dir: Path, artifacts_dir: Path | None = None) -> None:
    global TARGETS
    corpus_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = artifacts_dir or corpus_dir / "_source_artifacts"
    reset_run_scoped_artifact_dir(corpus_dir, artifacts_dir)
    configure_artifact_dirs(artifacts_dir)
    if ACTIVE_PROFILE == "sf_homelessness":
        TARGETS = sf_targets_from_payments(ACTIVE_TARGET_LIMIT)
    for old in corpus_dir.glob("*.json"):
        old.unlink()

    source_manifest = download_source_docs()
    page_manifest = fetch_all_pages()
    summary_rows = award_summary_rows()
    award_table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": (
            "Rank San Francisco homelessness-service candidates by completed-payment exposure from official SF Open Data, then boost citation-ready official adverse-record seeds for mandatory triage."
            if ACTIVE_PROFILE == "sf_homelessness"
            else "Rank source-listed nonprofit co-applicant names by the full HCD project-award amount attached to each Homekey/Homekey+ row. This is award exposure, not proof of direct receipt."
        ),
        "source_documents": source_manifest,
        "eligibility_sources": (
            [SF_NONPROFIT_SPENDING_DATASET_URL, SF_NONPROFIT_SPENDING_DASHBOARD_URL, SF_HOMELESSNESS_DATA_URL]
            if ACTIVE_PROFILE == "sf_homelessness"
            else [HCD_ROUND3_ELIGIBILITY_URL, HCD_PLUS_ELIGIBILITY_URL, HCD_HOMEKEY_FUNDING_URL]
        ),
        "entity_award_summary": summary_rows,
        "caveats": [
            (
                "SF Open Data completed-payment aggregation is public-dollar exposure by supplier name; it is not a finding that any payment was improper."
                if ACTIVE_PROFILE == "sf_homelessness"
                else "HCD award lists name eligible applicants and co-applicants; allocation among co-applicants is not stated in the award tables."
            ),
            (
                "Official adverse-record seeds are included so a lower-payment entity with a public-record ding is not missed at intake."
                if ACTIVE_PROFILE == "sf_homelessness"
                else "HHAP and ESG allocation pages were not used for the top-15 ranking because they do not provide a statewide nonprofit subrecipient table comparable to the Homekey award lists."
            ),
        ],
        "profile": ACTIVE_PROFILE,
    }
    award_table_path = RAW_DIR / "state_homeless_award_summary.json"
    write_json(award_table_path, award_table)

    outcome_manifest, join_summary = outcome_artifacts(summary_rows)
    enforcement_table = enforcement_docket_artifacts()
    tax_table = propublica_artifacts()
    raw_tax_table = raw_irs_990_artifacts(tax_table)
    fac_table = fac_audit_artifacts(tax_table)
    contract_discovery_table = contract_payment_discovery_artifacts(summary_rows)
    enforcement_discovery_table = enforcement_docket_discovery_artifacts(enforcement_table)

    records: list[dict[str, Any]] = []
    entities = [target["name"] for target in TARGETS]
    records.append(
        build_record(
            "source_table_state_homeless_awards",
            (
                "Parsed San Francisco HSH nonprofit completed-payment exposure table"
                if ACTIVE_PROFILE == "sf_homelessness"
                else "Parsed HCD Homekey/Homekey+ state homelessness award exposure table"
            ),
            str(award_table_path),
            "source_extraction_sf_hsh_payment_table" if ACTIVE_PROFILE == "sf_homelessness" else "source_extraction_state_homeless_award_table",
            "2026-05-02" if ACTIVE_PROFILE == "sf_homelessness" else "2026-02-18",
            entities,
            "\n".join(
                [
                    (
                        "Parsed San Francisco Open Data completed-payment exposure table for the Department of Homelessness and Supportive Housing."
                        if ACTIVE_PROFILE == "sf_homelessness"
                        else "Parsed California Department of Housing and Community Development Homekey/Homekey+ award exposure table."
                    ),
                    (
                        "Methodology: rank supplier names by official completed-payment exposure, then add official adverse-record seeds so the intake pass does not miss lower-payment public-record dings."
                        if ACTIVE_PROFILE == "sf_homelessness"
                        else "Methodology: rank source-listed nonprofit co-applicant names by the full project-award amount attached to each award row. This is materiality exposure, not direct-payment proof."
                    ),
                    top_award_summary_lines(summary_rows),
                    "Official source URLs:",
                    *(
                        [SF_NONPROFIT_SPENDING_DATASET_URL, SF_NONPROFIT_SPENDING_DASHBOARD_URL, SF_HOMELESSNESS_DATA_URL]
                        if ACTIVE_PROFILE == "sf_homelessness"
                        else [HCD_ROUND3_URL, HCD_PLUS_URL, HCD_ROUND3_ELIGIBILITY_URL, HCD_PLUS_ELIGIBILITY_URL]
                    ),
                    markdown_table(summary_rows, ["rank", "entity", "total_award_exposure", "project_count", "programs", "counties", "projects"], limit=20),
                ]
            ),
            {
                "state_homelessness_award_table": True,
                "source_extraction_table": True,
                "state_homelessness_award_exposure": True,
                "sf_hsh_completed_payment_exposure": ACTIVE_PROFILE == "sf_homelessness",
            },
            {
                "table_path": str(award_table_path),
                "row_count": len(summary_rows),
                "source_urls": [SF_NONPROFIT_SPENDING_DATASET_URL, SF_NONPROFIT_SPENDING_DASHBOARD_URL]
                if ACTIVE_PROFILE == "sf_homelessness"
                else [HCD_ROUND3_URL, HCD_PLUS_URL],
            },
        )
    )

    outcome_record = build_record(
        "source_table_official_homelessness_outcomes",
        "Official homelessness outcome-source manifest",
        str(OUTCOME_DIR / "official_outcome_source_manifest.json"),
        "source_extraction_official_outcome_table",
        "2025-12-22",
        entities,
        "\n".join(
            [
                "Official homelessness outcome-source manifest for spend-versus-results review.",
                "The CA System Performance Measures dataset says the metrics help assess progress toward preventing, reducing, and ending homelessness. CalDS uses these rows as geography-level context only.",
                CA_SPM_SOURCE_URL,
                HDIS_URL,
                json.dumps(outcome_manifest.get("sources", {}), indent=2, sort_keys=True),
            ]
        ),
        {"official_outcome_sources_indexed": True, "source_extraction_table": True, "outcome_context_present": True},
        {"manifest_path": str(OUTCOME_DIR / "official_outcome_source_manifest.json"), "table_path": str(OUTCOME_DIR / "official_outcome_source_manifest.json")},
    )
    records.append(outcome_record)

    join_record = build_record(
        "source_table_spend_vs_results_join",
        (
            "Deterministic SF HSH completed-payment exposure versus homelessness outcome-context join"
            if ACTIVE_PROFILE == "sf_homelessness"
            else "Deterministic state-award exposure versus homelessness outcome-context join"
        ),
        str(OUTCOME_DIR / "outcome_join_summary.json"),
        "source_extraction_spend_vs_results_table",
        "2026-04-29",
        entities,
        "\n".join(
            [
                (
                    "Deterministic join from SF HSH completed-payment exposure to official San Francisco Continuum of Care homelessness outcome context."
                    if ACTIVE_PROFILE == "sf_homelessness"
                    else "Deterministic join from HCD state project-award exposure to official county/Continuum of Care homelessness outcome context."
                ),
                "County and Continuum of Care outcomes are not provider-attributable without direct program outcome records.",
                markdown_table(
                    join_summary.get("entity_outcome_rows", []),
                    (
                        ["entity", "county", "risk_level", "public_funding_exposure", "outcome_flags"]
                        if ACTIVE_PROFILE == "sf_homelessness"
                        else ["entity", "county", "risk_level", "state_award_exposure", "state_project_count", "outcome_flags"]
                    ),
                    limit=80,
                ),
            ]
        ),
        {"spend_vs_results_join_created": True, "source_extraction_table": True, "outcome_context_present": bool(join_summary.get("entity_outcome_rows"))},
        {"join_summary_path": str(OUTCOME_DIR / "outcome_join_summary.json"), "table_path": str(OUTCOME_DIR / "outcome_join_summary.json"), "row_count": join_summary.get("row_count")},
    )
    records.append(join_record)

    tax_rows = list(tax_table.get("rows", []))
    tax_matches = list(tax_table.get("matches", []))
    tax_entities = sorted({row["entity"] for row in tax_rows})
    records.append(
        build_record(
            "source_table_irs_990_propublica",
            "ProPublica Nonprofit Explorer IRS Form 990 filing summary table",
            str(PROPUBLICA_DIR / "propublica_irs_990_summary.json"),
            "source_extraction_irs_990_table",
            "2026-04-30",
            tax_entities or entities,
            "\n".join(
                [
                    "ProPublica Nonprofit Explorer API filing summary for top-15 homelessness triage.",
                    "ProPublica provides a public API and viewer for IRS nonprofit filing data. CalDS treats this as an access layer; raw IRS XML/PDF filings remain controlling source documents.",
                    f"ProPublica API documentation: {PROPUBLICA_API_DOC_URL}",
                    f"IRS Form 990 downloads: {IRS_FORM_990_DOWNLOADS_URL}",
                    f"IRS tax-exempt bulk data: {IRS_TEOS_BULK_URL}",
                    markdown_table(
                        tax_rows,
                        [
                            "entity",
                            "ein",
                            "tax_period_year",
                            "total_revenue",
                            "total_expenses",
                            "officer_compensation_total",
                            "pdf_url",
                        ],
                        limit=120,
                    ),
                ]
            ),
            {"source_extraction_table": True, "irs_990_table": True, "propublica_nonprofit_api_checked": True, "irs_990_full_text_fallback": False},
            {
                "table_path": str(PROPUBLICA_DIR / "propublica_irs_990_summary.json"),
                "row_count": len(tax_rows),
                "matched_entity_count": len({match["entity"] for match in tax_matches if match.get("status") == "matched"}),
                "filing_row_entity_count": len(tax_entities),
                "matches": tax_matches,
                "source_urls": [PROPUBLICA_API_DOC_URL, IRS_FORM_990_DOWNLOADS_URL, IRS_TEOS_BULK_URL],
            },
        )
    )

    raw_tax_rows = list(raw_tax_table.get("rows", []))
    raw_tax_entities = sorted({row["entity"] for row in raw_tax_rows})
    records.append(
        build_record(
            "source_table_irs_990_raw_artifacts",
            "Raw IRS Form 990 artifact acquisition table",
            str(IRS_RAW_DIR / "raw_irs_990_artifact_summary.json"),
            "source_extraction_irs_990_raw_artifact_table",
            "2026-04-30",
            raw_tax_entities or tax_entities or entities,
            "\n".join(
                [
                    "Raw IRS Form 990 artifact acquisition for top-15 homelessness triage.",
                    "The table archives the latest full Form 990 PDF when a public filing URL is available and probes candidate IRS XML URLs. Missing XML remains an explicit source gap.",
                    f"PDFs downloaded: {raw_tax_table.get('pdf_downloaded_count', 0)} of {raw_tax_table.get('row_count', 0)} matched entities.",
                    f"IRS XML index confirmations: {raw_tax_table.get('xml_index_confirmed_count', 0)} of {raw_tax_table.get('row_count', 0)} matched entities.",
                    f"IRS XML files downloaded: {raw_tax_table.get('xml_downloaded_count', 0)} of {raw_tax_table.get('row_count', 0)} matched entities.",
                    markdown_table(raw_tax_rows, ["entity", "ein", "tax_period_year", "pdf_downloaded", "irs_index_confirmed", "xml_downloaded", "raw_source_status"], limit=40),
                ]
            ),
            {
                "source_extraction_table": True,
                "irs_990_raw_artifact_table": True,
                "full_990_pdf_acquisition_attempted": True,
                "irs_990_xml_index_confirmed_count": raw_tax_table.get("xml_index_confirmed_count", 0),
                "irs_990_xml_unresolved": int(raw_tax_table.get("xml_downloaded_count") or 0) < int(raw_tax_table.get("row_count") or 0),
                "missing_data": int(raw_tax_table.get("xml_downloaded_count") or 0) < int(raw_tax_table.get("row_count") or 0),
            },
            {
                "table_path": str(IRS_RAW_DIR / "raw_irs_990_artifact_summary.json"),
                "row_count": len(raw_tax_rows),
                "pdf_downloaded_count": raw_tax_table.get("pdf_downloaded_count", 0),
                "xml_index_confirmed_count": raw_tax_table.get("xml_index_confirmed_count", 0),
                "xml_downloaded_count": raw_tax_table.get("xml_downloaded_count", 0),
                "source_urls": raw_tax_table.get("source_urls", []),
            },
        )
    )
    for row in raw_tax_rows:
        entity = row["entity"]
        pdf_downloaded = bool(row.get("pdf_downloaded"))
        xml_index_confirmed = bool(row.get("irs_index_confirmed"))
        records.append(
            build_record(
                f"irs_990_raw_artifacts_{slugify(entity)}",
                f"Raw Form 990 artifact acquisition: {entity}",
                row.get("pdf_url") if pdf_downloaded else row.get("irs_xml_zip_url") or propublica_org_page(row.get("ein", "")),
                "irs_990_raw_artifact" if (pdf_downloaded or xml_index_confirmed) else "irs_990_raw_artifact_discovery",
                str(row.get("tax_period_year") or "2026"),
                [entity],
                "\n".join(
                    [
                        f"Latest matched Form 990 filing for {entity}: EIN {row.get('ein')}, tax period year {row.get('tax_period_year')}.",
                        f"Full PDF downloaded: {row.get('pdf_downloaded')} local path: {row.get('pdf_local_path') or 'not archived'}.",
                        f"PDF SHA256: {row.get('pdf_sha256') or 'not available'}.",
                        f"IRS object ID: {row.get('irs_object_id') or 'not available'}.",
                        f"Official IRS XML index confirmed: {row.get('irs_index_confirmed')} batch ZIP: {row.get('irs_xml_zip_url') or 'not available'}.",
                        f"Candidate IRS XML URLs checked: {', '.join(row.get('xml_candidate_urls') or []) or 'none'}",
                        f"IRS XML downloaded: {row.get('xml_downloaded')} local path: {row.get('xml_local_path') or 'not archived'}; ZIP entry: {row.get('xml_zip_entry', {}).get('filename') if isinstance(row.get('xml_zip_entry'), dict) else ''}.",
                        f"IRS XML SHA256: {row.get('xml_sha256') or 'not available'}.",
                        f"Parsed summary fields from ProPublica/IRS extract: {json.dumps(row.get('parsed_detail_fields', {}), sort_keys=True)}",
                        "Caveats:",
                        *[f"- {caveat}" for caveat in row.get("caveats", [])],
                    ]
                ),
                {
                    "irs_990_raw_artifact": True,
                    "full_990_pdf_downloaded": pdf_downloaded,
                    "raw_990_pdf_available": pdf_downloaded,
                    "irs_990_xml_index_confirmed": xml_index_confirmed,
                    "irs_990_xml_zip_available": xml_index_confirmed,
                    "irs_990_xml_downloaded": bool(row.get("xml_downloaded")),
                    "irs_990_xml_unresolved": not bool(row.get("xml_downloaded")),
                    "not_citation_ready": not (pdf_downloaded or xml_index_confirmed),
                    "missing_data": not bool(row.get("xml_downloaded")),
                },
                {
                    "ein": row.get("ein"),
                    "tax_period_year": row.get("tax_period_year"),
                    "irs_object_id": row.get("irs_object_id"),
                    "irs_index_entry": row.get("irs_index_entry"),
                    "irs_xml_zip_url": row.get("irs_xml_zip_url"),
                    "pdf_local_path": row.get("pdf_local_path"),
                    "pdf_sha256": row.get("pdf_sha256"),
                    "xml_probe_results": row.get("xml_probe_results", []),
                    "parsed_detail_fields": row.get("parsed_detail_fields", {}),
                    "source_urls": [row.get("pdf_url"), row.get("irs_xml_zip_url"), *row.get("xml_candidate_urls", [])],
                },
            )
        )

    fac_audit_rows = list(fac_table.get("audit_summary", []))
    fac_award_rows = list(fac_table.get("award_summary", []))
    fac_entities = sorted({row.get("entity") for row in fac_audit_rows if row.get("entity")})
    records.append(
        build_record(
            "source_table_fac_audit",
            "Federal Audit Clearinghouse target audit-source extraction table",
            str(FAC_DIR / "fac_audit_summary.json"),
            "source_extraction_fac_audit_table",
            "2026-04-30",
            fac_entities or tax_entities or entities,
            "\n".join(
                [
                    "Official Federal Audit Clearinghouse CSV extracts filtered to matched top-15 target EINs only. Name fallback is disabled to avoid broad false positives.",
                    "Rows with no Federal Audit Clearinghouse report are coverage results, not adverse findings. Row-level findings and corrective-action text are preserved when matching report IDs are found.",
                    f"FAC current download page: {FAC_DOWNLOAD_CURRENT_URL}",
                    f"Matched audit-summary rows: {len(fac_audit_rows)}.",
                    f"Matched top federal-award rows: {len(fac_award_rows)}.",
                    markdown_table(
                        fac_audit_rows,
                        [
                            "entity",
                            "status",
                            "audit_years",
                            "fac_report_count",
                            "fac_findings_row_count",
                            "fac_award_amount_total",
                            "material_weakness_years",
                            "internal_control_deficiency_years",
                            "material_noncompliance_years",
                        ],
                        limit=40,
                    ),
                ]
            ),
            {
                "source_extraction_table": True,
                "fac_audit_table": True,
                "fac_official_csv_filtered": True,
                "audit_source_coverage": True,
                "missing_data": bool(fac_table.get("errors")),
            },
            {
                "table_path": str(FAC_DIR / "fac_audit_summary.json"),
                "row_count": len(fac_audit_rows),
                "award_row_count": len(fac_award_rows),
                "source_urls": fac_table.get("source_urls", []),
                "errors": fac_table.get("errors", []),
            },
        )
    )
    for row in fac_audit_rows:
        entity = str(row.get("entity") or "")
        if not entity:
            continue
        records.append(
            build_record(
                f"fac_audit_summary_{slugify(entity)}",
                f"Federal Audit Clearinghouse coverage: {entity}",
                FAC_DOWNLOAD_CURRENT_URL,
                "fac_audit_summary",
                "2026-04-30",
                [entity],
                "\n".join(
                    [
                        f"FAC coverage status for {entity}: {row.get('status')}.",
                        f"Matched report IDs: {', '.join(row.get('report_ids') or []) or 'none'}; audit years: {', '.join(row.get('audit_years') or []) or 'none'}.",
                        f"Findings rows: {row.get('fac_findings_row_count')}; federal award amount total in matched rows: {money(float(row.get('fac_award_amount_total') or 0))}.",
                        f"Material weakness years: {', '.join(row.get('material_weakness_years') or []) or 'none'}.",
                        f"Internal-control deficiency years: {', '.join(row.get('internal_control_deficiency_years') or []) or 'none'}.",
                        f"Material noncompliance years: {', '.join(row.get('material_noncompliance_years') or []) or 'none'}.",
                    ]
                ),
                {
                    "fac_audit_summary": True,
                    "fac_report_found": row.get("status") == "fac_report_found",
                    "fac_no_report_found": row.get("status") == "no_fac_report_found_for_matched_ein",
                    "missing_data": False,
                },
                {
                    "report_ids": row.get("report_ids", []),
                    "audit_years": row.get("audit_years", []),
                    "matched_eins": row.get("matched_eins", []),
                    "source_urls": fac_table.get("source_urls", []),
                    "table_path": str(FAC_DIR / "fac_audit_summary.json"),
                },
            )
        )

    enforcement_rows = list(enforcement_table.get("rows", []))
    enforcement_entities = sorted({row["entity"] for row in enforcement_rows})
    records.append(
        build_record(
            "source_table_enforcement_docket",
            "Parsed official enforcement and docket source table",
            str(RAW_DIR / "enforcement_docket_source_summary.json"),
            "source_extraction_enforcement_docket_table",
            "2025-10-16",
            enforcement_entities,
            "\n".join(
                [
                    "Official enforcement and docket source table for top-15 homelessness triage.",
                    "This table creates deep-dive triggers only. It does not create legal conclusions.",
                    json.dumps(enforcement_table, indent=2, sort_keys=True),
                ]
            ),
            {"source_extraction_table": True, "official_enforcement_or_docket_table": True},
            {"table_path": str(RAW_DIR / "enforcement_docket_source_summary.json"), "row_count": len(enforcement_rows)},
        )
    )
    for index, row in enumerate(enforcement_rows, start=1):
        entity = row["entity"]
        records.append(
            build_record(
                f"enforcement_docket_{slugify(entity)}_{index}",
                f"Official enforcement/docket triage source: {entity}",
                row["source_urls"][0],
                "enforcement_or_docket_source",
                "2025-10-16",
                [entity],
                "\n".join(
                    [
                        row["observed_fact"],
                        "Official source URLs:",
                        *row["source_urls"],
                        "Caveats:",
                        *[f"- {caveat}" for caveat in row.get("caveats", [])],
                    ]
                ),
                {
                    "official_enforcement_or_docket_flag": True,
                    "third_party_charged": "third_party_charged" in str(row.get("legal_status", "")),
                    "connected_party_enforcement_exposure": bool(row.get("connected_party_entity_trigger")),
                    "automatic_deep_dive_trigger": bool(row.get("connected_party_entity_trigger")),
                    "missing_data": True,
                },
                {
                    "legal_status": row.get("legal_status"),
                    "relationship_type": row.get("relationship_type"),
                    "trigger_confidence": row.get("trigger_confidence"),
                    "source_urls": row.get("source_urls", []),
                    "reviewer_action": row.get("reviewer_action", ""),
                },
            )
        )

    contract_rows = list(contract_discovery_table.get("rows", []))
    records.append(
        build_record(
            "source_table_contract_payment_discovery",
            "Contract, payment-ledger, and monitoring acquisition gap table",
            str(CONTRACT_DIR / "contract_payment_discovery_summary.json"),
            "source_extraction_contract_payment_discovery_table",
            "2026-04-30",
            entities,
            "\n".join(
                [
                    "Systematic contract/payment-ledger acquisition scaffold for the top-15 homelessness entities.",
                    "These are acquisition tasks and source gaps, not recovered contract findings. They do not count as citation-ready contract evidence.",
                    markdown_table(
                        contract_rows,
                        [
                            "entity",
                            "rank",
                            "state_award_exposure",
                            "project_count",
                            "standard_agreement_status",
                            "payment_ledger_status",
                            "monitoring_or_corrective_action_status",
                        ],
                        limit=30,
                    ),
                ]
            ),
            {
                "contract_payment_discovery_table": True,
                "discovery_only_source_gap": True,
                "source_gap_only": True,
                "missing_data": True,
            },
            {"table_path": str(CONTRACT_DIR / "contract_payment_discovery_summary.json"), "row_count": len(contract_rows)},
        )
    )
    for source_index, source in enumerate(LOCAL_CONTRACT_MONITORING_SOURCES, start=1):
        entity = str(source["entity"])
        records.append(
            build_record(
                f"local_contract_monitoring_{slugify(entity)}_{source_index}",
                f"Official local project/funding source: {entity}",
                str(source["source_url"]),
                str(source.get("source_type") or "city_contract_monitoring_source"),
                "2026-04-30",
                [entity],
                "\n".join(
                    [
                        str(source["observed_fact"]),
                        f"Project context: {source.get('project_context')}.",
                        f"Money context: {source.get('money_context')}.",
                        "Control caveat: this record confirms a local official project, application, authorization, or operating-context source; it does not by itself prove direct receipt, cost allowability, or performance.",
                    ]
                ),
                {
                    "city_contract_monitoring_source": True,
                    "local_project_source_recovered": True,
                    "standard_agreement_or_payment_ledger_missing": True,
                    "missing_data": True,
                },
                {
                    "source_title": source.get("source_title"),
                    "project_context": source.get("project_context"),
                    "money_context": source.get("money_context"),
                    "source_urls": [source.get("source_url")],
                },
            )
        )
    for row in contract_rows:
        entity = row["entity"]
        citation_ready_payment = ACTIVE_PROFILE == "sf_homelessness" and str(row.get("payment_ledger_status") or "").startswith("official_sf")
        source_type = "county_contract_or_monitoring" if citation_ready_payment else "contract_payment_discovery"
        source_uri = SF_NONPROFIT_SPENDING_DATASET_URL if citation_ready_payment else HCD_HOMEKEY_FUNDING_URL
        records.append(
            build_record(
                f"contract_payment_discovery_{slugify(entity)}",
                f"{'SF payment ledger exposure' if citation_ready_payment else 'Contract/payment acquisition gap'}: {entity}",
                source_uri,
                source_type,
                "2026-04-30",
                [entity],
                "\n".join(
                    [
                        (
                            f"{entity} has {money(float(row.get('state_award_exposure') or 0))} in SF HSH completed-payment exposure in the current intake table."
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else f"{entity} has {money(float(row.get('state_award_exposure') or 0))} in HCD award-list exposure across {row.get('project_count')} project row(s)."
                        ),
                        (
                            "Official SF Open Data completed-payment aggregation was recovered as payment exposure; exact contracts, invoices, deliverables, monitoring letters, and corrective-action records were not recovered in this pass."
                            if citation_ready_payment
                            else "No direct standard agreement, payment ledger, monitoring letter, corrective-action record, or deliverable ledger was recovered in this pass."
                        ),
                        f"Official sources to search next: {', '.join(row.get('official_sources_to_search') or [])}.",
                        f"Query terms: {', '.join(row.get('query_terms') or [])}.",
                        f"Reviewer action: {row.get('reviewer_action')}",
                    ]
                ),
                {
                    "county_contract_monitoring_discovery": not citation_ready_payment,
                    "county_contract_source_match": citation_ready_payment,
                    "contract_payment_source": citation_ready_payment,
                    "sf_hsh_completed_payment_exposure": citation_ready_payment,
                    "discovery_only_source_gap": not citation_ready_payment,
                    "source_gap_only": not citation_ready_payment,
                    "not_citation_ready": not citation_ready_payment,
                    "missing_data": not citation_ready_payment,
                },
                {
                    "official_sources_to_search": row.get("official_sources_to_search", []),
                    "query_terms": row.get("query_terms", []),
                    "state_award_exposure": row.get("state_award_exposure"),
                    "project_count": row.get("project_count"),
                    "payment_ledger_status": row.get("payment_ledger_status"),
                },
            )
        )

    enforcement_discovery_rows = list(enforcement_discovery_table.get("rows", []))
    records.append(
        build_record(
            "source_table_enforcement_docket_discovery",
            "Systematic enforcement and docket source-search gap table",
            str(DOCKET_DIR / "enforcement_docket_discovery_summary.json"),
            "source_extraction_enforcement_docket_discovery_table",
            "2026-04-30",
            entities,
            "\n".join(
                [
                    "Systematic official-source enforcement and docket search table for all top-15 entities.",
            "Recovered official rows count as evidence hits; completed public official no-record searches remain source-access blockers, not legal clearance. Search target rows preserve remaining manual gaps and next actions.",
                    markdown_table(enforcement_discovery_rows, ["entity", "official_enforcement_row_recovered", "status", "public_official_search_completed_count", "public_official_search_possible_hit_count", "source_gap"], limit=30),
                ]
            ),
            {
                "enforcement_docket_discovery_table": True,
                "discovery_only_source_gap": True,
                "source_gap_only": True,
                "missing_data": True,
            },
            {"table_path": str(DOCKET_DIR / "enforcement_docket_discovery_summary.json"), "row_count": len(enforcement_discovery_rows)},
        )
    )
    for row in enforcement_discovery_rows:
        entity = row["entity"]
        status = str(row.get("status") or "")
        no_public_record = status == "searched_no_public_official_record"
        source_type = "enforcement_docket_official_no_record_search" if no_public_record else "enforcement_docket_discovery"
        source_uri = (
            str((row.get("public_official_searches") or [{}])[0].get("search_url") or US_DOJ_BASE_URL)
            if no_public_record
            else US_DOJ_BASE_URL
        )
        records.append(
            build_record(
                f"enforcement_docket_discovery_{slugify(entity)}",
                f"Official enforcement/docket public-source search: {entity}",
                source_uri,
                source_type,
                "2026-04-30",
                [entity],
                "\n".join(
                    [
                        f"Official enforcement row already recovered: {row.get('official_enforcement_row_recovered')}.",
                        f"Status: {row.get('status')}.",
                        f"Completed public official search count: {row.get('public_official_search_completed_count', 0)}.",
                        f"Possible public adverse search-hit count: {row.get('public_official_search_possible_hit_count', 0)}.",
                        "Public official search results:",
                        *[
                            f"- {item.get('source_name')}: {item.get('status')} for query {item.get('query')}; URL {item.get('search_url')}"
                            for item in row.get("public_official_searches", [])[:8]
                        ],
                        "Manual/credentialed sources still requiring controlled export or saved result:",
                        *[
                            f"- {item.get('name')}: {item.get('source_url')} ({item.get('reason')})"
                            for item in row.get("manual_sources_remaining", [])[:8]
                        ],
                        f"Official sources to search: {', '.join(row.get('official_sources_to_search') or [])}.",
                        f"Query terms: {', '.join(row.get('query_terms') or [])}.",
                        f"Reviewer action: {row.get('reviewer_action')}",
                    ]
                ),
                {
                    "enforcement_docket_discovery_attempted": True,
                    "official_source_search_completed_no_hit": no_public_record,
                    "searched_no_public_official_record": no_public_record,
                    "discovery_only_source_gap": not no_public_record,
                    "source_gap_only": not no_public_record,
                    "not_citation_ready": not no_public_record,
                    "official_enforcement_row_recovered": bool(row.get("official_enforcement_row_recovered")),
                    "missing_data": bool(row.get("source_gap")),
                },
                {
                    "official_sources_to_search": row.get("official_sources_to_search", []),
                    "query_terms": row.get("query_terms", []),
                    "status": row.get("status"),
                    "public_official_searches": row.get("public_official_searches", []),
                    "manual_sources_remaining": row.get("manual_sources_remaining", []),
                    "source_urls": [item.get("search_url") for item in row.get("public_official_searches", []) if item.get("search_url")],
                },
            )
        )

    service_rows = page_manifest["service"]
    statement_rows = page_manifest["statement"]
    tax_rows_by_entity = {
        entity: sorted([row for row in tax_rows if row.get("entity") == entity], key=lambda row: int(row.get("tax_period_year") or 0))
        for entity in entities
    }
    tax_matches_by_entity = {str(match.get("entity")): match for match in tax_matches}
    for target in TARGETS:
        summary = next(row for row in summary_rows if row["entity"] == target["name"])
        award_lines = []
        for award in target["awards"]:
            if ACTIVE_PROFILE == "sf_homelessness":
                award_lines.append(
                    f"- {award['award_date']} {award['program']}: {award['project']} in {award['city']}; public-payment exposure {money(float(award['amount']))}; source note {award['source_note']}."
                )
            else:
                award_lines.append(
                    f"- {award['award_date']} {award['program']}: {award['project']} in {award['city']}, {award['county']} County; eligible applicant {award['eligible_applicant']}; total awarded amount {money(float(award['amount']))}; HCD source note {award['source_note']}."
                )
        records.append(
            build_record(
                f"state_homeless_awards_{target['slug']}",
                (
                    f"San Francisco HSH completed-payment exposure: {target['name']}"
                    if ACTIVE_PROFILE == "sf_homelessness"
                    else f"HCD Homekey/Homekey+ award rows: {target['name']}"
                ),
                " ".join(sorted({award["source_url"] for award in target["awards"]})),
                "sf_hsh_payment_exposure" if ACTIVE_PROFILE == "sf_homelessness" else "state_homelessness_award",
                max(award["award_date"] for award in target["awards"]),
                [target["name"], *target["aliases"]],
                "\n".join(
                    [
                        f"Entity: {target['name']}.",
                        (
                            f"Rank by Review Value Score intake proxy from SF HSH payment exposure plus official adverse-record seeds: {target['rank']} of {len(TARGETS)}."
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else f"Rank by parsed state project-award exposure: {target['rank']} of 15."
                        ),
                        (
                            f"Total SF HSH completed-payment exposure recovered from SF Open Data aggregation: {money(float(summary['total_award_exposure']))}."
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else f"Total Homekey/Homekey+ project-award exposure from source-listed co-applicant rows: {money(float(summary['total_award_exposure']))}."
                        ),
                        "Funding rows:",
                        *award_lines,
                        (
                            "Important caveat: SF completed-payment exposure is a materiality screen and does not by itself indicate misuse, waste, fraud, abuse, or mismanagement."
                            if ACTIVE_PROFILE == "sf_homelessness"
                            else "Important caveat: this assigns the full project-award amount to each source-listed co-applicant for exposure ranking; the HCD award list does not state the direct payment allocation among co-applicants."
                        ),
                    ]
                ),
                {
                    "state_homelessness_award_exposure": True,
                    "large_state_award_exposure": summary["total_award_exposure"] >= 50_000_000,
                    "direct_payment_allocation_missing": True,
                    "missing_data": True,
                    "sf_hsh_completed_payment_exposure": ACTIVE_PROFILE == "sf_homelessness",
                },
                {"rank": target["rank"], "total_award_exposure": summary["total_award_exposure"], "project_count": summary["project_count"], "counties": summary["counties"]},
            )
        )

        target_tax_rows = tax_rows_by_entity.get(target["name"], [])
        if target_tax_rows:
            latest_tax = target_tax_rows[-1]
            tax_years = [str(row.get("tax_period_year")) for row in target_tax_rows if row.get("tax_period_year")]
            pdf_url = str(latest_tax.get("pdf_url") or "")
            records.append(
                build_record(
                    f"irs_990_summary_{target['slug']}",
                    f"ProPublica/IRS Form 990 summary: {target['name']}",
                    str(latest_tax.get("propublica_organization_url") or latest_tax.get("propublica_api_url") or PROPUBLICA_API_DOC_URL),
                    "irs_990_summary",
                    str(latest_tax.get("tax_period_year") or "2026"),
                    [target["name"], *target["aliases"]],
                    "\n".join(
                        [
                            f"Entity: {target['name']}.",
                            f"EIN: {latest_tax.get('ein')}.",
                            f"Parsed filing years from ProPublica/IRS extract: {', '.join(tax_years)}.",
                            (
                                f"Latest parsed year {latest_tax.get('tax_period_year')} reports total revenue {money(float(latest_tax.get('total_revenue') or 0))}, "
                                f"total expenses {money(float(latest_tax.get('total_expenses') or 0))}, and aggregate current officer/director/trustee compensation "
                                f"{money(float(latest_tax.get('officer_compensation_total') or 0))}."
                            ),
                            f"ProPublica organization page: {latest_tax.get('propublica_organization_url')}",
                            f"ProPublica API URL: {latest_tax.get('propublica_api_url')}",
                            f"Latest linked PDF: {pdf_url or 'not supplied by ProPublica API row'}.",
                            "Control caveat: ProPublica is a public access layer. Raw IRS XML/PDF controls all final financial and compensation interpretation.",
                        ]
                    ),
                    {
                        "propublica_irs_990_found": True,
                        "irs_990_summary": True,
                        "full_990_pdf_linked": bool(pdf_url),
                        "missing_data": False,
                    },
                    {
                        "ein": latest_tax.get("ein"),
                        "tax_years": tax_years,
                        "latest_pdf_url": pdf_url,
                        "propublica_api_url": latest_tax.get("propublica_api_url"),
                        "propublica_organization_url": latest_tax.get("propublica_organization_url"),
                        "table_path": str(PROPUBLICA_DIR / "propublica_irs_990_summary.json"),
                    },
                )
            )
        elif tax_matches_by_entity.get(target["name"], {}).get("status") == "matched":
            tax_match = tax_matches_by_entity[target["name"]]
            records.append(
                build_record(
                    f"irs_990_summary_{target['slug']}",
                    f"ProPublica/IRS Form 990 profile without parsed filings: {target['name']}",
                    str(tax_match.get("organization_page_url") or tax_match.get("organization_api_url") or PROPUBLICA_API_DOC_URL),
                    "irs_990_summary",
                    "2026-04-30",
                    [target["name"], *target["aliases"]],
                    "\n".join(
                        [
                            f"Entity: {target['name']}.",
                            f"EIN: {tax_match.get('ein')}.",
                            "ProPublica Nonprofit Explorer returned a matched organization profile, but the current API response did not include filings_with_data rows for CalDS financial tests.",
                            f"ProPublica organization page: {tax_match.get('organization_page_url')}",
                            f"ProPublica API URL: {tax_match.get('organization_api_url')}",
                            "Control caveat: this is a source-coverage note and filing-data gap, not an adverse finding.",
                        ]
                    ),
                    {
                        "propublica_irs_990_profile_found": True,
                        "irs_990_summary": True,
                        "irs_990_filing_rows_missing": True,
                        "missing_data": True,
                    },
                    {
                        "ein": tax_match.get("ein"),
                        "propublica_api_url": tax_match.get("organization_api_url"),
                        "propublica_organization_url": tax_match.get("organization_page_url"),
                        "table_path": str(PROPUBLICA_DIR / "propublica_irs_990_summary.json"),
                    },
                )
            )

        review_terms = {*HOMELESSNESS_SCOPE_HIGH_TERMS, *HOMELESSNESS_SCOPE_MEDIUM_TERMS}
        service_for_target = [row for row in service_rows if row["slug"] == target["slug"]]
        fetched_service = [row for row in service_for_target if row.get("fetched")]
        service_terms = sorted({term for row in service_for_target for term in row.get("matched_terms", []) if term in review_terms})
        service_summary_lines = [
            f"Organization: {target['name']}",
            f"Official service/program pages fetched: {len(fetched_service)} of {len(service_for_target)}.",
            f"Matched homelessness-scope review terms: {', '.join(service_terms) if service_terms else 'none from configured list'}.",
            "Service summary from official source(s):",
        ]
        for row in fetched_service:
            service_summary_lines.append(f"- {row['final_url']}: {row['summary']}")
        for row in service_for_target:
            if not row.get("fetched"):
                service_summary_lines.append(f"- Fetch gap for {row['url']}: {row.get('error', '')}")
        records.append(
            build_record(
                f"org_service_pages_{target['slug']}",
                f"Official service/program page harvest: {target['name']}",
                target["service_urls"][0],
                "org_service_page",
                "2026-04-29",
                [target["name"], *target["aliases"]],
                "\n".join(service_summary_lines),
                {
                    "org_service_page_checked": True,
                    "service_description_present": bool(fetched_service),
                    "off_scope_keyword_match": bool(service_terms),
                    "missing_data": len(fetched_service) < len(service_for_target),
                },
                {"service_pages": service_for_target, "matched_terms": service_terms},
            )
        )

        statement_for_target = [row for row in statement_rows if row["slug"] == target["slug"]]
        fetched_statement = [row for row in statement_for_target if row.get("fetched")]
        terms = sorted({term for row in statement_for_target for term in row.get("matched_terms", []) if term in review_terms})
        statement_lines = [
            f"Public or official statement pages fetched: {len(fetched_statement)} of {len(statement_for_target)}.",
            f"Matched review terms: {', '.join(terms) if terms else 'none from configured list'}.",
            "Snippets:",
        ]
        for row in fetched_statement:
            statement_lines.append(f"- {row['final_url']}: {row['summary']}")
        records.append(
            build_record(
                f"public_statements_{target['slug']}",
                f"Public statement page harvest: {target['name']}",
                target["statement_urls"][0] if target["statement_urls"] else target["service_urls"][0],
                "public_statement_source",
                "2026-04-29",
                [target["name"], *target["aliases"]],
                "\n".join(statement_lines),
                {"public_statement_source_checked": True, "off_scope_keyword_match": bool(terms), "missing_data": len(fetched_statement) < len(statement_for_target)},
                {"statement_pages": statement_for_target, "matched_terms": terms},
            )
        )

    for record in records:
        write_json(corpus_dir / f"{record['record_id']}.json", record)

    summary_path = ARTIFACT_BASE_DIR / "ingest_summary.json"
    write_json(
        summary_path,
        {
            "case_id": CASE_ID,
            "created_at": now(),
            "corpus_dir": str(corpus_dir),
            "artifacts_dir": str(ARTIFACT_BASE_DIR),
            "record_count": len(records),
            "target_count": len(TARGETS),
            "source_documents": source_manifest,
            "enforcement_or_docket_rows": enforcement_table.get("rows", []),
            "propublica_irs_990_profile_matched_entities": sorted({match["entity"] for match in tax_matches if match.get("status") == "matched"}),
            "propublica_irs_990_filing_entities": tax_entities,
            "propublica_irs_990_rows": len(tax_rows),
            "propublica_irs_990_match_errors": [match for match in tax_matches if match.get("status") != "matched"],
            "irs_raw_xml_downloaded_count": raw_tax_table.get("xml_downloaded_count", 0),
            "fac_audit_summary_rows": len(fac_audit_rows),
            "fac_filter_errors": fac_table.get("errors", []),
            "local_contract_monitoring_source_count": len(LOCAL_CONTRACT_MONITORING_SOURCES),
            "service_fetch_failures": [row for row in service_rows if not row.get("fetched")],
            "statement_fetch_failures": [row for row in statement_rows if not row.get("fetched")],
        },
    )


def build_case_request_payload(corpus_dir: Path) -> dict[str, Any]:
    if ACTIVE_PROFILE == "sf_homelessness":
        return {
            "case_id": CASE_ID,
            "title": "San Francisco homelessness NGO complex triage",
            "objective": (
                "Run a generic CalDS investigation profile against San Francisco homelessness-service nonprofit candidates, "
                "rank targets by Review Value Score, deep-dive entities with public-dollar exposure plus official adverse-record or scope-mismatch signals, "
                "and pause for human review with source-cited findings."
            ),
            "jurisdiction": "San Francisco, California",
            "allowed_sources": [
                "SF Open Data nonprofit spending",
                "SF Department of Homelessness and Supportive Housing records",
                "SF Controller audits",
                "SF Board and City records",
                "IRS Form 990 and ProPublica Nonprofit Explorer",
                "Federal Audit Clearinghouse",
                "official enforcement, docket, settlement, and adverse-action sources",
                "organization websites, public statements, and social-media pages",
                "official homelessness outcome data",
            ],
            "entities": [target["name"] for target in TARGETS],
            "max_results": min(len(TARGETS), ACTIVE_TARGET_LIMIT),
            "metadata": {
                "investigation_profile_path": "data/investigation_profiles/sf_homelessness.json",
                "topic": "homelessness",
                "target_universe": "San Francisco homelessness-service nonprofit candidates",
                "selection_metric": "Review Value Score",
                "target_selection_source": str(RAW_DIR / "sf_hsh_payment_target_rows.json"),
                "source_corpus_dir": str(corpus_dir),
                "profile": ACTIVE_PROFILE,
                "completeness_run_attempt": 1,
            },
        }
    return {
        "case_id": CASE_ID,
        "title": "California homelessness top-15 nonprofit triage",
        "objective": "Run CalDS homelessness triage against a source-listed California homelessness nonprofit target set.",
        "jurisdiction": "California",
        "allowed_sources": [
            "HCD Homekey and Homekey+ award lists",
            "IRS Form 990 and ProPublica Nonprofit Explorer",
            "Federal Audit Clearinghouse",
            "California Attorney General charity registry",
            "California Secretary of State business records",
            "California Grants Portal and Open FI$Cal",
            "CAL-ACCESS, Power Search, and FPPC campaign/lobbying sources",
            "official enforcement, docket, settlement, and adverse-action sources",
            "organization websites and public statements",
            "official homelessness outcome data",
        ],
        "entities": [target["name"] for target in TARGETS],
        "max_results": min(len(TARGETS), ACTIVE_TARGET_LIMIT),
        "metadata": {
            "investigation_profile_path": "data/investigation_profiles/ca_statewide_homelessness.json",
            "topic": "homelessness",
            "target_universe": "California source-listed homelessness nonprofit co-applicants",
            "selection_metric": "Review Value Score",
            "source_corpus_dir": str(corpus_dir),
            "profile": ACTIVE_PROFILE,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CalDS homelessness investigation corpus.")
    parser.add_argument("--profile", choices=["statewide_homekey", "ca_statewide_homelessness", "sf_homelessness"], default="statewide_homekey")
    parser.add_argument("--target-limit", type=int, default=15)
    parser.add_argument("--corpus-dir", type=Path, default=None)
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Run-scoped source artifact directory. Defaults to <corpus-dir>/_source_artifacts.",
    )
    parser.add_argument(
        "--case-file-out",
        type=Path,
        default=None,
        help="Optional path to write a runnable CalDS CaseRequest JSON for this generated corpus.",
    )
    args = parser.parse_args()
    configure_profile(args.profile, args.target_limit)
    corpus_dir = args.corpus_dir or DEFAULT_CORPUS_DIR
    write_corpus(corpus_dir, args.artifacts_dir)
    if args.case_file_out:
        write_json(args.case_file_out, build_case_request_payload(corpus_dir))
    print(f"case_id={CASE_ID}")
    print(f"profile={ACTIVE_PROFILE}")
    print(f"corpus_dir={corpus_dir}")
    print(f"artifacts_dir={ARTIFACT_BASE_DIR}")
    if args.case_file_out:
        print(f"case_file={args.case_file_out}")
    print(f"records={len([path for path in corpus_dir.glob('*.json') if not path.name.startswith('_')])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
