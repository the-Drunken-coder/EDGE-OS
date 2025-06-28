"""Configuration management for ATLAS Edge Agent.

Handles environment variables, CLI arguments, and configuration validation.
Follows the pattern from EDGE_AGENT_INTEGRATION.md for configuration via
environment variables with optional CLI overrides.
"""
from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field


class EdgeConfig(BaseModel):
    """Configuration for ATLAS Edge Agent."""
    
    # ATLAS backend configuration
    atlas_url: str = Field(
        default_factory=lambda: os.getenv("ATLAS_URL", "http://atlas-host.local:8000/api/v1"),
        description="Base URL for ATLAS Command API"
    )
    
    # Asset identification
    asset_id: str = Field(
        default_factory=lambda: os.getenv("ASSET_ID", "EDGE-0001"),
        description="Unique identifier for this edge device"
    )
    
    asset_name: str = Field(
        default_factory=lambda: os.getenv("ASSET_NAME", "Edge Agent Device"),
        description="Human-readable name for this device"
    )
    
    asset_model_id: int = Field(
        default_factory=lambda: int(os.getenv("ASSET_MODEL_ID", "1")),
        description="Asset model ID from ATLAS catalog"
    )
    
    # Telemetry and polling configuration
    telemetry_interval: float = Field(
        default_factory=lambda: float(os.getenv("TELEMETRY_INTERVAL", "5.0")),
        description="Seconds between telemetry posts (≤2 Hz recommended)"
    )
    
    command_poll_interval: float = Field(
        default_factory=lambda: float(os.getenv("COMMAND_POLL_INTERVAL", "2.0")),
        description="Seconds between command queue polls"
    )
    
    # HTTP client configuration
    request_timeout: float = Field(
        default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT", "5.0")),
        description="HTTP request timeout in seconds"
    )
    
    # Retry and back-off configuration
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")),
        description="Maximum retry attempts for failed requests"
    )
    
    backoff_base: float = Field(
        default_factory=lambda: float(os.getenv("BACKOFF_BASE", "2.0")),
        description="Base multiplier for exponential backoff"
    )
    
    # Authentication (future)
    bearer_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("BEARER_TOKEN"),
        description="Bearer token for API authentication"
    )


def load_config() -> EdgeConfig:
    """Load configuration from environment variables.
    
    Returns:
        EdgeConfig: Validated configuration object
        
    Raises:
        ValidationError: If configuration is invalid
    """
    return EdgeConfig()


def get_auth_headers(config: EdgeConfig) -> dict[str, str]:
    """Get HTTP headers for authentication.
    
    Args:
        config: Edge configuration
        
    Returns:
        Dictionary of HTTP headers
    """
    headers = {"Content-Type": "application/json"}
    
    if config.bearer_token:
        headers["Authorization"] = f"Bearer {config.bearer_token}"
    
    return headers 