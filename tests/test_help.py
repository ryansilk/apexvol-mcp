"""The `help` tool: the vendored _records.json, topic resolution (tool,
family, endpoint, path, search), the overview, and (monorepo only) that the
vendored records equal a fresh build from content/api_records.json.

Run with: python3 -m pytest apexvol-mcp/tests/test_help.py -q
"""

import asyncio
import json
import os
import sys

import pytest

from apexvol_mcp.help import _norm, load_records, lookup, overview

HERE = os.path.dirname(__file__)
MONOREPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SYNC_SCRIPT = os.path.join(MONOREPO, 'scripts', 'sync_mcp_prompts.py')


@pytest.fixture(scope='module')
def data():
    return load_records()


def test_vendored_records_are_complete(data):
    assert len(data['families']) == 11
    assert len(data['endpoints']) >= 60
    assert len(data['tools']) == 43
    assert data['conventions'] and data['errors'] and data['references']
    for e in data['endpoints']:
        for k in ('slug', 'family', 'method', 'path', 'question', 'one_liner', 'params', 'fields', 'plan', 'docs_url'):
            assert e.get(k) is not None, (e['slug'], k)
        assert 'sample' not in e, 'samples stay on the docs pages'
        assert e['markdown_url'] == e['docs_url'] + '.md'
    for t in data['tools']:
        assert t['endpoints'] and len(t['prompts']) == 3, t['name']


@pytest.mark.parametrize('topic,expected', [
    ('/api/mcp/data/iv-rank/NVDA', 'iv-rank'),
    ('https://apexvol.com/api/mcp/data/iv-rank/NVDA', 'iv-rank'),
    ('/iv-rank/{ticker}', 'iv-rank'),
    ('https://apexvol.com/developers/implied-volatility-api/iv-rank.md', 'iv-rank'),
    ('  IV Rank ', 'iv rank'),
    ('get_iv_rank', 'get_iv_rank'),
    ('', ''),
])
def test_norm(topic, expected):
    assert _norm(topic) == expected


def test_overview_lists_families_and_counts(data):
    out = overview(data)
    assert out['kind'] == 'overview'
    assert out['tool_count'] == 44 and out['endpoint_count'] == len(data['endpoints'])
    assert out['prompt_count'] == 41
    assert [f['family'] for f in out['families']][0] == 'implied-volatility-api'
    assert all(f['endpoints'] > 0 for f in out['families'])
    assert out['references']['openapi'].endswith('/docs/api/openapi.json')
    assert lookup(None, data) == out
    assert lookup('   ', data) == out


def test_tool_lookup_carries_the_endpoint_records(data):
    out = lookup('get_iv_rank', data)
    assert out['kind'] == 'tool' and out['name'] == 'get_iv_rank'
    assert out['arguments'] and len(out['prompts']) == 3
    ep = out['endpoints'][0]
    assert ep['slug'] == 'iv-rank' and ep['request'] == 'GET /api/mcp/data/iv-rank/{ticker}'
    assert ep['plan'] in ('basic', 'premium', 'pro')
    assert ep['docs_url'] == 'https://apexvol.com/developers/implied-volatility-api/iv-rank'
    # hyphens and spaces resolve to the same tool
    assert lookup('get-iv-rank', data)['kind'] == 'tool'


@pytest.mark.parametrize('topic', ['gamma-exposure-api', 'gamma-exposure', 'gex', 'Gamma exposure', 'GEX'])
def test_family_lookup_by_slug_short_or_name(topic, data):
    out = lookup(topic, data)
    assert out['kind'] == 'family' and out['family'] == 'gamma-exposure-api', topic
    assert {t['name'] for t in out['tools']} >= {'get_gex', 'get_zero_dte'}
    assert any(e['slug'] == 'gex' for e in out['endpoints'])
    assert len(out['prompts']) == 3
    assert out['markdown_url'].endswith('/developers/gamma-exposure-api.md')


def test_endpoint_lookup_by_slug_and_by_path(data):
    by_slug = lookup('iv-rank', data)
    assert by_slug['kind'] == 'endpoint' and by_slug['slug'] == 'iv-rank'
    assert by_slug['question'].endswith('?')
    assert by_slug['params'] and by_slug['fields'] and by_slug['units']
    assert by_slug['family_name'] == 'Implied volatility'
    assert lookup('/iv-rank/{ticker}', data) == by_slug
    assert lookup('/api/mcp/data/iv-rank/NVDA', data) == by_slug
    assert lookup('iv_rank', data) == by_slug


def test_gex_resolves_the_family_not_the_endpoint(data):
    """'gex' is both a family short name and an endpoint slug; the family
    wins because it lists the endpoint anyway."""
    assert lookup('gex', data)['kind'] == 'family'
    assert lookup('/gex/{ticker}', data)['kind'] == 'endpoint'


def test_search_ranks_name_matches_first(data):
    out = lookup('dealer gamma flip', data)
    assert out['kind'] == 'search'
    keys = [m['key'] for m in out['matches']]
    assert keys, 'no matches'
    assert any(k in ('gex', 'get_gex', 'zero-dte') for k in keys[:3]), keys
    assert all(m['ask'].startswith('help("') for m in out['matches'])
    assert len(out['matches']) <= 8
    # Words that spell a slug resolve to the endpoint itself, not a search.
    assert lookup('term structure', data)['kind'] == 'endpoint'


def test_search_with_no_match_offers_the_families(data):
    out = lookup('zzqx', data)
    assert out['kind'] == 'search' and out['matches'] == []
    assert len(out['families']) == 11


def test_conventions_errors_and_prompts_topics(data):
    assert lookup('conventions', data)['conventions'][0]['topic']
    assert lookup('errors', data)['errors'][0]['status'] == 400
    prompts = lookup('prompts', data)
    assert prompts['kind'] == 'prompts' and len(prompts['prompts']) == 41


def test_help_is_a_registered_read_only_tool():
    from apexvol_mcp.server import mcp
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert 'help' in tools
    assert tools['help'].annotations.readOnlyHint is True
    assert tools['help'].title == 'Help'
    assert 'topic' in tools['help'].inputSchema['properties']
    assert tools['help'].inputSchema.get('required', []) == []
    # call_tool returns the content blocks: one text block holding the JSON.
    blocks = asyncio.run(mcp.call_tool('help', {}))
    payload = json.loads(blocks[0].text)
    assert payload['kind'] == 'overview' and payload['tool_count'] == 44


def test_help_makes_no_network_call(monkeypatch):
    import httpx
    def boom(*a, **k):
        raise AssertionError('help must not call the API')
    monkeypatch.setattr(httpx.AsyncClient, 'request', boom)
    monkeypatch.setattr(httpx.AsyncClient, 'get', boom)
    assert lookup('get_gex')['kind'] == 'tool'
    assert lookup('what is the expected move')['kind'] == 'search'


def test_vendored_records_match_a_fresh_build():
    """Monorepo-only: the package copy must equal what the sync script
    builds from content/api_records.json."""
    if not os.path.exists(SYNC_SCRIPT):
        pytest.skip('monorepo-only cross-check: scripts/sync_mcp_prompts.py not present')
    sys.path.insert(0, os.path.dirname(SYNC_SCRIPT))
    import sync_mcp_prompts
    with open(sync_mcp_prompts.RECORDS_OUT, encoding='utf-8') as f:
        vendored = json.load(f)
    assert vendored == sync_mcp_prompts.build_records(), 'run python3 scripts/sync_mcp_prompts.py'
