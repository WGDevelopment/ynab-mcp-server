# YNAB MCP Server - Claude Code Context

## Project Overview

A minimal, auditable MCP (Model Context Protocol) server for YNAB budget management. Designed for local AI assistants that need to read and modify YNAB budgets while keeping sensitive financial context local.

## Architecture

```
src/ynab_mcp_server/
  __init__.py     # Package initialization
  api.py          # YNAB API client (~300 lines, all network communication)
  models.py       # Pydantic models for YNAB data structures
  server.py       # MCP server implementation with tool handlers
```

### Key Components

- **api.py**: All YNAB API communication goes through here. Single endpoint: `https://api.ynab.com/v1`
- **server.py**: MCP tool definitions and handlers. Entry point via `ynab-mcp run`
- **models.py**: Type-safe Pydantic models for budgets, accounts, categories, transactions

## Security Considerations

### Token Handling
- YNAB Personal Access Token stored in OS keyring (recommended) or environment variable
- Token retrieved at runtime via `keyring` library or `YNAB_API_TOKEN` env var
- **NEVER log tokens** - audit api.py for any logging statements

### Data Flow
- Local: User goals, AI coaching responses, conversation history, life context
- To YNAB API: Only structured API calls (get categories, create transaction, etc.)

### Audit Points
When reviewing changes, check:
1. `api.py` - All network calls, ensure no token leakage
2. Error handlers - Should not expose sensitive data
3. Logging statements - Should not include tokens or financial details

## Development

### Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install with dev dependencies
pip install -e .[dev]
```

### Testing
```bash
pytest -v
pytest --cov=src/ynab_mcp_server  # with coverage
```

### Linting
```bash
pip install ruff
ruff check src/
ruff format src/
```

## CI/CD

Comprehensive quality gates run on all PRs:

1. **Tests**: Python 3.10, 3.11, 3.12 matrix with coverage
2. **Semgrep**: SAST scanning (security-audit, OWASP, Python, secrets)
3. **pip-audit**: Dependency vulnerability scanning
4. **Linting**: Ruff + Super-Linter (YAML, Markdown, Shell)
5. **Type Checking**: mypy
6. **Claude Review**: AI code review after all gates pass

Security philosophy: **Fail closed** - if we can't confirm safe, fail the workflow.

See: [WGDevelopment CI/CD Standards](https://github.com/WGDevelopment/.github/blob/main/CICD-STANDARDS.md)

## MCP Tools

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

## Common Tasks

### Adding a New MCP Tool
1. Define Pydantic model in `models.py` if needed
2. Add API method in `api.py`
3. Create tool handler in `server.py`
4. Add tests

### Updating Dependencies
- Production deps: Check for YNAB API compatibility
- Dev deps: Generally safe to update

## Files to Never Commit
- `.env` files (may contain YNAB_API_TOKEN)
- Any credential files
- Personal keyring exports
