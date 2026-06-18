"""
Greeks and GEX Tools

Tools for Gamma Exposure (GEX), charm, third-order Greeks, and heatmaps.
Uses REST API calls to ApexVol platform.
"""

import logging
from typing import Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register Greeks tools with the MCP server."""

    @mcp.tool()
    async def get_gex(
        ticker: str,
        expiration: Optional[str] = None,
        aggregate: bool = True
    ) -> dict:
        """
        Get Gamma Exposure (GEX) levels and flip points.

        GEX measures the gamma exposure of market makers at each strike level.
        Positive GEX suggests dealer hedging will dampen moves (supportive).
        Negative GEX suggests dealer hedging will amplify moves (volatile).

        Use this tool when the user asks about:
        - Gamma exposure or GEX
        - Support and resistance from options
        - Dealer hedging levels
        - Market maker positioning

        Args:
            ticker: Stock symbol (e.g., "SPY", "QQQ")
            expiration: Specific expiration or None for aggregate
            aggregate: Whether to aggregate across all expirations

        Returns:
            GEX by strike, total GEX, and key levels
        """
        try:
            client = get_client()
            params = {'aggregate': str(aggregate).lower()}
            if expiration:
                params['expiration'] = expiration

            result = await client.get(f"/gex/{ticker.upper()}", params=params)

            total_gex = result.get('total_gex', 0)
            gex_flip = result.get('gex_flip', 0)
            regime = "Positive GEX (Supportive)" if total_gex > 0 else "Negative GEX (Volatile)"

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} Gamma Exposure

| Metric | Value |
|--------|-------|
| Total GEX | {total_gex:,.0f} |
| GEX Flip Point | ${gex_flip:.2f} |
| Regime | {regime} |

**Key Levels**:
- Max Call GEX: {result.get('max_call_gex_strike', 'N/A')}
- Max Put GEX: {result.get('max_put_gex_strike', 'N/A')}
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "aggregated": aggregate
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting GEX: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_charm_exposure(
        ticker: str,
        expiration: Optional[str] = None
    ) -> dict:
        """
        Get charm (delta decay) exposure by strike.

        Charm measures how delta changes with time. High charm exposure
        indicates significant delta changes as time passes, affecting
        hedging flows.

        Use this tool when the user asks about:
        - Charm exposure
        - Delta decay
        - Time-based hedging flows

        Args:
            ticker: Stock symbol
            expiration: Specific expiration or None for nearest

        Returns:
            Charm exposure by strike
        """
        try:
            client = get_client()
            params = {}
            if expiration:
                params['expiration'] = expiration

            result = await client.get(f"/charm/{ticker.upper()}", params=params if params else None)

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} Charm Exposure

Charm measures how delta changes with time. High charm at a strike
means significant hedging adjustments as expiration approaches.

Total Charm: {result.get('total_charm', 0):,.0f}
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting charm: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_third_order_greeks(
        ticker: str,
        expiration: Optional[str] = None
    ) -> dict:
        """
        Get third-order Greeks: Speed, Zomma, Color, Vomma, Ultima.

        These advanced Greeks measure higher-order sensitivities:
        - Speed: Rate of change of gamma
        - Zomma: Gamma sensitivity to volatility
        - Color: Gamma sensitivity to time
        - Vomma: Vega sensitivity to volatility
        - Ultima: Vomma sensitivity to volatility

        Use this tool when the user asks about:
        - Third-order Greeks
        - Speed, zomma, color
        - Advanced Greeks analysis

        Args:
            ticker: Stock symbol
            expiration: Specific expiration or None for nearest

        Returns:
            Third-order Greeks data
        """
        try:
            client = get_client()
            params = {}
            if expiration:
                params['expiration'] = expiration

            result = await client.get(f"/third-order-greeks/{ticker.upper()}", params=params if params else None)

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} Third-Order Greeks

| Greek | Description |
|-------|-------------|
| Speed | Rate of change of gamma |
| Zomma | Gamma sensitivity to vol |
| Color | Gamma sensitivity to time |
| Vomma | Vega sensitivity to vol |
| Ultima | Vomma sensitivity to vol |
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting third-order Greeks: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_greeks_heatmap(
        ticker: str,
        greek: str = "delta",
        option_type: str = "calls"
    ) -> dict:
        """
        Get Greeks visualization data across strikes and expirations.

        Returns a matrix of Greek values that can be visualized as a heatmap.
        Useful for understanding the Greek landscape across the chain.

        Use this tool when the user asks about:
        - Greeks across strikes
        - Delta/gamma/theta/vega heatmap
        - Greek distribution

        Args:
            ticker: Stock symbol
            greek: Which Greek to show ("delta", "gamma", "theta", "vega")
            option_type: "calls" or "puts"

        Returns:
            Heatmap matrix data with strikes and expirations
        """
        try:
            client = get_client()
            params = {
                'greek': greek,
                'option_type': option_type
            }

            result = await client.get(f"/greeks-heatmap/{ticker.upper()}", params=params)

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} {greek.capitalize()} Heatmap ({option_type.capitalize()})

Showing {greek} values across strikes and expirations.

**Strikes**: {len(result.get('strikes', []))}
**Expirations**: {len(result.get('expirations', []))}
**Stock Price**: ${result.get('stock_price', 0):.2f}
""",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "greek": greek,
                    "option_type": option_type
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting Greeks heatmap: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_cross_index_gex(
        tickers: Optional[str] = None
    ) -> dict:
        """
        Compare GEX across major indices.

        Shows gamma exposure comparison between SPY, QQQ, IWM, and other
        major indices to understand market-wide positioning.

        Use this tool when the user asks about:
        - Cross-index GEX comparison
        - Market-wide gamma positioning
        - Index relative GEX

        Args:
            tickers: Comma-separated tickers or None for defaults (SPY,QQQ,IWM,DIA)

        Returns:
            GEX comparison across indices
        """
        try:
            client = get_client()
            params = {}
            if tickers:
                params['tickers'] = tickers

            result = await client.get("/cross-index-gex", params=params if params else None)

            ticker_list = tickers.split(',') if tickers else ['SPY', 'QQQ', 'IWM', 'DIA']
            ticker_list = [t.strip().upper() for t in ticker_list]

            summary_lines = [
                "## Cross-Index GEX Comparison",
                "",
                "| Index | Total GEX | Regime |",
                "|-------|-----------|--------|"
            ]

            for t in ticker_list:
                data = result.get(t, {})
                total_gex = data.get('total_gex', 0)
                regime = 'Positive' if total_gex > 0 else 'Negative'
                summary_lines.append(f"| {t} | {total_gex:,.0f} | {regime} |")

            return {
                "success": True,
                "data": result,
                "summary": "\n".join(summary_lines),
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "tickers": ticker_list
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting cross-index GEX: {e}")
            return {"success": False, "error": str(e)}
