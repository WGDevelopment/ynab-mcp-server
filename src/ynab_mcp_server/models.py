"""
Pydantic models for MCP tool input validation.

All inputs are validated before being passed to the YNAB API.
"""

from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================================
# COMMON MODELS
# ============================================================================

class BudgetIdInput(BaseModel):
    """Base model with budget_id field."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    budget_id: str = Field(
        default="last-used",
        description="Budget ID or 'last-used' for the most recently accessed budget",
    )


# ============================================================================
# BUDGET TOOLS
# ============================================================================

class GetBudgetsInput(BaseModel):
    """Input for listing all budgets."""
    model_config = ConfigDict(str_strip_whitespace=True)


class GetBudgetInput(BudgetIdInput):
    """Input for getting a specific budget."""
    pass


# ============================================================================
# ACCOUNT TOOLS
# ============================================================================

class GetAccountsInput(BudgetIdInput):
    """Input for listing accounts in a budget."""
    pass


class GetAccountInput(BudgetIdInput):
    """Input for getting a specific account."""
    account_id: str = Field(..., description="The account ID")


# ============================================================================
# CATEGORY TOOLS
# ============================================================================

class GetCategoriesInput(BudgetIdInput):
    """Input for listing all categories in a budget."""
    pass


class GetCategoryInput(BudgetIdInput):
    """Input for getting a specific category."""
    category_id: str = Field(..., description="The category ID")


class MoveMoneyCategoryInput(BudgetIdInput):
    """Input for moving money between categories."""
    from_category_id: str = Field(..., description="Category ID to move money FROM")
    to_category_id: str = Field(..., description="Category ID to move money TO")
    amount: float = Field(..., description="Amount in dollars to move (e.g., 50.00)", gt=0)
    month: Optional[str] = Field(
        default=None,
        description="Month in YYYY-MM-DD format (first of month). Defaults to current month.",
        pattern=r"^\d{4}-\d{2}-01$",
    )


class SetCategoryBudgetInput(BudgetIdInput):
    """Input for setting a category's budgeted amount."""
    category_id: str = Field(..., description="The category ID")
    amount: float = Field(..., description="New budgeted amount in dollars (e.g., 500.00)", ge=0)
    month: Optional[str] = Field(
        default=None,
        description="Month in YYYY-MM-DD format (first of month). Defaults to current month.",
        pattern=r"^\d{4}-\d{2}-01$",
    )


# ============================================================================
# TRANSACTION TOOLS
# ============================================================================

class ClearedStatus(str, Enum):
    """Transaction cleared status."""
    CLEARED = "cleared"
    UNCLEARED = "uncleared"
    RECONCILED = "reconciled"


class GetTransactionsInput(BudgetIdInput):
    """Input for listing transactions."""
    since_date: Optional[str] = Field(
        default=None,
        description="Only return transactions on or after this date (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    account_id: Optional[str] = Field(default=None, description="Filter by account ID")
    category_id: Optional[str] = Field(default=None, description="Filter by category ID")
    limit: int = Field(default=50, description="Maximum number of transactions to return", ge=1, le=500)


class CreateTransactionInput(BudgetIdInput):
    """Input for creating a new transaction."""
    account_id: str = Field(..., description="The account ID for the transaction")
    amount: float = Field(
        ..., 
        description="Amount in dollars. Negative for spending, positive for income. E.g., -45.67",
    )
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$")
    payee_name: Optional[str] = Field(default=None, description="Name of the payee", max_length=200)
    category_id: Optional[str] = Field(default=None, description="Category ID for the transaction")
    memo: Optional[str] = Field(default=None, description="Optional memo/note", max_length=500)
    cleared: ClearedStatus = Field(default=ClearedStatus.UNCLEARED, description="Cleared status")
    approved: bool = Field(default=False, description="Whether the transaction is approved")
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Ensure amount has at most 2 decimal places."""
        return round(v, 2)


class UpdateTransactionInput(BudgetIdInput):
    """Input for updating an existing transaction."""
    transaction_id: str = Field(..., description="The transaction ID to update")
    amount: Optional[float] = Field(default=None, description="New amount in dollars")
    date: Optional[str] = Field(default=None, description="New date (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    payee_name: Optional[str] = Field(default=None, description="New payee name", max_length=200)
    category_id: Optional[str] = Field(default=None, description="New category ID")
    memo: Optional[str] = Field(default=None, description="New memo", max_length=500)
    cleared: Optional[ClearedStatus] = Field(default=None, description="New cleared status")
    approved: Optional[bool] = Field(default=None, description="New approved status")


# ============================================================================
# ANALYSIS TOOLS
# ============================================================================

class GetMonthSummaryInput(BudgetIdInput):
    """Input for getting a month's budget summary."""
    month: Optional[str] = Field(default="current", description="Month in YYYY-MM-DD format or 'current'")


class GetPayeesInput(BudgetIdInput):
    """Input for listing all payees."""
    pass
