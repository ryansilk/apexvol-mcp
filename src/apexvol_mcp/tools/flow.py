"""
Options Flow Tools

Tools for options flow analysis, smart money detection, and vol arbitrage.
Uses REST API calls to ApexVol platform.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError
from ._annotations import read_only

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register flow tools with the MCP server."""

    @mcp.tool(**read_only('Options Flow'))
    async def get_options_flow(
        ticker: str,
        limit: Optional[int] = None,
        detail: Optional[str] = None
    ) -> dict:
        """
        Analyze options flow and unusual activity for a ticker.

        Returns call/put volumes, premiums, and identifies unusual activity
        that may indicate institutional positioning.

        Use this tool when the user asks about:
        - Options flow or order flow
        - Call/put ratio
        - Unusual options activity
        - Large trades or sweeps

        Args:
            ticker: Stock symbol
            limit: Rows kept in the flow lists under compact detail (server
                default 25; 1 to 500).
            detail: "compact" (default) or "full" for every row.

        Returns:
            Flow analysis with volumes, premiums, and unusual activity
        """
        try:
            client = get_client()
            params = {}
            if limit is not None:
                params['limit'] = int(limit)
            if detail in ('compact', 'full'):
                params['detail'] = detail
            result = await client.get(f"/flow/{ticker.upper()}", params=params or None)

            # The server nests the totals under 'summary' (total_call_volume,
            # total_put_volume, total_call_premium, total_put_premium,
            # put_call_ratio, sentiment). 0.1.0 to 0.1.2 read top-level keys
            # that never existed and printed zeros above 60 KB of real rows.
            s = result.get('summary') or {}
            call_vol = int(s.get('total_call_volume') or 0)
            put_vol = int(s.get('total_put_volume') or 0)
            call_prem = float(s.get('total_call_premium') or 0)
            put_prem = float(s.get('total_put_premium') or 0)
            ratio = call_vol / put_vol if put_vol > 0 else 0
            sentiment = s.get('sentiment') or 'n/a'
            freshness = result.get('data_freshness') or ''
            note = result.get('message') or ''
            header = f"## {ticker.upper()} Options Flow"
            if freshness:
                header += f" ({freshness})"
            summary = f"""{header}

| Metric | Value |
|--------|-------|
| Call Volume | {call_vol:,} |
| Put Volume | {put_vol:,} |
| Call/Put Ratio | {ratio:.2f} |
| Call Premium | ${call_prem:,.0f} |
| Put Premium | ${put_prem:,.0f} |
| Net Premium | ${call_prem - put_prem:,.0f} |
| Sentiment | {sentiment} |

**Unusual Activity**: {len(result.get('unusual_activity', []))} trades flagged
"""
            if note:
                summary += f"\n_{note}_\n"

            return {
                "success": True,
                "data": result,
                "summary": summary,
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting flow: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Smart Money Flow'))
    async def get_smart_money_flow(ticker: str) -> dict:
        """
        Identify institutional/smart money options trades.

        Filters for large trades, sweeps, and block orders that may indicate
        informed positioning.

        Use this tool when the user asks about:
        - Smart money or institutional flow
        - Large options trades
        - Block trades or sweeps
        - Whale activity

        Args:
            ticker: Stock symbol

        Returns:
            Smart money flow patterns and significant trades
        """
        try:
            client = get_client()
            result = await client.get(f"/smart-money/{ticker.upper()}")

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} Smart Money Flow

**Significant Trades**: {len(result.get('trades', []))}
**Total Premium**: ${result.get('total_premium', 0):,.0f}
**Sentiment**: {result.get('sentiment', 'Neutral')}
""",
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting smart money flow: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Volatility Arbitrage Scan'))
    async def scan_volatility_arb() -> dict:
        """
        Scan for cross-index volatility arbitrage opportunities.

        Identifies when implied volatility relationships between correlated
        assets are mispriced, creating potential arbitrage opportunities.

        Use this tool when the user asks about:
        - Volatility arbitrage
        - Cross-asset vol relationships
        - Vol dislocations
        - Relative value opportunities

        Returns:
            Volatility arbitrage opportunities across indices
        """
        try:
            client = get_client()
            result = await client.get("/vol-arb-scan")

            opportunities = result.get('opportunities', [])

            return {
                "success": True,
                "data": result,
                "summary": f"""## Volatility Arbitrage Scan

**Opportunities Found**: {len(opportunities)}

Top opportunities are ranked by z-score deviation from historical relationships.
""",
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error scanning vol arb: {e}")
            return {"success": False, "error": str(e)}
