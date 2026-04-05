"""Main CV Parser service that orchestrates all extraction and analysis components."""

from pathlib import Path
from typing import Any
from uuid import UUID

from app.services.cv_parser.extractors.pdf_extractor import extract_pdf_text
from app.services.cv_parser.extractors.docx_extractor import extract_docx_text
from app.services.cv_parser.nlp.section_classifier import classify_sections
from app.services.cv_parser.extractors.job_entry_extractor import extract_job_entries
from app.services.cv_parser.analytics.duration_calculator import calculate_durations
from app.services.cv_parser.analytics.career_analytics import compute_career_analytics
from app.services.cv_parser.signals.career_signals import extract_career_signals


PARSER_VERSION = "1.0.0"


class CVParserError(Exception):
    """Exception raised when CV parsing fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _detect_file_type(file_path: str | Path) -> str:
    """
    Detect the file type based on extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File type string ('pdf', 'docx', 'txt', or 'unknown')
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == '.pdf':
        return 'pdf'
    elif suffix in ('.docx', '.doc'):
        return 'docx'
    elif suffix == '.txt':
        return 'txt'
    else:
        return 'unknown'


def _get_work_experience_text(sections: list[dict]) -> str:
    """
    Extract work experience section text from classified sections.
    
    Args:
        sections: List of classified sections
        
    Returns:
        Work experience section text or empty string
    """
    for section in sections:
        if section.get('type') == 'work_experience':
            return section.get('content', '')
    return ''


async def parse_cv(file_path: str | Path, user_id: UUID | None = None) -> dict:
    """
    Parse a CV file and extract all structured data.
    
    Args:
        file_path: Path to CV file (PDF or DOCX)
        user_id: Optional user ID for tracking
        
    Returns:
        dict with keys:
        - raw_text: str - extracted raw text
        - sections: list[dict] - classified sections
        - job_entries: list[dict] - extracted job entries
        - durations: dict - duration calculations
        - analytics: dict - career analytics
        - signals: list[dict] - career signals
        - metadata: dict - file metadata
        - success: bool
        - error: str | None
        - parser_version: str
    """
    file_path = Path(file_path)
    
    # Initialize result structure
    result: dict[str, Any] = {
        "raw_text": "",
        "sections": [],
        "job_entries": [],
        "durations": {},
        "analytics": {},
        "signals": [],
        "metadata": {},
        "success": False,
        "error": None,
        "parser_version": PARSER_VERSION,
    }
    
    try:
        # Validate file exists
        if not file_path.exists():
            raise CVParserError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise CVParserError(f"Path is not a file: {file_path}")
        
        # Detect file type
        file_type = _detect_file_type(file_path)
        
        if file_type == 'unknown':
            raise CVParserError(
                f"Unsupported file type: {file_path.suffix}",
                {"supported_types": [".pdf", ".docx", ".doc", ".txt"]}
            )
        
        # Step 1: Extract text based on file type
        if file_type == 'txt':
            # Plain text — read directly
            raw_text = file_path.read_text(encoding="utf-8")
            file_metadata = {"page_count": 1}
        elif file_type == 'pdf':
            extraction_result = await extract_pdf_text(file_path)
            if not extraction_result.get('success'):
                raise CVParserError(f"Text extraction failed: {extraction_result.get('error', 'Unknown')}")
            raw_text = extraction_result.get('text', '')
            file_metadata = extraction_result.get('metadata', {})
        else:  # docx
            extraction_result = await extract_docx_text(file_path)
            if not extraction_result.get('success'):
                raise CVParserError(f"Text extraction failed: {extraction_result.get('error', 'Unknown')}")
            raw_text = extraction_result.get('text', '')
            file_metadata = extraction_result.get('metadata', {})
        
        if not raw_text.strip():
            raise CVParserError("No text content extracted from file")
        
        result["raw_text"] = raw_text
        result["metadata"] = {
            **file_metadata,
            "file_type": file_type,
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
        }
        
        # Step 2: Classify sections
        classification_result = await classify_sections(raw_text)
        
        if not classification_result.get('success'):
            error_msg = classification_result.get('error', 'Unknown classification error')
            raise CVParserError(f"Section classification failed: {error_msg}")
        
        sections = classification_result.get('sections', [])
        result["sections"] = sections
        
        # Step 3: Extract job entries from work experience section
        work_experience_text = _get_work_experience_text(sections)
        
        # Fallback: if no work_experience section detected, use full raw text
        # The job entry extractor uses date-range patterns to find jobs regardless
        if not work_experience_text:
            work_experience_text = raw_text
        
        if work_experience_text:
            job_extraction_result = await extract_job_entries(work_experience_text)
            
            if job_extraction_result.get('success'):
                job_entries = job_extraction_result.get('entries', [])
                result["job_entries"] = job_entries
            else:
                # Log error but continue - job extraction failure shouldn't stop parsing
                result["metadata"]["job_extraction_error"] = job_extraction_result.get('error')
                job_entries = []
        else:
            job_entries = []
            result["metadata"]["no_work_experience_section"] = True
        
        # Step 4: Calculate durations if we have job entries
        if job_entries:
            durations_result = await calculate_durations(job_entries)
            
            if durations_result.get('success'):
                result["durations"] = {
                    "entries": durations_result.get('entries', []),
                    "total_months": durations_result.get('total_months', 0),
                    "overlaps": durations_result.get('overlaps', []),
                    "gaps": durations_result.get('gaps', []),
                }
                # Update job_entries with duration information
                result["job_entries"] = durations_result.get('entries', job_entries)
            else:
                result["metadata"]["duration_calculation_error"] = durations_result.get('error')
                result["durations"] = {
                    "entries": job_entries,
                    "total_months": 0,
                    "overlaps": [],
                    "gaps": [],
                }
        
        # Step 5: Compute career analytics if we have job entries with durations
        if result["job_entries"]:
            analytics_result = await compute_career_analytics(result["job_entries"])
            
            if analytics_result.get('success'):
                result["analytics"] = {
                    "metrics": analytics_result.get('analytics', {}),
                    "patterns": analytics_result.get('patterns', []),
                }
            else:
                result["metadata"]["analytics_error"] = analytics_result.get('error')
        
        # Step 6: Extract career signals if we have analytics
        if result["analytics"] and result["job_entries"]:
            signals_result = await extract_career_signals(
                result["job_entries"],
                result["analytics"].get("metrics", {})
            )
            
            if signals_result.get('success'):
                result["signals"] = signals_result.get('signals', [])
                result["metadata"]["signal_count"] = signals_result.get('signal_count', 0)
            else:
                result["metadata"]["signals_error"] = signals_result.get('error')
        
        # Add user_id to metadata if provided
        if user_id:
            result["metadata"]["user_id"] = str(user_id)
        
        result["success"] = True
        
    except CVParserError as e:
        result["success"] = False
        result["error"] = e.message
        if e.details:
            result["metadata"]["error_details"] = e.details
    except Exception as e:
        result["success"] = False
        result["error"] = f"Unexpected error during CV parsing: {str(e)}"
    
    return result
