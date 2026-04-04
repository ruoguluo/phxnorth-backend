"""Duration calculator for computing job durations and handling overlapping employment periods."""

import re
from datetime import date, datetime
from typing import Any


# Date parsing constants
CURRENT_KEYWORDS = {"present", "current", "now", "today"}


def _parse_date(date_str: str | None) -> date:
    """
    Parse a date string to a date object.
    
    Args:
        date_str: Date string in various formats (YYYY-MM, YYYY, Present/Current)
        
    Returns:
        date object representing the parsed date
        
    Raises:
        ValueError: If date string cannot be parsed
    """
    if not date_str:
        # Missing end_date means current job
        return date.today()
    
    date_str = date_str.strip()
    date_lower = date_str.lower()
    
    # Handle Present/Current/Now/Today
    if date_lower in CURRENT_KEYWORDS:
        return date.today()
    
    # Try YYYY-MM format
    if re.match(r"^\d{4}-\d{2}$", date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m").date()
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}")
    
    # Try YYYY format - assume January
    if re.match(r"^\d{4}$", date_str):
        try:
            year = int(date_str)
            return date(year, 1, 1)
        except ValueError:
            raise ValueError(f"Invalid year: {date_str}")
    
    raise ValueError(f"Unsupported date format: {date_str}")


def _calculate_months_between(start_date: date, end_date: date) -> int:
    """
    Calculate the number of months between two dates (inclusive).
    
    Args:
        start_date: Start date
        end_date: End date (must be >= start_date)
        
    Returns:
        Number of months between dates
    """
    if end_date < start_date:
        return 0
    
    # Calculate months difference
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    
    # Add 1 to include the start month
    return months + 1


def _detect_overlaps(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Detect overlapping employment periods.
    
    Args:
        entries: List of job entries with parsed start_date and end_date as date objects
        
    Returns:
        List of overlap dictionaries describing each overlap
    """
    overlaps = []
    
    # Sort entries by start date
    sorted_entries = sorted(entries, key=lambda x: x["_start_date"])
    
    for i in range(len(sorted_entries)):
        for j in range(i + 1, len(sorted_entries)):
            entry1 = sorted_entries[i]
            entry2 = sorted_entries[j]
            
            # Check if entry2 starts before entry1 ends
            if entry2["_start_date"] <= entry1["_end_date"]:
                # Calculate overlap period
                overlap_start = max(entry1["_start_date"], entry2["_start_date"])
                overlap_end = min(entry1["_end_date"], entry2["_end_date"])
                
                if overlap_start <= overlap_end:
                    overlap_months = _calculate_months_between(overlap_start, overlap_end)
                    
                    overlaps.append({
                        "entry1_index": entries.index(entry1),
                        "entry2_index": entries.index(entry2),
                        "entry1_company": entry1.get("company_name", ""),
                        "entry2_company": entry2.get("company_name", ""),
                        "overlap_start": overlap_start.isoformat(),
                        "overlap_end": overlap_end.isoformat(),
                        "overlap_months": overlap_months,
                    })
    
    return overlaps


def _calculate_unique_time_span(entries: list[dict[str, Any]]) -> tuple[date, date, int]:
    """
    Calculate the unique time span covered by all entries (without double-counting overlaps).
    
    Args:
        entries: List of job entries with parsed dates
        
    Returns:
        Tuple of (earliest_start, latest_end, total_unique_months)
    """
    if not entries:
        return date.today(), date.today(), 0
    
    # Find overall date range
    earliest_start = min(e["_start_date"] for e in entries)
    latest_end = max(e["_end_date"] for e in entries)
    
    # Calculate unique months using interval merging
    # Sort by start date
    sorted_intervals = sorted(
        [(e["_start_date"], e["_end_date"]) for e in entries],
        key=lambda x: x[0]
    )
    
    # Merge overlapping intervals
    merged = []
    for start, end in sorted_intervals:
        if not merged:
            merged.append([start, end])
        else:
            last_start, last_end = merged[-1]
            if start <= last_end:
                # Overlapping or adjacent, merge them
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end])
    
    # Calculate total unique months
    total_months = sum(
        _calculate_months_between(start, end) for start, end in merged
    )
    
    return earliest_start, latest_end, total_months


def _detect_gaps(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Detect gaps between employment periods.
    
    Args:
        entries: List of job entries with parsed dates
        
    Returns:
        List of gap dictionaries describing each gap
    """
    gaps = []
    
    if len(entries) < 2:
        return gaps
    
    # Sort entries by start date
    sorted_entries = sorted(entries, key=lambda x: x["_start_date"])
    
    for i in range(len(sorted_entries) - 1):
        current_entry = sorted_entries[i]
        next_entry = sorted_entries[i + 1]
        
        # Check for gap
        if next_entry["_start_date"] > current_entry["_end_date"]:
            gap_start = current_entry["_end_date"]
            gap_end = next_entry["_start_date"]
            # Calculate gap months (months between end of job A and start of job B)
            # For Jan 2020 - Jun 2020 to Jan 2021 - Jun 2021, gap is Jul-Dec = 6 months
            gap_months = (gap_end.year - gap_start.year) * 12 + (gap_end.month - gap_start.month) - 1
            
            if gap_months > 0:
                gaps.append({
                    "after_entry_index": entries.index(current_entry),
                    "before_entry_index": entries.index(next_entry),
                    "after_company": current_entry.get("company_name", ""),
                    "before_company": next_entry.get("company_name", ""),
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                    "gap_months": gap_months,
                })
    
    return gaps


def _calculate_career_span_months(entries: list[dict[str, Any]]) -> int:
    """
    Calculate total career span from earliest start to latest end.
    
    Args:
        entries: List of job entries with parsed dates
        
    Returns:
        Total career span in months
    """
    if not entries:
        return 0
    
    earliest_start = min(e["_start_date"] for e in entries)
    latest_end = max(e["_end_date"] for e in entries)
    
    return _calculate_months_between(earliest_start, latest_end)


async def calculate_durations(job_entries: list[dict]) -> dict:
    """
    Calculate durations for job entries with overlap resolution.
    
    Args:
        job_entries: List of job entry dicts with start_date and end_date
        
    Returns:
        dict with keys:
        - entries: list[dict] - job entries with added duration_months
        - total_months: int - total career span in months
        - overlaps: list[dict] - detected overlapping periods
        - gaps: list[dict] - detected gaps between jobs
        - success: bool
        - error: str | None
    """
    try:
        if not job_entries:
            return {
                "entries": [],
                "total_months": 0,
                "overlaps": [],
                "gaps": [],
                "success": True,
                "error": None,
            }
        
        # Parse dates and add to entries
        parsed_entries = []
        for entry in job_entries:
            try:
                start_date = _parse_date(entry.get("start_date"))
                end_date = _parse_date(entry.get("end_date"))
                
                # Ensure start <= end
                if start_date > end_date:
                    end_date = start_date
                
                parsed_entry = entry.copy()
                parsed_entry["_start_date"] = start_date
                parsed_entry["_end_date"] = end_date
                parsed_entries.append(parsed_entry)
            except ValueError as e:
                # Skip entries with invalid dates
                parsed_entry = entry.copy()
                parsed_entry["_start_date"] = date.today()
                parsed_entry["_end_date"] = date.today()
                parsed_entry["duration_months"] = 0
                parsed_entry["_date_error"] = str(e)
                parsed_entries.append(parsed_entry)
        
        # Calculate duration for each entry
        result_entries = []
        for entry in parsed_entries:
            if "_date_error" in entry:
                # Entry had date parsing error
                clean_entry = {k: v for k, v in entry.items() if not k.startswith("_")}
                clean_entry["duration_months"] = 0
                result_entries.append(clean_entry)
            else:
                duration = _calculate_months_between(entry["_start_date"], entry["_end_date"])
                clean_entry = {k: v for k, v in entry.items() if not k.startswith("_")}
                clean_entry["duration_months"] = duration
                result_entries.append(clean_entry)
        
        # Detect overlaps
        overlaps = _detect_overlaps(parsed_entries)
        
        # Detect gaps
        gaps = _detect_gaps(parsed_entries)
        
        # Calculate total unique career span (without double-counting overlaps)
        _, _, total_unique_months = _calculate_unique_time_span(parsed_entries)
        
        return {
            "entries": result_entries,
            "total_months": total_unique_months,
            "overlaps": overlaps,
            "gaps": gaps,
            "success": True,
            "error": None,
        }
        
    except Exception as e:
        return {
            "entries": [],
            "total_months": 0,
            "overlaps": [],
            "gaps": [],
            "success": False,
            "error": f"Failed to calculate durations: {str(e)}",
        }
