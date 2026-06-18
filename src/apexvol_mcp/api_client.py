"""
ApexVol API Client

HTTP client for calling ApexVol REST API endpoints.
Handles authentication and error handling.
"""

import os
import logging
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# Client version, sent on every request as X-ApexVol-Client so the server can
# warn/refuse outdated installs after a breaking API change.
try:
    from apexvol_mcp import __version__ as CLIENT_VERSION
except Exception:
    CLIENT_VERSION = "0"

# Default timeout for API requests (seconds)
# Theta Data API calls can take 30-60 seconds for complex queries
DEFAULT_TIMEOUT = 120.0


class ApexVolAPIError(Exception):
    """Exception raised for API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ApexVolClient:
    """HTTP client for ApexVol API."""

    def __init__(self):
        self.base_url = os.getenv('APEXVOL_API_URL', 'https://apexvol.com')
        self.token = os.getenv('APEXVOL_API_TOKEN', '')
        self.timeout = float(os.getenv('APEXVOL_API_TIMEOUT', DEFAULT_TIMEOUT))

        # Remove trailing slash from base URL
        self.base_url = self.base_url.rstrip('/')

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-ApexVol-Client': CLIENT_VERSION,
        }

    async def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and errors."""
        if response.status_code == 401:
            raise ApexVolAPIError("Invalid or missing API token", 401)
        elif response.status_code == 403:
            raise ApexVolAPIError("Access forbidden", 403)
        elif response.status_code == 404:
            raise ApexVolAPIError("Resource not found", 404)
        elif response.status_code >= 500:
            raise ApexVolAPIError("Server error", response.status_code)

        try:
            data = response.json()
        except Exception:
            raise ApexVolAPIError("Invalid JSON response")

        if not data.get('success', False):
            error_msg = data.get('error', 'Unknown error')
            raise ApexVolAPIError(error_msg)

        return data.get('data', {})

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        url = f"{self.base_url}/api/mcp/data{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params
                )
                return await self._handle_response(response)
            except httpx.TimeoutException:
                raise ApexVolAPIError("Request timed out")
            except httpx.RequestError as e:
                raise ApexVolAPIError(f"Request failed: {str(e)}")

    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request to API."""
        url = f"{self.base_url}/api/mcp/data{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=data or {}
                )
                return await self._handle_response(response)
            except httpx.TimeoutException:
                raise ApexVolAPIError("Request timed out")
            except httpx.RequestError as e:
                raise ApexVolAPIError(f"Request failed: {str(e)}")


# Global client instance
_client: Optional[ApexVolClient] = None


def get_client() -> ApexVolClient:
    """Get or create the API client instance."""
    global _client
    if _client is None:
        _client = ApexVolClient()
    return _client
