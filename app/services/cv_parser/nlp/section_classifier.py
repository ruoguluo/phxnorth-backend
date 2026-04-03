"""NLP section classifier for CV parsing using spaCy."""

import re
from typing import Any

import spacy


# Section keywords for classification
SECTION_KEYWORDS: dict[str, list[str]] = {
    "work_experience": [
        "experience",
        "work experience",
        "employment",
        "work history",
        "professional experience",
        "career history",
        "job history",
        "professional background",
        "positions held",
        "work background",
    ],
    "education": [
        "education",
        "academic background",
        "qualifications",
        "academic qualifications",
        "educational background",
        "degrees",
        "academic history",
        "training",
        "certifications",
        "courses",
    ],
    "skills": [
        "skills",
        "technical skills",
        "competencies",
        "expertise",
        "proficiencies",
        "key skills",
        "core competencies",
        "professional skills",
        "abilities",
        "skill set",
    ],
    "summary": [
        "summary",
        "profile",
        "objective",
        "about",
        "professional summary",
        "career summary",
        "personal profile",
        "career objective",
        "about me",
        "overview",
    ],
    "contact_info": [
        "contact",
        "contact information",
        "personal info",
        "personal information",
        "contact details",
        "personal details",
    ],
}

# Compile regex patterns for section header detection
HEADER_PATTERNS = [
    re.compile(r"^\s*([A-Z][A-Z\s&]+)\s*[:\-]?\s*$"),  # ALL CAPS headers
    re.compile(r"^\s*([A-Z][a-zA-Z\s&]+)\s*[:\-]\s*$"),  # Title Case with colon/dash
    re.compile(r"^\s*([A-Z][a-zA-Z\s&]+)\s*$"),  # Title Case without punctuation
]

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


def _is_section_header(line: str) -> tuple[bool, str]:
    """
    Check if a line is a section header.
    
    Returns:
        Tuple of (is_header, cleaned_header_text)
    """
    stripped = line.strip()
    
    if not stripped:
        return False, ""
    
    # Check for header patterns
    for pattern in HEADER_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return True, match.group(1).strip().lower()
    
    return False, ""


def _classify_section(header_text: str) -> tuple[str, float]:
    """
    Classify a section header into a section type.
    
    Args:
        header_text: The cleaned header text (lowercase)
        
    Returns:
        Tuple of (section_type, confidence_score)
    """
    best_match = "other"
    best_score = 0.0
    
    for section_type, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            # Exact match
            if header_text == keyword:
                return section_type, 1.0
            
            # Contains keyword
            if keyword in header_text:
                score = len(keyword) / len(header_text)
                if score > best_score:
                    best_score = score
                    best_match = section_type
            
            # Keyword contains header (for partial matches)
            if header_text in keyword:
                score = len(header_text) / len(keyword) * 0.8
                if score > best_score:
                    best_score = score
                    best_match = section_type
    
    # Use spaCy for semantic similarity if no keyword match
    if best_score < 0.5:
        nlp = _get_nlp()
        header_doc = nlp(header_text)
        
        for section_type, keywords in SECTION_KEYWORDS.items():
            for keyword in keywords:
                keyword_doc = nlp(keyword)
                if header_doc and keyword_doc and len(header_doc) > 0 and len(keyword_doc) > 0:
                    try:
                        similarity = header_doc.similarity(keyword_doc)
                        if similarity > best_score and similarity > 0.7:
                            best_score = similarity
                            best_match = section_type
                    except Exception:
                        continue
    
    return best_match, min(best_score, 1.0)


def _split_into_sections(text: str) -> list[dict[str, Any]]:
    """
    Split CV text into sections based on headers.
    
    Args:
        text: The full CV text
        
    Returns:
        List of sections with type, content, and confidence
    """
    lines = text.split("\n")
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    current_content: list[str] = []
    
    for line in lines:
        is_header, header_text = _is_section_header(line)
        
        if is_header:
            # Save previous section
            if current_section and current_content:
                current_section["content"] = "\n".join(current_content).strip()
                sections.append(current_section)
            
            # Start new section
            section_type, confidence = _classify_section(header_text)
            current_section = {
                "type": section_type,
                "header": line.strip(),
                "confidence": confidence,
                "content": "",
            }
            current_content = []
        else:
            current_content.append(line)
    
    # Don't forget the last section
    if current_section and current_content:
        current_section["content"] = "\n".join(current_content).strip()
        sections.append(current_section)
    
    # If no sections detected, treat entire text as "other"
    if not sections:
        sections.append({
            "type": "other",
            "header": "",
            "confidence": 0.5,
            "content": text.strip(),
        })
    
    return sections


def _enhance_with_spacy(sections: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    """
    Enhance section classification using spaCy NER and text analysis.
    
    Args:
        sections: List of detected sections
        text: Full text for context
        
    Returns:
        Enhanced sections with updated confidence scores
    """
    nlp = _get_nlp()
    
    for section in sections:
        section_text = section["content"]
        if not section_text:
            continue
        
        doc = nlp(section_text[:5000])  # Limit for performance
        
        # Adjust confidence based on content analysis
        if section["type"] == "work_experience":
            # Look for date patterns, job titles, companies
            date_count = len(re.findall(r"\b(19|20)\d{2}\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\bpresent\b", section_text.lower()))
            if date_count >= 2:
                section["confidence"] = min(section["confidence"] + 0.1, 1.0)
        
        elif section["type"] == "education":
            # Look for degree keywords
            degree_keywords = ["bachelor", "master", "phd", "degree", "university", "college", "school"]
            degree_count = sum(1 for kw in degree_keywords if kw in section_text.lower())
            if degree_count >= 1:
                section["confidence"] = min(section["confidence"] + 0.1, 1.0)
        
        elif section["type"] == "skills":
            # Look for bullet points or comma-separated lists
            bullet_count = section_text.count("•") + section_text.count("-") + section_text.count("*")
            comma_count = section_text.count(",")
            if bullet_count >= 3 or comma_count >= 5:
                section["confidence"] = min(section["confidence"] + 0.1, 1.0)
        
        elif section["type"] == "contact_info":
            # Look for email, phone patterns
            email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
            phone_pattern = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}")
            
            if email_pattern.search(section_text) or phone_pattern.search(section_text):
                section["confidence"] = min(section["confidence"] + 0.15, 1.0)
    
    return sections


async def classify_sections(text: str) -> dict[str, Any]:
    """
    Classify CV text into sections.
    
    Args:
        text: The CV text to classify
        
    Returns:
        Dictionary with keys:
        - sections: list[dict] - each with type, content, confidence
        - section_types: list[str] - detected section types
        - success: bool
        - error: str | None
    """
    try:
        if not text or not text.strip():
            return {
                "sections": [],
                "section_types": [],
                "success": True,
                "error": None,
            }
        
        # Split into sections
        sections = _split_into_sections(text)
        
        # Enhance with spaCy analysis
        sections = _enhance_with_spacy(sections, text)
        
        # Extract section types
        section_types = [s["type"] for s in sections]
        
        # Remove internal fields from output
        output_sections = [
            {
                "type": s["type"],
                "content": s["content"],
                "confidence": round(s["confidence"], 2),
            }
            for s in sections
        ]
        
        return {
            "sections": output_sections,
            "section_types": section_types,
            "success": True,
            "error": None,
        }
        
    except Exception as e:
        return {
            "sections": [],
            "section_types": [],
            "success": False,
            "error": f"Failed to classify sections: {str(e)}",
        }
