"""Tests for job entry extractor."""

import pytest

from app.services.cv_parser.extractors.job_entry_extractor import (
    _extract_dates,
    _extract_company,
    _extract_job_title,
    _extract_location,
    _extract_description,
    _normalize_date,
    _split_into_entries,
    _parse_job_entry,
    extract_job_entries,
)


class TestNormalizeDate:
    """Tests for _normalize_date function."""

    def test_normalize_present(self):
        """Test normalizing 'Present' variations."""
        assert _normalize_date("Present") == "Present"
        assert _normalize_date("present") == "Present"
        assert _normalize_date("Current") == "Current"
        assert _normalize_date("current") == "Current"

    def test_normalize_slash_format(self):
        """Test normalizing MM/YYYY format."""
        assert _normalize_date("01/2020") == "2020-01"
        assert _normalize_date("12/2022") == "2022-12"
        assert _normalize_date("6/2020") == "2020-06"

    def test_normalize_month_year_format(self):
        """Test normalizing Month Year format."""
        assert _normalize_date("Jan 2020") == "2020-01"
        assert _normalize_date("January 2020") == "2020-01"
        assert _normalize_date("Dec 2022") == "2022-12"
        assert _normalize_date("December 2022") == "2022-12"

    def test_normalize_year_only(self):
        """Test normalizing year only format."""
        assert _normalize_date("2020") == "2020-01"
        assert _normalize_date("2022") == "2022-01"


class TestExtractDates:
    """Tests for _extract_dates function."""

    def test_extract_month_year_range(self):
        """Test extracting month-year date ranges."""
        text = "Software Engineer at Acme Inc. Jan 2020 - Dec 2022"
        dates = _extract_dates(text)
        assert len(dates) == 1
        assert dates[0]["start_date"] == "2020-01"
        assert dates[0]["end_date"] == "2022-12"

    def test_extract_full_month_year_range(self):
        """Test extracting full month name date ranges."""
        text = "January 2020 - December 2022"
        dates = _extract_dates(text)
        assert len(dates) == 1
        assert dates[0]["start_date"] == "2020-01"
        assert dates[0]["end_date"] == "2022-12"

    def test_extract_slash_format_range(self):
        """Test extracting slash format date ranges."""
        text = "01/2020 - 12/2022"
        dates = _extract_dates(text)
        assert len(dates) == 1
        assert dates[0]["start_date"] == "2020-01"
        assert dates[0]["end_date"] == "2022-12"

    def test_extract_year_range(self):
        """Test extracting year-only date ranges."""
        text = "2020 - 2022"
        dates = _extract_dates(text)
        assert len(dates) == 1
        assert dates[0]["start_date"] == "2020-01"
        assert dates[0]["end_date"] == "2022-01"

    def test_extract_with_present(self):
        """Test extracting date ranges with Present."""
        text = "Jan 2020 - Present"
        dates = _extract_dates(text)
        assert len(dates) == 1
        assert dates[0]["start_date"] == "2020-01"
        assert dates[0]["end_date"] == "Present"

    def test_extract_with_current(self):
        """Test extracting date ranges with Current."""
        text = "2020 - Current"
        dates = _extract_dates(text)
        assert len(dates) == 1
        assert dates[0]["start_date"] == "2020-01"
        assert dates[0]["end_date"] == "Current"


class TestSplitIntoEntries:
    """Tests for _split_into_entries function."""

    def test_split_by_date_patterns(self):
        """Test splitting entries by date patterns."""
        text = """Software Engineer
Acme Inc.
Jan 2020 - Dec 2022
Developed key features

Senior Developer
Tech Corp
2021 - Present
Leading a team"""
        entries = _split_into_entries(text)
        assert len(entries) == 2

    def test_split_by_blank_lines(self):
        """Test splitting entries by blank lines when no dates."""
        text = """First job entry
with multiple lines

Second job entry
with more lines"""
        entries = _split_into_entries(text)
        assert len(entries) == 2

    def test_single_entry(self):
        """Test with single entry."""
        text = "Software Engineer at Acme Inc. Jan 2020 - Present"
        entries = _split_into_entries(text)
        assert len(entries) == 1


class TestExtractJobTitle:
    """Tests for _extract_job_title function."""

    def test_extract_engineer_title(self):
        """Test extracting engineer title."""
        text = "Software Engineer at Acme Inc."
        from app.services.cv_parser.extractors.job_entry_extractor import _get_nlp
        nlp = _get_nlp()
        doc = nlp(text)
        title, confidence = _extract_job_title(text, doc)
        assert "engineer" in title.lower()
        assert confidence > 0.5

    def test_extract_manager_title(self):
        """Test extracting manager title."""
        text = "Product Manager at Tech Corp"
        from app.services.cv_parser.extractors.job_entry_extractor import _get_nlp
        nlp = _get_nlp()
        doc = nlp(text)
        title, confidence = _extract_job_title(text, doc)
        assert "manager" in title.lower()
        assert confidence > 0.5


class TestExtractLocation:
    """Tests for _extract_location function."""

    def test_extract_city_state(self):
        """Test extracting city, state location."""
        text = "Software Engineer at Acme Inc. San Francisco, CA"
        location, confidence = _extract_location(text)
        assert "San Francisco" in location
        assert confidence > 0.5

    def test_extract_remote(self):
        """Test extracting remote location."""
        text = "Software Engineer (Remote) at Acme Inc."
        location, confidence = _extract_location(text)
        assert "Remote" in location
        assert confidence > 0.5


class TestExtractDescription:
    """Tests for _extract_description function."""

    def test_extract_description(self):
        """Test extracting job description."""
        text = """Software Engineer
Acme Inc.
Jan 2020 - Present
San Francisco, CA

Developed key features for the platform.
Led a team of 5 engineers.
Improved performance by 50%."""
        dates = [{"start_date": "2020-01", "end_date": "Present"}]
        description = _extract_description(text, dates)
        assert "Developed key features" in description
        assert "Led a team" in description


class TestParseJobEntry:
    """Tests for _parse_job_entry function."""

    def test_parse_complete_entry(self):
        """Test parsing a complete job entry."""
        text = """Software Engineer
Acme Inc.
Jan 2020 - Dec 2022
San Francisco, CA

Developed key features for the platform."""
        entry = _parse_job_entry(text)
        assert entry["job_title"] != ""
        assert entry["start_date"] == "2020-01"
        assert entry["end_date"] == "2022-12"
        assert entry["description"] != ""
        assert entry["confidence"] > 0


class TestExtractJobEntries:
    """Tests for extract_job_entries function."""

    @pytest.mark.asyncio
    async def test_extract_empty_text(self):
        """Test extracting from empty text."""
        result = await extract_job_entries("")
        assert result["success"] is True
        assert result["entry_count"] == 0
        assert result["entries"] == []

    @pytest.mark.asyncio
    async def test_extract_single_entry(self):
        """Test extracting single job entry."""
        text = """Software Engineer
Acme Inc.
Jan 2020 - Present
San Francisco, CA

Developed key features."""
        result = await extract_job_entries(text)
        assert result["success"] is True
        assert result["entry_count"] == 1
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["start_date"] == "2020-01"
        assert entry["end_date"] == "Present"

    @pytest.mark.asyncio
    async def test_extract_multiple_entries(self):
        """Test extracting multiple job entries."""
        text = """Software Engineer
Acme Inc.
Jan 2020 - Dec 2022

Senior Developer
Tech Corp
2021 - Present"""
        result = await extract_job_entries(text)
        assert result["success"] is True
        assert result["entry_count"] == 2
        assert len(result["entries"]) == 2

    @pytest.mark.asyncio
    async def test_extract_various_date_formats(self):
        """Test extracting with various date formats."""
        text = """Engineer at Company A 01/2020 - 12/2022

Developer at Company B 2020 - Present

Manager at Company C January 2020 - December 2022"""
        result = await extract_job_entries(text)
        assert result["success"] is True
        assert result["entry_count"] == 3
