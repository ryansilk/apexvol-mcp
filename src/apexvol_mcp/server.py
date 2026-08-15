"""
ApexVol MCP Server

Main entry point for the MCP server that provides options analytics
tools for Claude Code and Claude Desktop.

This server uses REST API calls to the ApexVol platform - no local
provider imports are required.
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .config import config

# Configure logging to stderr (important for stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("apexvol")


# Register tool modules
from .tools import chain, volatility, greeks, flow, strategy, risk, events, analytics

chain.register_tools(mcp)
volatility.register_tools(mcp)
greeks.register_tools(mcp)
flow.register_tools(mcp)
strategy.register_tools(mcp)
risk.register_tools(mcp)
events.register_tools(mcp)
analytics.register_tools(mcp)


def run_check() -> int:
    """Verify install + token against the live API (apexvol-mcp --check).

    Prints what a support ticket would otherwise have to ask for: version,
    target URL, auth result, and remaining quotas. Returns a process exit
    code (0 = healthy).
    """
    import os
    import httpx

    try:
        from apexvol_mcp import __version__ as version
    except Exception:
        version = 'unknown'

    base_url = os.getenv('APEXVOL_API_URL', 'https://apexvol.com').rstrip('/')
    token = os.getenv('APEXVOL_API_TOKEN', '')

    print(f"apexvol-mcp {version}")
    print(f"API URL: {base_url}")
    if not token:
        print("FAIL: APEXVOL_API_TOKEN is not set.")
        print("Set it in your MCP config env block, then re-run: apexvol-mcp --check")
        return 1
    print(f"Token: {token[:9]}…{token[-4:]} ({len(token)} chars)")
    if not token.startswith('avmcp_'):
        print("WARN: token does not start with 'avmcp_' — double-check you copied it fully.")

    try:
        resp = httpx.get(
            f"{base_url}/api/mcp/data/stock/AAPL",
            headers={'Authorization': f'Bearer {token}', 'X-ApexVol-Client': version},
            timeout=30,
        )
    except httpx.RequestError as e:
        print(f"FAIL: could not reach {base_url} — {e}")
        return 1

    if resp.status_code == 200:
        print("OK: authenticated and received data.")
        for header, label in (
            ('X-RateLimit-Remaining-Minute', 'Requests left this minute'),
            ('X-RateLimit-Remaining-Hour', 'Requests left this hour'),
            ('X-Monthly-Budget-Remaining', 'Monthly budget remaining'),
        ):
            if resp.headers.get(header):
                print(f"  {label}: {resp.headers[header]}")
        print("You're set — restart Claude Code/Desktop to load the server.")
        return 0

    try:
        detail = resp.json().get('error', '')
    except Exception:
        detail = resp.text[:200]
    print(f"FAIL: HTTP {resp.status_code} — {detail}")
    if resp.status_code == 401:
        print("The token was rejected. Re-copy it from apexvol.com/account → API Access,")
        print("or email support@apexvol.com if it keeps failing.")
    elif resp.status_code == 403:
        print("The token is valid but access is gated (Pro subscription / beta flag).")
    return 1


def main():
    """Run the MCP server (or a connectivity check with --check)."""
    if '--check' in sys.argv:
        sys.exit(run_check())

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        logger.error("Server may not function correctly - ensure APEXVOL_API_TOKEN is set")

    logger.info("Starting ApexVol MCP server")
    logger.info(f"API URL: {config.api_url}")
    mcp.run()


if __name__ == "__main__":
    main()
