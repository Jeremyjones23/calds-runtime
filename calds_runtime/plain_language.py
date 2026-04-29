from __future__ import annotations

import re


REVIEWER_GLOSSARY_LINES = [
    "- Federal Audit Clearinghouse: federal audit report, findings, and award data used for audit-control review.",
    "- California Department of Health Care Services: California licensing, facility-status, and adverse-action source context.",
    "- California Department of Housing and Community Development: state housing and homelessness grant source, including Homekey award records.",
    "- Internal Revenue Service: federal tax-return source for Form 990 revenue, expense, grant, and compensation fields.",
    "- Continuum of Care: regional homelessness-services geography used in official outcome datasets.",
    "- Homekey: California housing grant program used here as a source of project-award records.",
    "- Homeless Data Integration System: California homelessness data warehouse used for official outcome context.",
    "- Federal Housing Finance Agency Office of Inspector General: federal inspector-general source used for enforcement or prosecution press releases.",
    "- Employer Identification Number: federal tax identifier used to match nonprofit records.",
    "- Machine-readable filing data: structured source files used for source-system returns and extracts.",
    "- Source document: original audit, tax-return, or records file used as the controlling record.",
]


ACRONYM_REPLACEMENTS = [
    (r"\bWaste, Fraud, and Abuse \(WFA\)", "Waste, fraud, and abuse"),
    (r"\bWaste, fraud, and abuse \(WFA\)", "Waste, fraud, and abuse"),
    (r"\bwaste, fraud, and abuse \(WFA\)", "waste, fraud, and abuse"),
    (r"\bWFA\b", "waste, fraud, and abuse"),
    (r"\bIRS Form 990 XML\b", "Internal Revenue Service Form 990 machine-readable filing data"),
    (r"\bIRS XML\b", "Internal Revenue Service machine-readable filing data"),
    (r"\bIRS\b", "Internal Revenue Service"),
    (r"\bRaw XML\b", "Raw machine-readable filing data"),
    (r"\braw XML\b", "raw machine-readable filing data"),
    (r"\bofficial XML\b", "official machine-readable filing data"),
    (r"\bdownloaded XML\b", "downloaded machine-readable filing data"),
    (r"\bPDFs\b", "source documents"),
    (r"\bPDF\b", "source document"),
    (r"\bCSVs\b", "source data tables"),
    (r"\bCSV\b", "source data table"),
    (r"\bFAC\b", "Federal Audit Clearinghouse"),
    (r"\bDHCS\b", "California Department of Health Care Services"),
    (r"\bHCD\b", "California Department of Housing and Community Development"),
    (r"\bHDIS\b", "Homeless Data Integration System"),
    (r"\bFHFA-OIG\b", "Federal Housing Finance Agency Office of Inspector General"),
    (r"\bFHFA\b", "Federal Housing Finance Agency"),
    (r"\bcounty/CoC\b", "county or Continuum of Care"),
    (r"\bCoC\b", "Continuum of Care"),
    (r"\bSUD\b", "substance use disorder"),
    (r"\bLCD\b", "Licensing and Certification Division"),
    (r"\bEIN\b", "Employer Identification Number"),
    (r"\bNGO\b", "nonprofit organization"),
    (r"\bCEO\b", "chief executive officer"),
    (r"\bCFO\b", "chief financial officer"),
    (r"\bCOO\b", "chief operating officer"),
]


PROTECTED_TEXT_RE = re.compile(r"`[^`]*`|https?://[^\s|)]+", re.IGNORECASE)


def expand_reviewer_acronyms(text: object) -> str:
    """Expand reviewer-facing acronyms without rewriting code spans or source URLs."""

    value = str(text)
    protected: list[str] = []

    def protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"@@CALDS_PROTECTED_{len(protected) - 1}@@"

    value = PROTECTED_TEXT_RE.sub(protect, value)
    for pattern, replacement in ACRONYM_REPLACEMENTS:
        value = re.sub(pattern, replacement, value)
    for index, original in enumerate(protected):
        value = value.replace(f"@@CALDS_PROTECTED_{index}@@", original)
    return value
