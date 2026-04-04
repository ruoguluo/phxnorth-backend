"""Job entry extractor for parsing work experience sections."""

import re
from datetime import datetime
from typing import Any

import spacy

# spaCy model (lazy loaded)
_nlp: spacy.Language | None = None


def _get_nlp() -> spacy.Language:
    """Get or initialize spaCy NLP model."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not downloaded, use basic processing
            _nlp = spacy.blank("en")
    return _nlp


# Date patterns to match various formats
DATE_PATTERNS = [
    # Month Year - Month Year (e.g., "Jan 2020 - Dec 2022" or "January 2020 - December 2022")
    re.compile(
        r"(?:^|\n|\s)(?:" + 
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})" +
        r"\s*[-–—]\s*" +
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|Current)" +
        r")",
        re.IGNORECASE
    ),
    # MM/YYYY - MM/YYYY (e.g., "01/2020 - 12/2022")
    re.compile(
        r"(?:^|\n|\s)(?:\d{1,2}/\d{4}\s*[-–—]\s*(?:\d{1,2}/\d{4}|Present|Current))",
        re.IGNORECASE
    ),
    # Year - Year (e.g., "2020 - 2022" or "2020 - Present")
    re.compile(
        r"(?:^|\n|\s)(?:\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current))",
        re.IGNORECASE
    ),
    # Single year (e.g., "2020")
    re.compile(r"(?:^|\n|\s)(?:\d{4})"),
]

# Pattern to extract start and end dates from a date range string
DATE_RANGE_PATTERN = re.compile(
    r"(?P<start>(?:\d{1,2}/\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}))" +
    r"\s*[-–—]\s*" +
    r"(?P<end>(?:\d{1,2}/\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|Current))",
    re.IGNORECASE
)

# Month mapping
MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}


def _normalize_date(date_str: str) -> str:
    """
    Normalize a date string to YYYY-MM format.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Normalized date string in YYYY-MM format, or original if parsing fails
    """
    date_str = date_str.strip()
    
    # Handle Present/Current
    if date_str.lower() in ("present", "current"):
        return date_str.capitalize()
    
    # Try MM/YYYY format
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 2:
            month, year = parts
            return f"{year}-{month.zfill(2)}"
    
    # Try Month Year format
    month_match = re.match(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\.?\s+(\d{4})",
        date_str,
        re.IGNORECASE
    )
    if month_match:
        month_abbr = month_match.group(1).lower().rstrip(".")
        year = month_match.group(2)
        month_num = MONTH_MAP.get(month_abbr, "01")
        return f"{year}-{month_num}"
    
    # Try Year only format
    year_match = re.match(r"(\d{4})", date_str)
    if year_match:
        return f"{year_match.group(1)}-01"
    
    return date_str


def _extract_dates(text: str) -> list[dict[str, str]]:
    """
    Extract date ranges from text.
    
    Args:
        text: Text to extract dates from
        
    Returns:
        List of dicts with start_date and end_date
    """
    dates = []
    
    for match in DATE_RANGE_PATTERN.finditer(text):
        start_date = _normalize_date(match.group("start"))
        end_date = _normalize_date(match.group("end"))
        dates.append({
            "start_date": start_date,
            "end_date": end_date,
            "raw": match.group(0),
        })
    
    return dates


def _split_into_entries(text: str) -> list[str]:
    """
    Split work experience text into individual job entries.
    
    Uses date patterns and blank lines to identify entry boundaries.
    
    Args:
        text: Work experience section text
        
    Returns:
        List of entry texts
    """
    entries = []
    current_entry: list[str] = []
    
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts with a date pattern (indicating new entry)
        is_date_line = False
        for pattern in DATE_PATTERNS:
            if pattern.match(line.strip()):
                is_date_line = True
                break
        
        # If we found a date and have content, save current entry
        if is_date_line and current_entry:
            entry_text = "\n".join(current_entry).strip()
            if entry_text:
                entries.append(entry_text)
            current_entry = [line]
        else:
            current_entry.append(line)
        
        i += 1
    
    # Don't forget the last entry
    if current_entry:
        entry_text = "\n".join(current_entry).strip()
        if entry_text:
            entries.append(entry_text)
    
    # If no entries found using date patterns, try splitting by blank lines
    if not entries:
        paragraphs = text.split("\n\n")
        entries = [p.strip() for p in paragraphs if p.strip()]
    
    return entries


def _extract_company(entry_text: str, doc: spacy.tokens.Doc) -> tuple[str, float]:
    """
    Extract company name from entry text.
    
    Args:
        entry_text: The job entry text
        doc: spaCy doc object
        
    Returns:
        Tuple of (company_name, confidence)
    """
    # First try to find ORG entities
    orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    
    if orgs:
        # Use the first ORG entity as company
        return orgs[0], 0.8
    
    # Fallback: Look for common company indicators
    lines = entry_text.split("\n")
    for line in lines[:3]:  # Check first 3 lines
        # Skip date lines
        if any(pattern.search(line) for pattern in DATE_PATTERNS):
            continue
        
        # Look for @ symbol (often used for company)
        if "@" in line:
            parts = line.split("@")
            if len(parts) >= 2:
                company = parts[1].split()[0].strip(" ,")
                if company:
                    return company, 0.6
        
        # Check if line looks like a company name (capitalized, reasonable length)
        cleaned = line.strip()
        if cleaned and len(cleaned) > 2 and len(cleaned) < 100:
            # Avoid lines that are clearly not company names
            if not any(kw in cleaned.lower() for kw in [
                "experience", "employment", "work", "job", "position",
                "present", "current", "january", "february", "march",
                "april", "may", "june", "july", "august", "september",
                "october", "november", "december"
            ]):
                return cleaned, 0.5
    
    return "", 0.3


def _extract_job_title(entry_text: str, doc: spacy.tokens.Doc) -> tuple[str, float]:
    """
    Extract job title from entry text.
    
    Args:
        entry_text: The job entry text
        doc: spaCy doc object
        
    Returns:
        Tuple of (job_title, confidence)
    """
    # Common job title keywords
    title_keywords = [
        "engineer", "manager", "director", "developer", "analyst",
        "consultant", "specialist", "coordinator", "administrator",
        "supervisor", "lead", "head", "chief", "vice president", "vp",
        "president", "ceo", "cto", "cfo", "cio", "coo",
        "architect", "designer", "strategist", "associate", "intern",
        "assistant", "representative", "officer", "executive",
        "scientist", "researcher", "technician", "operator",
    ]
    
    lines = entry_text.split("\n")
    
    for line in lines[:5]:  # Check first 5 lines
        line_lower = line.lower()
        
        # Skip date lines
        if any(pattern.search(line) for pattern in DATE_PATTERNS):
            continue
        
        # Check for common title keywords
        for keyword in title_keywords:
            if keyword in line_lower:
                # Clean up the line
                title = line.strip()
                # Remove common prefixes/suffixes
                title = re.sub(r"^(at|with)\s+", "", title, flags=re.IGNORECASE)
                return title, 0.7
    
    # Fallback: Use first non-date, non-company line
    for line in lines[:3]:
        if any(pattern.search(line) for pattern in DATE_PATTERNS):
            continue
        cleaned = line.strip()
        if cleaned and len(cleaned) > 2 and len(cleaned) < 100:
            return cleaned, 0.5
    
    return "", 0.3


def _extract_location(entry_text: str) -> tuple[str, float]:
    """
    Extract location from entry text.
    
    Args:
        entry_text: The job entry text
        
    Returns:
        Tuple of (location, confidence)
    """
    # Common location patterns
    location_patterns = [
        # City, State/Country
        re.compile(r"([A-Z][a-zA-Z\s]+),?\s*([A-Z]{2}|[A-Z][a-zA-Z]+)"),
        # Remote indicators
        re.compile(r"\b(Remote|Hybrid|On-site|Onsite)\b", re.IGNORECASE),
    ]
    
    lines = entry_text.split("\n")
    
    for line in lines[:5]:
        # Skip date lines
        if any(pattern.search(line) for pattern in DATE_PATTERNS):
            continue
        
        for pattern in location_patterns:
            match = pattern.search(line)
            if match:
                return match.group(0), 0.7
    
    return "", 0.0


def _extract_description(entry_text: str, dates: list[dict[str, str]]) -> str:
    """
    Extract job description from entry text.
    
    Args:
        entry_text: The job entry text
        dates: Extracted dates to exclude from description
        
    Returns:
        Job description text
    """
    description_lines = []
    
    for line in entry_text.split("\n"):
        # Skip date lines
        if any(pattern.search(line) for pattern in DATE_PATTERNS):
            continue
        
        # Skip lines that are likely headers (company, title)
        stripped = line.strip()
        if not stripped:
            continue
        
        # Check if line is too short to be a description
        if len(stripped) < 10:
            continue
        
        description_lines.append(stripped)
    
    return "\n".join(description_lines)


def _parse_job_entry(entry_text: str) -> dict[str, Any]:
    """
    Parse a single job entry text into structured data.
    
    Args:
        entry_text: Text of a single job entry
        
    Returns:
        Dict with company_name, job_title, start_date, end_date, location, description, confidence
    """
    nlp = _get_nlp()
    doc = nlp(entry_text[:3000])  # Limit for performance
    
    # Extract dates
    dates = _extract_dates(entry_text)
    start_date = dates[0]["start_date"] if dates else ""
    end_date = dates[0]["end_date"] if dates else ""
    
    # Extract company
    company_name, company_confidence = _extract_company(entry_text, doc)
    
    # Extract job title
    job_title, title_confidence = _extract_job_title(entry_text, doc)
    
    # Extract location
    location, location_confidence = _extract_location(entry_text)
    
    # Extract description
    description = _extract_description(entry_text, dates)
    
    # Calculate overall confidence
    confidence_factors = [
        company_confidence,
        title_confidence,
        0.9 if start_date else 0.3,  # Date confidence
        0.8 if description else 0.3,  # Description confidence
    ]
    overall_confidence = sum(confidence_factors) / len(confidence_factors)
    
    return {
        "company_name": company_name,
        "job_title": job_title,
        "start_date": start_date,
        "end_date": end_date,
        "location": location,
        "description": description,
        "confidence": round(overall_confidence, 2),
    }


async def extract_job_entries(work_experience_text: str) -> dict[str, Any]:
    """
    Extract job entries from work experience section.
    
    Args:
        work_experience_text: The work experience section text
        
    Returns:
        dict with keys:
        - entries: list[dict] - each with company_name, job_title, start_date,
                   end_date, location, description, confidence
        - entry_count: int
        - success: bool
        - error: str | None
    """
    try:
        if not work_experience_text or not work_experience_text.strip():
            return {
                "entries": [],
                "entry_count": 0,
                "success": True,
                "error": None,
            }
        
        # Split into individual job entries
        entry_texts = _split_into_entries(work_experience_text)
        
        # Parse each entry
        entries = []
        for entry_text in entry_texts:
            if entry_text.strip():
                entry = _parse_job_entry(entry_text)
                entries.append(entry)
        
        return {
            "entries": entries,
            "entry_count": len(entries),
            "success": True,
            "error": None,
        }
        
    except Exception as e:
        return {
            "entries": [],
            "entry_count": 0,
            "success": False,
            "error": f"Failed to extract job entries: {str(e)}",
        }
