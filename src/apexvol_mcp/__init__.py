"""
ApexVol MCP Server

Professional options analytics via Claude Code.
Query IV rank, Greeks, GEX, volatility surfaces, and more using natural language.
"""

# Single source of truth is pyproject.toml; read it back from the installed
# distribution so the X-ApexVol-Client header and `--check` report the version
# that was actually installed. 0.1.1 and 0.1.2 shipped with this string left at
# "0.1.0", so every request announced the wrong client version. The fallback is
# for an un-installed checkout (tests, editable source without metadata).
_FALLBACK_VERSION = "0.1.4"
try:
    from importlib.metadata import version as _dist_version, PackageNotFoundError as _NotFound
    try:
        __version__ = _dist_version("apexvol-mcp")
    except _NotFound:
        __version__ = _FALLBACK_VERSION
except Exception:  # pragma: no cover - importlib.metadata is stdlib on 3.10+
    __version__ = _FALLBACK_VERSION
