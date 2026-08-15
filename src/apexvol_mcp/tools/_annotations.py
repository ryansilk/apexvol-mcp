"""Shared decorator kwargs for tool registration.

Every ApexVol tool is a read-only analytics query (nothing mutates platform
or user state), so each registers with a human-readable display title plus
readOnlyHint=True. The title goes both on the tool itself (2025-06-18 spec
field, preferred by current clients) and into annotations.title for clients
that predate it.
"""

from mcp.types import ToolAnnotations


def read_only(title: str) -> dict:
    """Kwargs for @mcp.tool() on a read-only analytics tool."""
    return {
        'title': title,
        'annotations': ToolAnnotations(title=title, readOnlyHint=True),
    }
