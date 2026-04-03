import asyncio
from pathlib import Path
import tempfile

import pytest

from app.services.cv_parser.extractors.pdf_extractor import (
    extract_pdf_text,
    PDFExtractionError,
    _extract_pdf_sync,
)


class TestPDFExtractionError:
    """Tests for PDFExtractionError exception."""

    def test_error_with_message_only(self):
        """Test error can be created with just a message."""
        error = PDFExtractionError("Test error")
        assert error.message == "Test error"
        assert error.details == {}
        assert str(error) == "Test error"

    def test_error_with_details(self):
        """Test error can be created with details."""
        details = {"file_path": "/test/file.pdf"}
        error = PDFExtractionError("Test error", details)
        assert error.message == "Test error"
        assert error.details == details


class TestExtractPDFSync:
    """Tests for synchronous PDF extraction."""

    def test_file_not_found(self):
        """Test extraction fails for non-existent file."""
        with pytest.raises(PDFExtractionError) as exc_info:
            _extract_pdf_sync("/nonexistent/file.pdf")
        assert "File not found" in str(exc_info.value)

    def test_path_is_not_file(self, tmp_path):
        """Test extraction fails when path is a directory."""
        with pytest.raises(PDFExtractionError) as exc_info:
            _extract_pdf_sync(tmp_path)
        assert "Path is not a file" in str(exc_info.value)


class TestExtractPDFTextAsync:
    """Tests for async PDF extraction."""

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_error(self):
        """Test async extraction handles non-existent file gracefully."""
        result = await extract_pdf_text("/nonexistent/file.pdf")
        
        assert result["success"] is False
        assert "File not found" in result["error"]
        assert result["text"] == ""
        assert result["pages"] == []
        assert result["metadata"]["page_count"] == 0

    @pytest.mark.asyncio
    async def test_directory_path_returns_error(self, tmp_path):
        """Test async extraction handles directory path gracefully."""
        result = await extract_pdf_text(tmp_path)
        
        assert result["success"] is False
        assert "Path is not a file" in result["error"]
        assert result["text"] == ""
        assert result["pages"] == []

    @pytest.mark.asyncio
    async def test_extracts_simple_pdf(self):
        """Test extraction from a simple PDF file."""
        # Create a simple test PDF using pdfplumber
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Create a simple PDF
            c = canvas.Canvas(tmp_path, pagesize=letter)
            c.drawString(100, 700, "Hello World")
            c.drawString(100, 680, "This is a test PDF")
            c.showPage()
            c.drawString(100, 700, "Page 2 content")
            c.showPage()
            c.save()
            
            result = await extract_pdf_text(tmp_path)
            
            assert result["success"] is True
            assert result["error"] is None
            assert "Hello World" in result["text"]
            assert "This is a test PDF" in result["text"]
            assert "Page 2 content" in result["text"]
            assert len(result["pages"]) == 2
            assert result["metadata"]["page_count"] == 2
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_preserves_line_breaks(self):
        """Test that line breaks and paragraph structure are preserved."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            c = canvas.Canvas(tmp_path, pagesize=letter)
            c.drawString(100, 700, "First paragraph line 1")
            c.drawString(100, 680, "First paragraph line 2")
            c.showPage()
            c.drawString(100, 700, "Second paragraph")
            c.showPage()
            c.save()
            
            result = await extract_pdf_text(tmp_path)
            
            assert result["success"] is True
            # Pages should be separated by double newline
            assert "\n\n" in result["text"]
            assert len(result["pages"]) == 2
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extracts_metadata(self):
        """Test that PDF metadata is extracted."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            c = canvas.Canvas(tmp_path, pagesize=letter)
            c.setTitle("Test Title")
            c.setAuthor("Test Author")
            c.drawString(100, 700, "Content")
            c.showPage()
            c.save()
            
            result = await extract_pdf_text(tmp_path)
            
            assert result["success"] is True
            assert result["metadata"]["page_count"] == 1
            # Note: reportlab stores metadata differently
            # pdfplumber may or may not extract it depending on the PDF
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_handles_empty_pdf(self):
        """Test extraction handles empty PDF (no text content)."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            c = canvas.Canvas(tmp_path, pagesize=letter)
            # Create a page with no text
            c.showPage()
            c.save()
            
            result = await extract_pdf_text(tmp_path)
            
            assert result["success"] is True
            assert result["text"] == ""
            assert result["pages"] == []
            assert result["metadata"]["page_count"] == 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_handles_corrupted_pdf(self):
        """Test extraction handles corrupted PDF gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode='w') as tmp:
            tmp.write("This is not a valid PDF content")
            tmp_path = tmp.name
        
        try:
            result = await extract_pdf_text(tmp_path)
            
            assert result["success"] is False
            assert result["error"] is not None
            assert result["text"] == ""
            assert result["pages"] == []
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_accepts_path_object(self):
        """Test extraction accepts Path objects."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            c = canvas.Canvas(str(tmp_path), pagesize=letter)
            c.drawString(100, 700, "Test content")
            c.showPage()
            c.save()
            
            result = await extract_pdf_text(tmp_path)
            
            assert result["success"] is True
            assert "Test content" in result["text"]
        finally:
            tmp_path.unlink(missing_ok=True)
