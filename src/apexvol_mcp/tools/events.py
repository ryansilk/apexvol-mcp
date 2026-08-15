"""
Events and Screening Tools

Tools for earnings calendar, event analysis, market screening, and overview.
Uses REST API calls to ApexVol platform.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError
from ._annotations import read_only

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register events and screening tools with the MCP server."""

    @mcp.tool(**read_only('Earnings Calendar'))
    async def get_earnings_calendar(
        days_ahead: int = 7,
        min_market_cap: Optional[float] = None
    ) -> dict:
        """
        Get upcoming earnings announcements.

        Shows companies reporting earnings in the upcoming period, including
        expected move implied by options pricing.

        Use this tool when the user asks about:
        - Upcoming earnings
        - What companies report this week
        - Earnings calendar

        Args:
            days_ahead: Number of days to look ahead (default 7)
            min_market_cap: Minimum market cap filter in billions

        Returns:
            List of upcoming earnings with expected moves
        """
        try:
            client = get_client()
            params = {'days_ahead': days_ahead}

            result = await client.get("/earnings-calendar", params=params)

            earnings = result.get('earnings', [])

            # Apply market cap filter if specified
            if min_market_cap:
                earnings = [e for e in earnings
                           if e.get('market_cap', 0) >= min_market_cap * 1e9]

            summary_lines = [
                "## Upcoming Earnings",
                "",
                f"**Period**: Next {days_ahead} days",
                f"**Total**: {len(earnings)} companies",
                "",
                "| Date | Ticker | Company | Expected Move |",
                "|------|--------|---------|---------------|"
            ]

            for e in earnings[:15]:  # Limit to 15 for readability
                summary_lines.append(
                    f"| {e.get('date', 'N/A')} | {e.get('ticker', 'N/A')} | "
                    f"{e.get('company', 'N/A')[:20]} | "
                    f"±{e.get('expected_move', 0)*100:.1f}% |"
                )

            return {
                "success": True,
                "data": {"earnings": earnings},
                "summary": "\n".join(summary_lines),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "days_ahead": days_ahead,
                    "count": len(earnings)
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting earnings calendar: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Earnings History'))
    async def analyze_earnings_history(ticker: str) -> dict:
        """
        Analyze historical earnings moves for a stock.

        Shows how the stock has moved on past earnings announcements,
        compared to the expected move implied by options.

        Use this tool when the user asks about:
        - Historical earnings moves
        - Past earnings reactions
        - Beat/miss patterns
        - Options pricing accuracy

        Args:
            ticker: Stock symbol

        Returns:
            Historical earnings move analysis
        """
        try:
            client = get_client()
            result = await client.get(f"/earnings-history/{ticker.upper()}")

            history = result.get('history', [])
            avg_move = result.get('avg_actual_move', 0)
            avg_expected = result.get('avg_expected_move', 0)

            summary_lines = [
                f"## {ticker.upper()} Earnings History",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Avg Actual Move | ±{avg_move*100:.1f}% |",
                f"| Avg Expected Move | ±{avg_expected*100:.1f}% |",
                f"| Beat Rate | {result.get('beat_rate', 0)*100:.0f}% |",
                f"| Move > Expected | {result.get('exceeded_expected_rate', 0)*100:.0f}% |",
                "",
                "### Recent Earnings",
                "| Date | Actual | Expected | Surprise |",
                "|------|--------|----------|----------|"
            ]

            for h in history[:8]:  # Last 8 quarters
                actual = h.get('actual_move', 0)
                expected = h.get('expected_move', 0)
                surprise = h.get('eps_surprise', 0)
                summary_lines.append(
                    f"| {h.get('date', 'N/A')} | "
                    f"{'+' if actual > 0 else ''}{actual*100:.1f}% | "
                    f"±{expected*100:.1f}% | "
                    f"{'+' if surprise > 0 else ''}{surprise*100:.1f}% |"
                )

            return {
                "success": True,
                "data": result,
                "summary": "\n".join(summary_lines),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ticker": ticker,
                    "quarters_analyzed": len(history)
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error analyzing earnings history: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Market Screener'))
    async def screen_market(
        screen_type: str = "high_iv_rank",
        limit: int = 20,
        min_market_cap: float = 0,
        exclude_earnings_days: int = 0
    ) -> dict:
        """
        Screen the market for trading opportunities.

        Preset screens run against the full ~6,000-ticker universe using bulk
        data (cheap on quota). Pass screen_type="list" to fetch the catalog.

        Screen types:
        - high_iv_rank / low_iv_rank: elevated or depressed IV vs 1-year range
        - high_vrp: IV rich vs realized — premium-selling edge
        - earnings_this_week: reporting in the next 7 days
        - high_skew: elevated put skew (hedging demand / fear)
        - steep_contango: large front-to-back IV spread (calendar spreads)
        - mean_reversion: IV/SPY ratio stretched vs its 1-year average
        - vol_pairs: rich-vs-cheap ticker pairs vs SPY
        - decorrelation: low-beta diversifiers
        - unusual_volume: options volume far above 20-day average
        - pin_risk: spot pinned near a large-OI strike into expiration

        Use this tool when the user asks about:
        - Finding trading opportunities
        - Screening for high IV stocks
        - Unusual activity scan
        - What to trade

        Args:
            screen_type: Screen name from the list above (or "list" for the catalog)
            limit: Maximum results to return (default 20)
            min_market_cap: Minimum market cap in dollars (0 = server default $1B)
            exclude_earnings_days: Skip tickers reporting within N days (0 = keep all)

        Returns:
            Stocks matching the screen criteria
        """
        try:
            client = get_client()
            params = {
                'screen_type': screen_type,
                'limit': limit
            }
            if min_market_cap:
                params['min_market_cap'] = min_market_cap
            if exclude_earnings_days:
                params['exclude_earnings_days'] = exclude_earnings_days

            result = await client.get("/screen", params=params)

            results = result.get('results', [])

            # Format based on screen type
            screen_names = {
                'high_iv_rank': 'High IV Rank',
                'low_iv_rank': 'Low IV Rank',
                'high_gex': 'High Positive GEX',
                'negative_gex': 'Negative GEX',
                'unusual_volume': 'Unusual Options Volume',
                'earnings_this_week': 'Earnings This Week'
            }

            summary_lines = [
                f"## {screen_names.get(screen_type, screen_type)} Screen",
                "",
                f"**Results**: {len(results)} stocks",
                "",
                "| Ticker | Score | Key Metric |",
                "|--------|-------|------------|"
            ]

            for r in results[:limit]:
                summary_lines.append(
                    f"| {r.get('ticker', 'N/A')} | "
                    f"{r.get('score', 0):.1f} | "
                    f"{r.get('key_metric', 'N/A')} |"
                )

            return {
                "success": True,
                "data": result,
                "summary": "\n".join(summary_lines),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "screen_type": screen_type,
                    "count": len(results)
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error running screen: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Market Overview'))
    async def get_market_overview() -> dict:
        """
        Get market-wide volatility overview.

        Shows aggregate volatility metrics across major indices and sectors,
        including VIX levels, put/call ratios, and GEX regime.

        Use this tool when the user asks about:
        - Market overview
        - Overall market volatility
        - VIX and market sentiment
        - Broad market positioning

        Returns:
            Market-wide volatility and positioning overview
        """
        try:
            client = get_client()
            result = await client.get("/market-overview")

            vix = result.get('vix', {})
            indices = result.get('indices', {})

            summary_lines = [
                "## Market Overview",
                "",
                "### Volatility",
                "| Metric | Value |",
                "|--------|-------|",
                f"| VIX | {vix.get('level', 0):.2f} |",
                f"| VIX Percentile | {vix.get('percentile', 0):.0f}% |",
                f"| VIX Term Structure | {vix.get('term_structure', 'N/A')} |",
                "",
                "### Major Indices",
                "| Index | Price | GEX Regime | IV Rank |",
                "|-------|-------|------------|---------|"
            ]

            for idx in ['SPY', 'QQQ', 'IWM', 'DIA']:
                data = indices.get(idx, {})
                regime = "Positive" if data.get('total_gex', 0) > 0 else "Negative"
                summary_lines.append(
                    f"| {idx} | ${data.get('price', 0):.2f} | "
                    f"{regime} | {data.get('iv_rank', 0):.0f}% |"
                )

            # Market sentiment
            pc_ratio = result.get('put_call_ratio', 0)
            if pc_ratio > 1.2:
                sentiment = "Bearish (High Put/Call)"
            elif pc_ratio < 0.8:
                sentiment = "Bullish (Low Put/Call)"
            else:
                sentiment = "Neutral"

            summary_lines.extend([
                "",
                f"### Sentiment",
                f"**Put/Call Ratio**: {pc_ratio:.2f}",
                f"**Interpretation**: {sentiment}"
            ])

            return {
                "success": True,
                "data": result,
                "summary": "\n".join(summary_lines),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting market overview: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Economic Calendar'))
    async def get_economic_calendar(
        from_date: str = "",
        to_date: str = ""
    ) -> dict:
        """
        Get the macro economic-event calendar (CPI, FOMC, jobs reports...).

        Use this tool when the user asks about:
        - Upcoming macro events or data releases
        - When the next CPI/FOMC/NFP is
        - Event risk beyond earnings

        Args:
            from_date: Start date YYYY-MM-DD (default today)
            to_date: End date YYYY-MM-DD (default ~1 week out)

        Returns:
            Economic events with dates and importance
        """
        try:
            client = get_client()
            params = {}
            if from_date:
                params['from_date'] = from_date
            if to_date:
                params['to_date'] = to_date
            result = await client.get("/economic-calendar", params=params or None)
            events = result.get('events', result if isinstance(result, list) else [])
            return {
                "success": True,
                "data": result,
                "summary": f"## Economic calendar — {len(events)} events (see data)",
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting economic calendar: {e}")
            return {"success": False, "error": str(e)}
