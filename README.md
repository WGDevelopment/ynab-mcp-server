# YNAB MCP Server

A minimal, auditable MCP (Model Context Protocol) server for YNAB budget management. Designed for local AI assistants that need to read and modify YNAB budgets.

## Why This Exists

Use a local LLM for financial coaching while keeping sensitive context (goals, reasoning, life circumstances) off cloud servers. Only structured API commands go to YNAB.

## Features

- **Read**: Budgets, accounts, categories, transactions, payees
- **Write**: Create transactions, move money between categories
- **Secure**: Token stored in OS keyring, never logged or transmitted elsewhere

## Installation

```bash
git clone https://github.com/wg-whm/ynab-mcp-server.git
cd ynab-mcp-server
pip install .
```

Or with uv:
```bash
uv pip install .
```

## Setup

1. Get a YNAB Personal Access Token at https://app.youneedabudget.com/settings/developer

2. Store the token:
```bash
# Option A: OS keyring (recommended)
ynab-mcp store-token

# Option B: Environment variable
export YNAB_API_TOKEN="your-token-here"
```

3. Verify:
```bash
ynab-mcp check-token
```

## Usage

### With Claude Code / MCP Clients

Add to your MCP config:
```json
{
  "mcpServers": {
    "ynab": {
      "command": "ynab-mcp"
    }
  }
}
```

### Direct

```bash
ynab-mcp run
```

## Available Tools

| Tool | Description | Modifies Data |
|------|-------------|---------------|
| `ynab_get_budgets` | List all budgets | No |
| `ynab_get_accounts` | List accounts with balances | No |
| `ynab_get_categories` | List categories with budgeted/spent/available | No |
| `ynab_get_transactions` | List transactions (filterable) | No |
| `ynab_get_month_summary` | Month overview with overspent warnings | No |
| `ynab_get_payees` | List all payees | No |
| `ynab_move_money` | Move money between categories | **Yes** |
| `ynab_create_transaction` | Create new transaction | **Yes** |
| `ynab_update_transaction` | Update existing transaction | **Yes** |

## Security

**What stays local:**
- Your goals and motivations
- AI coaching responses
- Conversation history
- Life context you share

**What goes to YNAB API:**
- Structured API calls (get categories, create transaction, etc.)
- Same data YNAB already has

**Audit points:**
- `src/ynab_mcp_server/api.py` - All API communication (~300 lines)
- Only endpoint: `https://api.ynab.com/v1`
- Token retrieved from keyring/env, never logged

## License

MIT
