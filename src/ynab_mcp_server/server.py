"""
YNAB MCP Server - Main entry point.

This file implements the MCP server with all YNAB tools.
Run with: python -m ynab_mcp_server.server

Or via the CLI: ynab-mcp
"""

import sys
import asyncio
from datetime import date
from typing import Optional
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .api import YNABClient, YNABAPIError, store_token, get_token
from .models import (
    GetBudgetsInput,
    GetBudgetInput,
    GetAccountsInput,
    GetAccountInput,
    GetCategoriesInput,
    GetCategoryInput,
    MoveMoneyCategoryInput,
    SetCategoryBudgetInput,
    GetTransactionsInput,
    CreateTransactionInput,
    UpdateTransactionInput,
    GetMonthSummaryInput,
    GetPayeesInput,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def dollars_to_milliunits(dollars: float) -> int:
    """Convert dollars to YNAB milliunits (1000 milliunits = $1.00)."""
    return int(round(dollars * 1000))


def milliunits_to_dollars(milliunits: int) -> float:
    """Convert YNAB milliunits to dollars."""
    return milliunits / 1000


def format_currency(milliunits: int) -> str:
    """Format milliunits as currency string."""
    dollars = milliunits_to_dollars(milliunits)
    return f"${dollars:,.2f}"


def get_current_month() -> str:
    """Get current month in YNAB format (YYYY-MM-01)."""
    today = date.today()
    return f"{today.year}-{today.month:02d}-01"


def format_error(e: Exception) -> str:
    """Format error for consistent error responses."""
    if isinstance(e, YNABAPIError):
        return f"Error: {str(e)}"
    return f"Error: Unexpected error - {type(e).__name__}: {str(e)}"


# ============================================================================
# MCP SERVER SETUP
# ============================================================================

@asynccontextmanager
async def lifespan(server):
    """Manage YNAB client lifecycle."""
    client = YNABClient()
    yield {"client": client}
    await client.close()


mcp = FastMCP("ynab_mcp", lifespan=lifespan)


# ============================================================================
# BUDGET TOOLS
# ============================================================================

@mcp.tool(
    name="ynab_get_budgets",
    annotations={
        "title": "List YNAB Budgets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_get_budgets(params: GetBudgetsInput) -> str:
    """List all budgets available to the authenticated user."""
    try:
        async with YNABClient() as client:
            budgets = await client.get_budgets()
        
        result = "## Your YNAB Budgets\n\n"
        for b in budgets:
            result += f"- **{b['name']}**\n"
            result += f"  - ID: `{b['id']}`\n"
            result += f"  - Last modified: {b.get('last_modified_on', 'N/A')}\n\n"
        
        return result
    except Exception as e:
        return format_error(e)


@mcp.tool(
    name="ynab_get_accounts",
    annotations={
        "title": "List Accounts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_get_accounts(params: GetAccountsInput) -> str:
    """List all accounts in a budget with their current balances."""
    try:
        async with YNABClient() as client:
            accounts = await client.get_accounts(params.budget_id)
        
        by_type = {}
        for a in accounts:
            if a.get("deleted") or a.get("closed"):
                continue
            atype = a.get("type", "other")
            if atype not in by_type:
                by_type[atype] = []
            by_type[atype].append(a)
        
        result = "## Accounts\n\n"
        total_balance = 0
        
        for atype, accts in by_type.items():
            result += f"### {atype.replace('_', ' ').title()}\n\n"
            for a in accts:
                balance = a.get("balance", 0)
                total_balance += balance
                result += f"- **{a['name']}**: {format_currency(balance)}\n"
                result += f"  - ID: `{a['id']}`\n"
            result += "\n"
        
        result += f"**Total Balance: {format_currency(total_balance)}**\n"
        return result
    except Exception as e:
        return format_error(e)


# ============================================================================
# CATEGORY TOOLS
# ============================================================================

@mcp.tool(
    name="ynab_get_categories",
    annotations={
        "title": "List Categories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_get_categories(params: GetCategoriesInput) -> str:
    """List all category groups and categories with budgeted amounts and balances."""
    try:
        async with YNABClient() as client:
            category_groups = await client.get_categories(params.budget_id)
        
        result = "## Budget Categories\n\n"
        
        for group in category_groups:
            if group.get("hidden") or group.get("deleted"):
                continue
            if group["name"] in ["Internal Master Category", "Credit Card Payments"]:
                continue
                
            result += f"### {group['name']}\n\n"
            result += "| Category | Budgeted | Spent | Available |\n"
            result += "|----------|----------|-------|----------|\n"
            
            for cat in group.get("categories", []):
                if cat.get("hidden") or cat.get("deleted"):
                    continue
                    
                budgeted = format_currency(cat.get("budgeted", 0))
                activity = format_currency(cat.get("activity", 0))
                balance = format_currency(cat.get("balance", 0))
                
                result += f"| {cat['name']} | {budgeted} | {activity} | {balance} |\n"
                result += f"| ↳ ID: `{cat['id']}` | | | |\n"
            
            result += "\n"
        
        return result
    except Exception as e:
        return format_error(e)


@mcp.tool(
    name="ynab_move_money",
    annotations={
        "title": "Move Money Between Categories",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def ynab_move_money(params: MoveMoneyCategoryInput) -> str:
    """Move money from one category to another."""
    try:
        month = params.month or get_current_month()
        amount_milliunits = dollars_to_milliunits(params.amount)
        
        async with YNABClient() as client:
            from_cat = await client.get_category(params.budget_id, params.from_category_id)
            to_cat = await client.get_category(params.budget_id, params.to_category_id)
            
            from_budgeted = from_cat.get("budgeted", 0)
            to_budgeted = to_cat.get("budgeted", 0)
            
            if from_budgeted < amount_milliunits:
                return (
                    f"Error: {from_cat['name']} only has {format_currency(from_budgeted)} budgeted. "
                    f"Cannot move {format_currency(amount_milliunits)}."
                )
            
            new_from = from_budgeted - amount_milliunits
            new_to = to_budgeted + amount_milliunits

            await client.update_category_budget(
                params.budget_id, params.from_category_id, month, new_from
            )
            await client.update_category_budget(
                params.budget_id, params.to_category_id, month, new_to
            )
        
        result = f"## Money Moved Successfully\n\n"
        result += f"**Moved {format_currency(amount_milliunits)}** from {from_cat['name']} to {to_cat['name']}\n\n"
        result += f"| Category | Before | After |\n"
        result += f"|----------|--------|-------|\n"
        result += f"| {from_cat['name']} | {format_currency(from_budgeted)} | {format_currency(new_from)} |\n"
        result += f"| {to_cat['name']} | {format_currency(to_budgeted)} | {format_currency(new_to)} |\n"
        
        return result
    except Exception as e:
        return format_error(e)


# ============================================================================
# TRANSACTION TOOLS
# ============================================================================

@mcp.tool(
    name="ynab_get_transactions",
    annotations={
        "title": "List Transactions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_get_transactions(params: GetTransactionsInput) -> str:
    """List recent transactions, optionally filtered by date, account, or category."""
    try:
        async with YNABClient() as client:
            transactions = await client.get_transactions(
                params.budget_id,
                since_date=params.since_date,
                account_id=params.account_id,
                category_id=params.category_id,
            )
        
        transactions = transactions[:params.limit]
        
        if not transactions:
            return "No transactions found matching the criteria."
        
        result = "## Transactions\n\n"
        result += "| Date | Payee | Category | Amount | Status |\n"
        result += "|------|-------|----------|--------|--------|\n"
        
        total = 0
        for t in transactions:
            date_str = t.get("date", "N/A")
            payee = t.get("payee_name", "Unknown")[:30]
            category = t.get("category_name", "Uncategorized")[:25]
            amount = t.get("amount", 0)
            total += amount
            
            status = "✓" if t.get("cleared") == "cleared" else "○"
            if t.get("approved"):
                status += "✓"
            
            result += f"| {date_str} | {payee} | {category} | {format_currency(amount)} | {status} |\n"
        
        result += f"\n**Total: {format_currency(total)}** ({len(transactions)} transactions)\n"
        return result
    except Exception as e:
        return format_error(e)


@mcp.tool(
    name="ynab_create_transaction",
    annotations={
        "title": "Create Transaction",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def ynab_create_transaction(params: CreateTransactionInput) -> str:
    """Create a new transaction. Use negative amounts for spending, positive for income."""
    try:
        amount_milliunits = dollars_to_milliunits(params.amount)
        
        async with YNABClient() as client:
            transaction = await client.create_transaction(
                budget_id=params.budget_id,
                account_id=params.account_id,
                amount=amount_milliunits,
                date=params.date,
                payee_name=params.payee_name,
                category_id=params.category_id,
                memo=params.memo,
                cleared=params.cleared.value,
                approved=params.approved,
            )
        
        result = "## Transaction Created\n\n"
        result += f"- **ID**: `{transaction['id']}`\n"
        result += f"- **Date**: {transaction['date']}\n"
        result += f"- **Amount**: {format_currency(transaction['amount'])}\n"
        result += f"- **Payee**: {transaction.get('payee_name', 'N/A')}\n"
        result += f"- **Category**: {transaction.get('category_name', 'Uncategorized')}\n"
        if params.memo:
            result += f"- **Memo**: {params.memo}\n"
        
        return result
    except Exception as e:
        return format_error(e)


@mcp.tool(
    name="ynab_update_transaction",
    annotations={
        "title": "Update Transaction",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_update_transaction(params: UpdateTransactionInput) -> str:
    """Update an existing transaction. Only specified fields will be updated."""
    try:
        updates = {}
        
        if params.amount is not None:
            updates["amount"] = dollars_to_milliunits(params.amount)
        if params.date is not None:
            updates["date"] = params.date
        if params.payee_name is not None:
            updates["payee_name"] = params.payee_name
        if params.category_id is not None:
            updates["category_id"] = params.category_id
        if params.memo is not None:
            updates["memo"] = params.memo
        if params.cleared is not None:
            updates["cleared"] = params.cleared.value
        if params.approved is not None:
            updates["approved"] = params.approved
        
        if not updates:
            return "Error: No fields to update. Specify at least one field to change."
        
        async with YNABClient() as client:
            transaction = await client.update_transaction(
                params.budget_id,
                params.transaction_id,
                **updates,
            )
        
        result = "## Transaction Updated\n\n"
        result += f"- **ID**: `{transaction['id']}`\n"
        result += f"- **Date**: {transaction['date']}\n"
        result += f"- **Amount**: {format_currency(transaction['amount'])}\n"
        result += f"- **Payee**: {transaction.get('payee_name', 'N/A')}\n"
        
        return result
    except Exception as e:
        return format_error(e)


# ============================================================================
# ANALYSIS TOOLS
# ============================================================================

@mcp.tool(
    name="ynab_get_month_summary",
    annotations={
        "title": "Get Month Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_get_month_summary(params: GetMonthSummaryInput) -> str:
    """Get a summary of a budget month including income, budgeted amounts, and spending."""
    try:
        month = params.month or "current"
        
        async with YNABClient() as client:
            month_data = await client.get_budget_month(params.budget_id, month)
        
        result = f"## Budget Summary for {month_data.get('month', month)}\n\n"
        
        income = month_data.get("income", 0)
        budgeted = month_data.get("budgeted", 0)
        activity = month_data.get("activity", 0)
        to_be_budgeted = month_data.get("to_be_budgeted", 0)
        
        result += f"- **Income**: {format_currency(income)}\n"
        result += f"- **Budgeted**: {format_currency(budgeted)}\n"
        result += f"- **Spending (Activity)**: {format_currency(activity)}\n"
        result += f"- **To Be Budgeted**: {format_currency(to_be_budgeted)}\n\n"
        
        categories = month_data.get("categories", [])
        
        overspent = [c for c in categories if c.get("balance", 0) < 0]
        if overspent:
            result += "### ⚠️ Overspent Categories\n\n"
            for c in overspent:
                result += f"- **{c['name']}**: {format_currency(c['balance'])}\n"
            result += "\n"
        
        return result
    except Exception as e:
        return format_error(e)


@mcp.tool(
    name="ynab_get_payees",
    annotations={
        "title": "List Payees",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def ynab_get_payees(params: GetPayeesInput) -> str:
    """List all payees in the budget."""
    try:
        async with YNABClient() as client:
            payees = await client.get_payees(params.budget_id)
        
        payees = [p for p in payees if not p.get("deleted") and not p["name"].startswith("Transfer")]
        payees = sorted(payees, key=lambda p: p["name"].lower())
        
        result = f"## Payees ({len(payees)} total)\n\n"
        
        for p in payees[:100]:
            result += f"- {p['name']} (`{p['id']}`)\n"
        
        if len(payees) > 100:
            result += f"\n*...and {len(payees) - 100} more*\n"
        
        return result
    except Exception as e:
        return format_error(e)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="YNAB MCP Server")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["run", "store-token", "check-token"],
        default="run",
        help="Command to execute (default: run)",
    )
    
    args = parser.parse_args()
    
    if args.command == "store-token":
        print("Enter your YNAB Personal Access Token:")
        print("(Get one at https://app.youneedabudget.com/settings/developer)")
        token = input("> ").strip()
        if token:
            if store_token(token):
                print("✓ Token stored securely in OS keyring.")
            else:
                print("✗ Failed to store token. Set YNAB_API_TOKEN environment variable instead.")
        else:
            print("✗ No token provided.")
        return
    
    if args.command == "check-token":
        try:
            token = get_token()
            print(f"✓ Token found ({len(token)} characters)")
            print(f"  First 8 chars: {token[:8]}...")
        except ValueError as e:
            print(f"✗ {e}")
        return
    
    # Default: run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
