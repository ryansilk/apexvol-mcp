"""
ApexVol API Client

HTTP client for calling ApexVol REST API endpoints.
Handles authentication, connection reuse, and error handling.
"""

import contextvars
import os
import logging
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# Per-request bearer token for multi-user hosting. The stdio (single-user)
# server never sets this and falls back to the env token, so published 0.1.x
# behavior is unchanged. The hosted resource server sets it per MCP request
# via set_request_token(); ContextVars propagate into asyncio tasks, so
# concurrent sessions can't see each other's credentials.
_request_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'apexvol_request_token', default=None
)


def set_request_token(token: str) -> contextvars.Token:
    """Bind the current request's API token. Returns a reset handle."""
    return _request_token.set(token)


def reset_request_token(ctx_token: contextvars.Token) -> None:
    """Unbind the request token (call from a finally block)."""
    _request_token.reset(ctx_token)

# Client version, sent on every request as X-ApexVol-Client so the server can
# warn/refuse outdated installs after a breaking API change. If the version
# can't be determined, omit the header entirely — sending a bogus value would
# trip the server's minimum-version gate and lock the client out.
try:
    from apexvol_mcp import __version__ as CLIENT_VERSION
except Exception:
    CLIENT_VERSION = None

# Default timeout for API requests (seconds). Complex analytics endpoints
# (multi-expiration chains, scans, backtests) can take tens of seconds
# server-side.
DEFAULT_TIMEOUT = 120.0

# Fallback error messages when the response body carries no 'error' field
_STATUS_MESSAGES = {
    401: 'Invalid or missing API token',
    403: 'Access forbidden',
    404: 'Resource not found',
    426: 'Client upgrade required',
    429: 'Rate limit exceeded',
    503: 'Service temporarily unavailable',
}


class ApexVolAPIError(Exception):
    """Exception raised for API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ApexVolClient:
    """HTTP client for ApexVol API."""

    def __init__(self):
        self.base_url = os.getenv('APEXVOL_API_URL', 'https://apexvol.com').rstrip('/')
        self.token = os.getenv('APEXVOL_API_TOKEN', '')
        self.timeout = float(os.getenv('APEXVOL_API_TIMEOUT', DEFAULT_TIMEOUT))
        self._http: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        """Non-auth headers baked into the pooled client. Authorization is
        deliberately NOT here: the pooled AsyncClient outlives requests, and
        a token frozen into its defaults would leak across users on a
        multi-user host. Auth travels per-call via _auth_headers()."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if CLIENT_VERSION:
            headers['X-ApexVol-Client'] = CLIENT_VERSION
        return headers

    def _auth_headers(self) -> Dict[str, str]:
        """Per-call Authorization: the request-scoped token when set (hosted
        multi-user server), else the env token (stdio single-user)."""
        token = _request_token.get() or self.token
        if not token:
            raise ApexVolAPIError('Invalid or missing API token', 401)
        return {'Authorization': f'Bearer {token}'}

    def _get_http(self) -> httpx.AsyncClient:
        """Shared AsyncClient so the TCP+TLS connection is reused across tool
        calls instead of paying a full handshake per request."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._get_headers(),
            )
        return self._http

    async def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and errors.

        Prefers the server's own 'error' message on failures — tier, budget,
        rate-limit, and outage responses all explain themselves in the body,
        and a generic "Server error" would hide that from the user.
        """
        try:
            payload = response.json()
        except Exception:
            payload = None

        if response.status_code >= 400:
            server_msg = payload.get('error') if isinstance(payload, dict) else None
            fallback = _STATUS_MESSAGES.get(
                response.status_code,
                'Server error' if response.status_code >= 500 else 'Request failed',
            )
            raise ApexVolAPIError(server_msg or fallback, response.status_code)

        if not isinstance(payload, dict):
            raise ApexVolAPIError('Invalid JSON response')

        if not payload.get('success', False):
            raise ApexVolAPIError(payload.get('error', 'Unknown error'))

        return payload.get('data', {})

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        url = f"{self.base_url}/api/mcp/data{endpoint}"
        try:
            response = await self._get_http().get(url, params=params,
                                                  headers=self._auth_headers())
            return await self._handle_response(response)
        except httpx.TimeoutException:
            raise ApexVolAPIError("Request timed out")
        except httpx.RequestError as e:
            raise ApexVolAPIError(f"Request failed: {str(e)}")

    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request to API."""
        url = f"{self.base_url}/api/mcp/data{endpoint}"
        try:
            response = await self._get_http().post(url, json=data or {},
                                                   headers=self._auth_headers())
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
