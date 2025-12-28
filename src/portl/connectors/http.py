"""
HTTP connection wrapper for Portl.

Provides a connection wrapper that holds an httpx client with base_url,
default headers, and connection pooling for efficient batch API calls.
"""

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class HTTPConnection:
    """
    HTTP connection wrapper with base_url and default headers.
    
    Provides connection pooling by reusing the same httpx.Client instance
    across multiple requests, which is important for batch API calls.
    
    Attributes:
        base_url: Base URL for all requests (e.g., "https://api.example.com")
        default_headers: Headers to include in every request
        timeout: Request timeout in seconds
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize HTTP connection from configuration.
        
        Args:
            config: Configuration dictionary with optional keys:
                - base_url: Base URL for requests
                - headers: Default headers dict
                - timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = config.get('base_url', '')
        self.default_headers = config.get('headers', {})
        self.timeout = config.get('timeout', 30)
        self._client: Optional[httpx.Client] = None
        
        logger.debug(f"Initialized HTTP connection: base_url={self.base_url}")
    
    def get_client(self) -> httpx.Client:
        """
        Get or create the httpx client.
        
        Returns:
            Configured httpx.Client instance with connection pooling
        """
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            logger.debug(f"Created httpx client for {self.base_url}")
        
        return self._client
    
    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request using the pooled client.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            url: URL path (relative to base_url) or absolute URL
            headers: Additional headers (merged with defaults, overrides on conflict)
            json: JSON body to send
            **kwargs: Additional arguments passed to httpx.request
            
        Returns:
            httpx.Response object
        """
        client = self.get_client()
        
        # Merge headers (step headers override connection defaults)
        merged_headers = {**self.default_headers}
        if headers:
            merged_headers.update(headers)
        
        return client.request(
            method=method,
            url=url,
            headers=merged_headers,
            json=json,
            **kwargs
        )
    
    def close(self) -> None:
        """Close the httpx client and release resources."""
        if self._client is not None:
            try:
                self._client.close()
                logger.debug(f"Closed httpx client for {self.base_url}")
            except Exception as e:
                logger.error(f"Error closing httpx client: {e}")
            finally:
                self._client = None
    
    def __enter__(self) -> "HTTPConnection":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close the client."""
        self.close()
    
    def __repr__(self) -> str:
        return f"HTTPConnection(base_url={self.base_url!r})"

