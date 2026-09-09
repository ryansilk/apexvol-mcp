"""
Ticker Analytics Tools

Consolidated access to the per-ticker analytics endpoints that don't warrant
a dedicated tool each: skew, dividends, borrow rates, correlation, HV
regimes, price context, relative value, Greeks exposure, earnings-move
studies, max pain, volume profile, and 0DTE analytics.
Uses REST API calls to ApexVol platform.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError
from ._annotations import read_only

logger = logging.getLogger(__name__)

# analysis name -> (endpoint template, human title)
_TICKER_ANALYTICS = {
    'skew': ('/skew/{t}', 'Skew Analysis'),
    'dividends': ('/dividend/{t}', 'Dividend Analytics'),
    'borrow_rate': ('/borrow-rate/{t}', 'Borrow Rate / Hard-to-Borrow'),
    'correlation': ('/correlation/{t}', 'Correlation & Beta'),
    'hv_regimes': ('/hv-regimes/{t}', 'Historical Volatility Regimes'),
    'price_context': ('/price-context/{t}', 'Price & Volatility Context'),
    'relative_value': ('/relative-value/{t}', 'Relative Value'),
    'greeks_exposure': ('/greeks-exposure/{t}', 'Dealer Greeks Exposure'),
}

_EARNINGS_ANALYTICS = {
    'mispricing': ('/mispricing-assessment/{t}', 'Earnings Mispricing Assessment'),
    'historical_moves': ('/historical-moves/{t}', 'Historical Earnings Moves'),
    'expected_vs_actual': ('/expected-vs-actual/{t}', 'Expected vs Actual Moves'),
    'verdict': ('/earnings-verdict/{t}', 'Earnings Straddle Verdict'),
    'seasonality': ('/seasonality/{t}', 'Seasonality'),
    'post_drift': ('/post-earnings-drift/{t}', 'Post-Earnings Drift'),
    'iv_crush': ('/iv-crush/{t}', 'Earnings IV Crush Pattern'),
}


def _scalar_summary(title: str, data: dict, max_rows: int = 14) -> str:
    """Compact markdown table of the payload's top-level scalar fields.

    The full payload is always returned in `data`; this summary just gives a
    fast human-readable orientation.
    """
    lines = [f"## {title}", "", "| Field | Value |", "|-------|-------|"]
    rows = 0
    for key, value in (data or {}).items():
        if key in ('ticker', 'timestamp', 'as_of', 'iv_units'):
            continue
        if isinstance(value, (str, int, float, bool)) and value != '':
            if isinstance(value, float):
                value = f"{value:,.2f}"
            lines.append(f"| {key} | {value} |")
            rows += 1
        elif isinstance(value, (list, dict)) and value:
            lines.append(f"| {key} | ({len(value)} items — see data) |")
            rows += 1
        if rows >= max_rows:
            lines.append("| … | (more in data) |")
            break
    return "\n".join(lines)


def register_tools(mcp: FastMCP):
    """Register consolidated analytics tools with the MCP server."""

    @mcp.tool(**read_only('Ticker Analytics'))
    async def get_ticker_analytics(
        ticker: str,
        analysis: str,
        expiration: Optional[str] = None,
        days: int = 252,
        view: str = "",
        compare_with: str = ""
    ) -> dict:
        """
        Get a specific per-ticker analytics view.

        One tool, eight analyses — pick via the `analysis` argument:
        - "skew": put/call IV skew (view: "analysis" default, "history", "curvature")
        - "dividends": dividend history, yield, and ex-date behavior
        - "borrow_rate": stock borrow cost / hard-to-borrow signals (short-squeeze context)
        - "correlation": correlation and beta vs SPY and sector; pass compare_with
          to get the pairwise correlation vs another ticker instead
        - "hv_regimes": historical volatility regimes (view: "dashboard" default,
          "signals", "decomposition", "ex_earnings")
        - "price_context": price action + volatility briefing for orientation
        - "relative_value": is this ticker's vol rich or cheap vs its own history and peers
        - "greeks_exposure": dealer gamma/delta/vanna/charm and third-order exposure by strike,
          with per-greek key levels (greek_levels), a unit label per greek and, for gamma,
          the flip, both walls and a positioning sentence

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            analysis: One of the eight analysis names above
            expiration: Optional YYYY-MM-DD filter (greeks_exposure only)
            days: History window in trading days (borrow_rate, relative_value, hv_regimes)
            view: Sub-view for skew / hv_regimes (see above)
            compare_with: Second ticker for pairwise correlation (correlation only)

        Returns:
            The selected analytics payload with a compact summary
        """
        key = analysis.strip().lower().replace('-', '_')
        if key not in _TICKER_ANALYTICS:
            return {
                "success": False,
                "error": f"Unknown analysis '{analysis}'. Choose one of: {', '.join(_TICKER_ANALYTICS)}",
            }
        endpoint, title = _TICKER_ANALYTICS[key]
        try:
            client = get_client()
            params = {}
            if key in ('borrow_rate', 'relative_value', 'hv_regimes') and days != 252:
                params['days'] = days
            if key == 'greeks_exposure' and expiration:
                params['expiration'] = expiration
            if view and key in ('skew', 'hv_regimes'):
                params['view'] = view.strip().lower()
            if compare_with and key == 'correlation':
                endpoint = '/correlation/{t}/compare/' + compare_with.strip().upper()
                title = f'Correlation vs {compare_with.strip().upper()}'

            result = await client.get(endpoint.format(t=ticker.upper()), params=params or None)

            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"{ticker.upper()} {title}", result),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "analysis": key,
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting {key} analytics: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Earnings Move Analysis'))
    async def get_earnings_move_analysis(
        ticker: str,
        analysis: str = "mispricing",
        periods: Optional[str] = None
    ) -> dict:
        """
        Analyze how a stock moves around earnings and whether options misprice it.

        Pick via the `analysis` argument:
        - "mispricing" (default): IV rank + VRP + expected-vs-actual history
          combined into an over/underpriced assessment
        - "historical_moves": realized post-earnings moves over several horizons
        - "expected_vs_actual": straddle-implied expected move vs what actually happened
        - "verdict": combined buy/sell-the-straddle verdict for the next earnings
        - "seasonality": monthly/quarterly return and volatility seasonality
        - "post_drift": post-earnings drift statistics over recent quarters
        - "iv_crush": IV build-up and crush pattern around past earnings

        Use this when the user asks whether earnings options are over/underpriced,
        how a stock usually moves on earnings, or if a straddle is worth buying.

        Args:
            ticker: Stock symbol
            analysis: One of the seven analysis names above
            periods: Comma-separated day horizons for historical_moves (default "7,14,21,30")

        Returns:
            The selected earnings analysis payload with a compact summary
        """
        key = analysis.strip().lower().replace('-', '_')
        if key not in _EARNINGS_ANALYTICS:
            return {
                "success": False,
                "error": f"Unknown analysis '{analysis}'. Choose one of: {', '.join(_EARNINGS_ANALYTICS)}",
            }
        endpoint, title = _EARNINGS_ANALYTICS[key]
        try:
            client = get_client()
            params = {}
            if key == 'historical_moves' and periods:
                params['periods'] = periods

            result = await client.get(endpoint.format(t=ticker.upper()), params=params or None)

            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"{ticker.upper()} {title}", result),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "analysis": key,
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting earnings analysis {key}: {e}")
            return {"success": False, "error": str(e)}



    @mcp.tool(**read_only('Ticker Search'))
    async def search_tickers(query: str, limit: int = 8) -> dict:
        """
        Search or validate tickers against the platform's coverage universe.

        Use before deep analysis when unsure a symbol is supported, or to
        resolve a company name to its ticker.

        Args:
            query: Symbol or company-name fragment (e.g. "NVDA" or "nvidia")
            limit: Max matches to return (1-20)

        Returns:
            Ranked matches plus exact-match/supported flags
        """
        try:
            client = get_client()
            result = await client.get("/search", params={'q': query, 'limit': limit})
            exact = result.get('exact_match')
            supported = 'yes' if result.get('supported') else 'no exact match'
            return {
                "success": True,
                "data": result,
                "summary": (
                    f"**{query}** — {result.get('count', 0)} matches; exact match: {supported}"
                    + (f" ({exact.get('name', '')})" if exact else "")
                ),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error searching tickers: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Relative Value Scan'))
    async def scan_relative_value(
        view: str = "mean_reversion",
        limit: int = 20,
        threshold: float = 1.5
    ) -> dict:
        """
        Market-wide relative-value scans.

        - "mean_reversion" (default): tickers whose IV/SPY ratio is stretched
          vs its own 1-year average — rich or cheap vol candidates
        - "pairs": rich-vs-cheap ticker pairs for pairs trading

        Args:
            view: "mean_reversion" or "pairs"
            limit: Max results (1-50)
            threshold: Z-score threshold for mean_reversion (default 1.5)

        Returns:
            Scan results ranked by stretch
        """
        try:
            client = get_client()
            params = {'view': view, 'limit': limit}
            if view == 'mean_reversion' and threshold != 1.5:
                params['threshold'] = threshold
            result = await client.get("/relative-value-scan", params=params)
            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"Relative-value scan ({view})", result),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error scanning relative value: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('ORATS Core Data'))
    async def get_orats_cores(
        ticker: str,
        fields: str = ""
    ) -> dict:
        """
        Get raw ORATS "cores" analytics for a ticker — 340+ pre-computed fields.

        The deepest single call available: IV surface summary metrics, IV/HV
        history stats, term-structure slope/contango, earnings-move components,
        borrow rates, betas, percentiles, and more, straight from the data
        vendor. Use when the curated endpoints don't carry the specific field
        you need.

        Use this tool when the user asks about:
        - A specific ORATS field by name
        - Deep vendor-level analytics not in other tools
        - Bulk fundamentals+vol context for one ticker

        Args:
            ticker: Stock symbol
            fields: Comma-separated field names for specific fields,
                "all" for the entire row, or empty for the curated ~45-field default

        Returns:
            The requested cores fields (available_field_count says how many exist)
        """
        try:
            client = get_client()
            params = {'fields': fields} if fields else None
            result = await client.get(f"/cores/{ticker.upper()}", params=params)

            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"{ticker.upper()} ORATS Cores", result, max_rows=20),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting cores: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Max Pain'))
    async def get_max_pain(
        ticker: str,
        expiration: Optional[str] = None
    ) -> dict:
        """
        Get the max pain strike for a ticker.

        Max pain is the strike where option holders lose the most at expiry
        (and writers keep the most premium) — often watched as a magnet level
        into expiration.

        Use this tool when the user asks about:
        - Max pain level
        - Where the stock might pin at expiration
        - Option-writer positioning

        Args:
            ticker: Stock symbol
            expiration: Expiration date YYYY-MM-DD (default: nearest)

        Returns:
            Max pain strike with the loss profile by strike
        """
        try:
            client = get_client()
            params = {'expiration': expiration} if expiration else None
            result = await client.get(f"/max-pain/{ticker.upper()}", params=params)

            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"{ticker.upper()} Max Pain", result),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting max pain: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Volume Profile'))
    async def get_volume_profile(
        ticker: str,
        expiration: Optional[str] = None
    ) -> dict:
        """
        Get the option volume and open-interest profile by strike.

        Shows where volume and OI concentrate across strikes — support/
        resistance implied by positioning, plus notable OI changes.

        Use this tool when the user asks about:
        - Where the open interest sits
        - Volume by strike
        - OI-implied support and resistance

        Args:
            ticker: Stock symbol
            expiration: Expiration date YYYY-MM-DD (default: nearest)

        Returns:
            Per-strike volume/OI profile
        """
        try:
            client = get_client()
            params = {'expiration': expiration} if expiration else None
            result = await client.get(f"/volume-profile/{ticker.upper()}", params=params)

            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"{ticker.upper()} Volume/OI Profile", result),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting volume profile: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('0DTE Analytics'))
    async def get_zero_dte(
        ticker: str,
        strikes_around: Optional[int] = None,
        detail: Optional[str] = None
    ) -> dict:
        """
        Get 0DTE (same-day expiration) analytics for a ticker.

        Includes 0DTE gamma exposure, gamma flip level, max pain, theta decay
        projection, and the chain for today's expiration. Only meaningful for
        tickers with daily expirations (SPY, QQQ, SPX...) on trading days.

        Use this tool when the user asks about:
        - 0DTE setups or same-day options
        - Intraday gamma/pinning levels
        - Today's expiration chain

        Args:
            ticker: Stock symbol with 0DTE listings (e.g., "SPY")
            strikes_around: Strikes kept each side of spot in by_strike and
                chain_table (server default 15); 0 keeps every strike.
            detail: "compact" (default) or "full" for the whole chain.

        Returns:
            0DTE analytics payload
        """
        try:
            client = get_client()
            params = {}
            if strikes_around is not None:
                params['strikes_around'] = int(strikes_around)
            if detail in ('compact', 'full'):
                params['detail'] = detail
            result = await client.get(f"/zero-dte/{ticker.upper()}", params=params or None)

            return {
                "success": True,
                "data": result,
                "summary": _scalar_summary(f"{ticker.upper()} 0DTE Analytics", result),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting 0DTE analytics: {e}")
            return {"success": False, "error": str(e)}
