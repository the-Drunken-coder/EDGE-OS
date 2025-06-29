"""HTTP client for ATLAS Command API.

Provides a resilient HTTP client with exponential backoff retry logic,
proper error handling, and rate limit compliance as specified in
EDGE_AGENT_INTEGRATION.md.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from .config import EdgeConfig, get_auth_headers

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API-related errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class RateLimitError(APIError):
    """Exception raised when API rate limit is exceeded (HTTP 429)."""
    pass


class RetryableError(APIError):
    """Exception for errors that should be retried (5xx, timeouts, etc.)."""
    pass


class PermanentError(APIError):
    """Exception for errors that should not be retried (4xx except 429)."""
    pass


class AtlasClient:
    """HTTP client for ATLAS Command API with retry logic and error handling."""
    
    def __init__(self, config: EdgeConfig):
        """Initialize ATLAS API client.
        
        Args:
            config: Edge agent configuration
        """
        self.config = config
        self.base_url = config.atlas_url
        self.headers = get_auth_headers(config)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> AtlasClient:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.config.request_timeout),
            headers=self.headers,
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    def _classify_error(self, response: httpx.Response) -> APIError:
        """Classify HTTP error response into appropriate exception type.
        
        Args:
            response: HTTP response object
            
        Returns:
            Appropriate exception instance
        """
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_code = error_data.get("error_code", "UNKNOWN_ERROR")
            detail = error_data.get("detail", f"HTTP {status_code}")
        except Exception:
            error_code = "UNKNOWN_ERROR"
            detail = f"HTTP {status_code}: {response.text[:100]}"
        
        if status_code == 429:
            return RateLimitError(f"Rate limit exceeded: {detail}", status_code, error_code)
        elif 500 <= status_code < 600:
            return RetryableError(f"Server error: {detail}", status_code, error_code)
        else:
            return PermanentError(f"Client error: {detail}", status_code, error_code)
    
    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Execute HTTP request with exponential backoff retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL (relative to base_url)
            **kwargs: Additional arguments for httpx request
            
        Returns:
            HTTP response object
            
        Raises:
            APIError: For various API error conditions
        """
        if not self._client:
            raise RuntimeError("Client not initialized - use async context manager")
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
                
                if response.is_success:
                    return response
                
                # Classify the error
                error = self._classify_error(response)
                
                # Don't retry permanent errors
                if isinstance(error, PermanentError):
                    raise error
                
                # Handle rate limiting with jitter
                if isinstance(error, RateLimitError):
                    if attempt < self.config.max_retries:
                        backoff_time = 5.0 + random.uniform(0, 2.0)  # 5s + jitter
                        logger.warning(f"Rate limited, backing off for {backoff_time:.1f}s")
                        await asyncio.sleep(backoff_time)
                        continue
                    else:
                        raise error
                
                # Handle retryable errors with exponential backoff
                if isinstance(error, RetryableError):
                    if attempt < self.config.max_retries:
                        backoff_time = (self.config.backoff_base ** attempt) + random.uniform(0, 1.0)
                        logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {backoff_time:.1f}s")
                        await asyncio.sleep(backoff_time)
                        continue
                    else:
                        raise error
                
                # Should not reach here
                raise error
                
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = RetryableError(f"Network error: {e}")
                
                if attempt < self.config.max_retries:
                    backoff_time = (self.config.backoff_base ** attempt) + random.uniform(0, 1.0)
                    logger.warning(f"Network error (attempt {attempt + 1}), retrying in {backoff_time:.1f}s")
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    raise last_exception
        
        # Should not reach here, but raise the last exception if we do
        raise last_exception or APIError("Max retries exceeded")
    
    async def get(self, url: str, **kwargs) -> dict[str, Any]:
        """Execute GET request.
        
        Args:
            url: Request URL (relative to base_url)
            **kwargs: Additional arguments for httpx request
            
        Returns:
            Parsed JSON response
        """
        response = await self._execute_with_retry("GET", url, **kwargs)
        return response.json()
    
    async def post(self, url: str, json_data: Optional[dict] = None, **kwargs) -> dict[str, Any]:
        """Execute POST request.
        
        Args:
            url: Request URL (relative to base_url)
            json_data: JSON data to send in request body
            **kwargs: Additional arguments for httpx request
            
        Returns:
            Parsed JSON response
        """
        if json_data is not None:
            kwargs["json"] = json_data
        
        response = await self._execute_with_retry("POST", url, **kwargs)
        return response.json()
    
    async def delete(self, url: str, **kwargs) -> Optional[dict[str, Any]]:
        """Execute DELETE request.
        
        Args:
            url: Request URL (relative to base_url)
            **kwargs: Additional arguments for httpx request
            
        Returns:
            Parsed JSON response if any, None for 204 responses
        """
        response = await self._execute_with_retry("DELETE", url, **kwargs)
        
        if response.status_code == 204:
            return None
        
        return response.json() 