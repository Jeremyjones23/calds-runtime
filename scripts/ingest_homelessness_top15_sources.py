from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import argparse
import hashlib
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "live_ca_homelessness_top15_2026_04_29"
COLLECTED_AT = "2026-04-29T00:00:00+00:00"
RAW_DIR = PROJECT_ROOT / "artifacts" / "homelessness_top15_sources_2026_04_29" / "raw"
OUTCOME_DIR = PROJECT_ROOT / "artifacts" / "homelessness_top15_sources_2026_04_29" / "outcomes"
WEB_DIR = PROJECT_ROOT / "artifacts" / "homelessness_top15_sources_2026_04_29" / "web"
DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "live_corpus" / f"{CASE_ID}_stage1"

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


TARGETS: list[dict[str, Any]] = [
    {
        "rank": 1,
        "name": "Hope the Mission",
        "slug": "hope_the_mission",
        "aliases": ["Hope The Mission"],
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
        "aliases": ["Habitat for Humanity Yuba/Sutter", "Habitat for Humanity Yuba-Sutter"],
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


def download_source_docs() -> dict[str, dict[str, Any]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, url in {
        "homekey_round3_awardee_list": HCD_ROUND3_URL,
        "homekey_plus_awardee_list": HCD_PLUS_URL,
        "fhfa_oig_homelessness_funds_press_release": FHFA_OIG_HOMELESSNESS_FUNDS_PRESS_RELEASE_URL,
        "la_city_homekey3_shelby_authorization": LA_CITY_HOMEKEY3_SHELBY_AUTHORIZATION_URL,
        "la_city_shelby_2026_operations": LA_CITY_SHELBY_2026_OPERATIONS_URL,
    }.items():
        path = RAW_DIR / f"{name}.pdf"
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
        }
    ]
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
                "advocacy",
                "lobbying",
                "policy",
                "policy advocacy",
                "community organizing",
                "voter registration",
                "power building",
                "political action",
            ]
            row.update(
                {
                    "fetched": True,
                    "final_url": final_url,
                    "content_type": content_type,
                    "text_chars": len(text),
                    "local_text_path": str(base_dir / f"{stem}.txt"),
                    "summary": snippet(text, terms, radius=420),
                    "matched_terms": [term for term in terms if term in text.lower()],
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
        "methodology": "Official CA SPM M1a rows are matched by county-name text to the counties listed in HCD Homekey/Homekey+ award rows. This is contextual screening and not provider attribution.",
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
                    "state_project_count": row["project_count"],
                    "spending_growth_pct": None,
                    "revenue_growth_pct": None,
                    "government_grant_growth_pct": None,
                    "homelessness_spm_change": county_changes,
                    "join_caveats": [
                        "County and Continuum of Care outcomes are not provider-attributable without direct program outcome records.",
                        "This join compares state project-award exposure to official geography-level homelessness service-system movement, not audited spend or client outcomes.",
                        "The award-list exposure total is not a verified direct-payment total to the nonprofit.",
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
        lines.append(f"| +{len(rows) - limit} additional row(s) |  |  |")
    return "\n".join(lines)


def top_award_summary_lines(summary_rows: list[dict[str, Any]], limit: int = 15) -> str:
    lines = ["Top source-ranked co-applicant project-award exposures from official HCD tables:"]
    for row in summary_rows[:limit]:
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


def write_corpus(corpus_dir: Path) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    for old in corpus_dir.glob("*.json"):
        old.unlink()

    source_manifest = download_source_docs()
    page_manifest = fetch_all_pages()
    summary_rows = award_summary_rows()
    award_table = {
        "created_at": now(),
        "case_id": CASE_ID,
        "methodology": "Rank source-listed nonprofit co-applicant names by the full HCD project-award amount attached to each Homekey/Homekey+ row. This is award exposure, not proof of direct receipt.",
        "source_documents": source_manifest,
        "eligibility_sources": [HCD_ROUND3_ELIGIBILITY_URL, HCD_PLUS_ELIGIBILITY_URL, HCD_HOMEKEY_FUNDING_URL],
        "entity_award_summary": summary_rows,
        "caveats": [
            "HCD award lists name eligible applicants and co-applicants; allocation among co-applicants is not stated in the award tables.",
            "HHAP and ESG allocation pages were not used for the top-15 ranking because they do not provide a statewide nonprofit subrecipient table comparable to the Homekey award lists.",
        ],
    }
    award_table_path = RAW_DIR / "state_homeless_award_summary.json"
    write_json(award_table_path, award_table)

    outcome_manifest, join_summary = outcome_artifacts(summary_rows)
    enforcement_table = enforcement_docket_artifacts()

    records: list[dict[str, Any]] = []
    entities = [target["name"] for target in TARGETS]
    records.append(
        build_record(
            "source_table_state_homeless_awards",
            "Parsed HCD Homekey/Homekey+ state homelessness award exposure table",
            str(award_table_path),
            "source_extraction_state_homeless_award_table",
            "2026-02-18",
            entities,
            "\n".join(
                [
                    "Parsed California Department of Housing and Community Development Homekey/Homekey+ award exposure table.",
                    "Methodology: rank source-listed nonprofit co-applicant names by the full project-award amount attached to each award row. This is materiality exposure, not direct-payment proof.",
                    top_award_summary_lines(summary_rows),
                    "Official source URLs:",
                    HCD_ROUND3_URL,
                    HCD_PLUS_URL,
                    HCD_ROUND3_ELIGIBILITY_URL,
                    HCD_PLUS_ELIGIBILITY_URL,
                    markdown_table(summary_rows, ["rank", "entity", "total_award_exposure", "project_count", "programs", "counties", "projects"], limit=20),
                ]
            ),
            {"state_homelessness_award_table": True, "source_extraction_table": True, "state_homelessness_award_exposure": True},
            {"table_path": str(award_table_path), "row_count": len(summary_rows), "source_urls": [HCD_ROUND3_URL, HCD_PLUS_URL]},
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
        "Deterministic state-award exposure versus homelessness outcome-context join",
        str(OUTCOME_DIR / "outcome_join_summary.json"),
        "source_extraction_spend_vs_results_table",
        "2026-04-29",
        entities,
        "\n".join(
            [
                "Deterministic join from HCD state project-award exposure to official county/Continuum of Care homelessness outcome context.",
                "County and Continuum of Care outcomes are not provider-attributable without direct program outcome records.",
                markdown_table(join_summary.get("entity_outcome_rows", []), ["entity", "county", "risk_level", "state_award_exposure", "state_project_count", "outcome_flags"], limit=80),
            ]
        ),
        {"spend_vs_results_join_created": True, "source_extraction_table": True, "outcome_context_present": bool(join_summary.get("entity_outcome_rows"))},
        {"join_summary_path": str(OUTCOME_DIR / "outcome_join_summary.json"), "table_path": str(OUTCOME_DIR / "outcome_join_summary.json"), "row_count": join_summary.get("row_count")},
    )
    records.append(join_record)

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
                    "missing_data": True,
                },
                {
                    "legal_status": row.get("legal_status"),
                    "source_urls": row.get("source_urls", []),
                    "reviewer_action": row.get("reviewer_action", ""),
                },
            )
        )

    service_rows = page_manifest["service"]
    statement_rows = page_manifest["statement"]
    for target in TARGETS:
        summary = next(row for row in summary_rows if row["entity"] == target["name"])
        award_lines = []
        for award in target["awards"]:
            award_lines.append(
                f"- {award['award_date']} {award['program']}: {award['project']} in {award['city']}, {award['county']} County; eligible applicant {award['eligible_applicant']}; total awarded amount {money(float(award['amount']))}; HCD source note {award['source_note']}."
            )
        records.append(
            build_record(
                f"state_homeless_awards_{target['slug']}",
                f"HCD Homekey/Homekey+ award rows: {target['name']}",
                " ".join(sorted({award["source_url"] for award in target["awards"]})),
                "state_homelessness_award",
                max(award["award_date"] for award in target["awards"]),
                [target["name"], *target["aliases"]],
                "\n".join(
                    [
                        f"Entity: {target['name']}.",
                        f"Rank by parsed state project-award exposure: {target['rank']} of 15.",
                        f"Total Homekey/Homekey+ project-award exposure from source-listed co-applicant rows: {money(float(summary['total_award_exposure']))}.",
                        "Award rows:",
                        *award_lines,
                        "Important caveat: this assigns the full project-award amount to each source-listed co-applicant for exposure ranking; the HCD award list does not state the direct payment allocation among co-applicants.",
                    ]
                ),
                {
                    "state_homelessness_award_exposure": True,
                    "large_state_award_exposure": summary["total_award_exposure"] >= 50_000_000,
                    "direct_payment_allocation_missing": True,
                    "missing_data": True,
                },
                {"rank": target["rank"], "total_award_exposure": summary["total_award_exposure"], "project_count": summary["project_count"], "counties": summary["counties"]},
            )
        )

        service_for_target = [row for row in service_rows if row["slug"] == target["slug"]]
        fetched_service = [row for row in service_for_target if row.get("fetched")]
        service_summary_lines = [
            f"Organization: {target['name']}",
            f"Official service/program pages fetched: {len(fetched_service)} of {len(service_for_target)}.",
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
                {"org_service_page_checked": True, "service_description_present": bool(fetched_service), "missing_data": len(fetched_service) < len(service_for_target)},
                {"service_pages": service_for_target},
            )
        )

        statement_for_target = [row for row in statement_rows if row["slug"] == target["slug"]]
        fetched_statement = [row for row in statement_for_target if row.get("fetched")]
        review_terms = {
            "lobbying",
            "policy advocacy",
            "voter registration",
            "power building",
            "political action",
            "community organizing",
        }
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

    summary_path = PROJECT_ROOT / "artifacts" / "homelessness_top15_sources_2026_04_29" / "ingest_summary.json"
    write_json(
        summary_path,
        {
            "case_id": CASE_ID,
            "created_at": now(),
            "corpus_dir": str(corpus_dir),
            "record_count": len(records),
            "target_count": len(TARGETS),
            "source_documents": source_manifest,
            "enforcement_or_docket_rows": enforcement_table.get("rows", []),
            "service_fetch_failures": [row for row in service_rows if not row.get("fetched")],
            "statement_fetch_failures": [row for row in statement_rows if not row.get("fetched")],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CalDS homelessness top-15 state-award corpus.")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    args = parser.parse_args()
    write_corpus(args.corpus_dir)
    print(f"case_id={CASE_ID}")
    print(f"corpus_dir={args.corpus_dir}")
    print(f"records={len([path for path in args.corpus_dir.glob('*.json') if not path.name.startswith('_')])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
