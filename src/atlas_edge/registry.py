"""Asset registry and command management for ATLAS Edge Agent.

Handles asset registration with ATLAS Command backend and command queue
polling/acknowledgment as specified in EDGE_AGENT_INTEGRATION.md.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .client import AtlasClient, APIError
from .config import EdgeConfig

logger = logging.getLogger(__name__)


class AssetRegistration(BaseModel):
    """Asset registration payload for POST /api/v1/assets."""
    
    asset_id: str = Field(description="Unique asset identifier")
    name: str = Field(description="Human-readable asset name")
    asset_model_id: int = Field(description="Asset model ID from catalog")
    location: Optional[Dict[str, Any]] = Field(default=None, description="Asset location data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional asset metadata")


class Command(BaseModel):
    """Command from ATLAS Command queue."""
    
    index: int = Field(description="Command index in queue")
    command_type: str = Field(description="Type of command")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    issued_at: datetime = Field(description="Command issue timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Command expiration time")
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> Command:
        """Create Command from API response data.
        
        Args:
            data: Raw command data from API
            
        Returns:
            Command instance
        """
        # Parse timestamps
        issued_at = datetime.fromisoformat(data["issued_at"].replace("Z", "+00:00"))
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        
        return cls(
            index=data["index"],
            command_type=data["command_type"],
            parameters=data.get("parameters", {}),
            issued_at=issued_at,
            expires_at=expires_at
        )
    
    def is_expired(self) -> bool:
        """Check if command has expired.
        
        Returns:
            True if command is expired
        """
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class AssetRegistry:
    """Manages asset registration and command queue operations."""
    
    def __init__(self, client: AtlasClient, config: EdgeConfig):
        """Initialize asset registry.
        
        Args:
            client: ATLAS API client
            config: Edge agent configuration
        """
        self.client = client
        self.config = config
        self._registered = False
    
    async def register_asset(self) -> bool:
        """Register this device as an asset with ATLAS Command.
        
        Uses idempotent registration - safe to call multiple times.
        
        Returns:
            True if registration successful, False otherwise
        """
        registration_data = AssetRegistration(
            asset_id=self.config.asset_id,
            name=self.config.asset_name,
            asset_model_id=self.config.asset_model_id,
            metadata={
                "edge_agent_version": "0.1.0",
                "device_type": "raspberry_pi_zero_2w",
                "registration_time": datetime.now(timezone.utc).isoformat()
            }
        )
        
        try:
            logger.info(f"Registering asset {self.config.asset_id}")
            
            response = await self.client.post(
                "/assets",
                json_data=registration_data.model_dump()
            )
            
            logger.info(f"Asset registration successful: {response}")
            self._registered = True
            return True
            
        except APIError as e:
            if e.status_code == 409:
                # Asset already exists - this is expected for idempotent registration
                logger.info(f"Asset {self.config.asset_id} already registered")
                self._registered = True
                return True
            else:
                logger.error(f"Asset registration failed: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error during asset registration: {e}")
            return False
    
    async def poll_commands(self) -> List[Command]:
        """Poll command queue for pending commands.
        
        Returns:
            List of pending commands
        """
        if not self._registered:
            logger.warning("Asset not registered, skipping command poll")
            return []
        
        try:
            response = await self.client.get(f"/assets/{self.config.asset_id}/commands")
            commands_data = response.get("commands", [])
            
            commands = []
            for cmd_data in commands_data:
                try:
                    command = Command.from_api_response(cmd_data)
                    
                    if command.is_expired():
                        logger.warning(f"Command {command.index} is expired, skipping")
                        # Acknowledge expired commands immediately
                        await self.acknowledge_command(command.index)
                        continue
                    
                    commands.append(command)
                except Exception as e:
                    logger.error(f"Failed to parse command: {e}")
                    continue
            
            if commands:
                logger.info(f"Retrieved {len(commands)} pending command(s)")
            
            return commands
            
        except APIError as e:
            if e.status_code == 404:
                logger.warning(f"Asset {self.config.asset_id} not found in command system")
                self._registered = False
            else:
                logger.error(f"Failed to poll commands: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during command poll: {e}")
            return []
    
    async def acknowledge_command(self, command_index: int) -> bool:
        """Acknowledge completion of a command.
        
        Args:
            command_index: Index of command to acknowledge
            
        Returns:
            True if acknowledgment successful
        """
        if not self._registered:
            logger.warning("Asset not registered, cannot acknowledge command")
            return False
        
        try:
            await self.client.delete(f"/assets/{self.config.asset_id}/commands/{command_index}")
            logger.info(f"Acknowledged command {command_index}")
            return True
            
        except APIError as e:
            if e.status_code == 404:
                logger.warning(f"Command {command_index} not found (may have expired)")
                return True  # Treat as success since command is gone
            else:
                logger.error(f"Failed to acknowledge command {command_index}: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error acknowledging command {command_index}: {e}")
            return False
    
    async def execute_command(self, command: Command) -> bool:
        """Execute a command and acknowledge it.
        
        Args:
            command: Command to execute
            
        Returns:
            True if command executed and acknowledged successfully
        """
        logger.info(f"Executing command {command.index}: {command.command_type}")
        
        try:
            # Command execution logic based on command_type
            if command.command_type == "ping":
                logger.info("Ping command - no action required")
                success = True
                
            elif command.command_type == "restart":
                logger.warning("Restart command received - would restart in production")
                # In a real implementation, this would trigger a graceful restart
                success = True
                
            elif command.command_type == "update_config":
                logger.info(f"Config update command: {command.parameters}")
                # In a real implementation, this would update configuration
                success = True
                
            elif command.command_type == "collect_logs":
                logger.info("Log collection command - would collect and upload logs")
                # In a real implementation, this would collect and upload logs
                success = True
                
            else:
                logger.warning(f"Unknown command type: {command.command_type}")
                success = False
            
            # Acknowledge the command
            if success:
                await self.acknowledge_command(command.index)
                logger.info(f"Command {command.index} executed and acknowledged")
                return True
            else:
                logger.error(f"Command {command.index} execution failed")
                return False
                
        except Exception as e:
            logger.error(f"Error executing command {command.index}: {e}")
            return False
    
    @property
    def is_registered(self) -> bool:
        """Check if asset is registered.
        
        Returns:
            True if asset is registered
        """
        return self._registered 