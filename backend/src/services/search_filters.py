"""Show and asset-type search filters.

A chat request may restrict the search to specific shows and file types.  The restriction
is enforced here, not by asking the LLM to add a WHERE clause: the generated query is
prefixed with CTEs named after the real tables (``files``, ``images``, ``shows``, ...)
that expose only the selected rows.  In PostgreSQL a CTE name takes precedence over a
table of the same name, so every unqualified reference in the query, at any nesting
depth, reads the filtered rows however the query was written.

The LLM's SQL text is spliced, never re-serialized.  sqlglot is used only to inspect it:
regenerating SQL from sqlglot's tree is not safe here because it rewrites pgvector's
``<=>`` distance operator as ``IS NOT DISTINCT FROM``.

This module depends only on sqlglot so it can be unit-tested without a database driver.
"""

import re
from typing import Any, Dict, List, Optional

import sqlglot
from sqlglot import exp

FILES_TABLE = "files"
SHOWS_TABLE = "shows"

# Tables whose rows belong to exactly one row of `files` through a `file_id` column.
CHILD_TABLES = (
    "blend_files",
    "images",
    "videos",
    "audio",
    "code",
    "spreadsheets",
    "documents",
    "caches",
    "unknown_files",
)

GUARDED_TABLES = frozenset({FILES_TABLE, SHOWS_TABLE, *CHILD_TABLES})

MAX_FILTER_VALUES = 100
MAX_FILTER_VALUE_LENGTH = 255

# Leading whitespace and SQL comments, then an optional WITH [RECURSIVE] keyword.
_LEADING_WITH = re.compile(
    r"^(?P<lead>(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*)(?P<with>WITH\b(?P<recursive>\s+RECURSIVE\b)?)?",
    re.IGNORECASE | re.DOTALL,
)


def _clean(values: Any) -> List[str]:
    if not values:
        return []
    cleaned: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if value and len(value) <= MAX_FILTER_VALUE_LENGTH and value not in cleaned:
            cleaned.append(value)
    return cleaned[:MAX_FILTER_VALUES]


def normalize_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Return ``{"shows": [...], "file_types": [...]}`` with blanks and duplicates removed.

    An empty list means "no restriction" for that dimension.
    """
    filters = filters or {}
    return {
        "shows": _clean(filters.get("shows")),
        "file_types": _clean(filters.get("file_types")),
    }


def has_filters(filters: Optional[Dict[str, Any]]) -> bool:
    normalized = normalize_filters(filters)
    return bool(normalized["shows"] or normalized["file_types"])


def describe_filters(filters: Optional[Dict[str, Any]]) -> str:
    """Prompt text telling the LLM which restriction is already enforced. Empty if none."""
    normalized = normalize_filters(filters)
    if not (normalized["shows"] or normalized["file_types"]):
        return ""
    parts = []
    if normalized["shows"]:
        parts.append("shows: " + ", ".join(normalized["shows"]))
    if normalized["file_types"]:
        parts.append("file types: " + ", ".join(normalized["file_types"]))
    return (
        "ACTIVE SEARCH FILTERS: the user restricted this search to "
        + "; ".join(parts)
        + ". The system enforces this restriction on every table automatically, so do NOT "
        "add show or file_type conditions for it yourself. Results only ever contain rows "
        "inside this selection: an empty or small result can be the correct answer, and "
        "the answer should say that it covers only the selected shows and file types. "
        "While filters are active, write table names without a schema prefix, do not name "
        "a CTE after a database table, and do not use WITH RECURSIVE."
    )


def _in_list(column: str, values: List[str]) -> str:
    # sqlglot renders the literal, so quotes inside a value are escaped.
    literals = ", ".join(exp.Literal.string(value).sql(dialect="postgres") for value in values)
    return f"{column} IN ({literals})"


def _filter_ctes(filters: Dict[str, List[str]]) -> List[str]:
    """CTE definitions that shadow each guarded table with its filtered rows.

    Inside a non-recursive WITH a CTE cannot see itself, so ``files`` in the body of the
    ``files`` CTE is the real table.  The child CTEs come later in the list, so the
    ``files`` they read is the filtered CTE.  NOT MATERIALIZED lets the planner inline
    them as ordinary subqueries; otherwise a CTE referenced twice would be computed in
    full, embedding columns included.
    """
    conditions = []
    if filters["shows"]:
        conditions.append(_in_list("show", filters["shows"]))
    if filters["file_types"]:
        conditions.append(_in_list("file_type", filters["file_types"]))

    ctes = [
        f"{FILES_TABLE} AS NOT MATERIALIZED "
        f"(SELECT * FROM {FILES_TABLE} WHERE {' AND '.join(conditions)})"
    ]
    for table in CHILD_TABLES:
        ctes.append(
            f"{table} AS NOT MATERIALIZED "
            f"(SELECT * FROM {table} WHERE file_id IN (SELECT id FROM {FILES_TABLE}))"
        )
    if filters["shows"]:
        ctes.append(
            f"{SHOWS_TABLE} AS NOT MATERIALIZED "
            f"(SELECT * FROM {SHOWS_TABLE} WHERE {_in_list('name', filters['shows'])})"
        )
    return ctes


def _reject_bypasses(sql: str) -> None:
    """Refuse the constructs that would get around, or collide with, the shadowing CTEs."""
    tree = sqlglot.parse_one(sql, dialect="postgres")

    for table in tree.find_all(exp.Table):
        if table.name.lower() in GUARDED_TABLES and (table.db or table.catalog):
            raise ValueError(
                f"Search filters are active: refer to the table as '{table.name}' "
                "without a schema prefix."
            )

    for cte in tree.find_all(exp.CTE):
        if cte.alias_or_name.lower() in GUARDED_TABLES:
            raise ValueError(
                f"Search filters are active: do not name a CTE '{cte.alias_or_name}', "
                "because that is a database table name. Choose a different CTE name."
            )


def apply_search_filters(sql: str, filters: Optional[Dict[str, Any]]) -> str:
    """Restrict ``sql`` to the selected shows and file types.

    Returns the SQL with the filter CTEs placed in front; the original text is otherwise
    unchanged.  Without active filters the SQL is returned as is.

    Raises:
        ValueError: if the query uses a construct the filters cannot be applied to safely
            (a schema-qualified guarded table, a CTE named after a guarded table, or
            WITH RECURSIVE).  The message is written to be usable as retry feedback.
    """
    normalized = normalize_filters(filters)
    if not (normalized["shows"] or normalized["file_types"]):
        return sql

    _reject_bypasses(sql)

    prefix = "WITH " + ", ".join(_filter_ctes(normalized))
    match = _LEADING_WITH.match(sql)
    if not match.group("with"):
        return f"{prefix} {sql}"
    if match.group("recursive"):
        raise ValueError("Search filters are active: WITH RECURSIVE is not supported.")
    # The query has its own WITH clause: put the filter CTEs first in that same clause.
    return f"{match.group('lead')}{prefix},{sql[match.end():]}"
