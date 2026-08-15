"""
First tests for the apexvol-mcp package: API client error handling,
position parsing, and tool registration integrity.

Run with: python3 -m pytest apexvol-mcp/tests/ -q
"""

import asyncio
import json

import httpx
import pytest

from apexvol_mcp.api_client import ApexVolClient, ApexVolAPIError
from apexvol_mcp.tools.risk import _parse_positions


def handle(response: httpx.Response):
    return asyncio.run(ApexVolClient()._handle_response(response))


# ----------------------------------------------------------------------
# _handle_response
# ----------------------------------------------------------------------

def test_success_envelope_unwrapped():
    resp = httpx.Response(200, json={"success": True, "data": {"iv_rank": 55}})
    assert handle(resp) == {"iv_rank": 55}


def test_server_error_message_preferred_over_generic():
    resp = httpx.Response(503, json={
        "success": False,
        "error": "Options flow data is temporarily unavailable: upstream feed.",
        "data_unavailable": True,
    })
    with pytest.raises(ApexVolAPIError) as e:
        handle(resp)
    assert "temporarily unavailable" in e.value.message
    assert e.value.status_code == 503


def test_403_with_body_message():
    resp = httpx.Response(403, json={"error": "API/MCP access requires an active Pro subscription."})
    with pytest.raises(ApexVolAPIError) as e:
        handle(resp)
    assert "Pro subscription" in e.value.message
    assert e.value.status_code == 403


def test_500_without_json_falls_back_generic():
    resp = httpx.Response(500, text="<html>nginx</html>")
    with pytest.raises(ApexVolAPIError) as e:
        handle(resp)
    assert e.value.message == "Server error"


def test_401_without_body_uses_fallback():
    resp = httpx.Response(401, json={})
    with pytest.raises(ApexVolAPIError) as e:
        handle(resp)
    assert "token" in e.value.message.lower()


def test_success_false_raises():
    resp = httpx.Response(200, json={"success": False, "error": "No expirations found"})
    with pytest.raises(ApexVolAPIError) as e:
        handle(resp)
    assert e.value.message == "No expirations found"


def test_non_json_200_raises():
    resp = httpx.Response(200, text="not json")
    with pytest.raises(ApexVolAPIError):
        handle(resp)


# ----------------------------------------------------------------------
# _parse_positions
# ----------------------------------------------------------------------

def test_parse_positions_json_array():
    raw = json.dumps([
        {"ticker": "aapl", "position_type": "call", "quantity": -2, "strike": 220, "delta": 0.31},
        {"ticker": "AAPL", "quantity": 100},
    ])
    positions, warning = _parse_positions(raw)
    assert warning is None
    assert positions[0]["ticker"] == "AAPL"
    assert positions[0]["position_type"] == "CALL"
    assert positions[0]["delta"] == 0.31
    assert positions[1]["position_type"] == "STOCK"  # default


def test_parse_positions_single_object():
    positions, warning = _parse_positions('{"ticker": "spy", "quantity": 50}')
    assert warning is None
    assert positions == [{"ticker": "SPY", "quantity": 50, "position_type": "STOCK"}]


def test_parse_positions_text_fallback_warns():
    positions, warning = _parse_positions("AAPL 100 shares, SPY -50 shares")
    assert warning is not None and "stock-only" in warning
    assert positions[0] == {"ticker": "AAPL", "quantity": 100, "position_type": "STOCK"}
    assert positions[1]["quantity"] == -50


def test_parse_positions_empty():
    assert _parse_positions("") == ([], None)


def test_parse_positions_bad_json_raises():
    with pytest.raises(json.JSONDecodeError):
        _parse_positions('[{"ticker": "AAPL",]')


# ----------------------------------------------------------------------
# Tool registration integrity
# ----------------------------------------------------------------------

def test_all_tools_registered_with_descriptions():
    """Every tool must expose a real docstring (guards against the f-string
    docstring pitfall, where __doc__ is silently None) and the count must
    match what the README advertises."""
    from apexvol_mcp.server import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 43
    for t in tools:
        assert t.description and len(t.description.strip()) > 40, f"{t.name} lacks a docstring"


def test_analytics_maps_cover_orphan_endpoints():
    from apexvol_mcp.tools.analytics import _TICKER_ANALYTICS, _EARNINGS_ANALYTICS
    endpoints = {v[0] for v in _TICKER_ANALYTICS.values()} | {v[0] for v in _EARNINGS_ANALYTICS.values()}
    expected = {
        '/skew/{t}', '/dividend/{t}', '/borrow-rate/{t}', '/correlation/{t}',
        '/hv-regimes/{t}', '/price-context/{t}', '/relative-value/{t}',
        '/greeks-exposure/{t}', '/mispricing-assessment/{t}',
        '/historical-moves/{t}', '/expected-vs-actual/{t}',
        '/earnings-verdict/{t}', '/seasonality/{t}',
        '/post-earnings-drift/{t}', '/iv-crush/{t}',
    }
    assert endpoints == expected


def test_docs_tool_count_matches_registry():
    """content/api_docs.json tool_count drives marketing/docs claims — it must
    equal the number of actually-registered tools. The docs file lives in the
    ApexVol monorepo, so a standalone checkout of apexvol-mcp skips this
    cross-check."""
    import os
    docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "content", "api_docs.json")
    if not os.path.exists(docs_path):
        pytest.skip("monorepo-only cross-check: content/api_docs.json not present")
    with open(docs_path) as f:
        tool_count = json.load(f)["tool_count"]
    from apexvol_mcp.server import mcp
    tools = asyncio.run(mcp.list_tools())
    assert tool_count == len(tools)


# ----------------------------------------------------------------------
# Per-request token (multi-user hosting seam)
# ----------------------------------------------------------------------

def test_env_token_fallback_when_no_request_token(monkeypatch):
    """stdio behavior unchanged: with no request-scoped token, the env token
    authenticates the call."""
    monkeypatch.setenv("APEXVOL_API_TOKEN", "avmcp_env_token")
    client = ApexVolClient()
    assert client._auth_headers() == {"Authorization": "Bearer avmcp_env_token"}


def test_request_token_wins_over_env(monkeypatch):
    from apexvol_mcp.api_client import set_request_token, reset_request_token
    monkeypatch.setenv("APEXVOL_API_TOKEN", "avmcp_env_token")
    client = ApexVolClient()
    ctx = set_request_token("avmcp_request_token")
    try:
        assert client._auth_headers() == {"Authorization": "Bearer avmcp_request_token"}
    finally:
        reset_request_token(ctx)
    assert client._auth_headers() == {"Authorization": "Bearer avmcp_env_token"}


def test_no_token_at_all_raises_locally(monkeypatch):
    monkeypatch.delenv("APEXVOL_API_TOKEN", raising=False)
    client = ApexVolClient()
    with pytest.raises(ApexVolAPIError) as e:
        client._auth_headers()
    assert e.value.status_code == 401


def test_pooled_client_defaults_carry_no_authorization(monkeypatch):
    """The token must never be frozen into the shared AsyncClient — a pooled
    default header would leak the first user's credentials to every later
    request on a multi-user host."""
    monkeypatch.setenv("APEXVOL_API_TOKEN", "avmcp_env_token")
    client = ApexVolClient()
    http = client._get_http()
    assert "authorization" not in {k.lower() for k in http.headers.keys()}


def test_context_isolation_across_tasks():
    """Two concurrent tasks each see only their own request token."""
    from apexvol_mcp.api_client import set_request_token, reset_request_token

    async def call_as(token):
        ctx = set_request_token(token)
        try:
            await asyncio.sleep(0.01)
            client = ApexVolClient()
            return client._auth_headers()["Authorization"]
        finally:
            reset_request_token(ctx)

    async def run():
        return await asyncio.gather(call_as("avmcp_user_a"), call_as("avmcp_user_b"))

    a, b = asyncio.run(run())
    assert a == "Bearer avmcp_user_a"
    assert b == "Bearer avmcp_user_b"
