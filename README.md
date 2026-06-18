# ApexVol MCP Server

A Model Context Protocol (MCP) server that provides natural language access to ApexVol's options analytics platform. Query options chains, volatility metrics, Greeks, flow analysis, and more using Claude Code or Claude Desktop.

## Architecture

```
Customer's Machine                     ApexVol Platform
┌─────────────────────┐               ┌─────────────────────┐
│ Claude Code/Desktop │               │ apexvol.com         │
│         │           │               │                     │
│         ▼           │               │                     │
│   ApexVol MCP       │──── HTTPS ───▶│  /api/mcp/data/...  │
│   (runs locally)    │               │                     │
└─────────────────────┘               └─────────────────────┘
```

The MCP server runs locally on your machine and makes API calls to the ApexVol platform. No additional infrastructure required.

## Features

- **29 Analytics Tools** covering the full ApexVol API
- **Natural Language Interface** - Ask questions like "What's the IV rank for SPY?"
- **Claude Code & Desktop Support** - Works with CLI and desktop applications
- **Token Authentication** - Secure API token validation

## Available Tools

### Options Chain (5 tools)
- `get_options_chain` - Full options chain for any ticker
- `get_expirations` - Available expiration dates
- `get_options_by_delta` - Find options at specific delta
- `get_stock_price` - Current price and company info
- `calculate_expected_move` - Expected move from straddle pricing

### Volatility Analysis (5 tools)
- `get_iv_rank` - IV rank and percentile
- `get_volatility_cone` - IV vs historical realized volatility
- `get_volatility_risk_premium` - VRP (IV minus RV)
- `get_term_structure` - IV across expirations
- `find_iv_opportunities` - Mean reversion opportunities

### Greeks & GEX (5 tools)
- `get_gex` - Gamma Exposure by strike
- `get_charm_exposure` - Delta decay exposure
- `get_third_order_greeks` - Speed, zomma, color, vomma, ultima
- `get_greeks_heatmap` - Greeks across strikes and expirations
- `get_cross_index_gex` - Compare GEX across indices

### Options Flow (3 tools)
- `get_options_flow` - Flow and unusual activity
- `get_smart_money_flow` - Institutional flow patterns
- `scan_volatility_arb` - Cross-index volatility arbitrage

### Strategy Building (3 tools)
- `build_strategy` - Build options strategies (iron condor, spreads, etc.)
- `analyze_strategy` - Full P&L and Greeks analysis
- `optimize_strategy` - Find optimal strikes

### Risk Management (4 tools)
- `calculate_portfolio_greeks` - Aggregate portfolio Greeks
- `run_scenario_analysis` - What-if scenarios
- `generate_stress_tests` - Stress test results
- `get_hedge_recommendations` - Hedging suggestions

### Events & Screening (4 tools)
- `get_earnings_calendar` - Upcoming earnings
- `analyze_earnings_history` - Historical earnings moves
- `screen_market` - Market screening (high IV, unusual volume, etc.)
- `get_market_overview` - Market-wide volatility overview

## Installation

### Prerequisites

- Python 3.10+
- An ApexVol Pro subscription and an API token (see "Getting a Token" below)

### Install the Package

```bash
pip install apexvol-mcp
```

Or install from source:

```bash
cd apexvol-mcp
pip install -e .
```

## Configuration

### Claude Code (CLI)

Add to your project's `.mcp.json` or global `~/.claude.json`:

```json
{
  "mcpServers": {
    "apexvol": {
      "command": "apexvol-mcp",
      "env": {
        "APEXVOL_API_TOKEN": "avmcp_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

### Claude Desktop App

**macOS**: Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: Edit `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "apexvol": {
      "command": "apexvol-mcp",
      "env": {
        "APEXVOL_API_TOKEN": "avmcp_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APEXVOL_API_TOKEN` | Yes | Your ApexVol API token |
| `APEXVOL_API_URL` | No | API URL (default: https://apexvol.com) |

## Usage

After configuration, restart Claude Code or Claude Desktop to load the MCP server.

### Example Queries

**Volatility Analysis:**
- "What's the IV rank for AAPL?"
- "Show me the volatility cone for SPY"
- "Is there a volatility risk premium in TSLA?"

**Options Chain:**
- "Get the options chain for QQQ expiring next week"
- "Find a 30 delta put on NVDA"
- "What's the expected move for AMZN earnings?"

**Greeks & GEX:**
- "What's the gamma exposure for SPY?"
- "Show me the GEX flip point for QQQ"
- "Compare GEX across major indices"

**Flow Analysis:**
- "What's the options flow in AAPL today?"
- "Any unusual options activity in META?"
- "Scan for volatility arbitrage opportunities"

**Strategy Building:**
- "Build an iron condor on SPY"
- "Analyze a 150/155 call spread on AAPL"
- "What are the Greeks for selling a 200 put on NVDA?"

**Risk Management:**
- "Calculate portfolio Greeks for 100 AAPL shares and 1 AAPL 200 call"
- "Run a stress test on my positions"
- "How should I hedge my delta exposure?"

**Market Overview:**
- "What's the market overview today?"
- "Show me stocks with high IV rank"
- "What earnings are coming up this week?"

## Response Format

All tools return structured data with a markdown summary:

```json
{
  "success": true,
  "data": { ... },
  "summary": "## AAPL IV Analysis\n\n| Metric | Value |\n...",
  "metadata": {
    "timestamp": "2025-01-08T10:30:00",
    "ticker": "AAPL"
  }
}
```

## Authentication

ApexVol MCP uses token-based authentication. Your token is sent with each API request to the ApexVol platform.

### Token Format
- Prefix: `avmcp_`
- Length: 38 characters total

### Getting a Token
API access requires an active **Pro** subscription and is currently **invite-only**.
Request a token by emailing **support@apexvol.com** — tokens are issued by the
ApexVol team. The token is sent with every request, so treat it like a password;
contact support to rotate or revoke it if it leaks.

## Troubleshooting

### "Invalid or missing API token"
- Verify your `APEXVOL_API_TOKEN` environment variable is set correctly
- Ensure your token hasn't been revoked
- Check that the token starts with `avmcp_`

### "Request timed out"
- Check your internet connection
- The ApexVol platform may be temporarily unavailable

### MCP Server Not Loading
- Restart Claude Code/Desktop after configuration changes
- Check that `apexvol-mcp` is in your PATH
- Verify the configuration JSON syntax is valid

## Development

### Running Locally

```bash
# Install in development mode
pip install -e ".[dev]"

# Run the server directly
python -m apexvol_mcp.server
```

### Running Tests

```bash
pytest tests/
```

## Support

For issues or questions:
- Email: support@apexvol.com
- Documentation: https://apexvol.com/docs/api

## License

MIT — see the `license` field in `pyproject.toml`. The client wrapper is open
source; access to the ApexVol platform itself remains gated by your API token and
subscription.
