"""PDF text extraction module using pdfplumber."""

import asyncio
from pathlib import Path
from typing import Any

import pdfplumber

from app.core.exceptions import ValidationException


class PDFExtractionError(Exception):
    """Exception raised when PDF extraction fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _extract_pdf_sync(file_path: str | Path) -> dict[str, Any]:
    """
    Synchronously extract text and metadata from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary containing extracted text, pages, and metadata

    Raises:
        PDFExtractionError: If extraction fails
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise PDFExtractionError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise PDFExtractionError(f"Path is not a file: {file_path}")

    try:
        with pdfplumber.open(file_path) as pdf:
            pages_text: list[str] = []

            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)

            # Extract metadata
            metadata: dict[str, Any] = {
                "page_count": len(pdf.pages),
            }

            # Try to get additional metadata from the PDF
            if pdf.metadata:
                pdf_meta = pdf.metadata
                if pdf_meta.get("Title"):
                    metadata["title"] = pdf_meta["Title"]
                if pdf_meta.get("Author"):
                    metadata["author"] = pdf_meta["Author"]
                if pdf_meta.get("CreationDate"):
                    metadata["creation_date"] = pdf_meta["CreationDate"]
                if pdf_meta.get("Producer"):
                    metadata["producer"] = pdf_meta["Producer"]

            # Join all pages with double newline to preserve paragraph structure
            full_text = "\n\n".join(pages_text)

            return {
                "text": full_text,
                "pages": pages_text,
                "metadata": metadata,
            }

    except PDFExtractionError:
        raise
    except Exception as e:
        raise PDFExtractionError(
            f"Failed to extract text from PDF: {str(e)}",
            {"file_path": str(file_path), "error_type": type(e).__name__}
        )


async def extract_pdf_text(file_path: str | Path) -> dict[str, Any]:
    """
    Extract text from a PDF file asynchronously.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary with keys:
        - text: str (full extracted text)
        - pages: list[str] (text per page)
        - metadata: dict (page_count, title, author, creation_date, producer)
        - success: bool
        - error: str | None
    """
    try:
        result = await asyncio.to_thread(_extract_pdf_sync, file_path)
        return {
            **result,
            "success": True,
            "error": None,
        }
    except PDFExtractionError as e:
        return {
            "text": "",
            "pages": [],
            "metadata": {"page_count": 0},
            "success": False,
            "error": e.message,
        }
    except Exception as e:
        return {
            "text": "",
            "pages": [],
            "metadata": {"page_count": 0},
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }
