"""
Prompt starters for the MCP prompt picker.

Claude Desktop, Cursor and VS Code list a server's prompts next to its
tools. Each starter here is a real question from the ApexVol prompt
library, with the ticker as an argument so the user can swap the symbol
before sending. The data is vendored into the package as _prompts.json by
scripts/sync_mcp_prompts.py in the ApexVol monorepo (the package cannot
read the site's content files at run time); a test there asserts the
vendored file equals a fresh build.

Nothing here calls the API: rendering a prompt is a string operation.
"""

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

_DATA = Path(__file__).with_name('_prompts.json')


def load_prompts() -> list:
    """The vendored starters, in picker order. Empty when the data file is
    missing so a broken build degrades to a server without prompts."""
    try:
        with _DATA.open(encoding='utf-8') as f:
            return json.load(f).get('prompts') or []
    except (OSError, ValueError) as e:  # pragma: no cover - packaging fault
        logger.warning("prompts unavailable: %s", e)
        return []


def render(entry: dict, **values) -> str:
    """The user message a starter expands to: the question with the
    argument values filled in, then which tools answer it and what comes
    back, then the reference page."""
    text = entry['template']
    for arg in entry.get('arguments') or []:
        value = values.get(arg['name']) or arg.get('default') or ''
        text = text.replace('{%s}' % arg['name'], str(value).strip().upper())
    tools = []
    for tool in entry.get('tools') or []:
        name = tool['name'] if isinstance(tool, dict) else str(tool)
        mode = tool.get('mode') if isinstance(tool, dict) else None
        tools.append(f"{name} ({mode.replace('_', ' ')} view)" if mode else name)
    lines = [text, '']
    if tools:
        lines.append(f"Use the ApexVol MCP tools {' and '.join(tools)}.")
    returns = (entry.get('returns') or '').strip()
    if returns:
        lines.append(returns)
    if entry.get('docs_url'):
        lines.append(f"Reference: {entry['docs_url']}")
    return '\n'.join(lines).rstrip()


def _make_fn(entry: dict):
    """A function whose signature carries the starter's arguments, so
    FastMCP derives the prompt arguments (with the symbol as default)."""
    args = entry.get('arguments') or []
    defaults = [a.get('default') or 'SPY' for a in args]
    if not args:
        def fn() -> str:
            return render(entry)
    elif len(args) == 1:
        d0 = defaults[0]

        def fn(ticker: str = d0) -> str:
            return render(entry, ticker=ticker)
    else:
        d0, d1 = defaults[0], defaults[1]

        def fn(ticker: str = d0, ticker_b: str = d1) -> str:
            return render(entry, ticker=ticker, ticker_b=ticker_b)
    fn.__name__ = entry['name'].replace('-', '_')
    fn.__doc__ = entry.get('description') or entry['template']
    return fn


def register_prompts(mcp: FastMCP) -> int:
    """Register every vendored starter as an MCP prompt. Returns the count."""
    entries = load_prompts()
    for entry in entries:
        mcp.prompt(
            name=entry['name'],
            title=entry.get('title'),
            description=entry.get('description'),
        )(_make_fn(entry))
    return len(entries)
