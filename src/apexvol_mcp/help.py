"""
The `help` tool: the API reference inside the server.

"Which tool gives me IV rank, what are its parameters, and what plan does
it need?" is answered here from the vendored _records.json (built by
scripts/sync_mcp_prompts.py in the ApexVol monorepo from the same records
the developer pages render). No network call, no market-data cost, no
token needed: the model can look before it calls.

Topics it resolves, in order: a tool name (get_iv_rank), a family
(implied-volatility-api, "vol", "Implied volatility"), an endpoint slug or
path (iv-rank, /iv-rank/{ticker}, /api/mcp/data/iv-rank/NVDA), and
otherwise a word search across names, questions and summaries.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .prompts import load_prompts
from .tools._annotations import read_only

logger = logging.getLogger(__name__)

_DATA = Path(__file__).with_name('_records.json')
_DATA_PREFIX = '/api/mcp/data'
_WORD = re.compile(r'[a-z0-9]+')
_MAX_MATCHES = 8


def load_records() -> dict:
    """The vendored records; an empty shell when the data file is missing so
    a broken build degrades to an honest 'no records' answer."""
    try:
        with _DATA.open(encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError) as e:  # pragma: no cover - packaging fault
        logger.warning("help records unavailable: %s", e)
        return {'families': [], 'endpoints': [], 'tools': [], 'conventions': [], 'errors': [], 'references': {}}


def _norm(topic: str) -> str:
    """Lower-case, prefix-free, hyphenated: '/api/mcp/data/iv-rank/NVDA' ->
    'iv-rank', 'get_iv_rank' -> 'get_iv_rank', 'IV Rank' -> 'iv rank'."""
    t = (topic or '').strip().lower()
    if t.startswith('https://') or t.startswith('http://'):
        t = t.split('/', 3)[-1] if t.count('/') >= 3 else ''
        t = '/' + t
    if t.startswith(_DATA_PREFIX):
        t = t[len(_DATA_PREFIX):]
    if t.startswith('/developers/'):
        t = t[len('/developers/'):]
        parts = [p for p in t.split('/') if p]
        t = parts[-1] if parts else ''
        t = t[:-3] if t.endswith('.md') else t
    if t.startswith('/'):
        parts = [p for p in t.split('/') if p]
        t = parts[0] if parts else ''
    return t.strip()


def _family_payload(fam: dict, data: dict) -> dict:
    slug = fam['slug']
    endpoints = [e for e in data['endpoints'] if e['family'] == slug]
    tools = [t for t in data['tools'] if t['family'] == slug]
    starters = [p for p in load_prompts() if p.get('family') == slug]
    return {
        'kind': 'family',
        'family': slug,
        'name': fam['name'],
        'docs_url': fam['docs_url'],
        'markdown_url': fam['docs_url'] + '.md',
        'endpoints': [{
            'slug': e['slug'], 'method': e['method'], 'path': e['path'], 'plan': e['plan'],
            'one_liner': e['one_liner'], 'tools': e['tools'],
        } for e in endpoints],
        'tools': [{'name': t['name'], 'one_liner': t['one_liner'], 'arguments': t['arguments']} for t in tools],
        'prompts': [{'name': p['name'], 'template': p['template']} for p in starters],
        'next': 'help("<tool name>") or help("<endpoint slug>") for parameters, units and fields.',
    }


def _endpoint_payload(e: dict, data: dict) -> dict:
    out = {'kind': 'endpoint'}
    out.update(e)
    out['request'] = f"{e['method']} {_DATA_PREFIX}{e['path']}"
    fam = next((f for f in data['families'] if f['slug'] == e['family']), None)
    out['family_name'] = fam['name'] if fam else e['family']
    return out


def _tool_payload(t: dict, data: dict) -> dict:
    by_slug = {e['slug']: e for e in data['endpoints']}
    return {
        'kind': 'tool',
        'name': t['name'],
        'family': t['family'],
        'one_liner': t['one_liner'],
        'arguments': t['arguments'],
        'prompts': t['prompts'],
        'endpoints': [_endpoint_payload(by_slug[s], data) for s in t['endpoints'] if s in by_slug],
    }


def _search(topic: str, data: dict) -> list:
    words = set(_WORD.findall(topic))
    if not words:
        return []
    scored = []
    for e in data['endpoints']:
        name_words = set(_WORD.findall(e['slug'])) | set(_WORD.findall(' '.join(e['tools'])))
        prose = ' '.join(str(e.get(k) or '') for k in ('question', 'one_liner', 'summary', 'units', 'basis')).lower()
        score = 3 * len(words & name_words) + sum(1 for w in words if w in prose)
        if score:
            scored.append((score, 'endpoint', e['slug'], e['one_liner'], e['tools'], e['docs_url']))
    for t in data['tools']:
        name_words = set(_WORD.findall(t['name']))
        prose = (t.get('one_liner') or '').lower() + ' ' + ' '.join(t.get('prompts') or []).lower()
        score = 3 * len(words & name_words) + sum(1 for w in words if w in prose)
        if score:
            scored.append((score, 'tool', t['name'], t['one_liner'], [t['name']], None))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    return [{
        'kind': kind, 'key': key, 'one_liner': one_liner, 'tools': tools,
        **({'docs_url': url} if url else {}),
        'ask': f'help("{key}")',
    } for _, kind, key, one_liner, tools, url in scored[:_MAX_MATCHES]]


def overview(data: Optional[dict] = None) -> dict:
    data = data or load_records()
    fams = []
    for f in data['families']:
        fams.append({
            'family': f['slug'],
            'name': f['name'],
            'endpoints': sum(1 for e in data['endpoints'] if e['family'] == f['slug']),
            'tools': [t['name'] for t in data['tools'] if t['family'] == f['slug']],
            'docs_url': f['docs_url'],
        })
    return {
        'kind': 'overview',
        'tool_count': len(data['tools']) + 1,
        'endpoint_count': len(data['endpoints']),
        'prompt_count': len(load_prompts()),
        'families': fams,
        'how_to': [
            'help("gex") or help("Gamma exposure") for a family: its endpoints, tools and starter prompts.',
            'help("get_iv_rank") for a tool: its arguments and the endpoint records behind it.',
            'help("iv-rank") or help("/iv-rank/{ticker}") for an endpoint: question, parameters, units, basis, fields, plan.',
            'help("term structure") for a word search when you do not know the name.',
            'help("conventions") for units and bases shared by every endpoint; help("errors") for the status codes.',
        ],
        'references': data.get('references') or {},
    }


def lookup(topic: Optional[str], data: Optional[dict] = None) -> dict:
    """Resolve a topic to a family, tool, endpoint, conventions, errors or a
    search; None or blank returns the overview."""
    data = data or load_records()
    key = _norm(topic or '')
    if not key:
        return overview(data)
    if key in ('conventions', 'convention', 'units', 'bases', 'basis'):
        return {'kind': 'conventions', 'conventions': data.get('conventions') or [],
                'docs_url': 'https://apexvol.com/developers/conventions'}
    if key in ('errors', 'error', 'status codes', 'status-codes'):
        return {'kind': 'errors', 'errors': data.get('errors') or [],
                'docs_url': 'https://apexvol.com/developers/errors'}
    if key in ('prompts', 'prompt', 'starters'):
        return {'kind': 'prompts', 'prompts': [
            {'name': p['name'], 'title': p['title'], 'family': p['family'], 'template': p['template'],
             'arguments': p['arguments']} for p in load_prompts()],
            'docs_url': (data.get('references') or {}).get('prompt_library')}

    hyphenated = key.replace('_', '-').replace(' ', '-')
    endpoint = next((e for e in data['endpoints'] if e['slug'] == hyphenated), None)
    # A path or URL names an endpoint unambiguously ('/gex/{ticker}' is the
    # endpoint; the bare word 'gex' is the family, which lists it anyway).
    if endpoint and (topic or '').strip().lower().startswith(('/', 'http')):
        return _endpoint_payload(endpoint, data)

    underscored = key.replace('-', '_').replace(' ', '_')
    for t in data['tools']:
        if t['name'] == underscored:
            return _tool_payload(t, data)

    for f in data['families']:
        names = {f['slug'], f['slug'].replace('-api', ''), f.get('short') or '', f['name'].lower()}
        if key in names or hyphenated in names:
            return _family_payload(f, data)

    if endpoint:
        return _endpoint_payload(endpoint, data)

    matches = _search(key, data)
    if matches:
        return {'kind': 'search', 'topic': topic, 'matches': matches,
                'next': 'Call help(match["key"]) for the full record.'}
    return {'kind': 'search', 'topic': topic, 'matches': [],
            'families': [{'family': f['slug'], 'name': f['name']} for f in data['families']],
            'next': 'No record matched. Pick a family, or search the docs hub.',
            'references': data.get('references') or {}}


def register_tools(mcp: FastMCP):
    """Register the help tool."""

    @mcp.tool(**read_only('Help'))
    def help(topic: Optional[str] = None) -> dict:
        """
        Look up the ApexVol tool or endpoint that answers a question, before
        calling it. Reads a bundled copy of the API reference: no network
        call, no market-data cost, works before a token is configured.

        Use this tool when:
        - You are not sure which tool returns a number (IV rank, dealer
          gamma, expected move, borrow rate)
        - You need an endpoint's parameters, units, basis, fields or plan
        - You want the starter prompts for a data family
        - A call failed with 403 or 404 and you want the documented shape

        Args:
            topic: None for the overview (families, counts, how to ask);
                a tool name ("get_iv_rank"); a family ("gex",
                "implied-volatility-api", "Gamma exposure"); an endpoint
                slug or path ("iv-rank", "/iv-rank/{ticker}"); "conventions",
                "errors" or "prompts"; or any words to search ("term structure").

        Returns:
            A record with a "kind" of overview, family, tool, endpoint,
            conventions, errors, prompts or search. Endpoint records carry
            question, request line, parameters, units, basis, fields, plan,
            tools, prompts and the docs URL (add .md for Markdown).
        """
        return lookup(topic)
