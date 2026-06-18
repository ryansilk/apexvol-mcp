"""
Volatility Analysis Tools

Tools for IV rank, volatility cone, VRP, term structure, and mean reversion.
Uses REST API calls to ApexVol platform.
"""

import logging
from typing import Optional, List
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register volatility tools with the MCP server."""

    @mcp.tool()
    async def get_iv_rank(
        ticker: str,
        lookback_days: int = 252
    ) -> dict:
        """
        Get IV Rank and percentile for a stock.

        IV Rank shows where current implied volatility stands relative to its
        historical range. High IV Rank (>50) suggests elevated volatility,
        potentially favorable for selling premium. Low IV Rank (<30) suggests
        cheap options, potentially favorable for buying premium.

        Use this tool when the user asks about:
        - Whether options are expensive or cheap
        - IV rank or IV percentile
        - Historical volatility context
        - Premium selling/buying opportunities

        Args:
            ticker: Stock symbol (e.g., "AAPL", "SPY")
            lookback_days: Historical lookback period (default 252 = 1 year)

        Returns:
            IV rank data with interpretation and strategy recommendations
        """
        try:
            client = get_client()
            params = {'lookback_days': lookback_days}
            result = await client.get(f"/iv-rank/{ticker.upper()}", params=params)

            # Determine assessment
            iv_rank = result.get('iv_rank', 0)
            if iv_rank >= 70:
                assessment = "HIGH - Consider selling premium"
            elif iv_rank >= 50:
                assessment = "ELEVATED - Neutral to selling bias"
            elif iv_rank >= 30:
                assessment = "NORMAL - No strong edge"
            else:
                assessment = "LOW - Consider buying premium"

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} IV Analysis

| Metric | Value |
|--------|-------|
| Current IV | {result.get('current_iv', 0):.1f}% |
| IV Rank | {iv_rank:.1f} |
| IV Percentile | {result.get('iv_percentile', 0):.1f}% |
| 52-Week Low | {result.get('iv_min_52w', 0):.1f}% |
| 52-Week High | {result.get('iv_max_52w', 0):.1f}% |

**Assessment**: {assessment}
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "lookback_days": lookback_days
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting IV rank: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_volatility_cone(
        ticker: str,
        periods: Optional[str] = None
    ) -> dict:
        """
        Get volatility cone comparing current IV to historical realized volatility.

        The volatility cone shows the historical distribution of realized
        volatility at different time horizons, allowing comparison with
        current implied volatility. This helps identify if options are
        over/underpriced relative to historical moves.

        Use this tool when the user asks about:
        - IV vs realized volatility comparison
        - Volatility cone analysis
        - Historical volatility distribution
        - Whether options are fairly priced

        Args:
            ticker: Stock symbol
            periods: Comma-separated periods in days (default "10,20,30,60,90")

        Returns:
            Volatility cone data with percentile rankings
        """
        try:
            client = get_client()
            params = {}
            if periods:
                params['periods'] = periods

            result = await client.get(f"/volatility-cone/{ticker.upper()}", params=params if params else None)

            return {
                "success": True,
                "data": result,
                "summary": _format_vol_cone(ticker, result),
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "periods": periods or "10,20,30,60,90"
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting volatility cone: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_volatility_risk_premium(
        ticker: str,
        lookback_days: int = 30
    ) -> dict:
        """
        Calculate the volatility risk premium (IV minus realized volatility).

        VRP measures the spread between implied and realized volatility.
        Positive VRP means options are pricing in more volatility than
        actually occurs - favorable for sellers. Negative VRP means
        options are cheap relative to actual moves.

        Use this tool when the user asks about:
        - Volatility risk premium or VRP
        - IV vs RV spread
        - Whether to sell or buy volatility
        - Premium edge assessment

        Args:
            ticker: Stock symbol
            lookback_days: Days for realized vol calculation (default 30)

        Returns:
            VRP data with assessment and strategy recommendation
        """
        try:
            client = get_client()
            params = {'lookback_days': lookback_days}
            result = await client.get(f"/vrp/{ticker.upper()}", params=params)

            vrp = result.get('vrp', 0)
            if vrp > 5:
                assessment = "HIGH VRP - Strong edge for premium sellers"
            elif vrp > 0:
                assessment = "POSITIVE VRP - Slight edge for sellers"
            elif vrp > -5:
                assessment = "NEUTRAL - No significant edge"
            else:
                assessment = "NEGATIVE VRP - Options may be cheap"

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} Volatility Risk Premium

| Metric | Value |
|--------|-------|
| Implied Volatility | {result.get('iv', 0)*100:.1f}% |
| Realized Volatility ({lookback_days}d) | {result.get('rv', 0)*100:.1f}% |
| **VRP** | **{vrp:+.1f}%** |

**Assessment**: {assessment}
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "lookback_days": lookback_days
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting VRP: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_term_structure(ticker: str) -> dict:
        """
        Get IV term structure across all expirations.

        Shows how implied volatility varies across different expiration
        dates. Contango (upward slope) is normal; backwardation suggests
        near-term event risk.

        Use this tool when the user asks about:
        - Term structure of volatility
        - Calendar spread opportunities
        - Event-driven vol bumps
        - Contango vs backwardation

        Args:
            ticker: Stock symbol

        Returns:
            Term structure data by expiration
        """
        try:
            client = get_client()
            result = await client.get(f"/term-structure/{ticker.upper()}")

            return {
                "success": True,
                "data": result,
                "summary": _format_term_structure(ticker, result),
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting term structure: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def find_iv_opportunities(
        ticker: str,
        z_score_threshold: float = 2.0
    ) -> dict:
        """
        Find IV mean reversion trading opportunities.

        Identifies when IV is statistically extreme (>2 std from mean)
        and suggests strategies to capture mean reversion.

        Use this tool when the user asks about:
        - Mean reversion opportunities
        - Extreme IV levels
        - When to sell/buy volatility
        - IV statistical analysis

        Args:
            ticker: Stock symbol
            z_score_threshold: Statistical threshold (default 2.0)

        Returns:
            Opportunity assessment with strategy recommendations
        """
        try:
            client = get_client()
            result = await client.get(f"/iv-opportunities/{ticker.upper()}")

            z_score = result.get('z_score', 0)
            if abs(z_score) >= z_score_threshold:
                if z_score > 0:
                    opportunity = "IV is significantly elevated - potential short vol opportunity"
                    strategy = "Consider selling premium via credit spreads or iron condors"
                else:
                    opportunity = "IV is significantly depressed - potential long vol opportunity"
                    strategy = "Consider buying premium via straddles or strangles"
            else:
                opportunity = "IV is within normal range - no extreme opportunity"
                strategy = "No strong directional vol trade recommended"

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} Mean Reversion Analysis

| Metric | Value |
|--------|-------|
| Current IV | {result.get('current_iv', 0)*100:.1f}% |
| Mean IV | {result.get('mean_iv', 0)*100:.1f}% |
| Std Dev | {result.get('std_iv', 0)*100:.1f}% |
| **Z-Score** | **{z_score:.2f}** |

**Opportunity**: {opportunity}

**Strategy**: {strategy}
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "threshold": z_score_threshold
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error finding IV opportunities: {e}")
            return {"success": False, "error": str(e)}


def _format_vol_cone(ticker: str, data: dict) -> str:
    """Format volatility cone data as markdown."""
    lines = [
        f"## {ticker.upper()} Volatility Cone",
        "",
        "| Period | Current RV | Median | 25th | 75th | Percentile |",
        "|--------|-----------|--------|------|------|------------|",
    ]

    cone_data = data.get('cone', {})
    for period, values in cone_data.items():
        lines.append(
            f"| {period}d | {values.get('current', 0)*100:.1f}% | "
            f"{values.get('median', 0)*100:.1f}% | "
            f"{values.get('p25', 0)*100:.1f}% | "
            f"{values.get('p75', 0)*100:.1f}% | "
            f"{values.get('percentile', 0):.0f}% |"
        )

    return "\n".join(lines)


def _format_term_structure(ticker: str, data: dict) -> str:
    """Format term structure data as markdown."""
    lines = [
        f"## {ticker.upper()} Term Structure",
        "",
        "| Expiration | ATM IV | Days to Exp |",
        "|------------|--------|-------------|",
    ]

    term_data = data.get('term_structure', [])
    for item in term_data[:8]:  # Limit to 8 expirations
        lines.append(
            f"| {item.get('expiration', 'N/A')} | "
            f"{item.get('atm_iv', 0)*100:.1f}% | "
            f"{item.get('dte', 0)} |"
        )

    return "\n".join(lines)
