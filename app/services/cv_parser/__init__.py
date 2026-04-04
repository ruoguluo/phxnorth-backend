"""CV Parser service module."""

from app.services.cv_parser.parser import parse_cv, CVParserError, PARSER_VERSION

__all__ = ["parse_cv", "CVParserError", "PARSER_VERSION"]
