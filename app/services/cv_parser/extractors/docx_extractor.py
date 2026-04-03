"""DOCX text extraction module using python-docx."""

import asyncio
from pathlib import Path
from typing import Any

from docx import Document


class DOCXExtractionError(Exception):
    """Exception raised when DOCX extraction fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _extract_docx_sync(file_path: str | Path) -> dict[str, Any]:
    """
    Synchronously extract text and metadata from a DOCX file.

    Args:
        file_path: Path to the DOCX file

    Returns:
        Dictionary containing extracted text, paragraphs, and metadata

    Raises:
        DOCXExtractionError: If extraction fails
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise DOCXExtractionError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise DOCXExtractionError(f"Path is not a file: {file_path}")

    try:
        doc = Document(file_path)

        # Extract text from paragraphs
        paragraphs: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:  # Only include non-empty paragraphs
                paragraphs.append(text)

        # Extract metadata from core properties
        metadata: dict[str, Any] = {}
        core_props = doc.core_properties

        if core_props.author:
            metadata["author"] = core_props.author
        if core_props.created:
            metadata["created"] = core_props.created.isoformat()
        if core_props.modified:
            metadata["modified"] = core_props.modified.isoformat()
        if core_props.title:
            metadata["title"] = core_props.title

        # Join paragraphs with double newline to preserve structure
        full_text = "\n\n".join(paragraphs)

        return {
            "text": full_text,
            "paragraphs": paragraphs,
            "metadata": metadata,
        }

    except DOCXExtractionError:
        raise
    except Exception as e:
        raise DOCXExtractionError(
            f"Failed to extract text from DOCX: {str(e)}",
            {"file_path": str(file_path), "error_type": type(e).__name__}
        )


async def extract_docx_text(file_path: str | Path) -> dict[str, Any]:
    """
    Extract text from a DOCX file asynchronously.

    Args:
        file_path: Path to the DOCX file

    Returns:
        Dictionary with keys:
        - text: str (full extracted text)
        - paragraphs: list[str] (text per paragraph)
        - metadata: dict (author, created, modified, title)
        - success: bool
        - error: str | None
    """
    try:
        result = await asyncio.to_thread(_extract_docx_sync, file_path)
        return {
            **result,
            "success": True,
            "error": None,
        }
    except DOCXExtractionError as e:
        return {
            "text": "",
            "paragraphs": [],
            "metadata": {},
            "success": False,
            "error": e.message,
        }
    except Exception as e:
        return {
            "text": "",
            "paragraphs": [],
            "metadata": {},
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }
