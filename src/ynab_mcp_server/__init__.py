"""
YNAB MCP Server - A minimal, auditable MCP server for YNAB budget management.

This package provides a Model Context Protocol (MCP) server that enables
AI assistants to interact with YNAB (You Need A Budget) for:
- Reading budget and account information
- Creating and managing transactions
- Moving money between categories
- Budget analysis and coaching

Security: Your YNAB API token is stored in your OS keyring and never
sent to any AI provider. Only structured API calls go to YNAB's servers.
"""

__version__ = "0.1.0"
__author__ = "Adam Gemberling"
__license__ = "MIT"
