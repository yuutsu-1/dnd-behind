"""Helpers shared by the list endpoints that search by name."""
from sqlalchemy import ColumnElement


def escape_like(term: str) -> str:
    """Make LIKE wildcards in a search term literal (`_` and `%` match themselves)."""
    return term.replace("\\", "\\\\").replace("%", "\%").replace("_", "\_")


def name_contains(column, term: str) -> ColumnElement[bool]:
    """Case-insensitive "contains" on `column`, with LIKE wildcards in `term` taken literally."""
    return column.ilike(f"%{escape_like(term)}%", escape="\\")
