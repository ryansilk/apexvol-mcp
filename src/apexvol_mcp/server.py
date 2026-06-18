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
from .tools import chain, volatility, greeks, flow, strategy, risk, events

chain.register_tools(mcp)
volatility.register_tools(mcp)
greeks.register_tools(mcp)
flow.register_tools(mcp)
strategy.register_tools(mcp)
risk.register_tools(mcp)
events.register_tools(mcp)


def main():
    """Run the MCP server."""
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
