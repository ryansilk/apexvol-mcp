# ApexVol MCP Server

[![PyPI](https://img.shields.io/pypi/v/apexvol-mcp)](https://pypi.org/project/apexvol-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/apexvol-mcp)](https://pypi.org/project/apexvol-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Model Context Protocol (MCP) server that gives AI assistants live access to ApexVol's options analytics platform: options chains, IV rank, volatility risk premium, Greeks, gamma exposure (GEX), expected moves, strategy building, and market screening. **43 tools**, one connector.

Works with Claude Code, Claude Desktop, claude.ai (remote connector — no install), and any MCP-compatible client.

- **Setup guide (step by step):** https://apexvol.com/learn/claude-options-data-mcp
- **REST API docs:** https://apexvol.com/docs/api
- **Single-file API reference, sized for LLM context windows:** https://apexvol.com/docs/api/apexvol-api.md

## Quickstart

### Option A — Remote connector (no install)

Add a custom connector in claude.ai or Claude Desktop (**Settings → Connectors → Add custom connector**) with this URL:

```
https://apexvol.com/mcp-server
```

Sign in with your ApexVol account when prompted (OAuth). That's it — no Python, no config files.

Claude Code can use the remote server too:

```bash
claude mcp add --transport http apexvol https://apexvol.com/mcp-server
```

then authenticate when prompted (the `/mcp` command shows login state).

### Option B — Local install (stdio)

```bash
pipx install apexvol-mcp
claude mcp add apexvol -e APEXVOL_API_TOKEN=avmcp_YOUR_TOKEN_HERE -- apexvol-mcp
```

**Access requires any paid ApexVol plan (from $55/mo).** Every tool returns the same data tier your web plan includes; Pro unlocks the full toolset. Tokens are self-served at **apexvol.com/account → API Access**.

## Example session

Real output, 2026-08-15:

> **You:** What's the IV rank for SPY?
>
> **Claude** calls `get_iv_rank("SPY")`:
>
> | Metric | Value |
> |--------|-------|
> | Current IV | 12.3% |
> | IV Rank | 7.8 |
> | IV Percentile | 8.3% |
> | 52-Week Low | 11.2% |
> | 52-Week High | 25.0% |
>
> **Assessment**: LOW — consider buying premium rather than selling it.

Follow-ups like "so is a calendar spread better than an iron condor here?" work because Claude can pull the term structure, build both strategies, and compare the Greeks — in the same conversation.

## Architecture

```
Remote (no install)
┌─────────────────────────┐            ┌──────────────────────────────┐
│ claude.ai / Desktop /   │── OAuth ──▶│ https://apexvol.com/mcp-server│
│ Claude Code (HTTP)      │            │ (streamable HTTP)             │
└─────────────────────────┘            └──────────────────────────────┘

Local (stdio)
┌─────────────────────┐               ┌─────────────────────┐
│ Claude Code/Desktop │               │ apexvol.com         │
│         │           │               │                     │
│         ▼           │               │                     │
│   ApexVol MCP       │──── HTTPS ───▶│  /api/mcp/data/...  │
│   (runs locally)    │               │                     │
└─────────────────────┘               └─────────────────────┘
```

The local server runs on your machine and calls the ApexVol platform API. The remote server is the same toolset hosted by ApexVol, authenticated with OAuth instead of a token.

## Features

- **43 Analytics Tools** — every `/api/mcp/data` endpoint is reachable from Claude
- **Natural Language Interface** - Ask questions like "What's the IV rank for SPY?"
- **Remote or local** - hosted OAuth connector, or a pipx-installed stdio server
- **Token Authentication** - Secure API token validation (local mode)
- **Built-in health check** - `apexvol-mcp --check` verifies your install and token

## Available Tools

### Options Chain (6 tools)
- `get_options_chain` - Full options chain for any ticker
- `get_expirations` - Available expiration dates
- `get_options_by_delta` - Find options at specific delta
- `get_stock_price` - Current price and company info
- `calculate_expected_move` - Expected move from straddle pricing
- `get_historical_chain` - Chain snapshot on any past trading day

### Volatility Analysis (7 tools)
- `get_iv_rank` - IV rank and percentile
- `get_volatility_cone` - IV vs historical realized volatility
- `get_volatility_risk_premium` - VRP (IV minus RV)
- `get_term_structure` - IV across expirations
- `find_iv_opportunities` - Mean reversion opportunities
- `get_vix_snapshot` - VIX level and term-structure state
- `get_monies_surface` - Smoothed vol surface: implied, forecast, or model-vs-market comparison

### Greeks & GEX (5 tools)
- `get_gex` - Gamma Exposure by strike
- `get_charm_exposure` - Delta decay exposure
- `get_third_order_greeks` - Speed, zomma, color, vomma, ultima
- `get_greeks_heatmap` - Greeks across strikes and expirations
- `get_cross_index_gex` - Compare GEX across indices

### Options Flow (3 tools)
- `get_options_flow` - Flow and unusual activity ⚠️ *temporarily unavailable — upstream feed lacks reliable intraday volume; the tool says so instead of returning zeros*
- `get_smart_money_flow` - Institutional flow patterns ⚠️ *same limitation as above*
- `scan_volatility_arb` - Cross-index volatility arbitrage

### Strategy Building (5 tools)
- `build_strategy` - Build options strategies (iron condor, spreads, etc.)
- `analyze_strategy` - Full P&L and Greeks analysis
- `optimize_strategy` - Find optimal strikes
- `simulate_option_chain` - Black-Scholes what-if re-pricing (price/DTE/IV shift)
- `calculate_probability_of_profit` - PoP for any set of legs

### Risk Management (4 tools)
- `calculate_portfolio_greeks` - Aggregate portfolio Greeks
- `run_scenario_analysis` - What-if scenarios
- `generate_stress_tests` - Stress test results
- `get_hedge_recommendations` - Delta-hedge suggestions (stock + option legs)

Positions are passed as a JSON array (ticker, position_type, quantity, strike,
expiration, Greeks) — pull option Greeks from `get_options_chain` first. Plain
text ("AAPL 100 shares") works for stock-only portfolios.

### Events & Screening (5 tools)
- `get_earnings_calendar` - Upcoming earnings
- `analyze_earnings_history` - Historical earnings moves
- `screen_market` - Market screening (high IV, unusual volume, etc.)
- `get_market_overview` - Market-wide volatility overview
- `get_economic_calendar` - Macro events (CPI, FOMC, jobs...)

### Ticker Analytics (8 tools)
- `get_ticker_analytics` - One tool, eight views: `skew`, `dividends`,
  `borrow_rate`, `correlation`, `hv_regimes`, `price_context`,
  `relative_value`, `greeks_exposure`
- `get_earnings_move_analysis` - seven views: `mispricing`, `historical_moves`,
  `expected_vs_actual`, `verdict`, `seasonality`, `post_drift`, `iv_crush`
- `get_max_pain` - Max pain strike and loss profile
- `get_volume_profile` - Volume/OI by strike with OI-implied support/resistance
- `get_zero_dte` - 0DTE gamma, flip level, max pain, theta decay (SPY/QQQ/SPX…)
- `get_orats_cores` - Raw vendor cores row (340+ fields) with field selection
- `search_tickers` - Resolve names to symbols / check coverage
- `scan_relative_value` - Market-wide IV/SPY mean-reversion and pairs scans

## Installation (local mode, in detail)

### Prerequisites

- Python 3.10+
- Any paid ApexVol plan and an API token (see "Getting a Token" below)

### Install the Package

We recommend [pipx](https://pipx.pypa.io) so the `apexvol-mcp` command is
isolated and always on your PATH:

```bash
pipx install apexvol-mcp
```

Plain `pip install apexvol-mcp` also works.

Or install from source:

```bash
git clone https://github.com/ryansilk/apexvol-mcp.git
cd apexvol-mcp
pip install -e .
```

### Verify the install

Before touching any Claude config, confirm the command works and your token
authenticates:

```bash
APEXVOL_API_TOKEN=avmcp_YOUR_TOKEN_HERE apexvol-mcp --check
```

`--check` prints the client version, auth result, and your remaining
rate-limit/monthly budget. If it says OK, the only step left is wiring it
into Claude.

## Configuration

### Claude Code (CLI)

One command:

```bash
claude mcp add apexvol -e APEXVOL_API_TOKEN=avmcp_YOUR_TOKEN_HERE -- apexvol-mcp
```

Or add to your project's `.mcp.json` or global `~/.claude.json` by hand:

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

(Claude Desktop also supports the remote connector under Settings → Connectors — see Quickstart Option A.)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APEXVOL_API_TOKEN` | Yes | Your ApexVol API token |
| `APEXVOL_API_URL` | No | API URL (default: https://apexvol.com) |

### Rate limits

60 requests/min, 1,000/hour, 10,000/month per account — shared across local
and remote modes. `apexvol-mcp --check` shows your remaining budget.

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

## Agent Skill

The repo ships an [Agent Skill](skills/options-analysis/SKILL.md) that
teaches an AI assistant how to combine these tools into complete analyses —
rich/cheap volatility assessment, earnings setups, premium-selling screens,
GEX regime reads, and strategy stress-testing — with interpretation
thresholds and error handling.

To use it with Claude Code, copy the skill into your skills directory:

```bash
mkdir -p ~/.claude/skills/options-analysis
curl -o ~/.claude/skills/options-analysis/SKILL.md \
  https://raw.githubusercontent.com/ryansilk/apexvol-mcp/main/skills/options-analysis/SKILL.md
```

Claude then loads it automatically whenever an options-analysis question
comes up (the MCP server itself must also be connected).

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

Local mode uses token-based authentication; the remote connector uses OAuth
(sign in with your ApexVol account, no token handling at all).

### Token Format
- Prefix: `avmcp_`
- Length: 38 characters total

### Getting a Token

API and MCP access are included with **every paid ApexVol plan** (Basic
$55/mo, Premium, Pro). Each tool returns the same data tier your web plan
includes; Pro unlocks the full toolset.

1. Create and manage tokens at **apexvol.com/account → API Access** —
   issuance, rotation, and revocation are all self-service.
2. Questions or issues: **support@apexvol.com**.

The token is sent with every request, so treat it like a password. If it
leaks, revoke it on the account page and create a new one.

## Troubleshooting

**Start with the health check** — it diagnoses most issues in one shot:

```bash
APEXVOL_API_TOKEN=avmcp_YOUR_TOKEN_HERE apexvol-mcp --check
```

### "Invalid or missing API token"
- Verify your `APEXVOL_API_TOKEN` environment variable is set correctly
- Ensure your token hasn't been revoked (check apexvol.com/account → API Access)
- Check that the token starts with `avmcp_`

### "Request timed out"
- Check your internet connection
- The ApexVol platform may be temporarily unavailable

### MCP Server Not Loading
- Restart Claude Code/Desktop after configuration changes
- Check that `apexvol-mcp` is in your PATH (`which apexvol-mcp`; pipx installs handle this automatically)
- Verify the configuration JSON syntax is valid

### Remote connector won't authorize
- Confirm your ApexVol account has an active paid plan, then remove and
  re-add the connector
- The connector URL is exactly `https://apexvol.com/mcp-server` (no trailing slash)

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
- Setup guide: https://apexvol.com/learn/claude-options-data-mcp

## License

MIT — see [LICENSE](LICENSE). The client is open source; access to the
ApexVol platform itself remains gated by your subscription.

<!-- mcp-name: io.github.ryansilk/apexvol-mcp -->
