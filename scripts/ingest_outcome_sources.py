from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
import urllib.parse
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE4_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage4"
DEFAULT_STAGE5_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage5"
DEFAULT_ARTIFACTS = PROJECT_ROOT / "artifacts" / "live_recovery_sources_2026_04_24"
DEFAULT_OUTCOME_DIR = DEFAULT_ARTIFACTS / "outcomes"
DATA_CA_API = "https://data.ca.gov/api/3/action"
DATA_CHHS_API = "https://data.chhs.ca.gov/api/3/action"
OPENJUSTICE_CRIME_CSV = "https://data-openjustice.doj.ca.gov/sites/default/files/dataset/2025-07/Crimes_and_Clearances_with_Arson-1985-2024.csv"
DHCS_SUSPENSION_REVOCATION = "https://www.dhcs.ca.gov/provgovpart/SUD-LCR/Pages/Suspension-Revocation.aspx"
DHCS_SUS_REV_NOV = "https://www.dhcs.ca.gov/provgovpart/SUD-LCR/Pages/SUS-REV-NOV.aspx"
DHCS_CALOMS = "https://www.dhcs.ca.gov/provgovpart/Pages/caloms-treatment.aspx"

RESOURCES = {
    "homelessness_spm": {"title": "CA System Performance Measures by CoC", "source_url": "https://lab.data.ca.gov/dataset/ca-system-performance-measures-statewide-and-by-coc", "api_base": DATA_CA_API, "resource_id": "e02178d9-1d34-4798-9979-f50af9f1742e", "join_grain": "CoC/year-period/metric"},
    "homelessness_demographics_gender": {"title": "People Receiving Homeless Response Services by Gender", "source_url": "https://lab.data.ca.gov/dataset/homelessness-demographics", "api_base": DATA_CA_API, "resource_id": "57142555-f2da-462f-a999-d44abf0af69c", "join_grain": "CoC/year/gender"},
    "mat_by_county": {"title": "Medication-Assisted Treatment in Medi-Cal for Opioid Use Disorders", "source_url": "https://data.chhs.ca.gov/dataset/medication-assisted-treatment-in-medi-cal-for-opioid-use-disorders-by-county", "api_base": DATA_CHHS_API, "resource_id": "bf66ffea-8f37-4553-8829-4bf9286e7802", "join_grain": "county/year/MAT type"},
    "drug_overdose_deaths": {"title": "County Health Status Profiles: Drug Overdose Deaths", "source_url": "https://data.chhs.ca.gov/dataset/county-health-status-profiles", "api_base": DATA_CHHS_API, "resource_id": "610d4269-d7fb-4af4-ad4a-75d44c80742a", "join_grain": "county/multi-year period"},
}
TARGETS = [
    {
        "slug": "tarzana",
        "name": "Tarzana Treatment Centers Inc",
        "aliases": ["Tarzana Treatment Centers", "Tarzana Treatment Centers Inc"],
        "service_urls": ["https://www.tarzanatc.org/services/"],
        "service_anchor_terms": ["Tarzana Treatment Centers, Inc. is a full-service", "TTC provides a full continuum"],
        "statement_urls": ["https://www.tarzanatc.org/who-we-are/meet-us/", "https://www.tarzanatc.org/who-we-are/our-history/", "https://www.tarzanatc.org/news-events/"],
    },
    {
        "slug": "healthright",
        "name": "HealthRIGHT 360",
        "aliases": ["HealthRIGHT 360", "HealthRight 360"],
        "service_urls": ["https://www.healthright360.org/our-services/substance-use-disorder/"],
        "service_anchor_terms": ["HealthRIGHT 360 provides a full continuum", "HealthRIGHT 360 offers a full spectrum"],
        "statement_urls": ["https://www.healthright360.org/about/staff-and-board/", "https://www.healthright360.org/about/news", "https://www.healthright360.org/about/our-impact/"],
    },
    {
        "slug": "westcare",
        "name": "WestCare California Inc",
        "aliases": ["WestCare California", "WestCare California Inc", "WestCare"],
        "service_urls": ["https://westcare.com/places/california/"],
        "service_anchor_terms": ["WestCare California has been providing", "WestCare provides a wide spectrum", "Treatment & Rehabilitation: WestCare California"],
        "statement_urls": ["https://westcare.com/leadership/", "https://westcare.com/leadership/senior/", "https://westcare.com/express/", "https://westcare.com/impact-report/"],
    },
    {
        "slug": "bhs",
        "name": "Behavioral Health Services Inc",
        "aliases": ["Behavioral Health Services", "Behavioral Health Services Inc", "BHS"],
        "service_urls": ["https://bhs-inc.org/services"],
        "service_anchor_terms": ["BHS programming attempts", "Services include"],
        "statement_urls": ["https://bhs-inc.org/", "https://www.bhs-inc.org/about-us", "https://bhs-inc.org/services/"],
    },
    {
        "slug": "crihelp",
        "name": "CRI-Help Inc",
        "aliases": ["CRI-Help", "CRI-Help Inc", "CRI Help"],
        "service_urls": ["https://cri-help.org/programs/residential-treatment/overview.html", "https://cri-help.org/programs/cri-help-outpatient.html"],
        "service_anchor_terms": ["Our residential treatment program", "CRI-Help offers flexible outpatient"],
        "statement_urls": ["https://cri-help.org/news-events/newsroom.html", "https://cri-help.org/who-we-are/core-values.html", "https://cri-help.org/"],
    },
    {
        "slug": "socialmodel",
        "name": "Social Model Recovery Systems Inc",
        "aliases": ["Social Model Recovery Systems", "Social Model Recovery Systems Inc"],
        "service_urls": ["https://socialmodelrecovery.org/services/"],
        "service_anchor_terms": ["Social Model Recovery Systems, Inc. has been a pioneer", "We offer a continuum of care"],
        "statement_urls": ["https://socialmodelrecovery.org/annual-report/", "https://www.socialmodelrecovery.org/about-us/", "https://www.socialmodelrecovery.org/programs/"],
    },
    {
        "slug": "phoenix",
        "name": "Phoenix Houses Of California Inc",
        "aliases": ["Phoenix Houses Of California", "Phoenix House California", "Phoenix Houses"],
        "service_urls": ["https://phoenixhouseca.org/what-we-do/"],
        "service_anchor_terms": ["At Phoenix House California, we take a holistic approach", "We offer specialized programs"],
        "statement_urls": ["https://phoenixhouseca.org/measuring-our-impact/", "https://phoenixhouseca.org/annual-reports/", "https://phoenixhouseca.org/impact-annual-reports/"],
    },
]
STATEMENT_TERMS = ["voter registration","power building","political action","campaign contribution","ballot measure","electioneering","lobbying","advocacy","policy and public affairs","public affairs","homelessness","housing","criminal justice","reentry","outcomes","evidence-based","equity"]
SERVICE_EXCERPT_TERMS = ["provides a full continuum", "full continuum", "program is designed", "we take a holistic approach", "take a holistic approach", "services include", "we offer a continuum", "offers flexible outpatient", "has been a pioneer in providing", "adult treatment services", "provides high quality", "provides a wide spectrum", "residential treatment program", "substance use disorder treatment", "residential treatment", "outpatient treatment", " we offer ", " offers ", " provides ", " provide ", "substance use", "treatment", "services"]
SERVICE_TEXT_FALLBACKS = {
    "https://socialmodelrecovery.org/services/": {
        "final_url": "https://socialmodelrecovery.org/services/",
        "content_type": "text/html; official-search-fallback",
        "text": "Official Social Model Recovery Systems Programs/Services page: Social Model Recovery Systems, Inc. says it has provided adult treatment services since 1986. The page describes a continuum of care from residential treatment at River Community to the Wellness Center; day treatment, partial day treatment, and outpatient services for co-occurring disorders at River Community Covina; outpatient services for substance abuse or mental health issues at Pasadena Council on Alcoholism and Drug Dependence; outpatient substance abuse services at Mid Valley Outpatient; residential substance abuse treatment for women and women with children at Mariposa and Stepping Stones; residential services for men at Omni Center; residential treatment at Bimini; and Royal Palms residential substance abuse treatment for men and women including those in the LGBTQ+ community. The same official page describes adolescent treatment and prevention services.",
        "fallback_note": "Automated fetch for the official services URL returned HTTP 403 in this environment; text is a bounded fallback from the official page recovered through web search/open on 2026-04-26.",
    }
}

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def copy_corpus(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if source.exists() and source.resolve() == destination.resolve():
        return
    for existing in destination.glob("*.json"):
        existing.unlink()
    for item in sorted(source.glob("*.json")):
        shutil.copy2(item, destination / item.name)

def fetch_bytes(url: str, timeout: int = 90) -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,text/csv,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl(), response.headers.get("Content-Type", "")

class TextStripper(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if data.strip():
            self.parts.append(data.strip())
def strip_html(raw: bytes) -> str:
    parser = TextStripper(); parser.feed(raw.decode("utf-8", "replace"))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def source_text(raw: bytes, content_type: str) -> str:
    if "pdf" in content_type.lower() or raw.startswith(b"%PDF"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(raw))
            text_parts = []
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    text_parts.append("")
            return re.sub(r"\s+", " ", " ".join(text_parts)).strip()
        except Exception:
            return strip_html(raw)
    return strip_html(raw)

def num(value: Any) -> float | None:
    if value is None or value == "": return None
    try: return float(str(value).replace(",", ""))
    except Exception: return None

def pct_change(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None: return None
    if previous == 0: return 0.0 if current == 0 else 100.0
    return ((current - previous) / abs(previous)) * 100.0

def normalize_county(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"\s+County$", "", text, flags=re.IGNORECASE)
    return text.lower()

def display_county(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())

def build_record(record_id: str, title: str, source_uri: str, source_type: str, published_at: str, entities: list[str], body: str, signals: dict[str, Any], attributes: dict[str, Any]) -> dict[str, Any]:
    return {"record_id":record_id,"title":title,"source_uri":source_uri,"source_type":source_type,"published_at":published_at,"collected_at":utc_now(),"entities":entities,"attributes":{"signals":signals, **attributes},"body":body}


def ckan_records(api_base: str, resource_id: str, limit: int = 50000) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        url = f"{api_base}/datastore_search?" + urllib.parse.urlencode({"resource_id":resource_id,"limit":min(limit,50000),"offset":offset})
        raw, _, _ = fetch_bytes(url, timeout=90)
        data = json.loads(raw.decode("utf-8", "replace"))
        if not data.get("success"):
            raise RuntimeError(f"CKAN datastore_search failed for {resource_id}: {data}")
        batch = data.get("result", {}).get("records", [])
        records.extend(batch)
        if len(batch) < min(limit,50000): break
        offset += len(batch)
        if offset >= limit: break
    return records

def ckan_sql(api_base: str, sql: str) -> list[dict[str, Any]]:
    url = f"{api_base}/datastore_search_sql?" + urllib.parse.urlencode({"sql":sql})
    raw, _, _ = fetch_bytes(url, timeout=90)
    data = json.loads(raw.decode("utf-8", "replace"))
    if not data.get("success"):
        raise RuntimeError(f"CKAN datastore_search_sql failed: {data}")
    return data.get("result", {}).get("records", [])

def fetch_official_outcome_sources(outcome_dir: Path) -> dict[str, Any]:
    outcome_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {}
    datasets: dict[str, list[dict[str, Any]]] = {}
    for key, meta in RESOURCES.items():
        try:
            if key == "drug_overdose_deaths":
                rid = meta["resource_id"]
                records = ckan_sql(meta["api_base"], f'SELECT * FROM "{rid}" WHERE "Health_Indicator_Desc"='"'"'Drug Overdose Deaths'"'"' AND "Strata"='"'"'Total Population'"'"'')
            else:
                records = ckan_records(meta["api_base"], meta["resource_id"])
            datasets[key] = records
            write_json(outcome_dir / f"{key}.json", {"metadata":meta, "rows":records})
            manifest[key] = {**meta, "row_count":len(records), "fetched":True, "error":""}
        except Exception as exc:
            datasets[key] = []
            manifest[key] = {**meta, "row_count":0, "fetched":False, "error":repr(exc)}
    try:
        raw, final_url, content_type = fetch_bytes(OPENJUSTICE_CRIME_CSV, timeout=120)
        (outcome_dir / "openjustice_crimes_clearances_1985_2024.csv").write_bytes(raw)
        crime_rows = list(csv.DictReader(raw.decode("utf-8", "replace").splitlines()))
        datasets["openjustice_crime"] = crime_rows
        manifest["openjustice_crime"] = {"title":"California DOJ OpenJustice Crimes and Clearances with Arson, 1985-2024", "source_url":OPENJUSTICE_CRIME_CSV, "final_url":final_url, "content_type":content_type, "row_count":len(crime_rows), "fetched":True, "error":"", "join_grain":"county/year/reporting agency"}
    except Exception as exc:
        datasets["openjustice_crime"] = []
        manifest["openjustice_crime"] = {"title":"California DOJ OpenJustice Crimes and Clearances with Arson, 1985-2024", "source_url":OPENJUSTICE_CRIME_CSV, "row_count":0, "fetched":False, "error":repr(exc), "join_grain":"county/year/reporting agency"}
    for key, url in {"dhcs_suspension_revocation":DHCS_SUSPENSION_REVOCATION, "dhcs_sus_rev_nov":DHCS_SUS_REV_NOV, "dhcs_caloms":DHCS_CALOMS}.items():
        try:
            raw, final_url, content_type = fetch_bytes(url, timeout=90)
            text = strip_html(raw)
            (outcome_dir / f"{key}.html").write_bytes(raw)
            (outcome_dir / f"{key}.txt").write_text(text, encoding="utf-8")
            manifest[key] = {"title":key.replace("_"," "), "source_url":url, "final_url":final_url, "content_type":content_type, "text_chars":len(text), "fetched":True, "error":"", "target_mentions":{target["name"]: any(alias.lower() in text.lower() for alias in target["aliases"]) for target in TARGETS}}
        except Exception as exc:
            manifest[key] = {"title":key.replace("_"," "), "source_url":url, "fetched":False, "error":repr(exc)}
    write_json(outcome_dir / "official_outcome_source_manifest.json", manifest)
    return {"manifest": manifest, "datasets": datasets}

def latest_pair(rows: list[dict[str, Any]], year_key: str, value_key: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    usable = [row for row in rows if num(row.get(value_key)) is not None and str(row.get(year_key, "")).isdigit()]
    usable = sorted(usable, key=lambda row: int(str(row.get(year_key))))
    if len(usable) < 2: return None
    return usable[-2], usable[-1]

def build_financial_series(artifacts: Path) -> dict[str, dict[str, Any]]:
    path = artifacts / "parsed" / "irs_990_financials.json"
    if not path.exists(): return {}
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("downloaded"): by_entity[str(row.get("entity", ""))].append(row)
    summary: dict[str, dict[str, Any]] = {}
    for entity, items in by_entity.items():
        rev = latest_pair(items, "tax_period_year", "total_revenue")
        exp = latest_pair(items, "tax_period_year", "total_expenses")
        grants = latest_pair(items, "tax_period_year", "government_grants")
        summary[entity] = {
            "revenue_growth_pct": pct_change(num(rev[0].get("total_revenue")) if rev else None, num(rev[1].get("total_revenue")) if rev else None),
            "expense_growth_pct": pct_change(num(exp[0].get("total_expenses")) if exp else None, num(exp[1].get("total_expenses")) if exp else None),
            "government_grant_growth_pct": pct_change(num(grants[0].get("government_grants")) if grants else None, num(grants[1].get("government_grants")) if grants else None),
        }
    return summary

def entity_counties_and_capacity(artifacts: Path) -> dict[str, dict[str, Any]]:
    current_path = artifacts / "dhcs_current_facility_matches.json"
    status_path = artifacts / "dhcs_lcd_status_matches.json"
    current = json.loads(current_path.read_text(encoding="utf-8")) if current_path.exists() else []
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else []
    result: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        counties: set[str] = set(); total_capacity = 0.0; treatment_capacity = 0.0; facility_count = 0
        for row in current:
            if row.get("_target_slug") != target["slug"]: continue
            county = normalize_county(row.get("CountyName"));
            if county: counties.add(county)
            total_capacity += num(row.get("Total_Capacity")) or 0.0
            treatment_capacity += num(row.get("Treatment_Capacity")) or 0.0
            facility_count += 1
        for row in status:
            if row.get("_target_slug") != target["slug"]: continue
            county = normalize_county(row.get("CountyName"));
            if county: counties.add(county)
        result[target["name"]] = {"counties":sorted(counties), "current_facility_rows":facility_count, "total_capacity":total_capacity, "treatment_capacity":treatment_capacity}
    return result


def summarize_mat(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], float] = defaultdict(float)
    for row in records:
        county = normalize_county(row.get("County")); year = str(row.get("Year", ""))
        if county and year: grouped[(county, year)] += num(row.get("members")) or 0.0
    by_county: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (county, year), members in grouped.items(): by_county[county].append({"year":year, "members":members})
    return {county: sorted(rows, key=lambda row: int(row["year"])) for county, rows in by_county.items()}

def summarize_overdose(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_county: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        county = normalize_county(row.get("County"))
        if not county: continue
        by_county[county].append({"period":str(row.get("Numerator_Year_Period") or row.get("Denominator_Year_Period") or ""), "crude_rate":num(row.get("Rate/Percentage")), "age_adjusted_rate":num(row.get("Age-Adjusted_Rate")), "annotation":row.get("Annotation_Desc")})
    return {county: sorted(rows, key=lambda row: row["period"]) for county, rows in by_county.items()}

def summarize_crime(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"violent":0.0,"property":0.0})
    for row in records:
        county = normalize_county(row.get("County")); year = str(row.get("Year", ""))
        if not county or not year.isdigit(): continue
        grouped[(county, year)]["violent"] += num(row.get("Violent_sum")) or 0.0
        grouped[(county, year)]["property"] += num(row.get("Property_sum")) or 0.0
    by_county: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (county, year), values in grouped.items(): by_county[county].append({"year":year, **values})
    return {county: sorted(rows, key=lambda row: int(row["year"])) for county, rows in by_county.items()}

def summarize_homelessness_spm(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in records:
        if row.get("Metric") != "M1a": continue
        periods = [(key, num(value)) for key, value in row.items() if re.match(r"[A-Z][a-z]{2} \d{4} - [A-Z][a-z]{2} \d{4}", str(key))]
        periods = [(key, value) for key, value in periods if value is not None]
        if len(periods) < 2: continue
        prev, cur = periods[-2], periods[-1]
        rows.append({"location":row.get("Location"), "metric":"M1a", "previous_period":prev[0], "previous_value":prev[1], "current_period":cur[0], "current_value":cur[1], "change_pct":pct_change(prev[1], cur[1])})
    return rows

def latest_change(rows: list[dict[str, Any]], value_key: str, label_key: str = "year") -> dict[str, Any] | None:
    usable = [row for row in rows if num(row.get(value_key)) is not None]
    if len(usable) < 2: return None
    previous, current = usable[-2], usable[-1]
    return {"previous_label":previous.get(label_key), "previous_value":num(previous.get(value_key)), "current_label":current.get(label_key), "current_value":num(current.get(value_key)), "change_pct":pct_change(num(previous.get(value_key)), num(current.get(value_key)))}

def build_join_summary(artifacts: Path, datasets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    financial = build_financial_series(artifacts)
    coverage = entity_counties_and_capacity(artifacts)
    mat = summarize_mat(datasets.get("mat_by_county", []))
    overdose = summarize_overdose(datasets.get("drug_overdose_deaths", []))
    crime = summarize_crime(datasets.get("openjustice_crime", []))
    homelessness = summarize_homelessness_spm(datasets.get("homelessness_spm", []))
    join_rows: list[dict[str, Any]] = []
    for target in TARGETS:
        entity = target["name"]; counties = coverage.get(entity, {}).get("counties", [])
        for county in counties:
            mat_change = latest_change(mat.get(county, []), "members", "year")
            overdose_change = latest_change(overdose.get(county, []), "age_adjusted_rate", "period") or latest_change(overdose.get(county, []), "crude_rate", "period")
            violent_change = latest_change(crime.get(county, []), "violent", "year")
            property_change = latest_change(crime.get(county, []), "property", "year")
            spm_matches = [row for row in homelessness if county in str(row.get("location", "")).lower()]
            spm_change = spm_matches[0] if spm_matches else None
            outcome_flags: list[str] = []
            for label, change in [("homelessness services count", spm_change), ("drug overdose death rate", overdose_change), ("violent crime count", violent_change), ("property crime count", property_change)]:
                if change and (change.get("change_pct") or 0) > 5:
                    outcome_flags.append(f"{label} up {change.get('change_pct'):.1f}%")
            fin = financial.get(entity, {})
            spending_growth = fin.get("expense_growth_pct"); grant_growth = fin.get("government_grant_growth_pct"); revenue_growth = fin.get("revenue_growth_pct")
            level = "Low"
            if outcome_flags and (spending_growth or 0) >= 20: level = "High"
            elif outcome_flags and ((revenue_growth or 0) >= 20 or (grant_growth or 0) >= 20): level = "Medium"
            elif outcome_flags: level = "Medium"
            join_rows.append({"entity":entity, "county":display_county(county), "risk_level":level, "outcome_flags":outcome_flags, "spending_growth_pct":spending_growth, "revenue_growth_pct":revenue_growth, "government_grant_growth_pct":grant_growth, "facility_total_capacity":coverage.get(entity, {}).get("total_capacity"), "facility_treatment_capacity":coverage.get(entity, {}).get("treatment_capacity"), "mat_members_change":mat_change, "drug_overdose_rate_change":overdose_change, "violent_crime_change":violent_change, "property_crime_change":property_change, "homelessness_spm_change":spm_change, "join_caveats":["Outcome rows are county or CoC-level context; they are not provider-attributable results.", "Homelessness SPM rows are CoC-grain and matched by county-name text where possible.", "Drug overdose rows use county-level public health indicators, not provider client outcomes."]})
    return {"created_at":utc_now(), "methodology":"Join entity spending/grant growth to county/CoC outcome movement for counties where target facilities appear. This is contextual screening, not attribution.", "entity_outcome_rows":join_rows, "coverage":coverage, "row_count":len(join_rows)}

def snippet(text: str, term: str, radius: int = 170) -> str:
    idx = text.lower().find(term.lower())
    if idx < 0: return ""
    start = max(0, idx-radius); end = min(len(text), idx+len(term)+radius)
    return ("..." if start else "") + text[start:end].strip() + ("..." if end < len(text) else "")

def harvest_public_statements(statement_dir: Path) -> dict[str, Any]:
    statement_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for target in TARGETS:
        for index, url in enumerate(target["statement_urls"], start=1):
            record: dict[str, Any] = {"entity":target["name"], "slug":target["slug"], "url":url}
            try:
                raw, final_url, content_type = fetch_bytes(url, timeout=60)
                text = source_text(raw, content_type)
                page_name = f"{target['slug']}_{index}"
                (statement_dir / f"{page_name}.html").write_bytes(raw)
                (statement_dir / f"{page_name}.txt").write_text(text, encoding="utf-8")
                matches = {term: snippet(text, term) for term in STATEMENT_TERMS if term.lower() in text.lower()}
                record.update({"fetched":True, "final_url":final_url, "content_type":content_type, "sha256":sha256_bytes(raw), "text_chars":len(text), "matched_terms":sorted(matches), "snippets":matches, "local_text_path":str(statement_dir / f"{page_name}.txt")})
            except Exception as exc:
                record.update({"fetched":False, "error":repr(exc), "matched_terms":[], "snippets":{}})
            manifest.append(record)
    write_json(statement_dir / "public_statement_manifest.json", manifest)
    return {"pages": manifest}


def service_excerpt(text: str, limit: int = 1400, preferred_terms: list[str] | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    lower = cleaned.lower()
    match_index = -1
    for term in [*(preferred_terms or []), *SERVICE_EXCERPT_TERMS]:
        match_index = lower.find(term.lower())
        if match_index >= 0:
            break
    start = max(0, match_index - 180) if match_index >= 0 else 0
    if start > 0 and match_index >= 0:
        sentence_start = cleaned.rfind(". ", 0, match_index)
        if sentence_start >= 0 and sentence_start > match_index - 500:
            start = sentence_start + 2
        else:
            start = match_index
    excerpt = cleaned[start:start + limit].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if start + limit < len(cleaned):
        excerpt += "..."
    return excerpt


def harvest_service_pages(service_dir: Path) -> dict[str, Any]:
    service_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for target in TARGETS:
        for index, url in enumerate(target.get("service_urls", []), start=1):
            record: dict[str, Any] = {"entity": target["name"], "slug": target["slug"], "url": url}
            try:
                raw, final_url, content_type = fetch_bytes(url, timeout=60)
                text = source_text(raw, content_type)
                page_name = f"{target['slug']}_{index}"
                (service_dir / f"{page_name}.html").write_bytes(raw)
                (service_dir / f"{page_name}.txt").write_text(text, encoding="utf-8")
                record.update(
                    {
                        "fetched": True,
                        "final_url": final_url,
                        "content_type": content_type,
                        "sha256": sha256_bytes(raw),
                        "text_chars": len(text),
                        "excerpt": service_excerpt(text, preferred_terms=target.get("service_anchor_terms", [])),
                        "local_text_path": str(service_dir / f"{page_name}.txt"),
                    }
                )
            except Exception as exc:
                fallback = SERVICE_TEXT_FALLBACKS.get(url)
                if fallback:
                    page_name = f"{target['slug']}_{index}_fallback"
                    text = fallback["text"]
                    (service_dir / f"{page_name}.txt").write_text(text, encoding="utf-8")
                    record.update(
                        {
                            "fetched": True,
                            "fetch_method": "official_search_fallback",
                            "final_url": fallback["final_url"],
                            "content_type": fallback["content_type"],
                            "sha256": sha256_bytes(text.encode("utf-8")),
                            "text_chars": len(text),
                            "excerpt": service_excerpt(text, preferred_terms=target.get("service_anchor_terms", [])),
                            "local_text_path": str(service_dir / f"{page_name}.txt"),
                            "fallback_note": fallback["fallback_note"],
                            "fetch_error": repr(exc),
                        }
                    )
                else:
                    record.update({"fetched": False, "error": repr(exc), "excerpt": ""})
            manifest.append(record)
    write_json(service_dir / "org_service_page_manifest.json", manifest)
    return {"pages": manifest}
def markdown_table(rows: list[dict[str, Any]], columns: list[str], limit: int = 40) -> str:
    clipped = rows[:limit]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in clipped:
        cells = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, list): value = "; ".join(str(item) for item in value)
            elif isinstance(value, dict): value = json.dumps(value, sort_keys=True)[:220]
            cells.append(str(value).replace("|", "/")[:240])
        lines.append("| " + " | ".join(cells) + " |")
    if len(rows) > limit:
        lines.append("| ... | " + f"{len(rows)-limit} additional rows omitted" + " |" * (len(columns)-2))
    return "\n".join(lines)

def write_corpus_records(stage5: Path, outcome_dir: Path, outcome: dict[str, Any], join_summary: dict[str, Any], statements: dict[str, Any], services: dict[str, Any]) -> None:
    entities = [target["name"] for target in TARGETS]
    outcome_manifest = outcome["manifest"]
    outcome_rows = [{"source":key, "title":item.get("title"), "fetched":item.get("fetched"), "row_count":item.get("row_count", item.get("text_chars", "")), "join_grain":item.get("join_grain", "page/text"), "source_url":item.get("source_url"), "error":item.get("error", "")} for key, item in sorted(outcome_manifest.items())]
    outcome_record = build_record("source_table_official_outcomes", "Official outcome-source manifest for spend-versus-results review", str(outcome_dir / "official_outcome_source_manifest.json"), "source_extraction_official_outcome_table", "2026-04-24", entities, "\n".join(["Official outcome source acquisition manifest. Sources are deterministic inputs for spend-versus-results screening; they do not attribute county outcomes to any provider.", markdown_table(outcome_rows, ["source","title","fetched","row_count","join_grain","source_url","error"], limit=30)]), {"official_outcome_sources_indexed":True, "source_extraction_table":True, "missing_data":any(not item.get("fetched") for item in outcome_manifest.values())}, {"manifest_path":str(outcome_dir / "official_outcome_source_manifest.json"), "row_count":len(outcome_rows)})
    write_json(stage5 / f"{outcome_record['record_id']}.json", outcome_record)
    join_rows = join_summary.get("entity_outcome_rows", [])
    join_record = build_record("source_table_spend_vs_results_join", "Deterministic spend-versus-results join for target entities and counties", str(outcome_dir / "outcome_join_summary.json"), "source_extraction_spend_vs_results_table", "2026-04-24", entities, "\n".join(["Deterministic join from parsed IRS spending/grant growth, DHCS facility counties/capacity, and official county/CoC outcome series. County outcomes are context, not provider-attributable results.", markdown_table(join_rows, ["entity","county","risk_level","outcome_flags","spending_growth_pct","revenue_growth_pct","government_grant_growth_pct","facility_total_capacity"], limit=80)]), {"spend_vs_results_join_created":True, "source_extraction_table":True, "outcome_context_present":bool(join_rows)}, {"join_summary_path":str(outcome_dir / "outcome_join_summary.json"), "row_count":len(join_rows)})
    write_json(stage5 / f"{join_record['record_id']}.json", join_record)
    statement_pages = statements.get("pages", [])
    statement_rows = [{"entity":row.get("entity"), "fetched":row.get("fetched"), "matched_terms":row.get("matched_terms"), "url":row.get("url"), "error":row.get("error", "")} for row in statement_pages]
    statement_record = build_record("source_table_public_statements", "Official and public statement page harvest for target entities", str(outcome_dir / "statements" / "public_statement_manifest.json"), "source_extraction_public_statement_table", "2026-04-24", entities, "\n".join(["Website/public statement harvest from configured official or attributable pages. Snippets are used only for context and off-scope review prompts.", markdown_table(statement_rows, ["entity","fetched","matched_terms","url","error"], limit=60)]), {"public_statement_pages_indexed":True, "source_extraction_table":True, "missing_data":any(not row.get("fetched") for row in statement_pages)}, {"manifest_path":str(outcome_dir / "statements" / "public_statement_manifest.json"), "row_count":len(statement_pages)})
    write_json(stage5 / f"{statement_record['record_id']}.json", statement_record)
    service_pages = services.get("pages", [])
    for target in TARGETS:
        rows = [row for row in service_pages if row.get("slug") == target["slug"]]
        fetched = [row for row in rows if row.get("fetched")]
        lines = [
            f"Organization: {target['name']}",
            f"Official service/program pages fetched: {len(fetched)} of {len(rows)}.",
            "Service summary from official source(s):",
        ]
        for row in fetched:
            lines.extend(
                [
                    f"- {row.get('excerpt', '')}",
                    f"  Source: {row.get('final_url') or row.get('url')}",
                ]
            )
        for row in rows:
            if not row.get("fetched"):
                lines.append(f"- Fetch failed for {row.get('url')}: {row.get('error', '')}")
        source_uri = (fetched[0].get("final_url") or fetched[0].get("url")) if fetched else (rows[0].get("url") if rows else "")
        record = build_record(
            f"org_service_pages_{target['slug']}",
            f"Official service/program page harvest: {target['name']}",
            source_uri,
            "org_service_page",
            "2026-04-26",
            [target["name"], *target["aliases"]],
            "\n".join(lines),
            {"org_service_page_checked": True, "service_description_present": bool(fetched), "missing_data": not bool(fetched), "partial_service_page_fetch": len(fetched) < len(rows)},
            {"service_pages": rows, "manifest_path": str(outcome_dir / "service_pages" / "org_service_page_manifest.json")},
        )
        write_json(stage5 / f"{record['record_id']}.json", record)
    for target in TARGETS:
        rows = [row for row in statement_pages if row.get("slug") == target["slug"]]
        fetched = [row for row in rows if row.get("fetched")]
        terms = sorted({term for row in rows for term in row.get("matched_terms", [])})
        snippets = []
        for row in rows:
            for term, text in list((row.get("snippets") or {}).items())[:4]: snippets.append(f"{term}: {text}")
        record = build_record(f"public_statements_{target['slug']}", f"Public statement page harvest: {target['name']}", rows[0].get("url") if rows else "", "public_statement_source", "2026-04-24", [target["name"], *target["aliases"]], "\n".join([f"Fetched public/official pages: {len(fetched)} of {len(rows)}.", f"Matched review terms: {', '.join(terms) if terms else 'none from configured list'}.", "Snippets:", *snippets[:12]]), {"public_statement_source_checked":True, "missing_data":len(fetched) < len(rows), "off_scope_keyword_match":bool(terms)}, {"statement_pages":rows})
        write_json(stage5 / f"{record['record_id']}.json", record)

def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest official outcome sources, service pages, and public statement pages for CalDS spend-versus-results screening.")
    parser.add_argument("--stage4-corpus", type=Path, default=DEFAULT_STAGE4_CORPUS)
    parser.add_argument("--stage5-corpus", type=Path, default=DEFAULT_STAGE5_CORPUS)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--outcome-dir", type=Path, default=DEFAULT_OUTCOME_DIR)
    args = parser.parse_args()
    copy_corpus(args.stage4_corpus, args.stage5_corpus)
    args.outcome_dir.mkdir(parents=True, exist_ok=True)
    outcome = fetch_official_outcome_sources(args.outcome_dir)
    join_summary = build_join_summary(args.artifacts_dir, outcome["datasets"])
    write_json(args.outcome_dir / "outcome_join_summary.json", join_summary)
    statements = harvest_public_statements(args.outcome_dir / "statements")
    services = harvest_service_pages(args.outcome_dir / "service_pages")
    write_corpus_records(args.stage5_corpus, args.outcome_dir, outcome, join_summary, statements, services)
    summary = {
        "completed_at": utc_now(),
        "stage5_corpus": str(args.stage5_corpus),
        "stage5_record_count": len(list(args.stage5_corpus.glob("*.json"))),
        "outcome_dir": str(args.outcome_dir),
        "outcome_source_count": len(outcome["manifest"]),
        "joined_rows": len(join_summary.get("entity_outcome_rows", [])),
        "statement_pages": len(statements.get("pages", [])),
        "statement_pages_fetched": sum(1 for row in statements.get("pages", []) if row.get("fetched")),
        "service_pages": len(services.get("pages", [])),
        "service_pages_fetched": sum(1 for row in services.get("pages", []) if row.get("fetched")),
    }
    write_json(args.outcome_dir / "outcome_ingest_summary.json", summary)
    print(f"stage5_corpus={args.stage5_corpus}")
    print(f"records={summary['stage5_record_count']}")
    print(f"outcome_sources={summary['outcome_source_count']}")
    print(f"joined_rows={summary['joined_rows']}")
    print(f"statement_pages_fetched={summary['statement_pages_fetched']}/{summary['statement_pages']}")
    print(f"service_pages_fetched={summary['service_pages_fetched']}/{summary['service_pages']}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())



















