"""Repository-level errors, shared by every DatabaseMCP backend (docs/DATABASE_MCP_CONTRACT.md §7).

Raised by repository implementations (`adapters/persistence/`), regardless of backend - the
in-process consumption path sees these Python exceptions directly;
`interface/mcp/database_server.py` catches them and translates each to its matching MCP tool
error `code`. `BACKEND_UNAVAILABLE` and
`INTERNAL` (§7) are not raised deliberately by repository code - they cover transport/deployment
failures the MCP server maps unexpected exceptions to, not a repository decision.
"""

from __future__ import annotations


class RepositoryError(Exception):
    """Base class for every error a repository/DatabaseMCP tool can raise on purpose."""


class NotFoundError(RepositoryError):
    """§7 NOT_FOUND: an operation that cannot proceed without a row addressed one that doesn't
    exist. Never raised by a `get_*` (a missing entity there is a `None` return, not an error)."""


class ConflictError(RepositoryError):
    """§7 CONFLICT: `store_*` was called with an existing id and different content (§3)."""


class InvalidArgumentError(RepositoryError):
    """§7 INVALID_ARGUMENT: a payload/argument fails validation - e.g. an unknown `search_notes`
    filter key. The message must name the offending field (§7: fed into an agent's single retry)."""
