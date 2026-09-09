"""Prompt starters: the vendored _prompts.json, its registration on the
server, and (in the monorepo only) that the vendored file equals a fresh
build from content/, so the picker and the /mcp/prompts page cannot drift.

Run with: python3 -m pytest apexvol-mcp/tests/test_prompts.py -q
"""

import asyncio
import json
import os
import re
import sys

import pytest

from apexvol_mcp import prompts as prompts_mod
from apexvol_mcp.prompts import load_prompts, render, register_prompts

HERE = os.path.dirname(__file__)
MONOREPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SYNC_SCRIPT = os.path.join(MONOREPO, 'scripts', 'sync_mcp_prompts.py')
EM_DASH = re.compile('[—–]')
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def test_vendored_file_is_well_formed():
    entries = load_prompts()
    assert len(entries) >= 30
    names = [e['name'] for e in entries]
    assert len(names) == len(set(names)), 'prompt names must be unique'
    for e in entries:
        assert NAME_RE.match(e['name']), e['name']
        assert e['title'] and e['description'] and e['template'], e['name']
        assert e['docs_url'].startswith('https://apexvol.com/developers/'), e['name']
        assert e['tools'], f"{e['name']} names no tool"
        for arg in e['arguments']:
            assert arg['name'] in ('ticker', 'ticker_b')
            assert '{%s}' % arg['name'] in e['template'], e['name']
            assert arg['default'].isupper()
        for field in ('title', 'description', 'template'):
            assert not EM_DASH.search(e[field]), f"{e['name']}.{field} has an em-dash"


def test_every_family_has_three_starters():
    by_family = {}
    for e in load_prompts():
        if e['family'] != 'recipes':
            by_family.setdefault(e['family'], []).append(e)
    assert len(by_family) == 11
    assert all(len(v) == 3 for v in by_family.values()), {k: len(v) for k, v in by_family.items()}


def test_render_fills_the_ticker_and_upper_cases_it():
    entry = {
        'name': 'vol-iv-rank', 'template': "What is {ticker}'s IV rank?",
        'arguments': [{'name': 'ticker', 'default': 'NVDA'}],
        'tools': [{'name': 'get_iv_rank', 'mode': None}],
        'returns': 'Rank and percentile.', 'docs_url': 'https://apexvol.com/developers/implied-volatility-api',
    }
    text = render(entry, ticker=' amd ')
    assert text.startswith("What is AMD's IV rank?\n\n")
    assert 'Use the ApexVol MCP tools get_iv_rank.' in text
    assert 'Rank and percentile.' in text
    assert text.endswith('Reference: https://apexvol.com/developers/implied-volatility-api')
    assert "What is NVDA's IV rank?" in render(entry)


def test_render_names_the_tool_view():
    entry = {
        'name': 'x', 'template': 'How much does {ticker} crush?',
        'arguments': [{'name': 'ticker', 'default': 'TSLA'}],
        'tools': [{'name': 'get_earnings_move_analysis', 'mode': 'iv_crush'}],
        'returns': '', 'docs_url': '',
    }
    assert 'get_earnings_move_analysis (iv crush view).' in render(entry)


def test_prompts_registered_on_the_server_with_arguments():
    from apexvol_mcp.server import mcp
    listed = asyncio.run(mcp.list_prompts())
    entries = load_prompts()
    assert len(listed) == len(entries)
    by_name = {p.name: p for p in listed}
    for e in entries:
        p = by_name[e['name']]
        assert p.title == e['title']
        assert p.description == e['description']
        assert [a.name for a in (p.arguments or [])] == [a['name'] for a in e['arguments']]
        assert all(not a.required for a in (p.arguments or [])), 'tickers have defaults'


def test_get_prompt_renders_a_user_message():
    from apexvol_mcp.server import mcp
    entry = next(e for e in load_prompts() if len(e['arguments']) == 1)
    result = asyncio.run(mcp.get_prompt(entry['name'], {'ticker': 'xom'}))
    assert len(result.messages) == 1
    msg = result.messages[0]
    assert msg.role == 'user'
    assert 'XOM' in msg.content.text
    assert entry['docs_url'] in msg.content.text
    # No arguments: the default symbol is used.
    result = asyncio.run(mcp.get_prompt(entry['name'], {}))
    assert entry['arguments'][0]['default'] in result.messages[0].content.text


def test_register_prompts_returns_the_count(monkeypatch):
    from mcp.server.fastmcp import FastMCP
    monkeypatch.setattr(prompts_mod, 'load_prompts', lambda: [{
        'name': 'a-b', 'title': 'A', 'description': 'd', 'template': 'Hi {ticker} and {ticker_b}',
        'arguments': [{'name': 'ticker', 'default': 'SPY'}, {'name': 'ticker_b', 'default': 'QQQ'}],
        'tools': [], 'returns': '', 'docs_url': '',
    }])
    fresh = FastMCP('t')
    assert register_prompts(fresh) == 1
    result = asyncio.run(fresh.get_prompt('a-b', {'ticker_b': 'iwm'}))
    assert result.messages[0].content.text.startswith('Hi SPY and IWM')


def test_vendored_file_matches_a_fresh_build():
    """Monorepo-only: the package copy must equal what the sync script
    builds from content/. A standalone checkout of apexvol-mcp skips it."""
    if not os.path.exists(SYNC_SCRIPT):
        pytest.skip('monorepo-only cross-check: scripts/sync_mcp_prompts.py not present')
    sys.path.insert(0, os.path.dirname(SYNC_SCRIPT))
    import sync_mcp_prompts
    with open(sync_mcp_prompts.OUT, encoding='utf-8') as f:
        vendored = json.load(f)
    assert vendored == sync_mcp_prompts.build(), 'run python3 scripts/sync_mcp_prompts.py'
