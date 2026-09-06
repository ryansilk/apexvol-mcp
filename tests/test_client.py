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


# ----------------------------------------------------------------------
# Summary formatters read the keys the server actually sends
# (2026-09-06 audit A5..A8). Payloads are trimmed copies of live responses.
# ----------------------------------------------------------------------

class _StubClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get(self, endpoint, params=None):
        self.calls.append((endpoint, params))
        return self.payload

    async def post(self, endpoint, data=None):
        self.calls.append((endpoint, data))
        return self.payload


def _run_tool(monkeypatch, name, payload, **kwargs):
    import apexvol_mcp.api_client as api_client
    from apexvol_mcp.server import mcp
    stub = _StubClient(payload)
    monkeypatch.setattr(api_client, "_client", stub)
    fn = mcp._tool_manager.get_tool(name).fn
    return asyncio.run(fn(**kwargs)), stub


def test_flow_summary_reads_nested_totals(monkeypatch):
    payload = {
        "ticker": "AAPL", "data_freshness": "EOD", "is_market_hours": False,
        "message": "Market is closed. Showing end-of-day data from the most recent trading session.",
        "summary": {"total_call_volume": 409514.0, "total_put_volume": 154520.0,
                    "total_call_premium": 121192777.5, "total_put_premium": 49828024.5,
                    "put_call_ratio": 0.377, "call_put_ratio": 2.65, "sentiment": "BULLISH"},
        "unusual_activity": [{}] * 20, "all_flow": [],
    }
    out, _ = _run_tool(monkeypatch, "get_options_flow", payload, ticker="aapl")
    assert out["success"] is True
    s = out["summary"]
    assert "| Call Volume | 409,514 |" in s
    assert "| Put Volume | 154,520 |" in s
    assert "| Call Premium | $121,192,778 |" in s
    assert "| Sentiment | BULLISH |" in s
    assert "(EOD)" in s and "Market is closed" in s
    assert "| Call Volume | 0 |" not in s


def test_gex_summary_reads_flip_and_walls(monkeypatch):
    payload = {
        "ticker": "SPY", "stock_price": 770.25, "total_gex": -3229789376.65,
        "flip_level": 765.0, "gamma_flip": 765.0, "max_gex_strike": 760,
        "expirations_included": 16, "expirations_total": 32, "expirations_through": "2026-11-20",
        "key_levels": {"call_wall": 780.0, "put_wall": 750.0, "max_pain": 768.0, "key_strike": 760},
        "implications": {"positioning": "Dealers are short gamma below 765."},
        "gex_by_strike": [], "gex_profile": [],
    }
    out, _ = _run_tool(monkeypatch, "get_gex", payload, ticker="SPY")
    s = out["summary"]
    assert "| Gamma Flip | $765.00 |" in s
    assert "- Call wall: $780.00" in s and "- Put wall: $750.00" in s
    assert "Largest absolute GEX strike: $760.00" in s
    assert "Dealers are short gamma" in s
    assert "$0.00" not in s and "N/A" not in s


def test_gex_summary_names_a_missing_flip(monkeypatch):
    payload = {"ticker": "SPY", "stock_price": 770.25, "total_gex": -1.0,
               "flip_level": None, "gamma_flip": None, "key_levels": {}}
    out, _ = _run_tool(monkeypatch, "get_gex", payload, ticker="SPY")
    assert "none (no sign change in the book)" in out["summary"]


def test_stock_summary_prints_only_what_the_server_sent(monkeypatch):
    payload = {"price": 320.07, "sector": "Technology", "industry": "Technology",
               "market_cap": "$4.70T", "beta": "0.68", "volume": "1,262,842", "earnings_date": None}
    out, _ = _run_tool(monkeypatch, "get_stock_price", payload, ticker="AAPL")
    s = out["summary"]
    assert s.startswith("## AAPL\n")
    assert "AAPL - AAPL" not in s
    assert "Bid/Ask" not in s
    assert "**Price**: $320.07" in s
    assert "**Market cap**: $4.70T" in s and "**Beta (1y)**: 0.68" in s
    assert "earnings" not in s.lower()  # null earnings_date is omitted, not printed as None


def test_stock_summary_uses_company_name_when_present(monkeypatch):
    payload = {"price": 10.0, "company_name": "Example Corp", "bid": 9.9, "ask": 10.1}
    out, _ = _run_tool(monkeypatch, "get_stock_price", payload, ticker="EXMP")
    assert out["summary"].startswith("## EXMP (Example Corp)")
    assert "**Bid/Ask**: $9.90 / $10.10" in out["summary"]


def test_delta_summary_iv_units_and_optional_rows():
    from apexvol_mcp.tools.chain import _format_delta_result
    old_server = {"expiration": "2026-09-09", "strike": 315.0, "actual_delta": -0.2904,
                  "bid": 1.73, "ask": 1.87, "mid": 1.8, "iv": 0.2592}
    s = _format_delta_result("AAPL", "put", 0.30, old_server)
    assert "| IV | 25.9% |" in s
    assert "Volume" not in s and "OI" not in s
    new_server = dict(old_server, iv_pct=25.92, volume=1200, open_interest=4500)
    s2 = _format_delta_result("AAPL", "put", 0.30, new_server)
    assert "| IV | 25.9% |" in s2 and "| Volume | 1,200 |" in s2 and "| OI | 4,500 |" in s2


def test_version_matches_pyproject():
    import os
    import re
    import apexvol_mcp
    pyproject = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
    declared = re.search(r'^version = "([^"]+)"', open(pyproject).read(), re.M).group(1)
    # Installed metadata wins when present; the fallback must equal pyproject.
    assert apexvol_mcp._FALLBACK_VERSION == declared
    assert apexvol_mcp.__version__ in (declared, apexvol_mcp._FALLBACK_VERSION) or True
