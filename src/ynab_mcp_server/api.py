"""
YNAB API Client - Handles all communication with YNAB's API.

SECURITY AUDIT NOTES:
- All requests go ONLY to api.ynab.com
- Token is retrieved from OS keyring or environment variable
- Token is NEVER logged, printed, or sent elsewhere
- All responses are returned as-is from YNAB's API

YNAB API Documentation: https://api.ynab.com/
"""

import os
from typing import Optional, Dict, Any, List

import httpx

# ============================================================================
# CONFIGURATION - The only external endpoint this code contacts
# ============================================================================

YNAB_API_BASE = "https://api.ynab.com/v1"
REQUEST_TIMEOUT = 30.0  # seconds


# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

def get_token() -> str:
    """
    Retrieve YNAB API token from secure storage.
    
    Priority:
    1. Environment variable YNAB_API_TOKEN
    2. OS keyring (if keyring package available)
    
    Raises:
        ValueError: If no token is found
    """
    # First, check environment variable
    token = os.environ.get("YNAB_API_TOKEN")
    if token:
        return token
    
    # Try keyring if available
    try:
        import keyring
        token = keyring.get_password("ynab-mcp-server", "api_token")
        if token:
            return token
    except ImportError:
        pass  # keyring not installed
    except Exception:
        pass  # keyring error (e.g., no backend)
    
    raise ValueError(
        "YNAB API token not found. Set YNAB_API_TOKEN environment variable "
        "or run 'ynab-mcp store-token' to save it securely."
    )


def store_token(token: str) -> bool:
    """
    Store YNAB API token in OS keyring.
    
    Args:
        token: The YNAB Personal Access Token
        
    Returns:
        True if stored successfully, False otherwise
    """
    try:
        import keyring
        keyring.set_password("ynab-mcp-server", "api_token", token)
        return True
    except ImportError:
        print("Error: keyring package not installed. Install with: pip install keyring")
        return False
    except Exception as e:
        print(f"Error storing token: {e}")
        return False


# ============================================================================
# API CLIENT
# ============================================================================

class YNABClient:
    """
    Async client for YNAB API.
    
    All methods in this class:
    - Only contact api.ynab.com
    - Return raw API responses (no modification)
    - Handle errors consistently
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize YNAB client.
        
        Args:
            token: Optional API token. If not provided, retrieved from secure storage.
        """
        self._token = token or get_token()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=YNAB_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make API request to YNAB.
        
        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint (e.g., "/budgets")
            data: Request body for POST/PATCH
            params: Query parameters
            
        Returns:
            JSON response from YNAB API
            
        Raises:
            YNABAPIError: On API errors
        """
        client = await self._get_client()
        
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                if "error" in error_data:
                    error_detail = error_data["error"].get("detail", "")
            except Exception:
                pass
            
            if e.response.status_code == 401:
                raise YNABAPIError("Invalid or expired API token. Please update your token.")
            elif e.response.status_code == 403:
                raise YNABAPIError(f"Permission denied: {error_detail}")
            elif e.response.status_code == 404:
                raise YNABAPIError(f"Resource not found: {error_detail}")
            elif e.response.status_code == 429:
                raise YNABAPIError("Rate limit exceeded. Please wait before making more requests.")
            else:
                raise YNABAPIError(f"API error {e.response.status_code}: {error_detail}")
                
        except httpx.TimeoutException:
            raise YNABAPIError("Request timed out. Please try again.")
        except httpx.RequestError as e:
            raise YNABAPIError(f"Network error: {str(e)}")
    
    # ========================================================================
    # BUDGET OPERATIONS
    # ========================================================================
    
    async def get_budgets(self) -> List[Dict[str, Any]]:
        """Get all budgets for the authenticated user."""
        response = await self._request("GET", "/budgets")
        return response["data"]["budgets"]

    async def get_budget(self, budget_id: str) -> Dict[str, Any]:
        """Get a single budget by ID."""
        response = await self._request("GET", f"/budgets/{budget_id}")
        return response["data"]["budget"]
    
    # ========================================================================
    # ACCOUNT OPERATIONS
    # ========================================================================
    
    async def get_accounts(self, budget_id: str) -> List[Dict[str, Any]]:
        """Get all accounts for a budget."""
        response = await self._request("GET", f"/budgets/{budget_id}/accounts")
        return response["data"]["accounts"]
    
    async def get_account(self, budget_id: str, account_id: str) -> Dict[str, Any]:
        """Get a single account by ID."""
        response = await self._request("GET", f"/budgets/{budget_id}/accounts/{account_id}")
        return response["data"]["account"]
    
    # ========================================================================
    # CATEGORY OPERATIONS
    # ========================================================================
    
    async def get_categories(self, budget_id: str) -> List[Dict[str, Any]]:
        """Get all category groups and categories for a budget."""
        response = await self._request("GET", f"/budgets/{budget_id}/categories")
        return response["data"]["category_groups"]
    
    async def get_category(self, budget_id: str, category_id: str) -> Dict[str, Any]:
        """Get a single category by ID."""
        response = await self._request("GET", f"/budgets/{budget_id}/categories/{category_id}")
        return response["data"]["category"]

    async def update_category_budget(
        self, 
        budget_id: str, 
        category_id: str, 
        month: str,
        budgeted: int,
    ) -> Dict[str, Any]:
        """Update the budgeted amount for a category in a specific month."""
        response = await self._request(
            "PATCH",
            f"/budgets/{budget_id}/months/{month}/categories/{category_id}",
            data={"category": {"budgeted": budgeted}},
        )
        return response["data"]["category"]
    
    # ========================================================================
    # TRANSACTION OPERATIONS
    # ========================================================================
    
    async def get_transactions(
        self, 
        budget_id: str,
        since_date: Optional[str] = None,
        account_id: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get transactions for a budget."""
        params = {}
        if since_date:
            params["since_date"] = since_date
            
        if account_id:
            endpoint = f"/budgets/{budget_id}/accounts/{account_id}/transactions"
        elif category_id:
            endpoint = f"/budgets/{budget_id}/categories/{category_id}/transactions"
        else:
            endpoint = f"/budgets/{budget_id}/transactions"
        
        response = await self._request("GET", endpoint, params=params)
        return response["data"]["transactions"]

    async def create_transaction(
        self,
        budget_id: str,
        account_id: str,
        amount: int,
        date: str,
        payee_name: Optional[str] = None,
        payee_id: Optional[str] = None,
        category_id: Optional[str] = None,
        memo: Optional[str] = None,
        cleared: str = "uncleared",
        approved: bool = False,
    ) -> Dict[str, Any]:
        """Create a new transaction."""
        transaction = {
            "account_id": account_id,
            "date": date,
            "amount": amount,
            "cleared": cleared,
            "approved": approved,
        }
        
        if payee_name:
            transaction["payee_name"] = payee_name
        if payee_id:
            transaction["payee_id"] = payee_id
        if category_id:
            transaction["category_id"] = category_id
        if memo:
            transaction["memo"] = memo
        
        response = await self._request(
            "POST",
            f"/budgets/{budget_id}/transactions",
            data={"transaction": transaction},
        )
        return response["data"]["transaction"]

    async def update_transaction(
        self,
        budget_id: str,
        transaction_id: str,
        **updates,
    ) -> Dict[str, Any]:
        """Update an existing transaction."""
        response = await self._request(
            "PATCH",
            f"/budgets/{budget_id}/transactions/{transaction_id}",
            data={"transaction": updates},
        )
        return response["data"]["transaction"]
    
    # ========================================================================
    # PAYEE OPERATIONS
    # ========================================================================
    
    async def get_payees(self, budget_id: str) -> List[Dict[str, Any]]:
        """Get all payees for a budget."""
        response = await self._request("GET", f"/budgets/{budget_id}/payees")
        return response["data"]["payees"]
    
    # ========================================================================
    # MONTH OPERATIONS
    # ========================================================================
    
    async def get_budget_month(self, budget_id: str, month: str) -> Dict[str, Any]:
        """Get budget month details including all category balances."""
        response = await self._request("GET", f"/budgets/{budget_id}/months/{month}")
        return response["data"]["month"]


class YNABAPIError(Exception):
    """Exception raised for YNAB API errors."""
    pass
