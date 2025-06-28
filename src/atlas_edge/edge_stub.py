#!/usr/bin/env python3
"""ATLAS Edge Agent - Stage 2 Stub Implementation.

This is the main entry point for the ATLAS Edge Agent during Stage-2 testing.
It demonstrates the complete integration flow: asset registration, telemetry
streaming, and command queue polling as specified in EDGE_AGENT_INTEGRATION.md.

Usage:
    python -m atlas_edge.edge_stub
    
Environment Variables:
    ATLAS_URL - ATLAS Command API base URL (default: http://atlas-host.local:8000/api/v1)
    ASSET_ID - Unique asset identifier (default: EDGE-0001)
    ASSET_NAME - Human-readable asset name (default: Edge Agent Device)
    TELEMETRY_INTERVAL - Seconds between telemetry posts (default: 5.0)
    COMMAND_POLL_INTERVAL - Seconds between command polls (default: 2.0)
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Optional

from .client import AtlasClient
from .config import EdgeConfig, load_config
from .registry import AssetRegistry
from .telemetry import MockTelemetryGenerator

# Configure logging to stdout (systemd will capture this)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

logger = logging.getLogger(__name__)


class EdgeAgent:
    """Main ATLAS Edge Agent implementation."""
    
    def __init__(self, config: EdgeConfig):
        """Initialize edge agent.
        
        Args:
            config: Agent configuration
        """
        self.config = config
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize components
        self.telemetry_generator = MockTelemetryGenerator(config.asset_id)
        
        # These will be initialized in start()
        self.client: Optional[AtlasClient] = None
        self.registry: Optional[AssetRegistry] = None
    
    async def start(self):
        """Start the edge agent."""
        logger.info(f"Starting ATLAS Edge Agent {self.config.asset_id}")
        logger.info(f"ATLAS URL: {self.config.atlas_url}")
        logger.info(f"Telemetry interval: {self.config.telemetry_interval}s")
        logger.info(f"Command poll interval: {self.config.command_poll_interval}s")
        
        # Initialize HTTP client and registry
        self.client = AtlasClient(self.config)
        self.registry = AssetRegistry(self.client, self.config)
        
        async with self.client:
            # Register asset
            registration_success = await self.registry.register_asset()
            if not registration_success:
                logger.error("Failed to register asset - continuing anyway")
            
            self.running = True
            
            # Start background tasks
            tasks = [
                asyncio.create_task(self._telemetry_loop(), name="telemetry"),
                asyncio.create_task(self._command_loop(), name="commands"),
                asyncio.create_task(self._wait_for_shutdown(), name="shutdown")
            ]
            
            try:
                # Wait for shutdown or task completion
                done, pending = await asyncio.wait(
                    tasks, 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # Check if any task failed
                for task in done:
                    if task.exception():
                        logger.error(f"Task {task.get_name()} failed: {task.exception()}")
                        
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                raise
            finally:
                self.running = False
                logger.info("ATLAS Edge Agent stopped")
    
    async def _telemetry_loop(self):
        """Background task for telemetry collection and transmission."""
        logger.info("Starting telemetry loop")
        
        while self.running:
            try:
                # Generate telemetry batch
                telemetry_batch = self.telemetry_generator.generate_telemetry_batch()
                
                # Send to ATLAS Command
                if self.registry and self.registry.is_registered:
                    try:
                        response = await self.client.post(
                            f"/assets/{self.config.asset_id}/telemetry",
                            json_data=telemetry_batch.model_dump()
                        )
                        logger.debug(f"Telemetry sent successfully: {len(telemetry_batch.readings)} readings")
                        
                    except Exception as e:
                        logger.warning(f"Failed to send telemetry: {e}")
                
                else:
                    logger.debug("Asset not registered, skipping telemetry")
                
                # Wait for next cycle
                await asyncio.sleep(self.config.telemetry_interval)
                
            except asyncio.CancelledError:
                logger.info("Telemetry loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in telemetry loop: {e}")
                await asyncio.sleep(self.config.telemetry_interval)
    
    async def _command_loop(self):
        """Background task for command queue polling and execution."""
        logger.info("Starting command loop")
        
        while self.running:
            try:
                if self.registry and self.registry.is_registered:
                    # Poll for commands
                    commands = await self.registry.poll_commands()
                    
                    # Execute commands
                    for command in commands:
                        try:
                            await self.registry.execute_command(command)
                        except Exception as e:
                            logger.error(f"Failed to execute command {command.index}: {e}")
                
                # Wait for next poll cycle
                await asyncio.sleep(self.config.command_poll_interval)
                
            except asyncio.CancelledError:
                logger.info("Command loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in command loop: {e}")
                await asyncio.sleep(self.config.command_poll_interval)
    
    async def _wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
        logger.info("Shutdown signal received")
    
    def shutdown(self):
        """Initiate graceful shutdown."""
        logger.info("Initiating graceful shutdown")
        self.running = False
        self._shutdown_event.set()


# Global agent instance for signal handling
_agent: Optional[EdgeAgent] = None


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    if _agent:
        logger.info(f"Received signal {signum}")
        _agent.shutdown()


async def main():
    """Main entry point."""
    global _agent
    
    try:
        # Load configuration
        config = load_config()
        
        # Create agent
        _agent = EdgeAgent(config)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start agent
        await _agent.start()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("ATLAS Edge Agent shutdown complete")


if __name__ == "__main__":
    # For direct execution: python edge_stub.py
    asyncio.run(main()) 