"""Extractors for CV Parser."""

from app.services.cv_parser.extractors.docx_extractor import extract_docx_text
from app.services.cv_parser.extractors.pdf_extractor import extract_pdf_text

__all__ = ["extract_pdf_text", "extract_docx_text"]
